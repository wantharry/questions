"""
Question generation system using LLM.
"""
import json
import re
from typing import List, Dict, Any, Optional
from app.models import (
    QuestionGenerationRequest,
    GeneratedQuestion,
    Subject,
    DifficultyLevel,
    QuestionType,
)
from app.llm.llm_manager import LLMManager
from app.llm.prompts import PromptTemplates
from app.utils.logger import app_logger


class QuestionGenerator:
    """Generate questions from context using LLM."""
    
    def __init__(self, retriever=None):
        self.llm = LLMManager.get_llm()
        self.retriever = retriever  # Optional, can be set later
        app_logger.info("Initialized QuestionGenerator")
    
    async def generate_questions(
        self,
        request: QuestionGenerationRequest,
        llm=None,
    ) -> List[GeneratedQuestion]:
        """
        Generate questions based on the request.

        Args:
            request: QuestionGenerationRequest with parameters
            llm: Optional custom LLM instance (uses self.llm if not provided)

        Returns:
            List of GeneratedQuestion objects
        """
        try:
            # Get context
            if request.context:
                context = request.context
            else:
                # Try to retrieve context if retriever is available
                if self.retriever:
                    query = f"{request.subject.value}"
                    if request.topic:
                        query += f" {request.topic}"
                    
                    # Convert index_filter to IndexType if provided
                    specific_indexes = None
                    if request.index_filter:
                        from app.models_advanced import IndexType
                        specific_indexes = [IndexType.from_string(idx) for idx in request.index_filter]
                    
                    context = self.retriever.get_context_for_query(
                        query, 
                        top_k=8,
                        specific_indexes=specific_indexes,
                    )
                else:
                    # Use provided context or generate generic questions
                    context = f"Generate {request.question_type.value} questions about {request.subject.value}"
                    if request.topic:
                        context += f" related to {request.topic}"
            
            # Get prompts
            system_prompt, user_prompt = PromptTemplates.get_question_prompt(
                subject=request.subject,
                difficulty=request.difficulty,
                context=context,
                num_questions=request.num_questions,
                question_type=request.question_type,
            )
            
            # Generate questions
            app_logger.info(
                f"Generating {request.num_questions} {request.difficulty.value} "
                f"{request.question_type.value} questions for {request.subject.value}"
            )
            
            # Use provided LLM or fall back to default
            llm_to_use = llm or self.llm

            response = await llm_to_use.generate(
                prompt=user_prompt,
                system_prompt=system_prompt,
                temperature=0.8,  # Slightly higher for variety
            )
            
            # Parse response
            questions = self._parse_llm_response(
                response.text,
                request.subject,
                request.difficulty,
                request.question_type,
                request.topic,
            )
            
            app_logger.info(f"Generated {len(questions)} questions")
            return questions
        
        except Exception as e:
            app_logger.error(f"Error generating questions: {e}")
            raise
    
    def _parse_llm_response(
        self,
        response_text: str,
        subject: Subject,
        difficulty: DifficultyLevel,
        question_type: QuestionType,
        topic: str = None,
    ) -> List[GeneratedQuestion]:
        """
        Parse LLM response into structured questions.
        
        The LLM should return JSON, but we'll handle various formats.
        """
        questions = []
        
        try:
            # Try to parse as JSON
            # Look for JSON array in the response
            response_text = response_text.strip()
            
            # Try to find JSON array
            start_idx = response_text.find('[')
            end_idx = response_text.rfind(']')
            
            if start_idx != -1 and end_idx != -1:
                json_str = response_text[start_idx:end_idx+1]
                
                # Try multiple parsing strategies
                parsed = None
                parse_errors = []
                
                # Strategy 1: Direct parsing
                try:
                    parsed = json.loads(json_str)
                except json.JSONDecodeError as e:
                    parse_errors.append(f"Direct parse: {e}")
                    
                    # Strategy 2: Try with strict=False to allow control characters
                    try:
                        parsed = json.loads(json_str, strict=False)
                    except json.JSONDecodeError as e2:
                        parse_errors.append(f"Lenient parse: {e2}")
                        
                        # Strategy 3: Escape backslashes (common with LaTeX)
                        try:
                            # This regex replaces \ with \\ only if not already followed by another \
                            json_str_escaped = re.sub(r'\\(?!["\\/bfnrtu])', r'\\\\', json_str)
                            parsed = json.loads(json_str_escaped)
                        except (json.JSONDecodeError, re.error) as e3:
                            parse_errors.append(f"Escaped parse: {e3}")
                
                if parsed and isinstance(parsed, list):
                    for item in parsed:
                        try:
                            if isinstance(item, dict):
                                question = GeneratedQuestion(
                                    question=item.get('question', ''),
                                    question_type=question_type,
                                    difficulty=difficulty,
                                    options=item.get('options'),
                                    correct_answer=item.get('correct_answer', item.get('answer', '')),
                                    explanation=item.get('explanation', ''),
                                    subject=subject,
                                    topic=topic or item.get('topic'),
                                )
                                questions.append(question)
                        except Exception as e:
                            app_logger.warning(f"Failed to parse question item: {e}")
                            continue
                else:
                    app_logger.warning(f"All JSON parsing strategies failed: {parse_errors}")
                    # Fallback to text parsing
                    questions = self._parse_text_response(
                        response_text, subject, difficulty, question_type, topic
                    )
            
            else:
                # Fallback: try to parse as structured text
                app_logger.warning("LLM response not in JSON format, using fallback parsing")
                questions = self._parse_text_response(
                    response_text, subject, difficulty, question_type, topic
                )
        
        except Exception as e:
            app_logger.error(f"Error parsing LLM response: {e}")
            # Log the raw response for debugging
            app_logger.debug(f"Raw LLM response (first 500 chars): {response_text[:500]}")
            # Return a question indicating parsing failure with helpful message
            questions = [
                GeneratedQuestion(
                    question="Failed to parse LLM response. The model may have included improperly formatted content.",
                    question_type=question_type,
                    difficulty=difficulty,
                    correct_answer="Please try again or adjust your parameters.",
                    explanation=f"Technical details: {str(e)}\n\nRaw response preview: {response_text[:200]}...",
                    subject=subject,
                    topic=topic,
                )
            ]
        
        return questions
    
    def _parse_text_response(
        self,
        text: str,
        subject: Subject,
        difficulty: DifficultyLevel,
        question_type: QuestionType,
        topic: str = None,
    ) -> List[GeneratedQuestion]:
        """Fallback text parser for non-JSON responses."""
        # Simple heuristic parsing
        questions = []
        
        # Split by common question markers
        parts = text.split('\n\n')
        
        for part in parts:
            if not part.strip():
                continue
            
            # Try to extract question
            lines = [l.strip() for l in part.split('\n') if l.strip()]
            if not lines:
                continue
            
            question_text = lines[0]
            answer = "See explanation below"
            explanation = '\n'.join(lines[1:]) if len(lines) > 1 else "No explanation provided"
            
            questions.append(
                GeneratedQuestion(
                    question=question_text,
                    question_type=question_type,
                    difficulty=difficulty,
                    correct_answer=answer,
                    explanation=explanation,
                    subject=subject,
                    topic=topic,
                )
            )
        
        return questions[:10]  # Limit fallback results
