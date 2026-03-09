"""
Abstract base class for pluggable embedding providers.
"""
from abc import ABC, abstractmethod
from typing import List
import numpy as np


class BaseEmbedder(ABC):
    """Abstract base class for embedding providers."""
    
    def __init__(self, model_name: str, dimension: int):
        self.model_name = model_name
        self.dimension = dimension
    
    @abstractmethod
    def embed_text(self, text: str) -> np.ndarray:
        """Embed a single text."""
        pass
    
    @abstractmethod
    def embed_batch(self, texts: List[str]) -> np.ndarray:
        """Embed a batch of texts."""
        pass
    
    @abstractmethod
    def get_model_info(self) -> dict:
        """Get information about the embedding model."""
        pass
