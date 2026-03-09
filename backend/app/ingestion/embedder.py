"""
Sentence Transformers embedding provider.
"""
from typing import List
import numpy as np
from sentence_transformers import SentenceTransformer
from app.ingestion.base_embedder import BaseEmbedder
from app.config import settings
from app.utils.logger import app_logger


class SentenceTransformerEmbedder(BaseEmbedder):
    """Sentence Transformers embedding provider."""
    
    def __init__(
        self,
        model_name: str = None,
        device: str = None,
        batch_size: int = None,
    ):
        self.model_name = model_name or settings.embedding_model
        self.device = device or settings.embedding_device
        self.batch_size = batch_size or settings.embedding_batch_size
        
        app_logger.info(f"Loading embedding model: {self.model_name} on {self.device}")
        
        self.model = SentenceTransformer(self.model_name, device=self.device)
        self.dimension = self.model.get_sentence_embedding_dimension()
        
        super().__init__(self.model_name, self.dimension)
        
        app_logger.info(
            f"Loaded {self.model_name} with dimension {self.dimension}"
        )
    
    def embed_text(self, text: str) -> np.ndarray:
        """Embed a single text."""
        if not text or not text.strip():
            # Return zero vector for empty text
            return np.zeros(self.dimension, dtype=np.float32)
        
        try:
            embedding = self.model.encode(
                text,
                convert_to_numpy=True,
                show_progress_bar=False,
                normalize_embeddings=True,  # Normalize for cosine similarity
            )
            return embedding.astype(np.float32)
        except Exception as e:
            app_logger.error(f"Error embedding text: {e}")
            raise
    
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Embed a batch of texts efficiently."""
        if not texts:
            return np.array([], dtype=np.float32).reshape(0, self.dimension)
        
        # Filter out empty texts and remember their indices
        valid_texts = []
        valid_indices = []
        for idx, text in enumerate(texts):
            if text and text.strip():
                valid_texts.append(text)
                valid_indices.append(idx)
        
        if not valid_texts:
            # All texts are empty
            return np.zeros((len(texts), self.dimension), dtype=np.float32)
        
        try:
            embeddings = self.model.encode(
                valid_texts,
                batch_size=self.batch_size,
                convert_to_numpy=True,
                show_progress_bar=len(valid_texts) > 100,
                normalize_embeddings=True,
            )
            
            # Create result array with zeros for empty texts
            result = np.zeros((len(texts), self.dimension), dtype=np.float32)
            for result_idx, embedding in zip(valid_indices, embeddings):
                result[result_idx] = embedding
            
            return result
        
        except Exception as e:
            app_logger.error(f"Error embedding batch: {e}")
            raise
    
    def get_model_info(self) -> dict:
        """Get embedding model information."""
        return {
            "provider": "sentence_transformers",
            "model": self.model_name,
            "dimension": self.dimension,
            "device": self.device,
            "batch_size": self.batch_size,
            "max_seq_length": self.model.max_seq_length,
        }
