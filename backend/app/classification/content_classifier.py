"""
Content type classifier for educational documents.
Identifies: theory, definitions, formulas, examples, exercises, solutions, etc.
"""
import re
from typing import List, Dict, Tuple
from app.models_advanced import ContentType, DifficultyLevel
from app.utils.logger import app_logger


class ContentClassifier:
    """Classify content type in educational documents."""
    
    def __init__(self):
        # Patterns for content type detection
        self.patterns = {
            ContentType.DEFINITION: [
                r'\b(?:definition|define|defined as|is defined|we define)\b',
                r'\b(?:refers to|means|meaning of|term)\b',
                r'^\s*(?:def|defn|definition)[\.:]\s*',
            ],
            ContentType.THEOREM: [
                r'\b(?:theorem|lemma|corollary|proposition)\b',
                r'^\s*(?:theorem|lemma|corollary)\s+\d',
                r'\b(?:states that|statement)\b',
            ],
            ContentType.FORMULA: [
                r'[\$\\]\s*[a-zA-Z].*?=.*?[\$\\]',  # LaTeX formulas
                r'\b(?:formula|equation|expression|relation)\b',
                r'[a-zA-Z]\s*=\s*[^a-zA-Z]{3,}',  # x = ...
                r'\b(?:given by|expressed as|calculated as)\b',
            ],
            ContentType.DERIVATION: [
                r'\b(?:proof|prove|derivation|derive|derived|deriving)\b',
                r'\b(?:starting from|beginning with|let us)\b',
                r'(?:step|steps)\s+\d',
            ],
            ContentType.WORKED_EXAMPLE: [
                r'\b(?:example|illustration|worked example|problem)\s*\d',
                r'^\s*(?:ex|example|eg|e\.g\.)[\.:]\s*',
                r'\b(?:solution|solving|solve)\b',
                r'\b(?:find|calculate|determine|compute)\b',
            ],
            ContentType.EXERCISE: [
                r'\b(?:exercise|problem|question)\s*\d',
                r'^\s*(?:q|ques|problem|exercise)[\.:]\s*\d',
                r'\b(?:exercises|problems|questions)\s*$',
                r'\b(?:practice|homework|assignment)\b',
            ],
            ContentType.SOLUTION: [
                r'\b(?:solution|answer|sol|ans)[\.:]\s*',
                r'^\s*(?:solution|answer)\s+to\s+',
                r'\b(?:solved|solving)\b',
            ],
            ContentType.SUMMARY: [
                r'\b(?:summary|recap|review|key points)\b',
                r'\b(?:in summary|to summarize|in conclusion)\b',
            ],
        }
        
        # Keywords indicating difficulty
        self.difficulty_keywords = {
            DifficultyLevel.BASIC: [
                'basic', 'fundamental', 'introduction', 'elementary',
                'simple', 'easy', 'beginner'
            ],
            DifficultyLevel.EASY: [
                'straightforward', 'direct', 'simple application'
            ],
            DifficultyLevel.MEDIUM: [
                'moderate', 'intermediate', 'standard'
            ],
            DifficultyLevel.HARD: [
                'difficult', 'challenging', 'complex', 'advanced problem',
                'tricky', 'hard'
            ],
            DifficultyLevel.ADVANCED: [
                'advanced', 'sophisticated', 'graduate level',
                'research level', 'olympiad'
            ],
        }
        
        app_logger.info("Initialized ContentClassifier")
    
    def classify_content(self, text: str, metadata: Dict = None) -> ContentType:
        """
        Classify content type based on text patterns.
        
        Args:
            text: Text content to classify
            metadata: Optional metadata (page number, section name, etc.)
        
        Returns:
            ContentType enum
        """
        if not text or len(text.strip()) < 10:
            return ContentType.UNKNOWN
        
        text_lower = text.lower()
        text_first_200 = text[:200].lower()
        
        # Score each content type
        scores = {}
        for content_type, patterns in self.patterns.items():
            score = 0
            for pattern in patterns:
                # Weight first 200 chars higher
                if re.search(pattern, text_first_200, re.IGNORECASE):
                    score += 3
                elif re.search(pattern, text_lower, re.IGNORECASE):
                    score += 1
            scores[content_type] = score
        
        # Additional heuristics
        
        # Check for mathematical formulas
        if self._has_formulas(text):
            scores[ContentType.FORMULA] = scores.get(ContentType.FORMULA, 0) + 2
        
        # Check for numbered items (likely exercises)
        if re.search(r'^\s*\d+[\.\)]\s+', text, re.MULTILINE):
            if 'solution' not in text_lower[:100]:
                scores[ContentType.EXERCISE] = scores.get(ContentType.EXERCISE, 0) + 2
        
        # Check for Q&A format
        if re.search(r'\bQ\s*\d+[\.\:]\s*', text):
            scores[ContentType.EXERCISE] = scores.get(ContentType.EXERCISE, 0) + 2
        
        # Check metadata hints
        if metadata:
            section = metadata.get('section', '').lower()
            if 'exercise' in section or 'problem' in section:
                scores[ContentType.EXERCISE] = scores.get(ContentType.EXERCISE, 0) + 3
            elif 'example' in section:
                scores[ContentType.WORKED_EXAMPLE] = scores.get(ContentType.WORKED_EXAMPLE, 0) + 3
            elif 'solution' in section:
                scores[ContentType.SOLUTION] = scores.get(ContentType.SOLUTION, 0) + 3
        
        # Get highest score
        if not scores or max(scores.values()) == 0:
            return ContentType.THEORY  # Default for educational content
        
        classified = max(scores.items(), key=lambda x: x[1])[0]
        
        app_logger.debug(f"Classified as {classified.value} with scores: {scores}")
        return classified
    
    def detect_difficulty(self, text: str, metadata: Dict = None) -> DifficultyLevel:
        """
        Detect difficulty level of content.
        
        Args:
            text: Text content
            metadata: Optional metadata
        
        Returns:
            DifficultyLevel enum
        """
        text_lower = text.lower()
        
        scores = {level: 0 for level in DifficultyLevel}
        
        # Check keywords
        for level, keywords in self.difficulty_keywords.items():
            for keyword in keywords:
                if keyword in text_lower:
                    scores[level] += 1
        
        # Heuristics
        
        # Long derivations → harder
        if len(text) > 2000 and 'proof' in text_lower:
            scores[DifficultyLevel.HARD] += 2
        
        # Multiple formulas → harder
        formula_count = text.count('=')
        if formula_count > 5:
            scores[DifficultyLevel.MEDIUM] += 1
        if formula_count > 10:
            scores[DifficultyLevel.HARD] += 1
        
        # Check metadata
        if metadata:
            chapter_num = metadata.get('chapter_number')
            if chapter_num:
                if chapter_num <= 2:
                    scores[DifficultyLevel.BASIC] += 1
                elif chapter_num > 10:
                    scores[DifficultyLevel.ADVANCED] += 1
        
        # Get highest score or default to MEDIUM
        if max(scores.values()) == 0:
            return DifficultyLevel.MEDIUM
        
        return max(scores.items(), key=lambda x: x[1])[0]
    
    def extract_keywords(self, text: str, top_k: int = 10) -> List[str]:
        """
        Extract important keywords from text.
        
        Simple implementation - can be enhanced with TF-IDF or KeyBERT.
        """
        # Remove common words
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to',
            'for', 'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are',
            'be', 'been', 'have', 'has', 'had', 'do', 'does', 'did', 'will',
            'would', 'should', 'could', 'may', 'might', 'can', 'this', 'that'
        }
        
        # Extract words
        words = re.findall(r'\b[a-zA-Z]{3,}\b', text.lower())
        
        # Count frequencies
        word_freq = {}
        for word in words:
            if word not in stop_words:
                word_freq[word] = word_freq.get(word, 0) + 1
        
        # Get top K
        sorted_words = sorted(word_freq.items(), key=lambda x: x[1], reverse=True)
        keywords = [word for word, freq in sorted_words[:top_k]]
        
        return keywords
    
    def extract_formulas(self, text: str) -> List[str]:
        """Extract mathematical formulas from text."""
        formulas = []
        
        # LaTeX formulas
        latex_patterns = [
            r'\$\$(.+?)\$\$',  # Display math
            r'\$(.+?)\$',      # Inline math
            r'\\begin\{equation\}(.+?)\\end\{equation\}',
            r'\\begin\{align\}(.+?)\\end\{align\}',
        ]
        
        for pattern in latex_patterns:
            matches = re.findall(pattern, text, re.DOTALL)
            formulas.extend(matches)
        
        # Simple equations (x = y + z)
        simple_eq = re.findall(r'\b[a-zA-Z_]+\s*=\s*[^\n]{10,50}', text)
        formulas.extend(simple_eq)
        
        # Clean and deduplicate
        formulas = [f.strip() for f in formulas if f.strip()]
        formulas = list(dict.fromkeys(formulas))  # Remove duplicates
        
        return formulas[:20]  # Limit to 20
    
    def _has_formulas(self, text: str) -> bool:
        """Check if text contains mathematical formulas."""
        # LaTeX indicators
        if re.search(r'[\$\\]', text):
            return True
        
        # Equation patterns
        if re.search(r'[a-zA-Z]\s*=\s*[^a-zA-Z\s]{3,}', text):
            return True
        
        # Mathematical symbols
        math_symbols = ['∫', '∑', '∏', '√', '∂', '∇', '≈', '≠', '≤', '≥', '×', '÷']
        if any(symbol in text for symbol in math_symbols):
            return True
        
        return False
    
    def classify_batch(
        self,
        texts: List[str],
        metadatas: List[Dict] = None
    ) -> List[Tuple[ContentType, DifficultyLevel]]:
        """Classify a batch of texts."""
        if metadatas is None:
            metadatas = [{}] * len(texts)
        
        results = []
        for text, metadata in zip(texts, metadatas):
            content_type = self.classify_content(text, metadata)
            difficulty = self.detect_difficulty(text, metadata)
            results.append((content_type, difficulty))
        
        return results
