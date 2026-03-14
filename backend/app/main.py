"""
FastAPI main application with all endpoints.
"""
import time
from datetime import datetime
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks, UploadFile, File, Header
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import os
from pathlib import Path
import shutil

from app.config import settings
from app.models import (
    HealthCheck,
    IngestionRequest,
    IngestionStatus,
    QueryRequest,
    QueryResponse,
    QuestionGenerationRequest,
    QuestionGenerationResponse,
    CreateIndexRequest,
    IndexInfo,
    ListIndexesResponse,
    IndexOperationResponse,
    CreateSessionRequest,
    CreateSessionResponse,
    SessionValidateRequest,
    SessionValidateResponse,
    UserSubjectRequest,
    UserSubjectResponse,
    DocumentUploadResponse,
    DocumentListResponse,
    DocumentIngestResponse,
)
from app.models_advanced import HybridSearchRequest
from app.ingestion.advanced_ingestion_manager import AdvancedIngestionManager
from app.retrieval.hybrid_retriever import HybridRetriever
from app.ingestion.embedder import SentenceTransformerEmbedder
from app.llm.question_generator import QuestionGenerator
from app.llm.llm_manager import LLMManager
from app.llm.prompts import PromptTemplates
from app.sessions import SessionManager
from app.vectorstore.metadata_db import init_database
from app.utils.logger import app_logger, setup_logging


