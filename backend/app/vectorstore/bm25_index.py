"""
BM25 sparse retrieval index for keyword and formula search.
Complements dense vector search with exact matching.
"""
from typing import List, Dict, Any, Tuple
from pathlib import Path
import json
import math
from collections import defaultdict, Counter
import re
import pickle
from app.config import settings
from app.utils.logger import app_logger


class BM25Index:
    """BM25 sparse retrieval index for keyword search."""
    
    def __init__(
        self,
        k1: float = 1.5,
        b: float = 0.75,
        store_dir: Path = None,
    ):
        """
        Initialize BM25 index.
        
        Args:
            k1: Term frequency saturation parameter (1.2-2.0)
            b: Length normalization parameter (0.75)
            store_dir: Directory to save index
        """
        self.k1 = k1
        self.b = b
        self.store_dir = Path(store_dir or settings.vector_store_dir)
        self.store_dir.mkdir(parents=True, exist_ok=True)
        
        # Index data structures
        self.doc_count = 0
        self.avgdl = 0.0  # Average document length
        self.doc_lens = {}  # {doc_id: length}
        self.doc_freqs = {}  # {term: doc_frequency}
        self.inverted_index = {}  # {term: {doc_id: term_freq}}
        self.documents = {}  # {doc_id: {text, metadata}}
        
        self.index_path = self.store_dir / "bm25_index.pkl"
        
        # Try to load existing index
        self._load_index()
        
        app_logger.info(f"Initialized BM25Index with {self.doc_count} documents")
    
    def add_documents(
        self,
        texts: List[str],
        metadatas: List[Dict[str, Any]],
        doc_ids: List[str] = None
    ):
        """
        Add documents to the index.
        
        Args:
            texts: List of document texts
            metadatas: List of metadata dicts
            doc_ids: Optional list of document IDs
        """
        if not doc_ids:
            doc_ids = [f"doc_{self.doc_count + i}" for i in range(len(texts))]
        
        for doc_id, text, metadata in zip(doc_ids, texts, metadatas):
            # Tokenize
            tokens = self._tokenize(text)
            doc_len = len(tokens)
            
            # Update doc info
            self.documents[doc_id] = {
                'text': text,
                'metadata': metadata,
                'length': doc_len
            }
            self.doc_lens[doc_id] = doc_len
            self.doc_count += 1
            
            # Update term frequencies
            term_freqs = Counter(tokens)
            
            for term, freq in term_freqs.items():
                # Update inverted index
                if term not in self.inverted_index:
                    self.inverted_index[term] = {}
                    self.doc_freqs[term] = 0
                
                if doc_id not in self.inverted_index[term]:
                    self.doc_freqs[term] += 1
                
                self.inverted_index[term][doc_id] = freq
        
        # Update average document length
        self.avgdl = sum(self.doc_lens.values()) / self.doc_count if self.doc_count > 0 else 0
        
        app_logger.info(f"Added {len(texts)} documents to BM25 index. Total: {self.doc_count}")
    
    def search(
        self,
        query: str,
        top_k: int = 20,
        filter_metadata: Dict[str, Any] = None
    ) -> List[Tuple[str, float, Dict[str, Any]]]:
        """
        Search the index with BM25 scoring.
        
        Args:
            query: Search query
            top_k: Number of results to return
            filter_metadata: Optional metadata filters
        
        Returns:
            List of (doc_id, score, metadata) tuples
        """
        if self.doc_count == 0:
            return []
        
        # Tokenize query
        query_tokens = self._tokenize(query)
        
        if not query_tokens:
            return []
        
        # Calculate BM25 scores
        scores = defaultdict(float)
        
        for term in query_tokens:
            if term not in self.inverted_index:
                continue
            
            # IDF calculation
            df = self.doc_freqs[term]
            idf = math.log((self.doc_count - df + 0.5) / (df + 0.5) + 1.0)
            
            # Score each document containing the term
            for doc_id, term_freq in self.inverted_index[term].items():
                doc_len = self.doc_lens[doc_id]
                
                # BM25 formula
                numerator = term_freq * (self.k1 + 1)
                denominator = term_freq + self.k1 * (1 - self.b + self.b * doc_len / self.avgdl)
                
                scores[doc_id] += idf * (numerator / denominator)
        
        # Apply metadata filters
        if filter_metadata:
            filtered_scores = {}
            for doc_id, score in scores.items():
                doc_metadata = self.documents[doc_id]['metadata']
                if self._matches_filters(doc_metadata, filter_metadata):
                    filtered_scores[doc_id] = score
            scores = filtered_scores
        
        # Sort and get top K
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        
        # Format results
        results = []
        for doc_id, score in sorted_docs:
            doc = self.documents[doc_id]
            results.append((doc_id, score, doc['metadata']))
        
        app_logger.debug(f"BM25 search returned {len(results)} results for query: {query[:50]}")
        return results
    
    def _tokenize(self, text: str) -> List[str]:
        """
        Tokenize text with special handling for STEM content.
        
        - Lowercase
        - Keep alphanumeric and special chars (for formulas)
        - Split on whitespace and punctuation
        - Keep mathematical symbols together
        """
        # Lowercase
        text = text.lower()
        
        # Keep formulas together (e.g., "f=ma", "e=mc^2")
        text = re.sub(r'([a-z])\s*=\s*([a-z0-9\+\-\*/\^]+)', r'\1=\2', text)
        
        # Tokenize
        tokens = re.findall(r'\b\w+\b|[=\+\-\*/\^]+', text)
        
        # Remove very short tokens (except mathematical operators)
        tokens = [t for t in tokens if len(t) > 1 or t in ['=', '+', '-', '*', '/', '^']]
        
        return tokens
    
    def _matches_filters(self, metadata: Dict, filters: Dict) -> bool:
        """Check if metadata matches filters."""
        for key, value in filters.items():
            if key not in metadata:
                return False
            if metadata[key] != value:
                return False
        return True
    
    def save_index(self):
        """Save index to disk."""
        try:
            data = {
                'doc_count': self.doc_count,
                'avgdl': self.avgdl,
                'doc_lens': self.doc_lens,
                'doc_freqs': self.doc_freqs,
                'inverted_index': self.inverted_index,
                'documents': self.documents,
                'k1': self.k1,
                'b': self.b,
            }
            
            with open(self.index_path, 'wb') as f:
                pickle.dump(data, f)
            
            app_logger.info(f"Saved BM25 index with {self.doc_count} documents")
        except Exception as e:
            app_logger.error(f"Error saving BM25 index: {e}")
    
    def _load_index(self):
        """Load index from disk."""
        if not self.index_path.exists():
            return
        
        try:
            with open(self.index_path, 'rb') as f:
                data = pickle.load(f)
            
            self.doc_count = data['doc_count']
            self.avgdl = data['avgdl']
            self.doc_lens = data['doc_lens']
            self.doc_freqs = data['doc_freqs']
            self.inverted_index = data['inverted_index']
            self.documents = data['documents']
            self.k1 = data.get('k1', self.k1)
            self.b = data.get('b', self.b)
            
            app_logger.info(f"Loaded BM25 index with {self.doc_count} documents")
        except Exception as e:
            app_logger.error(f"Error loading BM25 index: {e}")
    
    def get_stats(self) -> Dict[str, Any]:
        """Get index statistics."""
        return {
            'doc_count': self.doc_count,
            'avgdl': self.avgdl,
            'vocab_size': len(self.inverted_index),
            'index_size_bytes': self.index_path.stat().st_size if self.index_path.exists() else 0,
        }
