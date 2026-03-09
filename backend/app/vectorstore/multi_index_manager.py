"""
Multiple specialized vector indexes for different content types.
"""
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import numpy as np
from app.models_advanced import ContentType, IndexType
from app.vectorstore.faiss_manager import FAISSVectorStore
from app.config import settings
from app.utils.logger import app_logger


class MultiIndexManager:
    """
    Manages multiple FAISS indexes for different content types.
    
    Indexes:
    - theory_index: Explanations, theory, definitions
    - formula_index: Formulas, equations, derivations
    - exercise_index: Problems, exercises, questions
    - solution_index: Worked examples, solutions
    - general_index: Mixed/unclassified content
    """
    
    def __init__(self, store_dir: Path = None):
        """Initialize multiple specialized indexes."""
        self.store_dir = Path(store_dir or settings.vector_store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        
        # Create specialized indexes
        self.indexes = {}
        
        index_configs = {
            IndexType.THEORY: "theory_index",
            IndexType.FORMULA: "formula_index",
            IndexType.EXERCISE: "exercise_index",
            IndexType.SOLUTION: "solution_index",
            IndexType.GENERAL: "general_index",
        }
        
        for index_type, index_name in index_configs.items():
            index_dir = self.store_dir / index_name
            index_dir.mkdir(exist_ok=True)
            
            self.indexes[index_type] = FAISSVectorStore(
                dimension=settings.embedding_dimension,
                store_dir=index_dir
            )
        
        app_logger.info(f"Initialized {len(self.indexes)} specialized indexes")
    
    def add_documents(
        self,
        texts: List[str],
        embeddings: np.ndarray,
        metadatas: List[Dict[str, Any]],
        index_type: IndexType = IndexType.GENERAL
    ):
        """
        Add documents to appropriate index.
        
        Args:
            texts: Document texts
            embeddings: Document embeddings (already computed)
            metadatas: Document metadata (should include content_type)
            index_type: Which index to use (or route based on metadata)
        """
        # Route to appropriate index based on content_type if available
        if index_type == IndexType.GENERAL:
            # Try to determine from metadata
            for metadata in metadatas:
                content_type = metadata.get('content_type')
                if content_type:
                    index_type = self._map_content_to_index(content_type)
                    break
        
        # Add to specified index
        if index_type in self.indexes:
            self.indexes[index_type].add_vectors(embeddings, metadatas)
            app_logger.info(f"Added {len(embeddings)} documents to {index_type.value} index")
        else:
            # Fallback to general index
            self.indexes[IndexType.GENERAL].add_vectors(embeddings, metadatas)
            app_logger.warning(f"Unknown index type {index_type}, added to general index")
    
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 10,
        index_types: List[IndexType] = None,
        filter_metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Search across specified indexes.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results to return per index
            index_types: Which indexes to search (None = all)
            filter_metadata: Optional metadata filters
        
        Returns:
            Combined and de-duplicated results
        """
        if index_types is None:
            index_types = list(self.indexes.keys())
        
        all_results = []
        
        for index_type in index_types:
            if index_type not in self.indexes:
                continue
            
            try:
                results = self.indexes[index_type].search(
                    query_embedding,
                    top_k=top_k,
                    filter_metadata=filter_metadata
                )
                
                # Add index type to results
                for result in results:
                    result['metadata']['index_type'] = index_type.value
                
                all_results.extend(results)
            
            except Exception as e:
                app_logger.error(f"Error searching {index_type.value} index: {e}")
        
        # Sort by score and de-duplicate
        all_results = self._deduplicate_results(all_results)
        all_results = sorted(all_results, key=lambda x: x['score'], reverse=True)
        
        return all_results[:top_k * len(index_types)]
    
    def search_specific_index(
        self,
        query_embedding: np.ndarray,
        index_type: IndexType,
        top_k: int = 10,
        filter_metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Search a specific index."""
        if index_type not in self.indexes:
            app_logger.warning(f"Index type {index_type} not found")
            return []
        
        return self.indexes[index_type].search(
            query_embedding,
            top_k=top_k,
            filter_metadata=filter_metadata
        )
    
    def _map_content_to_index(self, content_type: str) -> IndexType:
        """Map content type to index type."""
        content_mapping = {
            ContentType.THEORY: IndexType.THEORY,
            ContentType.DEFINITION: IndexType.THEORY,
            ContentType.THEOREM: IndexType.THEORY,
            ContentType.FORMULA: IndexType.FORMULA,
            ContentType.DERIVATION: IndexType.FORMULA,
            ContentType.EXERCISE: IndexType.EXERCISE,
            ContentType.WORKED_EXAMPLE: IndexType.SOLUTION,
            ContentType.SOLUTION: IndexType.SOLUTION,
            ContentType.DIAGRAM: IndexType.GENERAL,
            ContentType.TABLE: IndexType.GENERAL,
            ContentType.OTHER: IndexType.GENERAL,
        }
        
        # Handle string or ContentType enum
        if isinstance(content_type, str):
            try:
                content_type = ContentType(content_type)
            except ValueError:
                return IndexType.GENERAL
        
        return content_mapping.get(content_type, IndexType.GENERAL)
    
    def _deduplicate_results(
        self,
        results: List[Dict[str, Any]],
        similarity_threshold: float = 0.95
    ) -> List[Dict[str, Any]]:
        """
        Remove duplicate results based on text similarity.
        
        Keep the result with the higher score.
        """
        if len(results) <= 1:
            return results
        
        # Simple deduplication based on exact text match
        seen_texts = {}
        deduped = []
        
        for result in results:
            text = result.get('text', '')
            
            if text not in seen_texts:
                seen_texts[text] = result
                deduped.append(result)
            else:
                # Keep the one with higher score
                if result.get('score', 0) > seen_texts[text].get('score', 0):
                    seen_texts[text] = result
                    # Replace in deduped list
                    deduped = [r for r in deduped if r.get('text') != text]
                    deduped.append(result)
        
        return deduped
    
    def get_stats(self) -> Dict[str, Dict[str, Any]]:
        """Get statistics for all indexes."""
        stats = {}
        for index_type, index in self.indexes.items():
            index_stats = index.get_stats()
            stats[index_type.value] = {
                'document_count': index_stats['total_vectors'],
                'dimension': index_stats['dimension'],
            }
        return stats
    
    def save_all_indexes(self):
        """Save all indexes to disk."""
        for index_type, index in self.indexes.items():
            try:
                index.save_index()
                app_logger.info(f"Saved {index_type.value} index")
            except Exception as e:
                app_logger.error(f"Error saving {index_type.value} index: {e}")
    
    def load_all_indexes(self):
        """Load all indexes from disk."""
        for index_type, index in self.indexes.items():
            try:
                index.load_index()
                app_logger.info(f"Loaded {index_type.value} index")
            except Exception as e:
                app_logger.error(f"Error loading {index_type.value} index: {e}")