# Global instances
ingestion_manager: AdvancedIngestionManager = None
retriever: HybridRetriever = None
embedder: SentenceTransformerEmbedder = None
question_generator: QuestionGenerator = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application resources."""
    global ingestion_manager, retriever, embedder, question_generator
    
    # Startup
    setup_logging()
    app_logger.info("Starting application with Advanced Hybrid RAG...")

    try:
        # Initialize database for multi-user support
        app_logger.info("Initializing database...")
        init_database()
        app_logger.info("Database ready")

        # Only initialize ingestion manager on startup (needed for ingestion)
        # This loads the embedding model which is required for document vectorization
        app_logger.info("Initializing ingestion manager...")
        ingestion_manager = AdvancedIngestionManager()
        app_logger.info("Ingestion manager ready")
        
        # Retriever, embedder, and question generator are lazy-loaded on first use
        # This allows fast startup for ingestion-only workflows
        retriever = None
        embedder = None
        question_generator = None
        
        app_logger.info("Application started successfully (query components will load on first use)")
    except Exception as e:
        app_logger.error(f"Startup error: {e}", exc_info=True)
        raise
    
    yield
    
    # Shutdown
    app_logger.info("Shutting down application...")


# Create FastAPI app
app = FastAPI(
    title=settings.app_name,
    description="Local RAG system for question generation from PDF/text/image documents",
    version="1.0.0",
    lifespan=lifespan,
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Lazy initialization helpers
def get_retriever():
    """Lazy-load retriever on first query."""
    global retriever
    if retriever is None:
        app_logger.info("Initializing retriever for first query...")
        retriever = HybridRetriever(
            multi_index_manager=ingestion_manager.multi_index,
            bm25_index=ingestion_manager.bm25_index,
        )
        app_logger.info("Retriever ready")
    return retriever


def get_embedder():
    """Lazy-load embedder on first query."""
    global embedder
    if embedder is None:
        app_logger.info("Initializing query embedder...")
        embedder = SentenceTransformerEmbedder()
        app_logger.info("Query embedder ready")
    return embedder


def get_question_generator():
    """Lazy-load question generator on first use."""
    global question_generator
    if question_generator is None:
        app_logger.info("Initializing question generator...")
        # Pass the retriever so question generator can retrieve context
        question_generator = QuestionGenerator(retriever=get_retriever())
        app_logger.info("Question generator ready")
    return question_generator


# Health check endpoint
@app.get("/health", response_model=HealthCheck)
async def health_check():
    """Check application health."""
    status = ingestion_manager.get_ingestion_status()
    
    # Count total chunks across all indexes
    total_chunks = 0
    if 'multi_index_stats' in status:
        for idx_stats in status['multi_index_stats'].values():
            total_chunks += idx_stats.get('document_count', 0)
    
    return HealthCheck(
        status="healthy",
        llm_provider=settings.llm_provider,
        embedding_provider=settings.embedding_provider,
        vector_store_type="hybrid_multi_index",
        total_documents=status['total_documents'],
        total_chunks=total_chunks,
    )


# Ingestion endpoints
@app.post("/api/ingest")
async def start_ingestion(request: IngestionRequest, background_tasks: BackgroundTasks):
    """
    Start document ingestion from a folder.
    
    This runs in the background and returns immediately.
    Use /api/ingestion/status to check progress.
    """
    if ingestion_manager.is_running:
        raise HTTPException(status_code=400, detail="Ingestion already running")
    
    app_logger.info(f"Starting ingestion: {request.folder_path}")
    
    # Run ingestion in background
    background_tasks.add_task(ingestion_manager.ingest_documents, request)
    
    return {
        "message": "Ingestion started",
        "folder_path": request.folder_path,
        "recursive": request.recursive,
    }


@app.get("/api/ingestion/status", response_model=IngestionStatus)
async def get_ingestion_status():
    """Get current ingestion status."""
    status = ingestion_manager.get_ingestion_status()
    
    progress = 0.0
    if status['total_documents'] > 0:
        progress = (status['completed_documents'] / status['total_documents']) * 100
    
    return IngestionStatus(
        is_running=status['is_running'],
        total_documents=status['total_documents'],
        processed_documents=status['completed_documents'],
        failed_documents=status['failed_documents'],
        progress_percentage=progress,
    )


# Query endpoint
@app.post("/api/query", response_model=QueryResponse)
async def query_knowledge_base(request: QueryRequest):
    """
    Query the knowledge base and get an answer.
    
    This retrieves relevant chunks and generates an answer using the LLM.
    """
    start_time = time.time()
    
    try:
        # Lazy-load query components
        current_embedder = get_embedder()
        current_retriever = get_retriever()
        
        # Generate query embedding
        query_embedding = current_embedder.embed_text(request.query)
        
        # Convert index_filter to IndexType if provided
        specific_indexes = None
        if request.index_filter:
            from app.models_advanced import IndexType
            specific_indexes = [IndexType.from_string(idx) for idx in request.index_filter]
        
        # Hybrid retrieval with automatic routing
        results = current_retriever.search(
            query=request.query,
            query_embedding=query_embedding,
            top_k=request.top_k,
            use_reranking=True,
            specific_indexes=specific_indexes,
        )
        
        if not results:
            return QueryResponse(
                query=request.query,
                answer="No relevant information found in the knowledge base for your query.",
                retrieved_chunks=[],
                processing_time=time.time() - start_time,
            )
        
        # Format context from results
        context_parts = []
        chunks = []
        for i, result in enumerate(results):
            context_parts.append(f"Source {i+1}:\n{result['text']}")

            # Extract source file name from various metadata fields
            source_file = (
                result['metadata'].get('file_name') or
                result['metadata'].get('document_name') or
                result['metadata'].get('source') or
                'Unknown'
            )

            chunks.append({
                'chunk_id': result['metadata'].get('chunk_id', result.get('id', f'chunk_{i}')),
                'content': result['text'],
                'source_file': source_file,
                'page_number': result['metadata'].get('page_number'),
                'similarity_score': result.get('hybrid_score', result.get('score', 0.0)),
                'content_type': result['metadata'].get('content_type') or 'unknown',
                'difficulty': result['metadata'].get('difficulty') or 'unknown',
                'index_type': result['metadata'].get('index_type') or 'unknown',
            })
        
        context = "\n\n".join(context_parts)
        
        # Generate answer using selected model or default
        if request.model:
            # Create LLM with specific model
            from app.llm.ollama_llm import OllamaLLM
            llm = OllamaLLM(
                model_name=request.model,
                base_url=settings.llm_base_url,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                timeout=settings.llm_timeout,
            )
        else:
            llm = LLMManager.get_llm()
        
        system_prompt, user_prompt = PromptTemplates.get_answer_prompt(context, request.query)
        
        response = await llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
        )
        
        # Clean up temporary LLM if created
        if request.model:
            await llm.close()
        
        processing_time = time.time() - start_time
        
        return QueryResponse(
            query=request.query,
            answer=response.text,
            retrieved_chunks=chunks,
            processing_time=processing_time,
        )
    
    except Exception as e:
        app_logger.error(f"Query error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Question generation endpoint
@app.post("/api/generate-questions", response_model=QuestionGenerationResponse)
async def generate_questions(request: QuestionGenerationRequest):
    """
    Generate questions based on the knowledge base.
    
    Can specify subject, difficulty, question type, and optionally a topic.
    """
    start_time = time.time()
    
    try:
        # Lazy-load question generator
        current_generator = get_question_generator()
        
        # Create LLM with specific model if provided
        custom_llm = None
        if request.model:
            from app.llm.ollama_llm import OllamaLLM
            custom_llm = OllamaLLM(
                model_name=request.model,
                base_url=settings.llm_base_url,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                timeout=settings.llm_timeout,
            )
        
        questions = await current_generator.generate_questions(request, llm=custom_llm)
        
        # Get the context that was used
        if request.context:
            context_used = request.context[:500] + "..." if len(request.context) > 500 else request.context
        else:
            # Use topic/subject info instead
            context_used = f"Generating {request.question_type.value} questions for {request.subject.value}"
            if request.topic:
                context_used += f" - Topic: {request.topic}"
        
        processing_time = time.time() - start_time
        
        # Clean up temporary LLM if created
        if custom_llm:
            await custom_llm.close()
        
        return QuestionGenerationResponse(
            questions=questions,
            context_used=context_used,
            processing_time=processing_time,
        )
    
    except Exception as e:
        app_logger.error(f"Question generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Statistics endpoint
@app.get("/api/stats")
async def get_statistics():
    """Get system statistics."""
    status = ingestion_manager.get_ingestion_status()
    
    # Count total chunks across all indexes
    total_chunks = 0
    if 'multi_index_stats' in status:
        for idx_stats in status['multi_index_stats'].values():
            total_chunks += idx_stats.get('document_count', 0)
    
    return {
        "documents": {
            "total": status['total_documents'],
            "completed": status['completed_documents'],
            "failed": status['failed_documents'],
        },
        "vector_store": {
            "total_vectors": total_chunks,
            "multi_index_stats": status.get('multi_index_stats', {}),
            "bm25_stats": status.get('bm25_stats', {}),
        },
        "configuration": {
            "llm_provider": settings.llm_provider,
            "llm_model": settings.llm_model,
            "embedding_provider": settings.embedding_provider,
            "embedding_model": settings.embedding_model,
            "chunk_size": settings.chunk_size,
            "chunk_overlap": settings.chunk_overlap,
            "architecture": "hybrid_rag_v2",
        },
    }


# LLM configuration endpoints
@app.get("/api/llm/info")
async def get_llm_info():
    """Get information about the current LLM."""
    llm = LLMManager.get_llm()
    return llm.get_model_info()


@app.get("/api/llm/health")
async def check_llm_health():
    """Check if LLM is available."""
    is_available = await LLMManager.health_check()
    
    if not is_available:
        raise HTTPException(
            status_code=503,
            detail=f"LLM provider '{settings.llm_provider}' is not available"
        )
    
    return {"status": "available"}


@app.get("/api/llm/models")
async def list_ollama_models():
    """List available models from Ollama."""
    if settings.llm_provider != "ollama":
        raise HTTPException(
            status_code=400,
            detail=f"Model listing only supported for Ollama provider. Current provider: {settings.llm_provider}"
        )
    
    try:
        from app.llm.ollama_llm import OllamaLLM
        temp_llm = OllamaLLM(
            model_name=settings.llm_model,
            base_url=settings.llm_base_url,
        )
        models = await temp_llm.list_models()
        await temp_llm.close()
        return {"models": models, "default": settings.llm_model}
    except Exception as e:
        app_logger.error(f"Error listing Ollama models: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Index Management Endpoints

@app.post("/api/indexes", response_model=IndexOperationResponse)
async def create_custom_index(request: CreateIndexRequest):
    """
    Create a new custom index.
    
    Custom indexes allow you to organize documents by topic, source, or any other criteria.
    Documents can be ingested directly into custom indexes.
    """
    try:
        # Create the custom index
        config = ingestion_manager.multi_index.create_custom_index(
            index_name=request.index_name,
            description=request.description,
            embedding_dimension=request.embedding_dimension
        )
        
        index_info = IndexInfo(
            name=config['index_name'],
            description=config.get('description', ''),
            document_count=config.get('document_count', 0),
            chunk_count=config.get('chunk_count', 0),
            dimension=config['embedding_dimension'],
            is_custom=True,
            created_at=datetime.fromisoformat(config['created_at']) if 'created_at' in config else None,
            last_updated=datetime.fromisoformat(config['last_updated']) if 'last_updated' in config else None
        )
        
        return IndexOperationResponse(
            success=True,
            message=f"Custom index '{request.index_name}' created successfully",
            index_info=index_info
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        app_logger.error(f"Error creating custom index: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create index: {str(e)}")


@app.get("/api/indexes", response_model=ListIndexesResponse)
async def list_indexes():
    """
    List all indexes (predefined and custom).
    
    Returns information about all available indexes including their document counts.
    """
    try:
        all_indexes = ingestion_manager.multi_index.list_all_indexes()
        
        index_list = []
        for name, stats in all_indexes.items():
            index_list.append(IndexInfo(
                name=name,
                description="",  # Could be fetched from config if needed
                document_count=stats['document_count'],
                chunk_count=stats['document_count'],  # Same as document_count for now
                dimension=stats['dimension'],
                is_custom=stats['is_custom']
            ))
        
        return ListIndexesResponse(
            indexes=index_list,
            total_count=len(index_list)
        )
    
    except Exception as e:
        app_logger.error(f"Error listing indexes: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list indexes: {str(e)}")


@app.delete("/api/indexes/{index_name}", response_model=IndexOperationResponse)
async def delete_custom_index(index_name: str):
    """
    Delete a custom index.
    
    Note: Predefined indexes (theory, formula, exercise, solution, general) cannot be deleted.
    """
    try:
        success = ingestion_manager.multi_index.delete_custom_index(index_name)
        
        if not success:
            raise HTTPException(status_code=404, detail=f"Index '{index_name}' not found")
        
        return IndexOperationResponse(
            success=True,
            message=f"Custom index '{index_name}' deleted successfully"
        )
    
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        app_logger.error(f"Error deleting custom index: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to delete index: {str(e)}")


@app.get("/api/indexes/{index_name}", response_model=IndexInfo)
async def get_index_info(index_name: str):
    """Get detailed information about a specific index."""
    try:
        all_indexes = ingestion_manager.multi_index.list_all_indexes()

        if index_name not in all_indexes:
            raise HTTPException(status_code=404, detail=f"Index '{index_name}' not found")

        stats = all_indexes[index_name]

        return IndexInfo(
            name=index_name,
            description="",
            document_count=stats['document_count'],
            chunk_count=stats['document_count'],
            dimension=stats['dimension'],
            is_custom=stats['is_custom']
        )

    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Error getting index info: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to get index info: {str(e)}")


# Session Management endpoints
@app.post("/api/session/create", response_model=CreateSessionResponse)
async def create_session(request: CreateSessionRequest):
    """
    Create a new user session.

    Returns a session token valid for 24 hours.
    No authentication required.
    """
    try:
        user_id, session_token = SessionManager.create_user(request.username)

        return CreateSessionResponse(
            user_id=user_id,
            session_token=session_token,
            expires_in_hours=SessionManager.SESSION_EXPIRY_HOURS,
            message=f"Session created for {request.username}",
        )
    except Exception as e:
        app_logger.error(f"Error creating session: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create session: {str(e)}")


@app.post("/api/session/validate", response_model=SessionValidateResponse)
async def validate_session(request: SessionValidateRequest):
    """
    Validate a session token.

    Returns user info if valid, empty response otherwise.
    """
    user_info = SessionManager.get_user_by_session(request.session_token)

    if user_info:
        return SessionValidateResponse(
            valid=True,
            user_id=user_info['user_id'],
            username=user_info['username'],
            session_expires_at=user_info['session_expires_at'],
        )
    else:
        return SessionValidateResponse(valid=False)


@app.post("/api/session/refresh")
async def refresh_session(request: SessionValidateRequest):
    """
    Extend session expiry by 24 hours.
    """
    success = SessionManager.refresh_session(request.session_token)

    if success:
        return {
            "success": True,
            "message": "Session refreshed",
        }
    else:
        raise HTTPException(status_code=401, detail="Invalid or expired session")


@app.post("/api/session/logout")
async def logout_session(request: SessionValidateRequest):
    """
    Invalidate/logout a session.
    """
    success = SessionManager.invalidate_session(request.session_token)

    if success:
        return {
            "success": True,
            "message": "Session invalidated",
        }
    else:
        raise HTTPException(status_code=401, detail="Invalid session")


@app.post("/api/subjects", response_model=UserSubjectResponse)
async def create_user_subject(
    request: UserSubjectRequest,
    session_token: str = None
):
    """
    Create a custom subject/topic for a user.

    Requires valid session token.
    """
    if not session_token:
        raise HTTPException(status_code=401, detail="Session token required")

    user_id = SessionManager.get_user_id_from_token(session_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    try:
        from app.vectorstore.metadata_db import UserSubject, get_session as get_db_session

        db_session = get_db_session()
        try:
            subject = UserSubject(
                user_id=user_id,
                name=request.name,
                description=request.description,
            )
            db_session.add(subject)
            db_session.commit()

            return UserSubjectResponse(
                id=subject.id,
                name=subject.name,
                description=subject.description,
                created_at=subject.created_at.isoformat(),
            )
        finally:
            db_session.close()

    except Exception as e:
        app_logger.error(f"Error creating subject: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to create subject: {str(e)}")


@app.get("/api/subjects")
async def list_user_subjects(session_token: str = None):
    """
    List all custom subjects for a user.

    Requires valid session token.
    """
    if not session_token:
        raise HTTPException(status_code=401, detail="Session token required")

    user_id = SessionManager.get_user_id_from_token(session_token)
    if not user_id:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    try:
        from app.vectorstore.metadata_db import UserSubject, get_session as get_db_session

        db_session = get_db_session()
        try:
            subjects = db_session.query(UserSubject).filter(
                UserSubject.user_id == user_id
            ).all()

            return {
                "subjects": [
                    {
                        "id": s.id,
                        "name": s.name,
                        "description": s.description,
                        "created_at": s.created_at.isoformat(),
                    }
                    for s in subjects
                ],
                "count": len(subjects),
            }
        finally:
            db_session.close()

    except Exception as e:
        app_logger.error(f"Error listing subjects: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list subjects: {str(e)}")


# Document Upload Endpoints
def get_user_uploads_dir(user_id: int) -> Path:
    """Get or create user's uploads directory."""
    uploads_dir = Path(settings.data_dir) / "users" / str(user_id) / "uploads"
    uploads_dir.mkdir(parents=True, exist_ok=True)
    return uploads_dir


