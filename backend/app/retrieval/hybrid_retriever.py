"""
Hybrid retrieval system combining dense (FAISS) and sparse (BM25) search.
"""
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
from app.vectorstore.multi_index_manager import MultiIndexManager
from app.vectorstore.bm25_index import BM25Index
from app.retrieval.reranker import Reranker
from app.retrieval.query_router import QueryRouter
from app.models_advanced import QueryIntent, IndexType, HybridSearchRequest
from app.ingestion.embedder import SentenceTransformerEmbedder
from app.config import settings
from app.utils.logger import app_logger


class HybridRetriever:
    """
    Hybrid retrieval combining:
    1. Dense semantic search (FAISS)
    2. Sparse keyword search (BM25)
    3. Query routing
    4. Cross-encoder reranking
    """
    
    def __init__(
        self,
        multi_index_manager: MultiIndexManager = None,
        bm25_index: BM25Index = None,
        reranker: Reranker = None,
        query_router: QueryRouter = None,
        embedder: SentenceTransformerEmbedder = None,
    ):
        """Initialize hybrid retriever."""
        self.multi_index = multi_index_manager or MultiIndexManager()
        self.bm25 = bm25_index or BM25Index()
        self.reranker = reranker or Reranker()
        self.query_router = query_router or QueryRouter()
        self.embedder = embedder or SentenceTransformerEmbedder()
        
        app_logger.info("Initialized HybridRetriever")
    
    def search(
        self,
        query: str,
        query_embedding: np.ndarray,
        top_k: int = 5,
        dense_weight: float = 0.5,
        sparse_weight: float = 0.5,
        use_reranking: bool = True,
        filter_metadata: Dict[str, Any] = None,
        specific_indexes: List[IndexType] = None,
    ) -> List[Dict[str, Any]]:
        """
        Hybrid search with automatic query routing.

        Args:
            query: Query text
            query_embedding: Query vector for dense search
            top_k: Number of final results
            dense_weight: Weight for dense scores (0-1)
            sparse_weight: Weight for sparse scores (0-1)
            use_reranking: Whether to rerank results
            filter_metadata: Optional metadata filters
            specific_indexes: Specific indexes to search (None = search all indexes by default)

        Returns:
            List of ranked documents with metadata
        """

        # Step 1: Default to all indexes if none specified
        if specific_indexes is None:
            # Search all available indexes by default
            specific_indexes = list(self.multi_index.indexes.keys())

        # Adjust retrieval count for reranking
        retrieval_k = top_k * 4 if use_reranking else top_k
        
        # Step 2: Dense search (FAISS)
        dense_results = self.multi_index.search(
            query_embedding,
            top_k=retrieval_k,
            index_types=specific_indexes,
            filter_metadata=filter_metadata
        )
        
        # Normalize dense scores to [0, 1]
        dense_results = self._normalize_scores(dense_results, 'score')
        
        # Step 3: Sparse search (BM25)
        sparse_results_raw = self.bm25.search(
            query,
            top_k=retrieval_k,
            filter_metadata=filter_metadata
        )
        
        # Convert BM25 results to standard format
        sparse_results = []
        for doc_id, score, metadata in sparse_results_raw:
            doc = self.bm25.documents.get(doc_id, {})
            sparse_results.append({
                'text': doc.get('text', ''),
                'metadata': metadata,
                'score': score,
                'doc_id': doc_id
            })
        
        # Normalize sparse scores
        sparse_results = self._normalize_scores(sparse_results, 'score')
        
        # Step 4: Hybrid fusion
        combined_results = self._fuse_results(
            dense_results,
            sparse_results,
            dense_weight=dense_weight,
            sparse_weight=sparse_weight
        )
        
        app_logger.debug(
            f"Hybrid search: {len(dense_results)} dense + {len(sparse_results)} sparse "
            f"= {len(combined_results)} combined"
        )
        
        # Step 5: Reranking
        if use_reranking and combined_results:
            combined_results = self.reranker.rerank(
                query,
                combined_results,
                top_k=top_k
            )
            app_logger.debug(f"Reranked to top {len(combined_results)} results")
        else:
            combined_results = combined_results[:top_k]
        
        return combined_results
    
    def search_with_request(
        self,
        request: HybridSearchRequest,
        query_embedding: np.ndarray
    ) -> List[Dict[str, Any]]:
        """Search using a HybridSearchRequest object."""
        return self.search(
            query=request.query,
            query_embedding=query_embedding,
            top_k=request.top_k,
            dense_weight=request.dense_weight,
            sparse_weight=request.sparse_weight,
            use_reranking=request.use_reranking,
            filter_metadata=request.filter_metadata,
            specific_indexes=request.specific_indexes,
        )
    
    def _normalize_scores(
        self,
        results: List[Dict[str, Any]],
        score_key: str = 'score'
    ) -> List[Dict[str, Any]]:
        """Normalize scores to [0, 1] range using min-max normalization."""
        if not results:
            return results
        
        scores = [r.get(score_key, 0) for r in results]
        
        if not scores:
            return results
        
        min_score = min(scores)
        max_score = max(scores)
        
        if max_score == min_score:
            # All scores are the same
            for r in results:
                r[f'normalized_{score_key}'] = 1.0
        else:
            for r in results:
                score = r.get(score_key, 0)
                r[f'normalized_{score_key}'] = (score - min_score) / (max_score - min_score)
        
        return results
    
    def _fuse_results(
        self,
        dense_results: List[Dict[str, Any]],
        sparse_results: List[Dict[str, Any]],
        dense_weight: float = 0.5,
        sparse_weight: float = 0.5
    ) -> List[Dict[str, Any]]:
        """
        Fuse dense and sparse results using weighted score combination.
        
        Uses doc_id or text for matching.
        """
        # Build lookup maps
        dense_map = {}
        for r in dense_results:
            key = r.get('doc_id') or r.get('text', '')[:100]  # Use text prefix as fallback
            if key:
                dense_map[key] = r
        
        sparse_map = {}
        for r in sparse_results:
            key = r.get('doc_id') or r.get('text', '')[:100]
            if key:
                sparse_map[key] = r
        
        # Combine scores
        all_keys = set(dense_map.keys()) | set(sparse_map.keys())
        fused_results = []
        
        for key in all_keys:
            dense_r = dense_map.get(key)
            sparse_r = sparse_map.get(key)
            
            # Calculate weighted score
            dense_score = dense_r.get('normalized_score', 0) if dense_r else 0
            sparse_score = sparse_r.get('normalized_score', 0) if sparse_r else 0
            
            hybrid_score = (dense_weight * dense_score) + (sparse_weight * sparse_score)
            
            # Use the document with more information (prefer dense)
            base_doc = dense_r if dense_r else sparse_r
            
            fused_doc = {
                **base_doc,
                'hybrid_score': hybrid_score,
                'dense_score': dense_score,
                'sparse_score': sparse_score,
            }
            
            fused_results.append(fused_doc)
        
        # Sort by hybrid score
        fused_results = sorted(
            fused_results,
            key=lambda x: x.get('hybrid_score', 0),
            reverse=True
        )
        
        return fused_results
    
    def get_retrieval_stats(self) -> Dict[str, Any]:
        """Get statistics about the retrieval system."""
        return {
            'multi_index_stats': self.multi_index.get_stats(),
            'bm25_stats': self.bm25.get_stats(),
            'reranker_model': self.reranker.model_name if self.reranker.model else None,
        }
    
    def get_context_for_query(
        self,
        query: str,
        top_k: int = 5,
        max_tokens: int = 4000,
    ) -> str:
        """
        Retrieve and format context for a query using hybrid search.
        
        Args:
            query: Natural language query
            top_k: Number of chunks to retrieve
            max_tokens: Approximate max tokens to include
        
        Returns:
            Formatted context string
        """
        try:
            # Generate query embedding
            query_embedding = self.embedder.embed_text(query)
            
            # Perform hybrid search
            results = self.search(
                query=query,
                query_embedding=query_embedding,
                top_k=top_k,
                use_reranking=True,
                specific_indexes=specific_indexes,
            )
            
            if not results:
                return "No relevant context found in the knowledge base."
            
            context_parts = []
            total_length = 0
            
            for result in results:
                text = result.get('text', '')
                metadata = result.get('metadata', {})
                score = result.get('hybrid_score', result.get('score', 0))
                
                # Format chunk with source information
                chunk_text = f"[Source: {metadata.get('file_name', metadata.get('file_path', 'unknown'))}"
                if 'page_number' in metadata:
                    chunk_text += f", Page {metadata['page_number']}"
                chunk_text += f" | Relevance: {score:.2f}]\n{text}\n"
                
                # Rough token estimation (1 token ≈ 4 characters)
                estimated_tokens = len(chunk_text) // 4
                
                if total_length + estimated_tokens > max_tokens:
                    break
                
                context_parts.append(chunk_text)
                total_length += estimated_tokens
            
            if not context_parts:
                return "No relevant context found within token limit."
            
            context = "\n---\n".join(context_parts)
            app_logger.info(f"Generated context from {len(context_parts)} chunks (~{total_length} tokens)")
            
            return context
        
        except Exception as e:
            app_logger.error(f"Error getting context for query: {e}")
            return f"Error retrieving context: {str(e)}"
