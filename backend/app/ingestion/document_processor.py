"""
Central document processor that routes to appropriate extractors.
"""
from pathlib import Path
from typing import Dict, Any, List, Optional
import hashlib
from app.models import DocumentType
from app.ingestion.extractors import (
    PDFExtractor,
    HTMLExtractor,
    ImageExtractor,
    TextExtractor,
    MarkdownExtractor,
    DocxExtractor,
)
from app.utils.logger import app_logger


class DocumentProcessor:
    """Process documents and extract content."""
    
    def __init__(self, enable_ocr: bool = True, ocr_language: str = "eng"):
        self.enable_ocr = enable_ocr
        self.ocr_language = ocr_language
        
        # Initialize extractors
        self.pdf_extractor = PDFExtractor(enable_ocr, ocr_language)
        self.html_extractor = HTMLExtractor()
        self.image_extractor = ImageExtractor(enable_ocr, ocr_language)
        self.text_extractor = TextExtractor()
        self.markdown_extractor = MarkdownExtractor()
        self.docx_extractor = DocxExtractor()
        
        app_logger.info("Initialized DocumentProcessor")
    
    def detect_document_type(self, file_path: Path) -> DocumentType:
        """Detect document type from file extension."""
        suffix = file_path.suffix.lower()
        
        type_map = {
            '.pdf': DocumentType.PDF,
            '.html': DocumentType.HTML,
            '.htm': DocumentType.HTML,
            '.md': DocumentType.MARKDOWN,
            '.markdown': DocumentType.MARKDOWN,
            '.docx': DocumentType.DOCX,
            '.txt': DocumentType.TEXT,
            '.jpg': DocumentType.IMAGE,
            '.jpeg': DocumentType.IMAGE,
            '.png': DocumentType.IMAGE,
            '.gif': DocumentType.IMAGE,
            '.bmp': DocumentType.IMAGE,
            '.tiff': DocumentType.IMAGE,
        }
        
        return type_map.get(suffix, DocumentType.UNKNOWN)
    
    def compute_file_hash(self, file_path: Path) -> str:
        """Compute SHA256 hash of file for change detection."""
        sha256_hash = hashlib.sha256()
        with open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                sha256_hash.update(byte_block)
        return sha256_hash.hexdigest()
    
    def process_document(self, file_path: Path) -> Dict[str, Any]:
        """
        Process a document and extract all content.
        
        Returns:
            Dict with 'content', 'metadata', 'document_type', 'file_hash'
        """
        doc_type = self.detect_document_type(file_path)
        
        if doc_type == DocumentType.UNKNOWN:
            raise ValueError(f"Unknown document type: {file_path.suffix}")
        
        app_logger.info(f"Processing {doc_type.value}: {file_path.name}")
        
        try:
            file_hash = self.compute_file_hash(file_path)
            
            # Extract content based on type
            if doc_type == DocumentType.PDF:
                extracted = self.pdf_extractor.extract(file_path)
                # Combine page texts
                content = "\n\n".join([
                    f"[Page {page['page_number']}]\n{page['text']}"
                    for page in extracted['pages']
                ])
                # Add image text if available
                image_texts = [img['text'] for img in extracted.get('images', []) if img.get('text')]
                if image_texts:
                    content += "\n\n[Extracted from Images]\n" + "\n".join(image_texts)
                
                metadata = extracted['metadata']
                metadata['total_pages'] = len(extracted['pages'])
                
            elif doc_type == DocumentType.HTML:
                extracted = self.html_extractor.extract(file_path)
                content = extracted['text']
                metadata = extracted['metadata']
                
            elif doc_type == DocumentType.IMAGE:
                extracted = self.image_extractor.extract(file_path)
                content = extracted['text']
                metadata = extracted['metadata']
                
            elif doc_type == DocumentType.TEXT:
                extracted = self.text_extractor.extract(file_path)
                content = extracted['text']
                metadata = extracted['metadata']
                
            elif doc_type == DocumentType.MARKDOWN:
                extracted = self.markdown_extractor.extract(file_path)
                content = extracted['text']
                metadata = extracted['metadata']
                
            elif doc_type == DocumentType.DOCX:
                extracted = self.docx_extractor.extract(file_path)
                content = extracted['text']
                metadata = extracted['metadata']
            
            else:
                raise ValueError(f"Unsupported document type: {doc_type}")
            
            # Add common metadata
            metadata['file_path'] = str(file_path)
            metadata['file_name'] = file_path.name
            metadata['file_size'] = file_path.stat().st_size
            
            return {
                'content': content,
                'metadata': metadata,
                'document_type': doc_type,
                'file_hash': file_hash,
            }
        
        except Exception as e:
            app_logger.error(f"Error processing {file_path}: {e}")
            raise
    
    def process_batch(self, file_paths: List[Path]) -> List[Dict[str, Any]]:
        """Process multiple documents."""
        results = []
        
        for file_path in file_paths:
            try:
                result = self.process_document(file_path)
                results.append(result)
            except Exception as e:
                app_logger.error(f"Failed to process {file_path}: {e}")
                results.append({
                    'error': str(e),
                    'file_path': str(file_path),
                })
        
        return results