def get_user_index_name(user_uuid: str) -> str:
    """Generate user's custom index name from UUID."""
    return f"user_{user_uuid[:8]}"


def ensure_user_index(db_session, user_db_id: int, user_uuid: str):
    """Create user's custom index if it doesn't exist."""
    try:
        index_name = get_user_index_name(user_uuid)
        # Check if index already exists
        existing_indexes = ingestion_manager.multi_index.list_all_indexes()
        if index_name not in existing_indexes:
            ingestion_manager.multi_index.create_custom_index(
                index_name=index_name,
                description=f"User documents for {user_uuid}",
                embedding_dimension=settings.embedding_dimension
            )
            app_logger.info(f"Created custom index: {index_name}")
    except Exception as e:
        app_logger.error(f"Error ensuring user index: {e}")
        raise


@app.post("/api/documents/upload", response_model=DocumentUploadResponse)
async def upload_documents(
    files: list[UploadFile] = File(...),
    x_session_token: str = Header(None),
):
    """
    Upload documents for a user.

    Accepts multipart/form-data with file(s).
    Requires valid session token in X-Session-Token header.
    """
    if not x_session_token:
        raise HTTPException(status_code=401, detail="Session token required")

    # Validate session
    user_info = SessionManager.get_user_by_session(x_session_token)
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user_db_id = SessionManager.get_user_id_from_token(x_session_token)
    user_uuid = user_info['user_id']

    try:
        from app.vectorstore.metadata_db import User, get_session as get_db_session

        # Ensure user's custom index exists
        ensure_user_index(None, user_db_id, user_uuid)

        # Get user's uploads directory
        uploads_dir = get_user_uploads_dir(user_db_id)

        uploaded_files = []
        for file in files:
            if not file.filename:
                continue

            # Security: validate file extension
            allowed_extensions = {'.pdf', '.txt', '.md', '.html', '.htm', '.docx', '.doc'}
            file_ext = Path(file.filename).suffix.lower()
            if file_ext not in allowed_extensions:
                app_logger.warning(f"Rejected file with extension {file_ext}: {file.filename}")
                continue

            # Save file
            file_path = uploads_dir / file.filename

            # If file exists, create a new name
            counter = 1
            base_name = file_path.stem
            while file_path.exists():
                file_path = uploads_dir / f"{base_name}_{counter}{file_ext}"
                counter += 1

            with open(file_path, 'wb') as f:
                contents = await file.read()
                f.write(contents)

            uploaded_files.append({
                "filename": file_path.name,
                "path": str(file_path),
                "size": file_path.stat().st_size,
            })

            app_logger.info(f"Uploaded file: {file_path}")

        return DocumentUploadResponse(
            success=True,
            message=f"Uploaded {len(uploaded_files)} file(s)",
            files=uploaded_files,
            upload_dir=str(uploads_dir),
        )

    except Exception as e:
        app_logger.error(f"Error uploading documents: {e}")
        raise HTTPException(status_code=500, detail=f"Upload failed: {str(e)}")


