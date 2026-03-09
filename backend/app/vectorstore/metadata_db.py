"""
SQLAlchemy models for metadata storage.
"""
from datetime import datetime
from typing import Optional
from sqlalchemy import (
    create_engine,
    Column,
    Integer,
    String,
    Text,
    DateTime,
    Boolean,
    ForeignKey,
    JSON,
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from app.config import settings


Base = declarative_base()


class Document(Base):
    """Document metadata table."""
    
    __tablename__ = "documents"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    file_path = Column(String(1000), unique=True, nullable=False, index=True)
    file_hash = Column(String(64), nullable=False)  # SHA256
    document_type = Column(String(20), nullable=False)
    status = Column(String(20), nullable=False, default="pending")
    
    total_pages = Column(Integer, nullable=True)
    total_chunks = Column(Integer, default=0)
    file_size = Column(Integer, nullable=False)  # bytes
    
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    processed_at = Column(DateTime, nullable=True)
    updated_at = Column(DateTime, default=datetime.now, onupdate=datetime.now)
    
    error_message = Column(Text, nullable=True)
    doc_metadata = Column(JSON, default=dict)
    
    # Relationship
    chunks = relationship("Chunk", back_populates="document", cascade="all, delete-orphan")
    
    def __repr__(self):
        return f"<Document(id={self.id}, path={self.file_path}, status={self.status})>"


class Chunk(Base):
    """Document chunk table."""
    
    __tablename__ = "chunks"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    chunk_id = Column(String(64), unique=True, nullable=False, index=True)  # UUID
    document_id = Column(Integer, ForeignKey("documents.id"), nullable=False)
    
    chunk_index = Column(Integer, nullable=False)
    content = Column(Text, nullable=False)
    content_hash = Column(String(64), nullable=False)  # SHA256 of content
    
    page_number = Column(Integer, nullable=True)
    section = Column(String(500), nullable=True)
    
    has_image = Column(Boolean, default=False)
    has_table = Column(Boolean, default=False)
    tokens = Column(Integer, default=0)
    
    created_at = Column(DateTime, default=datetime.now, nullable=False)
    
    # Relationship
    document = relationship("Document", back_populates="chunks")
    
    def __repr__(self):
        return f"<Chunk(id={self.id}, doc_id={self.document_id}, index={self.chunk_index})>"


class IngestionLog(Base):
    """Ingestion process log."""
    
    __tablename__ = "ingestion_logs"
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    
    action = Column(String(50), nullable=False)  # start, process, complete, error
    message = Column(Text, nullable=True)
    
    documents_total = Column(Integer, default=0)
    documents_processed = Column(Integer, default=0)
    documents_failed = Column(Integer, default=0)
    
    timestamp = Column(DateTime, default=datetime.now, nullable=False)
    
    log_metadata = Column(JSON, default=dict)
    
    def __repr__(self):
        return f"<IngestionLog(id={self.id}, session={self.session_id}, action={self.action})>"


# Database engine and session
def get_engine():
    """Create SQLAlchemy engine with timeout."""
    db_path = settings.metadata_db_path
    engine = create_engine(
        f"sqlite:///{db_path}",
        echo=False,
        connect_args={
            "check_same_thread": False,
            "timeout": 5  # 5-second timeout for DB locks
        },
        pool_pre_ping=True,  # Verify connections before using
        pool_recycle=3600,   # Recycle connections every hour
    )
    return engine


def init_database():
    """Initialize database and create tables."""
    engine = get_engine()
    Base.metadata.create_all(engine)
    return engine


def get_session():
    """Get a database session."""
    engine = get_engine()
    Session = sessionmaker(bind=engine)
    return Session()
