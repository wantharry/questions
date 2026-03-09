"""
Query router to classify user intent and route to appropriate indexes.
"""
from typing import List, Dict, Any, Tuple
import re
from app.models_advanced import QueryIntent, ContentType, IndexType
from app.config import settings
from app.utils.logger import app_logger


class QueryRouter:
    """
    Classifies query intent and recommends search strategy.
    """
    
    def __init__(self):
        """Initialize query router with intent patterns."""
        
        # Intent detection patterns
        self.intent_patterns = {
            QueryIntent.EXPLAIN_CONCEPT: [
                r'\b(what is|explain|define|describe|meaning of)\b',
                r'\b(how does|why does|concept of)\b',
                r'\b(definition of|explain the)\b',
            ],
            QueryIntent.FORMULA_LOOKUP: [
                r'\b(formula for|equation for|expression for)\b',
                r'\b(derive|derivation of)\b',
                r'\b(how to calculate|calculate)\b',
                r'=',  # Contains equation
            ],
            QueryIntent.FIND_EXAMPLES: [
                r'\b(example of|examples on|show examples)\b',
                r'\b(worked example|solved problem|solution to)\b',
                r'\b(how to solve|solve)\b',
                r'\b(practice problems|exercises on|problems on)\b',
                r'\b(questions on|questions about)\b',
                r'\b(find exercises|find problems)\b',
            ],
            QueryIntent.GENERATE_QUESTIONS: [
                r'\b(generate|create|make)\b.*\b(questions|problems|exercises)\b',
                r'\b(give me.*questions|give me.*problems)\b',
                r'\b(question generation|generate questions)\b',
            ],
            QueryIntent.COMPARE_CONCEPTS: [
                r'\b(compare|difference between|vs|versus)\b',
                r'\b(contrast|how do.*differ)\b',
            ],
        }
        
        # Formula indicators
        self.formula_indicators = [
            r'[a-z]\s*=\s*[a-z0-9]',  # f=ma
            r'\b(sin|cos|tan|log|ln|exp|sqrt)\b',
            r'[∫∑∏∂√π]',  # Math symbols
            r'\^|\*\*|²|³',  # Exponents
        ]
        
        # Subject detection patterns
        self.subject_patterns = {
            'physics': [
                r'\b(force|velocity|acceleration|energy|momentum|friction)\b',
                r'\b(newton|mechanics|kinematics|dynamics|thermodynamics)\b',
                r'\b(electric|magnetic|waves|optics)\b',
            ],
            'chemistry': [
                r'\b(atom|molecule|element|compound|reaction|bond)\b',
                r'\b(acid|base|ph|solution|equilibrium)\b',
                r'\b(organic|inorganic|periodic table)\b',
            ],
            'mathematics': [
                r'\b(integral|derivative|equation|function|matrix)\b',
                r'\b(theorem|proof|calculus|algebra|geometry)\b',
                r'\b(polynomial|trigonometry|logarithm)\b',
            ],
        }
        
        app_logger.info("Initialized QueryRouter")
    
    def route_query(
        self,
        query: str,
        metadata_context: Dict[str, Any] = None
    ) -> Dict[str, Any]:
        """
        Analyze query and return routing strategy.
        
        Args:
            query: User query
            metadata_context: Optional context (e.g., selected subject filter)
        
        Returns:
            Dict with:
            - intent: QueryIntent
            - recommended_indexes: List[IndexType]
            - search_strategy: Dict with weights and params
            - detected_subject: Optional subject
            - contains_formula: bool
        """
        query_lower = query.lower()
        
        # Detect intent
        intent = self._detect_intent(query_lower)
        
        # Detect subject
        detected_subject = self._detect_subject(query_lower)
        
        # Check for formulas
        contains_formula = self._contains_formula(query)
        
        # Determine recommended indexes
        recommended_indexes = self._recommend_indexes(intent, contains_formula)
        
        # Determine search strategy
        search_strategy = self._get_search_strategy(intent, contains_formula)
        
        routing = {
            'intent': intent,
            'recommended_indexes': recommended_indexes,
            'search_strategy': search_strategy,
            'detected_subject': detected_subject,
            'contains_formula': contains_formula,
        }
        
        app_logger.debug(f"Query routed: intent={intent.value}, indexes={[i.value for i in recommended_indexes]}")
        return routing
    
    def _detect_intent(self, query: str) -> QueryIntent:
        """Detect primary query intent."""
        scores = {intent: 0 for intent in QueryIntent}
        
        for intent, patterns in self.intent_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    scores[intent] += 1
        
        # Return intent with highest score
        max_intent = max(scores, key=scores.get)
        
        # If no clear intent, default to GENERAL
        if scores[max_intent] == 0:
            return QueryIntent.GENERAL
        
        return max_intent
    
    def _detect_subject(self, query: str) -> str:
        """Detect subject domain from query."""
        scores = {subject: 0 for subject in self.subject_patterns.keys()}
        
        for subject, patterns in self.subject_patterns.items():
            for pattern in patterns:
                if re.search(pattern, query, re.IGNORECASE):
                    scores[subject] += 1
        
        max_subject = max(scores, key=scores.get)
        
        if scores[max_subject] > 0:
            return max_subject
        
        return None
    
    def _contains_formula(self, query: str) -> bool:
        """Check if query contains formula/equation."""
        for pattern in self.formula_indicators:
            if re.search(pattern, query, re.IGNORECASE):
                return True
        return False
    
    def _recommend_indexes(
        self,
        intent: QueryIntent,
        contains_formula: bool
    ) -> List[IndexType]:
        """Recommend which indexes to search."""
        
        # Map intents to indexes
        intent_to_indexes = {
            QueryIntent.EXPLAIN_CONCEPT: [IndexType.THEORY, IndexType.GENERAL],
            QueryIntent.FORMULA_LOOKUP: [IndexType.FORMULA, IndexType.THEORY],
            QueryIntent.FIND_EXAMPLES: [IndexType.SOLUTION, IndexType.EXERCISE],
            QueryIntent.GENERATE_QUESTIONS: [IndexType.EXERCISE, IndexType.SOLUTION],
            QueryIntent.COMPARE_CONCEPTS: [IndexType.THEORY, IndexType.GENERAL],
            QueryIntent.GENERAL: [IndexType.GENERAL, IndexType.THEORY],
        }
        
        indexes = intent_to_indexes.get(intent, [IndexType.GENERAL])
        
        # Add formula index if formula detected
        if contains_formula and IndexType.FORMULA not in indexes:
            indexes.insert(0, IndexType.FORMULA)
        
        return indexes
    
    def _get_search_strategy(
        self,
        intent: QueryIntent,
        contains_formula: bool
    ) -> Dict[str, Any]:
        """
        Determine search strategy parameters.
        
        Returns:
            Dict with:
            - dense_weight: Weight for dense/semantic search (0-1)
            - sparse_weight: Weight for sparse/BM25 search (0-1)
            - rerank: Whether to use reranking
            - top_k_retrieval: How many to retrieve before rerank
            - top_k_final: How many to return after rerank
        """
        
        # Default balanced strategy
        strategy = {
            'dense_weight': 0.5,
            'sparse_weight': 0.5,
            'rerank': True,
            'top_k_retrieval': 20,
            'top_k_final': 5,
        }
        
        # Adjust based on intent
        if intent == QueryIntent.EXPLAIN_CONCEPT:
            # Semantic understanding more important
            strategy['dense_weight'] = 0.7
            strategy['sparse_weight'] = 0.3
        
        elif intent == QueryIntent.FORMULA_LOOKUP:
            # Keyword matching crucial for formulas
            strategy['dense_weight'] = 0.3
            strategy['sparse_weight'] = 0.7
        
        elif intent == QueryIntent.FIND_EXAMPLES:
            # Balanced approach
            strategy['dense_weight'] = 0.5
            strategy['sparse_weight'] = 0.5
        
        elif intent == QueryIntent.GENERATE_QUESTIONS:
            # Need diverse examples
            strategy['dense_weight'] = 0.6
            strategy['sparse_weight'] = 0.4
            strategy['top_k_retrieval'] = 30
            strategy['top_k_final'] = 10
        
        # Boost sparse if formula detected
        if contains_formula:
            strategy['sparse_weight'] += 0.2
            strategy['dense_weight'] = max(0.1, strategy['dense_weight'] - 0.2)
            # Normalize
            total = strategy['dense_weight'] + strategy['sparse_weight']
            strategy['dense_weight'] /= total
            strategy['sparse_weight'] /= total
        
        return strategy
