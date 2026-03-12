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
    target_index: Optional[str] = Field(default=None, description="Target custom index name (None = auto-route)")
    model: Optional[str] = Field(default=None, description="LLM model to use for processing (None = use default)")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "folder_path": "C:/Users/data/physics_books",
            "recursive": True,
            "file_patterns": ["*.pdf", "*.html"],
            "force_reprocess": False,
            "target_index": "ncert_physics"
        }
    })


class IngestionStatus(BaseModel):
    """Status of document ingestion process."""
    is_running: bool
    total_documents: int = 0
    processed_documents: int = 0
    failed_documents: int = 0
    current_document: Optional[str] = None
    progress_percentage: float = 0.0
    estimated_time_remaining: Optional[int] = None  # seconds
    last_updated: datetime = Field(default_factory=datetime.now)


class QueryRequest(BaseModel):
    """Request model for querying the knowledge base."""
    query: str = Field(..., min_length=1, description="Natural language query")
    top_k: int = Field(default=5, ge=1, le=50, description="Number of results to retrieve")
    subject_filter: Optional[Subject] = Field(default=None, description="Filter by subject")
    index_filter: Optional[List[str]] = Field(default=None, description="Specific indexes to search (None = search all available indexes)")
    model: Optional[str] = Field(default=None, description="LLM model to use (None = use default from config)")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "query": "Explain Newton's laws of motion",
            "top_k": 5,
            "subject_filter": "physics",
            "index_filter": ["ncert_physics", "theory"]
        }
    })


class RetrievedChunk(BaseModel):
    """Retrieved document chunk with metadata."""
    content: str
    source_file: str
    page_number: Optional[int] = None
    chunk_id: str
    similarity_score: float
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
    index_filter: Optional[List[str]] = Field(default=None, description="Filter by specific indexes (None = search all)")
    model: Optional[str] = Field(default=None, description="LLM model to use (None = use default from config)")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "subject": "physics",
            "difficulty": "medium",
            "question_type": "multiple_choice",
            "num_questions": 5,
            "topic": "thermodynamics",
            "index_filter": ["ncert_physics"]
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


# Index Management Models

class CreateIndexRequest(BaseModel):
    """Request to create a custom index."""
    index_name: str = Field(..., min_length=1, max_length=50, description="Name for the custom index")
    description: str = Field(default="", max_length=500, description="Optional description")
    embedding_dimension: Optional[int] = Field(default=None, description="Embedding dimension (defaults to system setting)")
    
    model_config = ConfigDict(json_schema_extra={
        "example": {
            "index_name": "ncert_physics",
            "description": "NCERT Physics textbooks",
            "embedding_dimension": 384
        }
    })


class IndexInfo(BaseModel):
    """Information about an index."""
    name: str
    description: str = ""
    document_count: int = 0
    chunk_count: int = 0
    dimension: int
    is_custom: bool
    created_at: Optional[datetime] = None
    last_updated: Optional[datetime] = None


class ListIndexesResponse(BaseModel):
    """Response with list of all indexes."""
    indexes: List[IndexInfo]
    total_count: int


class IndexOperationResponse(BaseModel):
    """Response for index operations."""
    success: bool
    message: str
    index_info: Optional[IndexInfo] = None
