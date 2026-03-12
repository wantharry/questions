"""
FastAPI main application with all endpoints.
"""
import json
import time
from datetime import datetime
from pathlib import Path
from typing import Dict, Any
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

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
    DeleteIndexRequest,
    IndexIngestionRequest,
    RetrievalMode,
    AdvancedQuerySettings,
    SearchType,
)
from app.models_advanced import HybridSearchRequest, IndexType
from app.ingestion.advanced_ingestion_manager import AdvancedIngestionManager
from app.retrieval.hybrid_retriever import HybridRetriever
from app.ingestion.embedder import SentenceTransformerEmbedder
from app.llm.question_generator import QuestionGenerator
from app.llm.llm_manager import LLMManager
from app.llm.prompts import PromptTemplates
from app.utils.logger import app_logger, setup_logging


# Global instances
ingestion_manager: AdvancedIngestionManager = None
retriever: HybridRetriever = None
embedder: SentenceTransformerEmbedder = None
question_generator: QuestionGenerator = None

# Custom index storage — persisted to disk so indexes survive backend restarts
custom_indexes: Dict[str, Dict[str, Any]] = {}

_CUSTOM_INDEXES_FILE = Path("./data/custom_indexes.json")


def _load_custom_indexes():
    """Load custom indexes from disk into the in-memory dict."""
    global custom_indexes
    if not _CUSTOM_INDEXES_FILE.exists():
        return
    try:
        with open(_CUSTOM_INDEXES_FILE, "r", encoding="utf-8") as f:
            raw = json.load(f)
        # Re-parse datetime strings back to datetime objects
        for idx in raw.values():
            for dt_field in ("created_at", "last_updated"):
                val = idx.get(dt_field)
                if isinstance(val, str):
                    try:
                        idx[dt_field] = datetime.fromisoformat(val)
                    except ValueError:
                        idx[dt_field] = None
        custom_indexes = raw
        app_logger.info(f"Loaded {len(custom_indexes)} custom indexes from disk")
    except Exception as e:
        app_logger.warning(f"Could not load custom indexes from disk: {e}")


