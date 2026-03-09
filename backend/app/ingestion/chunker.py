"""
Text chunking strategies with overlap support.
"""
from typing import List, Dict, Any
from langchain_text_splitters import RecursiveCharacterTextSplitter
from app.config import settings
from app.utils.logger import app_logger


class TextChunker:
    """Chunk text documents with configurable strategies."""
    
    def __init__(
        self,
        chunk_size: int = None,
        chunk_overlap: int = None,
        separators: List[str] = None,
    ):
        self.chunk_size = chunk_size or settings.chunk_size
        self.chunk_overlap = chunk_overlap or settings.chunk_overlap
        
        # Default separators prioritize semantic boundaries
        self.separators = separators or [
            "\n\n",  # Paragraph breaks
            "\n",    # Line breaks
            ". ",    # Sentence breaks
            "? ",
            "! ",
            "; ",
            ": ",
            ", ",
            " ",     # Word breaks
            "",      # Character breaks (last resort)
        ]
        
        self.splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.chunk_size,
            chunk_overlap=self.chunk_overlap,
            length_function=len,
            separators=self.separators,
            is_separator_regex=False,
        )
        
        app_logger.info(
            f"Initialized TextChunker: chunk_size={self.chunk_size}, "
            f"overlap={self.chunk_overlap}"
        )
    
    def chunk_text(
        self,
        text: str,
        metadata: Dict[str, Any] = None,
    ) -> List[Dict[str, Any]]:
        """
        Chunk text into smaller pieces with metadata.
        
        Args:
            text: Text to chunk
            metadata: Optional metadata to attach to each chunk
        
        Returns:
            List of dicts with 'text' and 'metadata'
        """
        if not text or not text.strip():
            return []
        
        try:
            chunks = self.splitter.split_text(text)
            
            result = []
            for idx, chunk in enumerate(chunks):
                chunk_metadata = {
                    "chunk_index": idx,
                    "total_chunks": len(chunks),
                    "chunk_size": len(chunk),
                }
                
                # Merge with provided metadata
                if metadata:
                    chunk_metadata.update(metadata)
                
                result.append({
                    "text": chunk,
                    "metadata": chunk_metadata,
                })
            
            app_logger.debug(f"Split text into {len(result)} chunks")
            return result
        
        except Exception as e:
            app_logger.error(f"Error chunking text: {e}")
            raise
    
    def chunk_documents(
        self,
        documents: List[Dict[str, Any]],
    ) -> List[Dict[str, Any]]:
        """
        Chunk multiple documents.
        
        Args:
            documents: List of dicts with 'text' and optional 'metadata'
        
        Returns:
            List of chunks with merged metadata
        """
        all_chunks = []
        
        for doc in documents:
            text = doc.get("text", "")
            doc_metadata = doc.get("metadata", {})
            
            chunks = self.chunk_text(text, doc_metadata)
            all_chunks.extend(chunks)
        
        app_logger.info(f"Chunked {len(documents)} documents into {len(all_chunks)} chunks")
        return all_chunks


class SemanticChunker:
    """
    Advanced semantic chunking (optional enhancement).
    Groups sentences by semantic similarity.
    """
    
    def __init__(self, embedder=None, similarity_threshold: float = 0.5):
        self.embedder = embedder
        self.similarity_threshold = similarity_threshold
        # TODO: Implement semantic chunking using sentence embeddings
        app_logger.warning("SemanticChunker not yet fully implemented")
    
    def chunk_text(self, text: str, metadata: Dict[str, Any] = None) -> List[Dict[str, Any]]:
        """Semantic chunking - to be implemented."""
        # Fallback to recursive character splitting
        chunker = TextChunker()
        return chunker.chunk_text(text, metadata)
