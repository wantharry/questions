"""
Data models for the application using Pydantic for validation.
"""
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class DocumentStatus(str, Enum):
    """Processing status for documents."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    SKIPPED = "skipped"


class DocumentType(str, Enum):
    """Supported document types."""
    PDF = "pdf"
    HTML = "html"
    MARKDOWN = "markdown"
    DOCX = "docx"
    TEXT = "text"
    IMAGE = "image"
    UNKNOWN = "unknown"


class Subject(str, Enum):
    """Academic subjects for question generation."""
    MATHEMATICS = "mathematics"
    PHYSICS = "physics"
    CHEMISTRY = "chemistry"
    GENERAL = "general"


class DifficultyLevel(str, Enum):
    """Question difficulty levels."""
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"


class QuestionType(str, Enum):
    """Types of questions to generate."""
    MULTIPLE_CHOICE = "multiple_choice"
    SHORT_ANSWER = "short_answer"
    LONG_ANSWER = "long_answer"
    NUMERICAL = "numerical"
    TRUE_FALSE = "true_false"


# Request/Response Models

class IngestionRequest(BaseModel):
    """Request model for document ingestion."""
    folder_path: str = Field(..., description="Path to folder containing documents")
    recursive: bool = Field(default=True, description="Process subdirectories recursively")
    file_patterns: Optional[List[str]] = Field(
        default=["*.pdf", "*.html", "*.htm", "*.md", "*.docx", "*.txt"],
        description="File patterns to match"
    )
    force_reprocess: bool = Field(default=False, description="Reprocess already indexed files")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "folder_path": "C:/Users/data/physics_books",
            "recursive": True,
            "file_patterns": ["*.pdf", "*.html"],
            "force_reprocess": False
        }
    })


class IngestionStatus(BaseModel):
    """Status of document ingestion process."""
    is_running: bool
    total_documents: int = 0
    processed_documents: int = 0
    failed_documents: int = 0
    skipped_documents: int = 0
    current_document: Optional[str] = None
    progress_percentage: float = 0.0
    estimated_time_remaining: Optional[int] = None  # seconds
    last_updated: datetime = Field(default_factory=datetime.now)


class SearchType(str, Enum):
    """Search type for retrieval."""
    HYBRID = "hybrid"
    VECTOR = "vector"
    FTS = "fts"


class AdvancedQuerySettings(BaseModel):
    """Advanced query configuration settings."""
    # General Settings
    query_decomposition: bool = Field(default=False, description="Break complex queries into sub-queries")
    compose_sub_answers: bool = Field(default=False, description="Merge answers from decomposed queries")
    pruning: bool = Field(default=False, description="Remove irrelevant retrieved chunks")
    verify_answer: bool = Field(default=True, description="Verify answer quality before returning")
    streaming: bool = Field(default=False, description="Stream response tokens")
    
    # Retrieval Settings
    retrieval_llm: Optional[str] = Field(default=None, description="LLM for retrieval tasks")
    search_type: SearchType = Field(default=SearchType.HYBRID, description="Search strategy")
    retrieval_chunks: int = Field(default=20, ge=5, le=50, description="Number of chunks to retrieve")
    
    # Reranking & Context
    ai_reranker: bool = Field(default=True, description="Use AI-based reranking")
    reranker_top_chunks: int = Field(default=10, ge=3, le=20, description="Top chunks after reranking")
    expand_context_window: bool = Field(default=False, description="Include surrounding chunks")
    context_window_size: int = Field(default=1, ge=0, le=5, description="Number of surrounding chunks to include")


class QueryRequest(BaseModel):
    """Request model for querying the knowledge base."""
    query: str = Field(..., min_length=1, description="Natural language query")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of results to retrieve")
    subject_filter: Optional[Subject] = Field(default=None, description="Filter by subject")
    index_name: Optional[str] = Field(default=None, description="Specific index to search (None = all indexes)")
    settings: Optional[AdvancedQuerySettings] = Field(default=None, description="Advanced query settings")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "query": "Explain Newton's laws of motion",
            "top_k": 5,
            "subject_filter": "physics",
            "index_name": "physics_textbooks",
            "settings": {
                "query_decomposition": True,
                "ai_reranker": True,
                "retrieval_chunks": 20
            }
        }
    })


class RetrievedChunk(BaseModel):
    """Retrieved document chunk with metadata."""
    content: str
    source_file: str
    page_number: Optional[int] = None
    chunk_id: str
    similarity_score: float
    content_type: Optional[str] = None
    difficulty: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)


class QueryResponse(BaseModel):
    """Response model for queries."""
    query: str
    answer: str
    retrieved_chunks: List[RetrievedChunk]
    processing_time: float  # seconds


class QuestionGenerationRequest(BaseModel):
    """Request model for question generation."""
    context: Optional[str] = Field(default=None, description="Specific context or leave empty to use retrieved context")
    subject: Subject = Field(..., description="Subject area for questions")
    difficulty: DifficultyLevel = Field(default=DifficultyLevel.MEDIUM)
    question_type: QuestionType = Field(default=QuestionType.MULTIPLE_CHOICE)
    num_questions: int = Field(default=5, ge=1, le=20, description="Number of questions to generate")
    topic: Optional[str] = Field(default=None, description="Specific topic within subject")
    index_name: Optional[str] = Field(default=None, description="Specific index to use for context (None = all indexes)")
    settings: Optional[AdvancedQuerySettings] = Field(default=None, description="Advanced retrieval settings")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "subject": "physics",
            "difficulty": "medium",
            "question_type": "multiple_choice",
            "num_questions": 5,
            "topic": "thermodynamics",
            "index_name": "physics_textbooks"
        }
    })


class GeneratedQuestion(BaseModel):
    """A single generated question with answer."""
    question: str
    question_type: QuestionType
    difficulty: DifficultyLevel
    options: Optional[List[str]] = None  # For multiple choice
    correct_answer: str
    explanation: str
    subject: Subject
    topic: Optional[str] = None


class QuestionGenerationResponse(BaseModel):
    """Response model for question generation."""
    questions: List[GeneratedQuestion]
    context_used: str
    processing_time: float


# Database Models

class DocumentMetadata(BaseModel):
    """Metadata for a processed document."""
    file_path: str
    file_hash: str  # For detecting changes
    document_type: DocumentType
    status: DocumentStatus
    total_pages: Optional[int] = None
    total_chunks: int = 0
    file_size: int  # bytes
    created_at: datetime = Field(default_factory=datetime.now)
    processed_at: Optional[datetime] = None
    error_message: Optional[str] = None
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    model_config = ConfigDict(from_attributes=True)


class ChunkMetadata(BaseModel):
    """Metadata for a document chunk."""
    chunk_id: str
    document_id: int
    chunk_index: int
    content: str
    page_number: Optional[int] = None
    section: Optional[str] = None
    has_image: bool = False
    has_table: bool = False
    tokens: int = 0
    created_at: datetime = Field(default_factory=datetime.now)
    
    model_config = ConfigDict(from_attributes=True)


# Index Management Models

class RetrievalMode(str, Enum):
    """Retrieval mode for search."""
    HYBRID = "hybrid"
    VECTOR = "vector"
    FTS = "fts"


class CreateIndexRequest(BaseModel):
    """Request model for creating a new custom index."""
    index_name: str = Field(..., min_length=1, max_length=100, description="Unique name for the index")
    retrieval_mode: RetrievalMode = Field(default=RetrievalMode.HYBRID, description="Search mode")
    late_chunk_vectors: bool = Field(default=True, description="Compute vectors during indexing")
    high_recall_chunking: bool = Field(default=True, description="Use overlapping chunks for better recall")
    chunk_size: int = Field(default=512, ge=100, le=4000, description="Size of text chunks")
    chunk_overlap: int = Field(default=64, ge=0, le=500, description="Overlap between chunks")
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2", description="Embedding model name")
    overview_llm: Optional[str] = Field(default=None, description="LLM for document overviews")
    enable_contextual_retrieval: bool = Field(default=False, description="Enable contextual retrieval")
    context_window: int = Field(default=5, ge=1, le=20, description="Context window for retrieval")
    retrieval_llm: Optional[str] = Field(default=None, description="LLM for contextual retrieval")
    batch_size: int = Field(default=32, ge=1, le=256, description="Batch size for processing")
    description: Optional[str] = Field(default=None, description="Index description")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "index_name": "physics_textbooks",
            "retrieval_mode": "hybrid",
            "chunk_size": 512,
            "chunk_overlap": 64,
            "embedding_model": "sentence-transformers/all-MiniLM-L6-v2",
            "enable_contextual_retrieval": True,
            "context_window": 5
        }
    })


class IndexInfo(BaseModel):
    """Information about an existing index."""
    index_name: str
    retrieval_mode: RetrievalMode
    chunk_size: int
    chunk_overlap: int
    embedding_model: str
    document_count: int = 0
    chunk_count: int = 0
    created_at: datetime
    last_updated: Optional[datetime] = None
    description: Optional[str] = None
    config: Dict[str, Any] = Field(default_factory=dict)


class ListIndexesResponse(BaseModel):
    """Response for listing all indexes."""
    indexes: List[IndexInfo]
    total_count: int


class DeleteIndexRequest(BaseModel):
    """Request to delete an index."""
    index_name: str = Field(..., description="Name of index to delete")
    confirm: bool = Field(..., description="Must be True to confirm deletion")


class IndexIngestionRequest(BaseModel):
    """Request model for ingesting documents into a specific index."""
    index_name: str = Field(..., description="Name of the index to ingest into")
    folder_path: Optional[str] = Field(default=None, description="Path to folder containing documents")
    file_paths: Optional[List[str]] = Field(default=None, description="Specific file paths to ingest")
    recursive: bool = Field(default=True, description="Process subdirectories recursively")
    file_patterns: Optional[List[str]] = Field(
        default=["*.pdf", "*.html", "*.htm", "*.md", "*.docx", "*.txt"],
        description="File patterns to match"
    )
    force_reprocess: bool = Field(default=False, description="Reprocess already indexed files")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "index_name": "physics_textbooks",
            "folder_path": "/mnt/c/Users/data/physics",
            "recursive": True,
            "file_patterns": ["*.pdf"],
            "force_reprocess": False
        }
    })


# Health Check

class HealthCheck(BaseModel):
    """Health check response."""
    status: str = "healthy"
    timestamp: datetime = Field(default_factory=datetime.now)
    version: str = "1.0.0"
    llm_provider: str
    embedding_provider: str
    vector_store_type: str
    total_documents: int = 0
    total_chunks: int = 0
