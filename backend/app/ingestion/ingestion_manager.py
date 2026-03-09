"""
Resumable ingestion manager that coordinates the entire RAG pipeline.
"""
import asyncio
from pathlib import Path
from typing import List, Optional, Dict, Any
from datetime import datetime
from uuid import uuid4
from concurrent.futures import ThreadPoolExecutor
import hashlib

from sqlalchemy.orm import Session
from app.config import settings
from app.models import DocumentStatus, IngestionRequest
from app.ingestion.document_processor import DocumentProcessor
from app.ingestion.chunker import TextChunker
from app.ingestion.embedder import SentenceTransformerEmbedder
from app.vectorstore.faiss_manager import FAISSVectorStore
from app.vectorstore.metadata_db import (
    Document,
    Chunk,
    IngestionLog,
    get_session,
    init_database,
)
from app.utils.logger import app_logger


class IngestionManager:
    """Manage the document ingestion pipeline with resumability."""
    
    def __init__(self):
        # Initialize database
        init_database()
        
        # Initialize components
        self.doc_processor = DocumentProcessor(
            enable_ocr=settings.enable_ocr,
            ocr_language=settings.ocr_language,
        )
        self.chunker = TextChunker(
            chunk_size=settings.chunk_size,
            chunk_overlap=settings.chunk_overlap,
        )
        self.embedder = SentenceTransformerEmbedder()
        self.vector_store = FAISSVectorStore(
            dimension=self.embedder.dimension
        )
        
        self.executor = ThreadPoolExecutor(max_workers=settings.max_workers)
        self.is_running = False
        self.current_session_id: Optional[str] = None
        
        app_logger.info("Initialized IngestionManager")
    
    def _create_session_id(self) -> str:
        """Create a unique session ID for logging."""
        return str(uuid4())
    
    def _log_ingestion(
        self,
        session_id: str,
        action: str,
        message: str = None,
        **kwargs
    ):
        """Log ingestion progress to database."""
        db = get_session()
        try:
            log = IngestionLog(
                session_id=session_id,
                action=action,
                message=message,
                **kwargs
            )
            db.add(log)
            db.commit()
        except Exception as e:
            app_logger.error(f"Failed to log ingestion: {e}")
            db.rollback()
        finally:
            db.close()
    
    def _find_documents(self, request: IngestionRequest) -> List[Path]:
        """Find all documents matching the request criteria."""
        folder = Path(request.folder_path)
        if not folder.exists():
            raise ValueError(f"Folder does not exist: {folder}")
        
        if not folder.is_dir():
            raise ValueError(f"Path is not a directory: {folder}")
        
        app_logger.info(f"Scanning folder: {folder}")
        
        all_files = []
        for pattern in request.file_patterns:
            if request.recursive:
                files = folder.rglob(pattern)
            else:
                files = folder.glob(pattern)
            all_files.extend(files)
        
        # Remove duplicates and sort
        all_files = sorted(set([f for f in all_files if f.is_file()]))
        
        app_logger.info(f"Found {len(all_files)} files")
        return all_files
    
    def _is_document_processed(self, file_path: Path, file_hash: str) -> bool:
        """Check if document is already processed and up-to-date."""
        db = get_session()
        try:
            doc = db.query(Document).filter_by(file_path=str(file_path)).first()
            if doc and doc.status == DocumentStatus.COMPLETED.value:
                if doc.file_hash == file_hash:
                    return True  # Already processed and unchanged
                else:
                    app_logger.info(f"File changed: {file_path.name}")
                    return False  # File changed, needs reprocessing
            return False
        finally:
            db.close()
    
    def _store_document_and_chunks(
        self,
        file_path: Path,
        processed_doc: Dict[str, Any],
        chunks: List[Dict[str, Any]],
        embeddings: Any,
    ):
        """Store document metadata and chunks in database and vector store."""
        db = get_session()
        try:
            # Check if document exists
            doc = db.query(Document).filter_by(file_path=str(file_path)).first()
            
            if doc:
                # Update existing document
                doc.file_hash = processed_doc['file_hash']
                doc.status = DocumentStatus.COMPLETED.value
                doc.processed_at = datetime.now()
                doc.total_chunks = len(chunks)
                doc.error_message = None
                
                # Delete old chunks
                db.query(Chunk).filter_by(document_id=doc.id).delete()
            else:
                # Create new document
                doc = Document(
                    file_path=str(file_path),
                    file_hash=processed_doc['file_hash'],
                    document_type=processed_doc['document_type'].value,
                    status=DocumentStatus.COMPLETED.value,
                    total_pages=processed_doc['metadata'].get('total_pages'),
                    total_chunks=len(chunks),
                    file_size=file_path.stat().st_size,
                    processed_at=datetime.now(),
                    doc_metadata=processed_doc['metadata'],
                )
                db.add(doc)
                db.flush()  # Get the document ID
            
            # Create chunk records
            chunk_metadatas = []
            for idx, chunk_data in enumerate(chunks):
                chunk_id = hashlib.sha256(
                    f"{file_path}{idx}{chunk_data['text']}".encode()
                ).hexdigest()
                
                chunk = Chunk(
                    chunk_id=chunk_id,
                    document_id=doc.id,
                    chunk_index=idx,
                    content=chunk_data['text'],
                    content_hash=hashlib.sha256(chunk_data['text'].encode()).hexdigest(),
                    page_number=chunk_data['metadata'].get('page_number'),
                    tokens=len(chunk_data['text'].split()),
                )
                db.add(chunk)
                
                # Prepare metadata for vector store
                chunk_metadatas.append({
                    'chunk_id': chunk_id,
                    'document_id': doc.id,
                    'file_path': str(file_path),
                    'file_name': file_path.name,
                    'chunk_index': idx,
                    'page_number': chunk_data['metadata'].get('page_number'),
                    'content': chunk_data['text'],
                })
            
            db.commit()
            
            # Add to vector store
            self.vector_store.add_vectors(embeddings, chunk_metadatas)
            
            app_logger.info(f"Stored {len(chunks)} chunks for {file_path.name}")
            
        except Exception as e:
            db.rollback()
            app_logger.error(f"Error storing document: {e}")
            raise
        finally:
            db.close()
    
    async def ingest_documents(self, request: IngestionRequest) -> Dict[str, Any]:
        """
        Ingest documents from a folder with resumability.
        
        This is the main entry point for document ingestion.
        """
        if self.is_running:
            raise RuntimeError("Ingestion already running")
        
        self.is_running = True
        self.current_session_id = self._create_session_id()
        
        session_id = self.current_session_id
        
        try:
            # Find documents
            documents = self._find_documents(request)
            total_docs = len(documents)
            
            self._log_ingestion(
                session_id,
                "start",
                f"Starting ingestion of {total_docs} documents",
                documents_total=total_docs,
            )
            
            processed_count = 0
            failed_count = 0
            skipped_count = 0
            
            # Process in batches
            batch = []
            for idx, file_path in enumerate(documents):
                try:
                    # Compute hash for change detection
                    file_hash = self.doc_processor.compute_file_hash(file_path)
                    
                    # Skip if already processed
                    if settings.skip_existing and not request.force_reprocess:
                        if self._is_document_processed(file_path, file_hash):
                            app_logger.info(f"Skipping already processed: {file_path.name}")
                            skipped_count += 1
                            continue
                    
                    # Process document
                    app_logger.info(f"Processing [{idx+1}/{total_docs}]: {file_path.name}")
                    processed_doc = self.doc_processor.process_document(file_path)
                    
                    # Chunk text
                    chunks = self.chunker.chunk_text(
                        processed_doc['content'],
                        metadata={'file_path': str(file_path)}
                    )
                    
                    if not chunks:
                        app_logger.warning(f"No chunks extracted from {file_path.name}")
                        skipped_count += 1
                        continue
                    
                    # Generate embeddings
                    chunk_texts = [chunk['text'] for chunk in chunks]
                    embeddings = self.embedder.embed_batch(chunk_texts)
                    
                    # Store in database and vector store
                    self._store_document_and_chunks(
                        file_path,
                        processed_doc,
                        chunks,
                        embeddings,
                    )
                    
                    processed_count += 1
                    batch.append(file_path)
                    
                    # Save checkpoint every batch_size documents
                    if len(batch) >= settings.batch_size:
                        self.vector_store.save_index()
                        app_logger.info(f"Checkpoint: {processed_count} documents processed")
                        batch = []
                    
                except Exception as e:
                    app_logger.error(f"Failed to process {file_path}: {e}", exc_info=True)
                    failed_count += 1
                    
                    # Mark as failed in database
                    db = get_session()
                    try:
                        doc = db.query(Document).filter_by(file_path=str(file_path)).first()
                        if doc:
                            doc.status = DocumentStatus.FAILED.value
                            doc.error_message = str(e)
                        else:
                            doc = Document(
                                file_path=str(file_path),
                                file_hash="",
                                document_type="unknown",
                                status=DocumentStatus.FAILED.value,
                                file_size=0,
                                error_message=str(e),
                            )
                            db.add(doc)
                        db.commit()
                    finally:
                        db.close()
            
            # Final save
            self.vector_store.save_index()
            
            result = {
                "session_id": session_id,
                "total_documents": total_docs,
                "processed": processed_count,
                "failed": failed_count,
                "skipped": skipped_count,
                "success": failed_count == 0,
            }
            
            self._log_ingestion(
                session_id,
                "complete",
                "Ingestion completed",
                documents_total=total_docs,
                documents_processed=processed_count,
                documents_failed=failed_count,
            )
            
            app_logger.info(
                f"Ingestion complete: {processed_count} processed, "
                f"{failed_count} failed, {skipped_count} skipped"
            )
            
            return result
        
        except Exception as e:
            app_logger.error(f"Ingestion error: {e}", exc_info=True)
            self._log_ingestion(
                session_id,
                "error",
                f"Ingestion failed: {e}",
            )
            raise
        
        finally:
            self.is_running = False
            self.current_session_id = None
    
    def get_ingestion_status(self) -> Dict[str, Any]:
        """Get current ingestion status."""
        db = get_session()
        try:
            total = db.query(Document).count()
            completed = db.query(Document).filter_by(
                status=DocumentStatus.COMPLETED.value
            ).count()
            failed = db.query(Document).filter_by(
                status=DocumentStatus.FAILED.value
            ).count()
            
            return {
                "is_running": self.is_running,
                "current_session_id": self.current_session_id,
                "total_documents": total,
                "completed_documents": completed,
                "failed_documents": failed,
                "vector_store_stats": self.vector_store.get_stats(),
            }
        finally:
            db.close()
