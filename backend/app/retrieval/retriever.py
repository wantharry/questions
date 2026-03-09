"""
Retrieval system for semantic search over the knowledge base.
"""
from typing import List, Dict, Any, Optional
from app.models import QueryRequest, RetrievedChunk
from app.ingestion.embedder import SentenceTransformerEmbedder
from app.vectorstore.faiss_manager import FAISSVectorStore
from app.config import settings
from app.utils.logger import app_logger


class Retriever:
    """Semantic search and retrieval system."""
    
    def __init__(self):
        self.embedder = SentenceTransformerEmbedder()
        self.vector_store = FAISSVectorStore(dimension=self.embedder.dimension)
        app_logger.info("Initialized Retriever")
    
    def retrieve(
        self,
        query: str,
        top_k: int = 5,
        subject_filter: Optional[str] = None,
    ) -> List[RetrievedChunk]:
        """
        Retrieve relevant chunks for a query.
        
        Args:
            query: Natural language query
            top_k: Number of results to return
            subject_filter: Optional subject filter (not yet implemented)
        
        Returns:
            List of RetrievedChunk objects
        """
        if not query or not query.strip():
            return []
        
        try:
            # Generate query embedding
            query_embedding = self.embedder.embed_text(query)
            
            # Search vector store
            results = self.vector_store.search(query_embedding, top_k=top_k)
            
            # Format results
            retrieved_chunks = []
            for idx, (vector_id, similarity, metadata) in enumerate(results):
                chunk = RetrievedChunk(
                    content=metadata.get('content', ''),
                    source_file=metadata.get('file_name', metadata.get('file_path', 'unknown')),
                    page_number=metadata.get('page_number'),
                    chunk_id=metadata.get('chunk_id', f'chunk_{vector_id}'),
                    similarity_score=similarity,
                    metadata=metadata,
                )
                retrieved_chunks.append(chunk)
            
            app_logger.info(f"Retrieved {len(retrieved_chunks)} chunks for query: {query[:50]}...")
            return retrieved_chunks
        
        except Exception as e:
            app_logger.error(f"Retrieval error: {e}")
            raise
    
    def get_context_for_query(
        self,
        query: str,
        top_k: int = 5,
        max_tokens: int = 4000,
    ) -> str:
        """
        Retrieve and format context for a query.
        
        Args:
            query: Natural language query
            top_k: Number of chunks to retrieve
            max_tokens: Approximate max tokens to include
        
        Returns:
            Formatted context string
        """
        chunks = self.retrieve(query, top_k=top_k)
        
        if not chunks:
            return "No relevant context found in the knowledge base."
        
        context_parts = []
        total_length = 0
        
        for chunk in chunks:
            chunk_text = f"[Source: {chunk.source_file}"
            if chunk.page_number:
                chunk_text += f", Page {chunk.page_number}"
            chunk_text += f"]\n{chunk.content}\n"
            
            # Rough token estimation (1 token ≈ 4 characters)
            estimated_tokens = len(chunk_text) // 4
            
            if total_length + estimated_tokens > max_tokens:
                break
            
            context_parts.append(chunk_text)
            total_length += estimated_tokens
        
        return "\n---\n".join(context_parts)
