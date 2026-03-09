"""
Advanced ingestion manager using hybrid architecture.
Integrates smart chunking, content classification, and multi-index storage.
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
from app.models_advanced import ContentType, IndexType
from app.ingestion.document_processor import DocumentProcessor
from app.ingestion.smart_chunker import SmartChunker
from app.ingestion.embedder import SentenceTransformerEmbedder
from app.classification.content_classifier import ContentClassifier
from app.vectorstore.multi_index_manager import MultiIndexManager
from app.vectorstore.bm25_index import BM25Index
from app.vectorstore.metadata_db import (
    Document,
    Chunk,
    IngestionLog,
    get_session,
    init_database,
)
from app.utils.logger import app_logger


class AdvancedIngestionManager:
    """
    Advanced ingestion manager with:
    - Structure-aware smart chunking
    - Content type classification
    - Multiple specialized indexes
    - BM25 sparse index
    - Enhanced metadata tracking
    """
    
    def __init__(self):
        # Initialize database
        init_database()
        
        # Initialize components
        self.doc_processor = DocumentProcessor(
            enable_ocr=settings.enable_ocr,
            ocr_language=settings.ocr_language,
        )
        
        self.classifier = ContentClassifier()
        
        self.smart_chunker = SmartChunker(
            content_classifier=self.classifier,
            max_chunk_size=settings.chunk_size,
        )
        
        self.embedder = SentenceTransformerEmbedder()
        
        # Multi-index for dense retrieval
        self.multi_index = MultiIndexManager()
        
        # BM25 for sparse retrieval
        self.bm25_index = BM25Index()
        
        self.executor = ThreadPoolExecutor(max_workers=settings.max_workers)
        self.is_running = False
        self.current_session_id: Optional[str] = None
        
        app_logger.info("Initialized AdvancedIngestionManager with hybrid architecture")
    
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
        """Store document metadata and chunks in multiple indexes."""
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
            
            # Group chunks by content type for routing to appropriate indexes
            chunks_by_type = {}
            chunk_texts = []
            chunk_metadatas = []
            bm25_texts = []
            bm25_metadatas = []
            bm25_ids = []
            
            for idx, chunk_data in enumerate(chunks):
                # Generate chunk ID
                chunk_id = hashlib.sha256(
                    f"{file_path}{idx}{chunk_data['text']}".encode()
                ).hexdigest()
                
                # Get content type (from smart chunker or classifier)
                content_type = chunk_data.get('content_type')
                if not content_type:
                    content_type = self.classifier.classify_content(
                        chunk_data['text'],
                        chunk_data.get('metadata', {})
                    )
                
                # Detect difficulty
                difficulty = self.classifier.detect_difficulty(chunk_data['text'])
                
                # Extract keywords and formulas
                keywords = self.classifier.extract_keywords(chunk_data['text'])
                formulas = self.classifier.extract_formulas(chunk_data['text'])
                
                # Create enhanced metadata
                enhanced_metadata = {
                    'chunk_id': chunk_id,
                    'document_id': doc.id,
                    'file_path': str(file_path),
                    'file_name': file_path.name,
                    'chunk_index': idx,
                    'page_number': chunk_data.get('metadata', {}).get('page_number'),
                    'content': chunk_data['text'],
                    'content_type': content_type.value if hasattr(content_type, 'value') else str(content_type),
                    'difficulty': difficulty.value if hasattr(difficulty, 'value') else str(difficulty),
                    'keywords': keywords,
                    'formulas': formulas,
                    'is_complete': chunk_data.get('metadata', {}).get('is_complete', True),
                }
                
                # Create chunk record in DB
                chunk = Chunk(
                    chunk_id=chunk_id,
                    document_id=doc.id,
                    chunk_index=idx,
                    content=chunk_data['text'],
                    content_hash=hashlib.sha256(chunk_data['text'].encode()).hexdigest(),
                    page_number=chunk_data.get('metadata', {}).get('page_number'),
                    tokens=len(chunk_data['text'].split()),
                )
                db.add(chunk)
                
                # Prepare for vector store
                chunk_texts.append(chunk_data['text'])
                chunk_metadatas.append(enhanced_metadata)
                
                # Group by content type
                if content_type not in chunks_by_type:
                    chunks_by_type[content_type] = []
                chunks_by_type[content_type].append((chunk_data['text'], enhanced_metadata, idx))
                
                # Prepare for BM25
                bm25_texts.append(chunk_data['text'])
                bm25_metadatas.append(enhanced_metadata)
                bm25_ids.append(chunk_id)
            
            db.commit()
            
            # Add to BM25 index
            self.bm25_index.add_documents(bm25_texts, bm25_metadatas, bm25_ids)
            
            # Add to appropriate FAISS indexes based on content type
            for content_type, chunks_of_type in chunks_by_type.items():
                # Determine target index
                if isinstance(content_type, str):
                    try:
                        content_type = ContentType(content_type)
                    except:
                        content_type = ContentType.OTHER
                
                # Map content type to index type
                if content_type in [ContentType.THEORY, ContentType.DEFINITION, ContentType.THEOREM]:
                    index_type = IndexType.THEORY
                elif content_type in [ContentType.FORMULA, ContentType.DERIVATION]:
                    index_type = IndexType.FORMULA
                elif content_type == ContentType.EXERCISE:
                    index_type = IndexType.EXERCISE
                elif content_type in [ContentType.WORKED_EXAMPLE, ContentType.SOLUTION]:
                    index_type = IndexType.SOLUTION
                else:
                    index_type = IndexType.GENERAL
                
                # Extract texts, metadatas, and embedding indices for this type
                type_texts = [t for t, m, i in chunks_of_type]
                type_metadatas = [m for t, m, i in chunks_of_type]
                type_indices = [i for t, m, i in chunks_of_type]
                
                # Get embeddings for this subset
                type_embeddings = embeddings[type_indices]
                
                # Add to specialized index
                self.multi_index.add_documents(
                    type_texts,
                    type_embeddings,
                    type_metadatas,
                    index_type=index_type
                )
            
            app_logger.info(
                f"Stored {len(chunks)} chunks for {file_path.name} "
                f"across {len(chunks_by_type)} content types"
            )
            
        except Exception as e:
            db.rollback()
            app_logger.error(f"Error storing document: {e}")
            raise
        finally:
            db.close()
    
    async def ingest_documents(self, request: IngestionRequest) -> Dict[str, Any]:
        """
        Ingest documents using advanced hybrid architecture.
        
        Pipeline:
        1. Extract text from documents
        2. Smart chunking with structure awareness
        3. Content type classification
        4. Generate embeddings
        5. Store in multiple specialized indexes
        6. Store in BM25 sparse index
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
                f"Starting advanced ingestion of {total_docs} documents",
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
                    
                    # Smart chunking with structure awareness
                    chunks = self.smart_chunker.chunk_document(
                        processed_doc['content'],
                        metadata={
                            'file_path': str(file_path),
                            'file_name': file_path.name,
                            **processed_doc['metadata']
                        }
                    )
                    
                    if not chunks:
                        app_logger.warning(f"No chunks extracted from {file_path.name}")
                        skipped_count += 1
                        continue
                    
                    # Generate embeddings
                    chunk_texts = [chunk['text'] for chunk in chunks]
                    embeddings = self.embedder.embed_batch(chunk_texts)
                    
                    # Store in multiple indexes
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
                        self.multi_index.save_all_indexes()
                        self.bm25_index.save_index()
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
            self.multi_index.save_all_indexes()
            self.bm25_index.save_index()
            
            # Get index stats
            index_stats = self.multi_index.get_stats()
            bm25_stats = self.bm25_index.get_stats()
            
            result = {
                "session_id": session_id,
                "total_documents": total_docs,
                "processed": processed_count,
                "failed": failed_count,
                "skipped": skipped_count,
                "success": failed_count == 0,
                "index_stats": index_stats,
                "bm25_stats": bm25_stats,
            }
            
            self._log_ingestion(
                session_id,
                "complete",
                "Advanced ingestion completed",
                documents_total=total_docs,
                documents_processed=processed_count,
                documents_failed=failed_count,
            )
            
            app_logger.info(
                f"Advanced ingestion complete: {processed_count} processed, "
                f"{failed_count} failed, {skipped_count} skipped"
            )
            
            return result
        
        except Exception as e:
            app_logger.error(f"Advanced ingestion error: {e}", exc_info=True)
            self._log_ingestion(
                session_id,
                "error",
                f"Advanced ingestion failed: {e}",
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
                "multi_index_stats": self.multi_index.get_stats(),
                "bm25_stats": self.bm25_index.get_stats(),
            }
        finally:
            db.close()
