"""
FastAPI main application with all endpoints.
"""
import time
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
)
from app.models_advanced import HybridSearchRequest
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Initialize and cleanup application resources."""
    global ingestion_manager, retriever, embedder, question_generator
    
    # Startup
    setup_logging()
    app_logger.info("Starting application with Advanced Hybrid RAG...")
    
    try:
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
        question_generator = QuestionGenerator()
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
        
        # Hybrid retrieval with automatic routing
        results = current_retriever.search(
            query=request.query,
            query_embedding=query_embedding,
            top_k=request.top_k,
            use_reranking=True,
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
            query = f"{request.subject.value}"
            if request.topic:
                query += f" {request.topic}"
            context_used = get_retriever().get_context_for_query(query, top_k=5)
            context_used = context_used[:500] + "..." if len(context_used) > 500 else context_used
        
        processing_time = time.time() - start_time
        
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
