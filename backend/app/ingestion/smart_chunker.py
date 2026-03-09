"""
Structure-aware smart chunker for educational content.
Keeps formulas, examples, and exercises intact.
"""
from typing import List, Dict, Any, Tuple
import re
from app.models_advanced import ContentType, EnhancedChunkMetadata
from app.classification.content_classifier import ContentClassifier
from app.config import settings
from app.utils.logger import app_logger


class SmartChunker:
    """Structure-aware chunking for STEM textbooks."""
    
    def __init__(
        self,
        content_classifier: ContentClassifier = None,
        max_chunk_size: int = None,
        min_chunk_size: int = 200,
    ):
        self.classifier = content_classifier or ContentClassifier()
        self.max_chunk_size = max_chunk_size or settings.chunk_size
        self.min_chunk_size = min_chunk_size
        
        app_logger.info(
            f"Initialized SmartChunker: max={self.max_chunk_size}, "
            f"min={self.min_chunk_size}"
        )
    
    def chunk_document(
        self,
        text: str,
        metadata: Dict[str, Any] = None
    ) -> List[Dict[str, Any]]:
        """
        Chunk document with structure awareness.
        
        Strategy:
        1. Detect structural boundaries (chapters, sections)
        2. Identify content types
        3. Keep related content together
        4. Split by paragraphs/sentences if needed
        
        Returns:
            List of chunk dicts with text and metadata
        """
        if not text or not text.strip():
            return []
        
        metadata = metadata or {}
        
        # Step 1: Detect major sections
        sections = self._detect_sections(text)
        
        chunks = []
        chunk_index = 0
        
        for section in sections:
            section_text = section['text']
            section_metadata = {**metadata, **section['metadata']}
            
            # Step 2: Classify content type
            content_type = self.classifier.classify_content(
                section_text, section_metadata
            )
            
            # Step 3: Chunk based on content type
            if content_type == ContentType.WORKED_EXAMPLE:
                # Keep examples intact if possible
                section_chunks = self._chunk_example(section_text, section_metadata)
            
            elif content_type == ContentType.EXERCISE:
                # Keep each exercise separate
                section_chunks = self._chunk_exercises(section_text, section_metadata)
            
            elif content_type == ContentType.FORMULA or content_type == ContentType.DERIVATION:
                # Keep formulas with context
                section_chunks = self._chunk_formula_section(section_text, section_metadata)
            
            elif content_type == ContentType.DEFINITION or content_type == ContentType.THEOREM:
                # Keep definitions intact
                section_chunks = self._chunk_definition(section_text, section_metadata)
            
            else:
                # Default: theory chunks
                section_chunks = self._chunk_theory(section_text, section_metadata)
            
            # Add chunk indices
            for chunk in section_chunks:
                chunk['chunk_index'] = chunk_index
                chunk['content_type'] = content_type
                chunk_index += 1
            
            chunks.extend(section_chunks)
        
        app_logger.info(f"Created {len(chunks)} smart chunks from document")
        return chunks
    
    def _detect_sections(self, text: str) -> List[Dict[str, Any]]:
        """Detect major sections in text."""
        sections = []
        
        # Detect section headers
        # Patterns: "1.2.3 Title", "Chapter 5: Title", "Section A", etc.
        section_pattern = r'^(?:\d+(?:\.\d+)*\.?\s+|Chapter\s+\d+[\.:]\s*|Section\s+[A-Z\d]+[\.:]\s*|\*\*[^*]+\*\*\s*$|#{1,3}\s+)'
        
        lines = text.split('\n')
        section_starts = []
        
        for i, line in enumerate(lines):
            if re.match(section_pattern, line.strip(), re.IGNORECASE):
                section_starts.append(i)
        
        # If no sections found, treat whole text as one section
        if not section_starts:
            return [{
                'text': text,
                'metadata': {}
            }]
        
        # Extract sections
        for i, start in enumerate(section_starts):
            end = section_starts[i + 1] if i + 1 < len(section_starts) else len(lines)
            
            section_lines = lines[start:end]
            section_text = '\n'.join(section_lines)
            
            # Extract section metadata
            header = lines[start].strip()
            section_num = re.search(r'\d+(?:\.\d+)*', header)
            
            sections.append({
                'text': section_text,
                'metadata': {
                    'section': header,
                    'section_number': section_num.group() if section_num else None,
                }
            })
        
        return sections
    
    def _chunk_example(
        self,
        text: str,
        metadata: Dict
    ) -> List[Dict[str, Any]]:
        """Chunk worked examples - try to keep intact."""
        # If example is short enough, keep as one chunk
        if len(text) <= self.max_chunk_size * 1.5:  # Allow 50% overflow for examples
            return [{
                'text': text,
                'metadata': {**metadata, 'is_complete': True}
            }]
        
        # Otherwise, split by "Solution:", "Answer:", etc.
        solution_pattern = r'\n(?:Solution|Answer|Sol|Ans)[\.:]\s*\n'
        parts = re.split(solution_pattern, text, flags=re.IGNORECASE)
        
        chunks = []
        for i, part in enumerate(parts):
            if part.strip():
                # Add context about which part this is
                part_metadata = {
                    **metadata,
                    'example_part': 'problem f' if i == 0 else 'solution',
                    'is_complete': True
                }
                chunks.append({'text': part.strip(), 'metadata': part_metadata})
        
        return chunks if chunks else [{'text': text, 'metadata': metadata}]
    
    def _chunk_exercises(
        self,
        text: str,
        metadata: Dict
    ) -> List[Dict[str, Any]]:
        """Chunk exercises - one per chunk if possible."""
        # Split by numbered items
        exercise_pattern = r'\n(\d+[\.\)]\s+)'
        parts = re.split(exercise_pattern, text)
        
        chunks = []
        current_number = None
        current_text = ""
        
        for part in parts:
            # Check if this looks like a number
            if re.match(r'\d+[\.\)]\s+', part):
                # Save previous exercise
                if current_text.strip():
                    chunks.append({
                        'text': current_text.strip(),
                        'metadata': {
                            **metadata,
                            'exercise_number': current_number,
                            'is_complete': True
                        }
                    })
                # Start new exercise
                current_number = re.match(r'(\d+)', part).group(1)
                current_text = part
            else:
                current_text += part
        
        # Add last exercise
        if current_text.strip():
            chunks.append({
                'text': current_text.strip(),
                'metadata': {
                    **metadata,
                    'exercise_number': current_number,
                    'is_complete': True
                }
            })
        
        # If no numbered items found, fall back to theory chunking
        if not chunks or len(chunks) == 1 and len(text) > self.max_chunk_size:
            return self._chunk_theory(text, metadata)
        
        return chunks
    
    def _chunk_formula_section(
        self,
        text: str,
        metadata: Dict
    ) -> List[Dict[str, Any]]:
        """Chunk formula/derivation - keep formulas with nearby context."""
        # Extract formulas
        formulas = self.classifier.extract_formulas(text)
        
        if not formulas:
            return self._chunk_theory(text, metadata)
        
        # For derivations, try to keep steps together
        if 'deriv' in text.lower() or 'proof' in text.lower():
            # Keep entire derivation if possible
            if len(text) <= self.max_chunk_size * 2:
                return [{
                    'text': text,
                    'metadata': {
                        **metadata,
                        'has_formula': True,
                        'formulas': formulas,
                        'is_complete': True
                    }
                }]
        
        # Otherwise chunk by paragraphs
        return self._chunk_theory(text, metadata, preserve_formulas=True)
    
    def _chunk_definition(
        self,
        text: str,
        metadata: Dict
    ) -> List[Dict[str, Any]]:
        """Chunk definitions - keep intact."""
        # Definitions should be kept together
        if len(text) <= self.max_chunk_size * 1.5:
            return [{
                'text': text,
                'metadata': {**metadata, 'is_complete': True}
            }]
        
        # If too long, split by paragraphs
        return self._chunk_theory(text, metadata)
    
    def _chunk_theory(
        self,
        text: str,
        metadata: Dict,
        preserve_formulas: bool = False
    ) -> List[Dict[str, Any]]:
        """Chunk theory content by paragraphs and sentences."""
        chunks = []
        
        # Split by paragraphs
        paragraphs = text.split('\n\n')
        
        current_chunk = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            # Check if adding this paragraph exceeds limit
            if len(current_chunk) + len(para) + 2 > self.max_chunk_size:
                # Save current chunk
                if current_chunk.strip():
                    chunks.append({
                        'text': current_chunk.strip(),
                        'metadata': {**metadata, 'is_complete': True}
                    })
                
                # Start new chunk
                # If paragraph itself is too long, split by sentences
                if len(para) > self.max_chunk_size:
                    sentence_chunks = self._split_by_sentences(para, metadata)
                    chunks.extend(sentence_chunks)
                    current_chunk = ""
                else:
                    current_chunk = para
            else:
                current_chunk += "\n\n" + para if current_chunk else para
        
        # Add last chunk
        if current_chunk.strip():
            chunks.append({
                'text': current_chunk.strip(),
                'metadata': {**metadata, 'is_complete': True}
            })
        
        return chunks
    
    def _split_by_sentences(
        self,
        text: str,
        metadata: Dict
    ) -> List[Dict[str, Any]]:
        """Split long paragraph by sentences."""
        # Simple sentence splitting
        sentences = re.split(r'(?<=[.!?])\s+', text)
        
        chunks = []
        current_chunk = ""
        
        for sentence in sentences:
            if len(current_chunk) + len(sentence) + 1 > self.max_chunk_size:
                if current_chunk.strip():
                    chunks.append({
                        'text': current_chunk.strip(),
                        'metadata': {**metadata, 'is_complete': False}  # Mid-paragraph
                    })
                current_chunk = sentence
            else:
                current_chunk += " " + sentence if current_chunk else sentence
        
        if current_chunk.strip():
            chunks.append({
                'text': current_chunk.strip(),
                'metadata': {**metadata, 'is_complete': False}
            })
        
        return chunks
