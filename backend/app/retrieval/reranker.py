"""
Cross-encoder reranker for refining search results.
Uses semantic similarity to rerank top-K candidates.
"""
from typing import List, Dict, Any, Tuple
from sentence_transformers import CrossEncoder
import numpy as np
from app.config import settings
from app.utils.logger import app_logger


class Reranker:
    """Cross-encoder model for reranking search results."""
    
    def __init__(
        self,
        model_name: str = None,
        device: str = None,
    ):
        """
        Initialize reranker.
        
        Args:
            model_name: HuggingFace cross-encoder model
            device: 'cpu', 'cuda', or 'mps'
        """
        self.model_name = model_name or "cross-encoder/ms-marco-MiniLM-L-6-v2"
        self.device = device or ("cuda" if settings.use_gpu else "cpu")
        
        try:
            app_logger.info(f"Loading cross-encoder model: {self.model_name}")
            self.model = CrossEncoder(self.model_name, device=self.device)
            app_logger.info("Cross-encoder loaded successfully")
        except Exception as e:
            app_logger.error(f"Error loading cross-encoder: {e}")
            self.model = None
    
    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
        return_scores: bool = True
    ) -> List[Dict[str, Any]]:
        """
        Rerank documents using cross-encoder.
        
        Args:
            query: Search query
            documents: List of document dicts with 'text' and 'metadata'
            top_k: Number of top results to return
            return_scores: Whether to add rerank score to results
        
        Returns:
            List of reranked documents
        """
        if not self.model:
            app_logger.warning("Reranker model not available, returning original order")
            return documents[:top_k]
        
        if not documents:
            return []
        
        # Prepare query-document pairs
        pairs = [[query, doc.get('text', '')] for doc in documents]
        
        try:
            # Get cross-encoder scores
            scores = self.model.predict(pairs)
            
            # Add scores to documents
            for doc, score in zip(documents, scores):
                if return_scores:
                    doc['rerank_score'] = float(score)
            
            # Sort by score
            ranked_docs = sorted(
                documents,
                key=lambda x: x.get('rerank_score', 0),
                reverse=True
            )
            
            app_logger.debug(f"Reranked {len(documents)} documents, returning top {top_k}")
            return ranked_docs[:top_k]
        
        except Exception as e:
            app_logger.error(f"Error during reranking: {e}")
            return documents[:top_k]
    
    def rerank_with_metadata_boost(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
        metadata_boosts: Dict[str, float] = None
    ) -> List[Dict[str, Any]]:
        """
        Rerank with metadata-based score boosting.
        
        Args:
            query: Search query
            documents: List of document dicts
            top_k: Number of results to return
            metadata_boosts: Dict of {metadata_key: boost_factor}
                Example: {'content_type': {'formula': 1.2, 'exercise': 1.1}}
        
        Returns:
            List of reranked documents
        """
        # First, get base rerank scores
        documents = self.rerank(query, documents, top_k=len(documents), return_scores=True)
        
        if not metadata_boosts:
            return documents[:top_k]
        
        # Apply metadata boosts
        for doc in documents:
            metadata = doc.get('metadata', {})
            boost = 1.0
            
            for meta_key, boost_values in metadata_boosts.items():
                if meta_key in metadata:
                    meta_value = metadata[meta_key]
                    if isinstance(boost_values, dict) and meta_value in boost_values:
                        boost *= boost_values[meta_value]
                    elif isinstance(boost_values, (int, float)):
                        boost *= boost_values
            
            # Apply boost to score
            if 'rerank_score' in doc:
                doc['boosted_score'] = doc['rerank_score'] * boost
            else:
                doc['boosted_score'] = boost
        
        # Re-sort by boosted score
        documents = sorted(
            documents,
            key=lambda x: x.get('boosted_score', 0),
            reverse=True
        )
        
        return documents[:top_k]
    
    def batch_rerank(
        self,
        queries: List[str],
        document_lists: List[List[Dict[str, Any]]],
        top_k: int = 5
    ) -> List[List[Dict[str, Any]]]:
        """
        Rerank multiple query-document sets.
        
        Args:
            queries: List of queries
            document_lists: List of document lists (one per query)
            top_k: Number of results per query
        
        Returns:
            List of reranked document lists
        """
        results = []
        for query, documents in zip(queries, document_lists):
            ranked = self.rerank(query, documents, top_k=top_k)
            results.append(ranked)
        return results
