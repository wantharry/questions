"""
Multiple specialized vector indexes for different content types.
"""
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path
import numpy as np
import json
from datetime import datetime
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
        
        # Path to custom indexes config
        self.custom_indexes_file = self.store_dir.parent / "custom_indexes.json"
        
        # Create specialized indexes
        self.indexes = {}
        
        # Default index configs (predefined)
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
        
        # Load custom indexes from config file
        self._load_custom_indexes()
        
        app_logger.info(f"Initialized {len(self.indexes)} specialized indexes")
    
    def _load_custom_indexes(self):
        """Load custom indexes from JSON config file."""
        if not self.custom_indexes_file.exists():
            app_logger.info("No custom indexes config found")
            return
        
        try:
            with open(self.custom_indexes_file, 'r') as f:
                custom_configs = json.load(f)
            
            for index_name, config in custom_configs.items():
                # Skip if already exists (predefined indexes)
                index_type = IndexType.from_string(index_name)
                if index_type in self.indexes:
                    app_logger.info(f"Index {index_name} already loaded (predefined)")
                    continue
                
                # Create custom index
                index_dir = self.store_dir / f"{index_name}_index"
                index_dir.mkdir(exist_ok=True)
                
                # Get embedding dimension from config or use default
                dimension = config.get('embedding_dimension', settings.embedding_dimension)
                
                self.indexes[index_type] = FAISSVectorStore(
                    dimension=dimension,
                    store_dir=index_dir
                )
                
                app_logger.info(f"Loaded custom index: {index_name}")
        
        except Exception as e:
            app_logger.error(f"Error loading custom indexes: {e}")
    
    def create_custom_index(
        self,
        index_name: str,
        description: str = "",
        embedding_dimension: int = None
    ) -> Dict[str, Any]:
        """
        Create a new custom index.
        
        Args:
            index_name: Name for the custom index
            description: Optional description
            embedding_dimension: Embedding dimension (default: from settings)
        
        Returns:
            Dictionary with index info
        """
        # Validate index name
        if not index_name or not index_name.replace('_', '').replace('-', '').isalnum():
            raise ValueError("Index name must be alphanumeric (underscores and hyphens allowed)")
        
        index_name = index_name.lower()
        index_type = IndexType.from_string(index_name)
        
        # Check if already exists
        if index_type in self.indexes:
            raise ValueError(f"Index {index_name} already exists")
        
        # Create index directory
        index_dir = self.store_dir / f"{index_name}_index"
        index_dir.mkdir(exist_ok=True)
        
        # Use provided dimension or default
        dimension = embedding_dimension or settings.embedding_dimension
        
        # Create FAISS index
        self.indexes[index_type] = FAISSVectorStore(
            dimension=dimension,
            store_dir=index_dir
        )
        
        # Save to custom indexes config
        config = {
            "index_name": index_name,
            "description": description,
            "embedding_dimension": dimension,
            "created_at": datetime.now().isoformat(),
            "last_updated": datetime.now().isoformat(),
            "document_count": 0,
            "chunk_count": 0
        }
        
        self._save_custom_index_config(index_name, config)
        
        app_logger.info(f"Created custom index: {index_name}")
        
        return config
    
    def delete_custom_index(self, index_name: str) -> bool:
        """
        Delete a custom index (predefined indexes cannot be deleted).
        
        Args:
            index_name: Name of the index to delete
        
        Returns:
            True if deleted, False if not found or is predefined
        """
        index_name = index_name.lower()
        index_type = IndexType.from_string(index_name)
        
        # Prevent deletion of predefined indexes
        predefined = [IndexType.THEORY, IndexType.FORMULA, IndexType.EXERCISE, 
                     IndexType.SOLUTION, IndexType.GENERAL]
        
        if index_type in predefined:
            raise ValueError(f"Cannot delete predefined index: {index_name}")
        
        if index_type not in self.indexes:
            return False
        
        # Remove from memory
        del self.indexes[index_type]
        
        # Remove from config file
        self._remove_custom_index_config(index_name)
        
        # Optionally delete files (commented out for safety)
        # index_dir = self.store_dir / f"{index_name}_index"
        # if index_dir.exists():
        #     import shutil
        #     shutil.rmtree(index_dir)
        
        app_logger.info(f"Deleted custom index: {index_name}")
        
        return True
    
    def list_all_indexes(self) -> Dict[str, Dict[str, Any]]:
        """List all indexes (predefined and custom) with their stats."""
        all_indexes = {}
        
        for index_type, index in self.indexes.items():
            stats = index.get_stats()
            all_indexes[index_type.value] = {
                'name': index_type.value,
                'document_count': stats['total_vectors'],
                'dimension': stats['dimension'],
                'is_custom': self._is_custom_index(index_type)
            }
        
        return all_indexes
    
    def _is_custom_index(self, index_type: IndexType) -> bool:
        """Check if an index is custom (not predefined)."""
        predefined = [IndexType.THEORY, IndexType.FORMULA, IndexType.EXERCISE, 
                     IndexType.SOLUTION, IndexType.GENERAL]
        return index_type not in predefined
    
    def _save_custom_index_config(self, index_name: str, config: Dict[str, Any]):
        """Save custom index configuration to JSON file."""
        # Load existing configs
        configs = {}
        if self.custom_indexes_file.exists():
            try:
                with open(self.custom_indexes_file, 'r') as f:
                    configs = json.load(f)
            except:
                pass
        
        # Update with new config
        configs[index_name] = config
        
        # Save back
        with open(self.custom_indexes_file, 'w') as f:
            json.dump(configs, f, indent=2)
    
    def _remove_custom_index_config(self, index_name: str):
        """Remove custom index from configuration file."""
        if not self.custom_indexes_file.exists():
            return
        
        try:
            with open(self.custom_indexes_file, 'r') as f:
                configs = json.load(f)
            
            if index_name in configs:
                del configs[index_name]
            
            with open(self.custom_indexes_file, 'w') as f:
                json.dump(configs, f, indent=2)
        
        except Exception as e:
            app_logger.error(f"Error removing index config: {e}")
    
    def add_documents(
        self,
        texts: List[str],
        embeddings: np.ndarray,
        metadatas: List[Dict[str, Any]],
        index_type: Optional[Any] = None
    ):
        """
        Add documents to appropriate index.
        
        Args:
            texts: Document texts
            embeddings: Document embeddings (already computed)
            metadatas: Document metadata (should include content_type)
            index_type: Which index to use (IndexType, string, or None for auto-routing)
        """
        # Convert string to IndexType if needed
        if isinstance(index_type, str):
            index_type = IndexType.from_string(index_type)
        
        # Route to appropriate index based on content_type if not specified
        if index_type is None or index_type == IndexType.GENERAL:
            # Try to determine from metadata
            for metadata in metadatas:
                content_type = metadata.get('content_type')
                if content_type:
                    index_type = self._map_content_to_index(content_type)
                    break
            
            # Default to GENERAL if still not determined
            if index_type is None:
                index_type = IndexType.GENERAL
        
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
        index_types: List[Any] = None,
        filter_metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Search across specified indexes.
        
        Args:
            query_embedding: Query vector
            top_k: Number of results to return per index
            index_types: Which indexes to search (None = all, can be IndexType or string)
            filter_metadata: Optional metadata filters
        
        Returns:
            Combined and de-duplicated results
        """
        if index_types is None:
            index_types = list(self.indexes.keys())
        else:
            # Convert strings to IndexType
            index_types = [
                IndexType.from_string(it) if isinstance(it, str) else it
                for it in index_types
            ]
        
        all_results = []
        
        for index_type in index_types:
            if index_type not in self.indexes:
                continue
            
            try:
                results = self.indexes[index_type].search(
                    query_embedding,
                    top_k=top_k
                )
                
                # Convert tuples to dict format and add index type
                for idx, score, metadata in results:
                    metadata['index_type'] = index_type.value
                    all_results.append({
                        'id': idx,
                        'score': score,
                        'metadata': metadata,
                        'text': metadata.get('text', '')
                    })
            
            except Exception as e:
                app_logger.error(f"Error searching {index_type.value} index: {e}")
        
        # Sort by score and de-duplicate
        all_results = self._deduplicate_results(all_results)
        all_results = sorted(all_results, key=lambda x: x['score'], reverse=True)
        
        return all_results[:top_k * len(index_types)]
    
    def search_specific_index(
        self,
        query_embedding: np.ndarray,
        index_type: Any,
        top_k: int = 10,
        filter_metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """Search a specific index."""
        # Convert string to IndexType if needed
        if isinstance(index_type, str):
            index_type = IndexType.from_string(index_type)
        
        if index_type not in self.indexes:
            app_logger.warning(f"Index type {index_type} not found")
            return []
        
        return self.indexes[index_type].search(
            query_embedding,
            top_k=top_k
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
            ContentType.UNKNOWN: IndexType.GENERAL,
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
