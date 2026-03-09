"""
Application configuration management using Pydantic Settings.
Supports environment variables and .env files.
"""
from pathlib import Path
from typing import Literal, Optional
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings with validation and type safety."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore"
    )
    
    # Application
    app_name: str = Field(default="RAG Question Generator")
    environment: Literal["development", "production"] = Field(default="development")
    log_level: str = Field(default="INFO")
    
    # Paths
    data_dir: Path = Field(default=Path("./data"))
    vector_store_dir: Path = Field(default=Path("./data/vector_store"))
    metadata_db_path: Path = Field(default=Path("./data/metadata/metadata.db"))
    logs_dir: Path = Field(default=Path("./data/logs"))
    models_dir: Path = Field(default=Path("./models"))
    
    # LLM Configuration (Pluggable)
    llm_provider: Literal["ollama", "openai", "llama_cpp", "vllm"] = Field(default="ollama")
    llm_model: str = Field(default="mistral:7b-instruct")
    llm_base_url: str = Field(default="http://localhost:11434")
    llm_temperature: float = Field(default=0.7, ge=0.0, le=2.0)
    llm_max_tokens: int = Field(default=2048, ge=1)
    llm_timeout: int = Field(default=120, ge=1)
    
    # Alternative LLM configs
    openai_api_key: Optional[str] = Field(default=None)
    openai_base_url: Optional[str] = Field(default=None)
    llama_cpp_model_path: Optional[Path] = Field(default=None)
    
    # Embeddings Configuration (Pluggable)
    embedding_provider: Literal["sentence_transformers", "openai", "huggingface"] = Field(
        default="sentence_transformers"
    )
    embedding_model: str = Field(default="sentence-transformers/all-MiniLM-L6-v2")
    embedding_dimension: int = Field(default=384, ge=1)
    embedding_device: Literal["cpu", "cuda"] = Field(default="cpu")
    embedding_batch_size: int = Field(default=32, ge=1)
    use_gpu: bool = Field(default=False)  # Whether to use GPU for reranking and other operations
    
    # Vector Store Configuration
    vector_store_type: Literal["faiss", "chroma"] = Field(default="faiss")
    faiss_index_type: str = Field(default="IndexFlatL2")
    similarity_top_k: int = Field(default=5, ge=1)
    
    # Document Processing
    chunk_size: int = Field(default=1000, ge=100)
    chunk_overlap: int = Field(default=200, ge=0)
    max_workers: int = Field(default=4, ge=1)
    enable_ocr: bool = Field(default=True)
    ocr_language: str = Field(default="eng")
    
    # Ingestion Settings
    batch_size: int = Field(default=50, ge=1)
    resume_on_error: bool = Field(default=True)
    skip_existing: bool = Field(default=True)
    
    # API Settings
    api_host: str = Field(default="0.0.0.0")
    api_port: int = Field(default=8601, ge=1, le=65535)
    api_workers: int = Field(default=1, ge=1)
    
    # Frontend Settings
    streamlit_server_port: int = Field(default=8602, ge=1, le=65535)
    streamlit_server_address: str = Field(default="localhost")
    
    def model_post_init(self, __context) -> None:
        """Create necessary directories after initialization."""
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.vector_store_dir.mkdir(parents=True, exist_ok=True)
        self.metadata_db_path.parent.mkdir(parents=True, exist_ok=True)
        self.logs_dir.mkdir(parents=True, exist_ok=True)
        self.models_dir.mkdir(parents=True, exist_ok=True)


# Global settings instance
settings = Settings()