def _save_custom_indexes():
    """Persist the in-memory custom_indexes dict to disk."""
    try:
        _CUSTOM_INDEXES_FILE.parent.mkdir(parents=True, exist_ok=True)
        serialisable = {}
        for k, v in custom_indexes.items():
            entry = dict(v)
            for dt_field in ("created_at", "last_updated"):
                if isinstance(entry.get(dt_field), datetime):
                    entry[dt_field] = entry[dt_field].isoformat()
            serialisable[k] = entry
        with open(_CUSTOM_INDEXES_FILE, "w", encoding="utf-8") as f:
            json.dump(serialisable, f, indent=2)
    except Exception as e:
        app_logger.warning(f"Could not save custom indexes to disk: {e}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application resources."""
    global ingestion_manager, retriever, embedder, question_generator
    
    # Startup
    setup_logging()
    app_logger.info("Starting application with Advanced Hybrid RAG...")
    
    try:
        # Load persisted custom indexes before anything else
        _load_custom_indexes()

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
    if ingestion_manager is None:
        # Still starting up
        return HealthCheck(
            status="starting",
            llm_provider=settings.llm_provider,
            embedding_provider=settings.embedding_provider,
            vector_store_type="hybrid_multi_index",
            total_documents=0,
            total_chunks=0,
        )

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
    try:
        status = ingestion_manager.get_ingestion_status()
    except Exception as e:
        app_logger.warning(f"Status endpoint DB timeout or error: {e}")
        # Return partial status from in-memory state if DB is locked
        return IngestionStatus(
            is_running=ingestion_manager.is_running,
            current_document=ingestion_manager.current_document,
            total_documents=ingestion_manager.session_total,
            processed_documents=ingestion_manager.session_processed,
            skipped_documents=ingestion_manager.session_skipped,
            failed_documents=ingestion_manager.session_failed,
            progress_percentage=(
                ((ingestion_manager.session_processed + ingestion_manager.session_skipped) /
                 ingestion_manager.session_total * 100)
                if ingestion_manager.session_total > 0 else 0
            ),
        )

    session_total = status.get('session_total', 0)
    session_processed = status.get('session_processed', 0)
    session_skipped = status.get('session_skipped', 0)

    progress = 0.0
    if session_total > 0:
        progress = ((session_processed + session_skipped) / session_total) * 100

    return IngestionStatus(
        is_running=status['is_running'],
        current_document=status.get('current_document'),
        total_documents=session_total,
        processed_documents=session_processed,
        skipped_documents=session_skipped,
        failed_documents=status.get('session_failed', 0),
        progress_percentage=progress,
    )


# Query endpoint
@app.post("/api/query", response_model=QueryResponse)
async def query_knowledge_base(request: QueryRequest):
    """
    Query the knowledge base and get an answer.
    
    This retrieves relevant chunks and generates an answer using the LLM.
    Supports advanced query settings for fine-grained control.
    """
    start_time = time.time()
    
    try:
        # Use advanced settings if provided, otherwise use defaults
        settings = request.settings or AdvancedQuerySettings()
        
        # Lazy-load query components
        current_embedder = get_embedder()
        current_retriever = get_retriever()
        
        # Generate query embedding
        query_embedding = current_embedder.embed_text(request.query)
        
        # Determine retrieval count (use settings if available)
        retrieval_count = settings.retrieval_chunks if request.settings else request.top_k
        
        # Determine which indexes to search
        specific_indexes = None
        filter_metadata = None
        if request.index_name and request.index_name != "default":
            # Map index name to IndexType for the default specialized indexes
            index_mapping = {
                "theory": IndexType.THEORY,
                "formula": IndexType.FORMULA,
                "exercise": IndexType.EXERCISE,
                "solution": IndexType.SOLUTION,
                "general": IndexType.GENERAL,
            }
            
            if request.index_name in index_mapping:
                specific_indexes = [index_mapping[request.index_name]]
                app_logger.info(f"Query targeting specific index: {request.index_name}")
            elif request.index_name in custom_indexes:
                # Custom index - check if it uses classification
                use_classification = custom_indexes[request.index_name].get('use_classification', False)
                filter_metadata = {"custom_index_name": request.index_name}
                
                if use_classification:
                    # Classification mode: search all indexes with metadata filter
                    app_logger.info(f"Query targeting custom index with classification: {request.index_name}")
                else:
                    # Unified mode: search only GENERAL index with metadata filter
                    specific_indexes = [IndexType.GENERAL]
                    app_logger.info(f"Query targeting unified custom index (GENERAL only): {request.index_name}")
            else:
                app_logger.info(f"Query targeting unknown index: {request.index_name}, searching all")
        else:
            app_logger.info("Query searching all indexes with automatic routing")
        
        # Hybrid retrieval with automatic routing
        results = current_retriever.search(
            query=request.query,
            query_embedding=query_embedding,
            top_k=retrieval_count,
            use_reranking=settings.ai_reranker,
            specific_indexes=specific_indexes,
            filter_metadata=filter_metadata,
        )
        
        if not results:
            return QueryResponse(
                query=request.query,
                answer="No relevant information found in the knowledge base for your query.",
                retrieved_chunks=[],
                processing_time=time.time() - start_time,
            )
        
        # Apply reranker top chunks limit if reranking is enabled
        if settings.ai_reranker and settings.reranker_top_chunks < len(results):
            results = results[:settings.reranker_top_chunks]
        
        # Expand context window if enabled
        if settings.expand_context_window and settings.context_window_size > 0:
            # TODO: Implement context window expansion
            # This would fetch surrounding chunks for each result
            app_logger.info(f"Context window expansion requested but not yet implemented")
        
        # Format context from results
        context_parts = []
        chunks = []
        for i, result in enumerate(results):
            context_parts.append(f"Source {i+1}:\n{result['text']}")
            chunks.append({
                'chunk_id': result['metadata'].get('chunk_id', result.get('id', f'chunk_{i}')),
                'content': result['text'],
                'source_file': result['metadata'].get('file_name', 'Unknown'),
                'page_number': result['metadata'].get('page_number'),
                'similarity_score': result.get('hybrid_score', result.get('score', 0.0)),
                'content_type': result['metadata'].get('content_type', 'unknown'),
                'difficulty': result['metadata'].get('difficulty', 'unknown'),
            })
        
        context = "\n\n".join(context_parts)
        
        # Generate answer
        llm = LLMManager.get_llm()
        system_prompt, user_prompt = PromptTemplates.get_answer_prompt(context, request.query)
        
        response = await llm.generate(
            prompt=user_prompt,
            system_prompt=system_prompt,
        )
        
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
        questions = await current_generator.generate_questions(request)
        
        # Get the context that was used
        if request.context:
            context_used = request.context[:500] + "..." if len(request.context) > 500 else request.context
        else:
            # Use topic/subject info instead
            context_used = f"Generating {request.question_type.value} questions for {request.subject.value}"
            if request.topic:
                context_used += f" - Topic: {request.topic}"
        
        processing_time = time.time() - start_time
        
        return QuestionGenerationResponse(
            questions=questions,
            context_used=context_used,
            processing_time=processing_time,
        )
    
    except Exception as e:
        app_logger.error(f"Question generation error: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# Index Management endpoints
@app.post("/api/indexes/create")
async def create_index(request: CreateIndexRequest):
    """Create a new custom index with specific configuration."""
    if request.index_name in custom_indexes:
        raise HTTPException(status_code=400, detail=f"Index '{request.index_name}' already exists")
    
    try:
        # Store index configuration
        custom_indexes[request.index_name] = {
            "index_name": request.index_name,
            "retrieval_mode": request.retrieval_mode,
            "use_classification": request.use_classification,
            "chunk_size": request.chunk_size,
            "chunk_overlap": request.chunk_overlap,
            "embedding_model": request.embedding_model,
            "overview_llm": request.overview_llm,
            "enable_contextual_retrieval": request.enable_contextual_retrieval,
            "context_window": request.context_window,
            "retrieval_llm": request.retrieval_llm,
            "batch_size": request.batch_size,
            "description": request.description,
            "created_at": datetime.now(),
            "last_updated": None,
            "document_count": 0,
            "chunk_count": 0,
        }
        
        _save_custom_indexes()
        app_logger.info(f"Created new index: {request.index_name}")
        
        return {
            "message": f"Index '{request.index_name}' created successfully",
            "index_name": request.index_name,
        }
    
    except Exception as e:
        app_logger.error(f"Error creating index: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/indexes", response_model=ListIndexesResponse)
async def list_indexes():
    """List all available indexes (both default and custom)."""
    try:
        status = ingestion_manager.get_ingestion_status()
        multi_index_stats = status.get('multi_index_stats', {})
        
        indexes = []
        
        # Add default indexes (content-type based)
        for idx_name, idx_stats in multi_index_stats.items():
            indexes.append(IndexInfo(
                index_name=idx_name,
                retrieval_mode=RetrievalMode.HYBRID,
                chunk_size=settings.chunk_size,
                chunk_overlap=settings.chunk_overlap,
                embedding_model=settings.embedding_model,
                document_count=idx_stats.get('document_count', 0),
                chunk_count=idx_stats.get('document_count', 0),
                created_at=datetime.now(),
                description=f"Default {idx_name} content index",
                config={}
            ))
        
        # Add custom indexes
        for idx_name, idx_config in custom_indexes.items():
            indexes.append(IndexInfo(
                index_name=idx_config['index_name'],
                retrieval_mode=idx_config['retrieval_mode'],
                chunk_size=idx_config['chunk_size'],
                chunk_overlap=idx_config['chunk_overlap'],
                embedding_model=idx_config['embedding_model'],
                document_count=idx_config['document_count'],
                chunk_count=idx_config['chunk_count'],
                created_at=idx_config['created_at'],
                last_updated=idx_config.get('last_updated'),
                description=idx_config.get('description'),
                config=idx_config
            ))
        
        return ListIndexesResponse(
            indexes=indexes,
            total_count=len(indexes)
        )
    
    except Exception as e:
        app_logger.error(f"Error listing indexes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/api/indexes/{index_name}", response_model=IndexInfo)
async def get_index_info(index_name: str):
    """Get information about a specific index."""
    # Check custom indexes first
    if index_name in custom_indexes:
        idx_config = custom_indexes[index_name]
        return IndexInfo(
            index_name=idx_config['index_name'],
            retrieval_mode=idx_config['retrieval_mode'],
            chunk_size=idx_config['chunk_size'],
            chunk_overlap=idx_config['chunk_overlap'],
            embedding_model=idx_config['embedding_model'],
            document_count=idx_config['document_count'],
            chunk_count=idx_config['chunk_count'],
            created_at=idx_config['created_at'],
            last_updated=idx_config.get('last_updated'),
            description=idx_config.get('description'),
            config=idx_config
        )
    
    # Check default indexes
    status = ingestion_manager.get_ingestion_status()
    multi_index_stats = status.get('multi_index_stats', {})
    
    if index_name in multi_index_stats:
        idx_stats = multi_index_stats[index_name]
        return IndexInfo(
            index_name=index_name,
            retrieval_mode=RetrievalMode.HYBRID,
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
            embedding_model=settings.embedding_model,
            document_count=idx_stats.get('document_count', 0),
            chunk_count=idx_stats.get('document_count', 0),
            created_at=datetime.now(),
            description=f"Default {index_name} content index",
            config={}
        )
    
    raise HTTPException(status_code=404, detail=f"Index '{index_name}' not found")


@app.delete("/api/indexes/{index_name}")
async def delete_index(index_name: str, request: DeleteIndexRequest):
    """Delete a custom index."""
    if not request.confirm:
        raise HTTPException(status_code=400, detail="Must confirm deletion")
    
    if index_name not in custom_indexes:
        raise HTTPException(status_code=404, detail=f"Index '{index_name}' not found")
    
    try:
        # Remove index configuration
        del custom_indexes[index_name]
        _save_custom_indexes()
        
        app_logger.info(f"Deleted index: {index_name}")
        
        return {"message": f"Index '{index_name}' deleted successfully"}
    
    except Exception as e:
        app_logger.error(f"Error deleting index: {e}")
        raise HTTPException(status_code=500, detail=str(e))


def _ingest_and_update_count(idx_name: str, req: IngestionRequest):
    """Run ingestion then update the custom index document/chunk counts."""
    try:
        result = ingestion_manager.ingest_documents(req)
        if idx_name in custom_indexes:
            processed = result.get("processed", 0)
            skipped = result.get("skipped", 0)
            # Count both processed AND skipped: skipped means already in the system,
            # so they still belong to this index (e.g. re-ingesting same folder).
            total_for_index = processed + skipped
            custom_indexes[idx_name]["document_count"] = (
                custom_indexes[idx_name].get("document_count", 0) + total_for_index
            )
            # Estimate chunk count using BM25 total (reflects actual indexed text chunks)
            bm25_total = result.get("bm25_stats", {}).get("total_documents", 0)
            custom_indexes[idx_name]["chunk_count"] = bm25_total if bm25_total else custom_indexes[idx_name]["document_count"]
            custom_indexes[idx_name]["last_updated"] = datetime.now()
            app_logger.info(
                f"Updated index '{idx_name}' counts: "
                f"document_count={custom_indexes[idx_name]['document_count']} "
                f"(processed={processed}, skipped={skipped}), "
                f"chunk_count={custom_indexes[idx_name]['chunk_count']}"
            )
            _save_custom_indexes()
    except Exception as e:
        app_logger.error(f"Ingestion error for index '{idx_name}': {e}")
        raise


@app.post("/api/indexes/{index_name}/ingest")
async def ingest_into_index(index_name: str, request: IndexIngestionRequest, background_tasks: BackgroundTasks):
    """Ingest documents into a specific index."""
    # Verify index exists
    if index_name not in custom_indexes:
        # Check if it's a default index
        status = ingestion_manager.get_ingestion_status()
        multi_index_stats = status.get('multi_index_stats', {})
        if index_name not in multi_index_stats:
            raise HTTPException(status_code=404, detail=f"Index '{index_name}' not found")
    
    if ingestion_manager.is_running:
        raise HTTPException(status_code=400, detail="Ingestion already running")
    
    # Convert to standard ingestion request
    use_classification = custom_indexes[index_name].get('use_classification', False) if index_name in custom_indexes else True
    ingestion_req = IngestionRequest(
        folder_path=request.folder_path if request.folder_path else "",
        recursive=request.recursive,
        file_patterns=request.file_patterns,
        force_reprocess=request.force_reprocess,
        custom_index_name=index_name if index_name in custom_indexes else None,
        use_classification=use_classification,
    )
    
    app_logger.info(f"Starting ingestion into index '{index_name}': {request.folder_path}")
    
    # Run ingestion in background; wrapper updates custom index doc/chunk counts on completion
    if index_name in custom_indexes:
        background_tasks.add_task(_ingest_and_update_count, index_name, ingestion_req)
    else:
        background_tasks.add_task(ingestion_manager.ingest_documents, ingestion_req)
    
    return {
        "message": f"Ingestion started for index '{index_name}'",
        "index_name": index_name,
        "folder_path": request.folder_path,
    }


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