@app.get("/api/documents", response_model=DocumentListResponse)
async def list_documents(x_session_token: str = Header(None)):
    """
    List user's uploaded documents.

    Requires valid session token in X-Session-Token header.
    """
    if not x_session_token:
        raise HTTPException(status_code=401, detail="Session token required")

    # Validate session
    user_info = SessionManager.get_user_by_session(x_session_token)
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user_db_id = SessionManager.get_user_id_from_token(x_session_token)

    try:
        uploads_dir = get_user_uploads_dir(user_db_id)

        files = []
        if uploads_dir.exists():
            for file_path in sorted(uploads_dir.glob('*')):
                if file_path.is_file():
                    stat = file_path.stat()
                    files.append({
                        "filename": file_path.name,
                        "path": str(file_path),
                        "size": stat.st_size,
                        "uploaded_at": datetime.fromtimestamp(stat.st_mtime).isoformat(),
                    })

        return DocumentListResponse(
            files=files,
            count=len(files),
        )

    except Exception as e:
        app_logger.error(f"Error listing documents: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to list documents: {str(e)}")


@app.post("/api/documents/ingest", response_model=DocumentIngestResponse)
async def ingest_user_documents(
    background_tasks: BackgroundTasks,
    x_session_token: str = Header(None),
):
    """
    Trigger ingestion of user's uploaded documents.

    Runs in background. Documents are ingested into user's private index.
    Requires valid session token in X-Session-Token header.
    """
    if not x_session_token:
        raise HTTPException(status_code=401, detail="Session token required")

    # Validate session
    user_info = SessionManager.get_user_by_session(x_session_token)
    if not user_info:
        raise HTTPException(status_code=401, detail="Invalid or expired session")

    user_db_id = SessionManager.get_user_id_from_token(x_session_token)
    user_uuid = user_info['user_id']

    try:
        if ingestion_manager.is_running:
            raise HTTPException(status_code=400, detail="Ingestion already running")

        # Ensure user's custom index exists
        ensure_user_index(None, user_db_id, user_uuid)

        # Get user's uploads directory
        uploads_dir = get_user_uploads_dir(user_db_id)

        if not uploads_dir.exists() or not any(uploads_dir.iterdir()):
            raise HTTPException(status_code=400, detail="No files to ingest")

        # Create ingestion request for user's documents
        user_index_name = get_user_index_name(user_uuid)

        request = IngestionRequest(
            folder_path=str(uploads_dir),
            recursive=False,  # Don't recursively scan the uploads directory
            target_index=user_index_name,
        )

        app_logger.info(f"Starting user ingestion for {user_uuid} into index {user_index_name}")

        # Run ingestion in background
        background_tasks.add_task(ingestion_manager.ingest_documents, request)

        return DocumentIngestResponse(
            success=True,
            message="Ingestion started",
            upload_dir=str(uploads_dir),
            target_index=user_index_name,
        )

    except HTTPException:
        raise
    except Exception as e:
        app_logger.error(f"Error starting user ingestion: {e}")
        raise HTTPException(status_code=500, detail=f"Failed to start ingestion: {str(e)}")


# Error handlers
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """Global exception handler."""
    app_logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": "Internal server error", "error": str(exc)},
    )


if __name__ == "__main__":
    import uvicorn
    
    uvicorn.run(
        "app.main:app",
        host=settings.api_host,
        port=settings.api_port,
        reload=settings.environment == "development",
        log_level=settings.log_level.lower(),
    )
