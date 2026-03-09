"""
Enhanced data models for advanced RAG architecture.
Supports content classification, hierarchy, and specialized indexes.
"""
from datetime import datetime
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field, ConfigDict


class ContentType(str, Enum):
    """Types of content in educational documents."""
    THEORY = "theory"
    DEFINITION = "definition"
    FORMULA = "formula"
    THEOREM = "theorem"
    DERIVATION = "derivation"
    WORKED_EXAMPLE = "worked_example"
    EXERCISE = "exercise"
    SOLUTION = "solution"
    DIAGRAM = "diagram"
    TABLE = "table"
    SUMMARY = "summary"
    QUESTION = "question"
    UNKNOWN = "unknown"


class DifficultyLevel(str, Enum):
    """Difficulty levels for content."""
    BASIC = "basic"
    EASY = "easy"
    MEDIUM = "medium"
    HARD = "hard"
    ADVANCED = "advanced"


class IndexType(str, Enum):
    """Types of specialized indexes."""
    THEORY = "theory"
    FORMULA = "formula"
    EXERCISE = "exercise"
    SOLUTION = "solution"
    GENERAL = "general"


class QueryIntent(str, Enum):
    """User query intent classification."""
    EXPLAIN_CONCEPT = "explain_concept"
    FORMULA_LOOKUP = "formula_lookup"
    FIND_EXAMPLES = "find_examples"
    GENERATE_QUESTIONS = "generate_questions"
    SOLVE_PROBLEM = "solve_problem"
    COMPARE_CONCEPTS = "compare_concepts"
    FIND_PREREQUISITES = "find_prerequisites"
    GENERAL = "general"


# Enhanced chunk metadata
class EnhancedChunkMetadata(BaseModel):
    """Rich metadata for intelligent chunks."""
    # Identity
    chunk_id: str
    document_id: int
    chunk_index: int
    
    # Content
    content: str
    content_hash: str
    
    # Hierarchy
    book_name: Optional[str] = None
    subject: Optional[str] = None  # physics, math, chemistry
    chapter: Optional[str] = None
    chapter_number: Optional[int] = None
    section: Optional[str] = None
    section_number: Optional[str] = None
    subsection: Optional[str] = None
    page_number: Optional[int] = None
    
    # Classification
    content_type: ContentType = ContentType.UNKNOWN
    difficulty: Optional[DifficultyLevel] = None
    
    # Semantic tags
    topics: List[str] = Field(default_factory=list)
    keywords: List[str] = Field(default_factory=list)
    formulas: List[str] = Field(default_factory=list)
    
    # Relations
    prerequisites: List[str] = Field(default_factory=list)
    related_chunks: List[str] = Field(default_factory=list)
    
    # References
    has_image: bool = False
    image_ids: List[str] = Field(default_factory=list)
    has_table: bool = False
    has_formula: bool = False
    
    # Quality
    tokens: int = 0
    is_complete: bool = True  # Not truncated mid-sentence
    
    model_config = ConfigDict(from_attributes=True)


class StructuredDocument(BaseModel):
    """Document with detected structure."""
    document_id: int
    file_path: str
    
    # Book metadata
    book_name: str
    subject: Optional[str] = None
    authors: List[str] = Field(default_factory=list)
    edition: Optional[str] = None
    
    # Structure
    chapters: List[Dict[str, Any]] = Field(default_factory=list)
    total_pages: int
    
    # Statistics
    theory_chunks: int = 0
    formula_chunks: int = 0
    exercise_chunks: int = 0
    example_chunks: int = 0
    
    # Extracted elements
    formulas: List[str] = Field(default_factory=list)
    diagrams: List[Dict[str, Any]] = Field(default_factory=list)
    
    created_at: datetime = Field(default_factory=datetime.now)


class HybridSearchRequest(BaseModel):
    """Request for hybrid retrieval."""
    query: str
    
    # Search parameters
    top_k: int = Field(default=20, ge=1, le=100)
    rerank_top_k: int = Field(default=5, ge=1, le=20)
    
    # Weights
    dense_weight: float = Field(default=0.7, ge=0.0, le=1.0)
    sparse_weight: float = Field(default=0.3, ge=0.0, le=1.0)
    
    # Filters
    subject_filter: Optional[str] = None
    chapter_filter: Optional[str] = None
    book_filter: Optional[str] = None
    content_type_filter: Optional[List[ContentType]] = None
    difficulty_filter: Optional[DifficultyLevel] = None
    
    # Index selection
    index_type: IndexType = IndexType.GENERAL
    
    # Query intent (auto-detected or manual)
    intent: Optional[QueryIntent] = None


class RetrievedChunk(BaseModel):
    """Enhanced retrieved chunk with scores."""
    content: str
    metadata: EnhancedChunkMetadata
    
    # Scores
    dense_score: float
    sparse_score: Optional[float] = None
    rerank_score: Optional[float] = None
    final_score: float
    
    # Source information
    source_file: str
    book_name: Optional[str] = None
    chapter: Optional[str] = None
    page_number: Optional[int] = None


class QuestionGenerationRequest(BaseModel):
    """Enhanced question generation request."""
    subject: str
    difficulty: DifficultyLevel
    
    # Targeting
    chapter: Optional[str] = None
    topic: Optional[str] = None
    book_name: Optional[str] = None
    
    # Generation parameters
    num_questions: int = Field(default=5, ge=1, le=20)
    question_type: str = "multiple_choice"
    
    # Context retrieval
    use_similar_exercises: bool = True
    include_theory: bool = True
    include_formulas: bool = True
    
    # Quality control
    ensure_unique: bool = True
    progressive_difficulty: bool = False


class ConceptExplanationRequest(BaseModel):
    """Request for concept explanation."""
    concept: str
    
    # Context
    subject: Optional[str] = None
    chapter: Optional[str] = None
    
    # Depth
    include_prerequisites: bool = True
    include_examples: bool = True
    include_formulas: bool = True
    
    # Target audience
    difficulty_level: DifficultyLevel = DifficultyLevel.MEDIUM


class ProblemSolvingRequest(BaseModel):
    """Request for problem solving."""
    problem: str
    
    # Context
    subject: Optional[str] = None
    topic: Optional[str] = None
    
    # Solution style
    step_by_step: bool = True
    show_formulas: bool = True
    show_similar_examples: bool = True
    explain_concepts: bool = True
