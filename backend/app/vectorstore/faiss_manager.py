"""
FAISS vector store manager with persistent storage.
"""
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import numpy as np
import faiss
import pickle
from app.config import settings
from app.utils.logger import app_logger


class FAISSVectorStore:
    """Manage FAISS vector store with metadata."""
    
    def __init__(
        self,
        dimension: int = None,
        index_type: str = None,
        store_dir: Path = None,
    ):
        self.dimension = dimension or settings.embedding_dimension
        self.index_type = index_type or settings.faiss_index_type
        self.store_dir = Path(store_dir or settings.vector_store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        
        self.index_path = self.store_dir / "faiss_index.bin"
        self.metadata_path = self.store_dir / "metadata.pkl"
        
        self.index: Optional[faiss.Index] = None
        self.id_to_metadata: Dict[int, Dict[str, Any]] = {}
        self.chunk_id_to_idx: Dict[str, int] = {}
        self.next_id = 0
        
        self._load_or_create_index()
        
        app_logger.info(
            f"Initialized FAISS store: dimension={self.dimension}, "
            f"index_type={self.index_type}, vectors={self.next_id}"
        )
    
    def _load_or_create_index(self):
        """Load existing index or create new one."""
        if self.index_path.exists() and self.metadata_path.exists():
            try:
                self._load_index()
                app_logger.info(f"Loaded existing FAISS index with {self.next_id} vectors")
                return
            except Exception as e:
                app_logger.warning(f"Failed to load index: {e}. Creating new index.")
        
        self._create_index()
    
    def _create_index(self):
        """Create a new FAISS index."""
        if self.index_type == "IndexFlatL2":
            self.index = faiss.IndexFlatL2(self.dimension)
        elif self.index_type == "IndexFlatIP":
            self.index = faiss.IndexFlatIP(self.dimension)  # Inner product (cosine similarity)
        elif self.index_type == "IndexIVFFlat":
            # For large datasets, use IVF index
            quantizer = faiss.IndexFlatL2(self.dimension)
            self.index = faiss.IndexIVFFlat(quantizer, self.dimension, 100)
            self.index.nprobe = 10
        elif self.index_type == "IndexHNSWFlat":
            # HNSW for fast approximate search
            self.index = faiss.IndexHNSWFlat(self.dimension, 32)
        else:
            app_logger.warning(f"Unknown index type {self.index_type}, using IndexFlatL2")
            self.index = faiss.IndexFlatL2(self.dimension)
        
        self.id_to_metadata = {}
        self.chunk_id_to_idx = {}
        self.next_id = 0
        
        app_logger.info(f"Created new FAISS index: {self.index_type}")
    
    def _load_index(self):
        """Load index and metadata from disk."""
        self.index = faiss.read_index(str(self.index_path))
        
        with open(self.metadata_path, 'rb') as f:
            data = pickle.load(f)
            self.id_to_metadata = data['id_to_metadata']
            self.chunk_id_to_idx = data['chunk_id_to_idx']
            self.next_id = data['next_id']
    
    def save_index(self):
        """Save index and metadata to disk."""
        try:
            # Save FAISS index
            faiss.write_index(self.index, str(self.index_path))
            
            # Save metadata
            data = {
                'id_to_metadata': self.id_to_metadata,
                'chunk_id_to_idx': self.chunk_id_to_idx,
                'next_id': self.next_id,
            }
            with open(self.metadata_path, 'wb') as f:
                pickle.dump(data, f)
            
            app_logger.info(f"Saved FAISS index with {self.next_id} vectors")
        except Exception as e:
            app_logger.error(f"Error saving index: {e}")
            raise
    
    def add_vectors(
        self,
        embeddings: np.ndarray,
        metadatas: List[Dict[str, Any]],
    ) -> List[int]:
        """
        Add vectors with metadata to the index.
        
        Args:
            embeddings: Array of shape (n, dimension)
            metadatas: List of metadata dicts (length n)
        
        Returns:
            List of IDs assigned to the vectors
        """
        if len(embeddings) != len(metadatas):
            raise ValueError("Embeddings and metadatas must have same length")
        
        if len(embeddings) == 0:
            return []
        
        # Ensure correct shape and dtype
        embeddings = embeddings.astype(np.float32)
        if len(embeddings.shape) == 1:
            embeddings = embeddings.reshape(1, -1)
        
        # Train index if needed (for IVF indices)
        if hasattr(self.index, 'is_trained') and not self.index.is_trained:
            if len(embeddings) >= 100:
                self.index.train(embeddings)
            else:
                app_logger.warning("Not enough vectors to train IVF index")
        
        # Add to index
        self.index.add(embeddings)
        
        # Store metadata
        ids = []
        for metadata in metadatas:
            idx = self.next_id
            self.id_to_metadata[idx] = metadata
            
            chunk_id = metadata.get('chunk_id')
            if chunk_id:
                self.chunk_id_to_idx[chunk_id] = idx
            
            ids.append(idx)
            self.next_id += 1
        
        app_logger.debug(f"Added {len(embeddings)} vectors to index")
        return ids
    
    def search(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5,
    ) -> List[Tuple[int, float, Dict[str, Any]]]:
        """
        Search for similar vectors.
        
        Args:
            query_embedding: Query vector of shape (dimension,) or (1, dimension)
            top_k: Number of results to return
        
        Returns:
            List of (id, similarity_score, metadata) tuples
        """
        if self.index.ntotal == 0:
            return []
        
        # Ensure correct shape
        query_embedding = query_embedding.astype(np.float32)
        if len(query_embedding.shape) == 1:
            query_embedding = query_embedding.reshape(1, -1)
        
        # Search
        top_k = min(top_k, self.index.ntotal)
        distances, indices = self.index.search(query_embedding, top_k)
        
        # Format results
        results = []
        for dist, idx in zip(distances[0], indices[0]):
            if idx == -1:  # No result
                continue
            
            metadata = self.id_to_metadata.get(idx, {})
            
            # Convert distance to similarity score (depends on index type)
            if "IP" in self.index_type or "HNSW" in self.index_type:
                # For inner product, higher is better
                similarity = float(dist)
            else:
                # For L2 distance, convert to similarity
                similarity = 1.0 / (1.0 + float(dist))
            
            results.append((int(idx), similarity, metadata))
        
        return results
    
    def delete_by_chunk_ids(self, chunk_ids: List[str]):
        """Delete vectors by chunk IDs (not efficiently supported by FAISS, requires rebuild)."""
        # FAISS doesn't support efficient deletion, so we'd need to rebuild the index
        # For now, just log a warning
        app_logger.warning("FAISS doesn't support efficient deletion. Use Chroma for this feature.")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get vector store statistics."""
        return {
            "total_vectors": self.index.ntotal if self.index else 0,
            "dimension": self.dimension,
            "index_type": self.index_type,
            "metadata_count": len(self.id_to_metadata),
        }
