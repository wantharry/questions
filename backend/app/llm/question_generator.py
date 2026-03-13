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
        # Handle large batches by chunking into smaller requests
        CHUNK_SIZE = 10  # Generate 10 questions at a time (proven stable)
        if request.num_questions > CHUNK_SIZE:
            app_logger.info(
                f"Large batch detected ({request.num_questions} questions). "
                f"Splitting into {CHUNK_SIZE}-question chunks..."
            )
            all_questions = []
            remaining = request.num_questions
            chunk_num = 1

            while remaining > 0:
                # Calculate chunk size (last chunk may be smaller)
                current_chunk_size = min(CHUNK_SIZE, remaining)

                # Create request for this chunk
                chunk_request = QuestionGenerationRequest(
                    context=request.context,
                    subject=request.subject,
                    difficulty=request.difficulty,
                    question_type=request.question_type,
                    num_questions=current_chunk_size,
                    topic=request.topic,
                    index_filter=request.index_filter,
                    model=request.model,
                )

                app_logger.info(f"Generating chunk {chunk_num} ({current_chunk_size} questions)...")
                chunk_questions = await self.generate_questions(chunk_request, llm)
                all_questions.extend(chunk_questions)

                remaining -= current_chunk_size
                chunk_num += 1

            app_logger.info(f"Generated all {len(all_questions)} questions from {chunk_num - 1} chunks")
            return all_questions

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

                        # Strategy 3: Process character by character to escape backslashes properly
                        try:
                            # Build a properly escaped string
                            result = []
                            i = 0
                            while i < len(json_str):
                                if json_str[i] == '\\':
                                    # Look ahead to see what follows the backslash
                                    if i + 1 < len(json_str):
                                        next_char = json_str[i + 1]
                                        # Valid JSON escape sequences
                                        if next_char in '"\\/bfnrtu':
                                            result.append(json_str[i:i+2])
                                            i += 2
                                        else:
                                            # Invalid escape - double the backslash
                                            result.append('\\\\')
                                            result.append(next_char)
                                            i += 2
                                    else:
                                        result.append('\\\\')
                                        i += 1
                                else:
                                    result.append(json_str[i])
                                    i += 1
                            json_str_cleaned = ''.join(result)
                            parsed = json.loads(json_str_cleaned)
                        except (json.JSONDecodeError, re.error, ValueError) as e3:
                            parse_errors.append(f"Character-by-character escape: {e3}")

                            # Strategy 4: Fallback - try to extract valid JSON objects manually
                            try:
                                # Find all {...} patterns and try to parse them individually
                                import ast
                                # Try a very lenient approach - just get the structure
                                json_str_fixed = json_str.replace("'", '"')  # Single to double quotes
                                # Remove control characters
                                json_str_fixed = ''.join(c for c in json_str_fixed if ord(c) >= 32 or c in '\n\t\r')
                                parsed = json.loads(json_str_fixed)
                            except (json.JSONDecodeError, re.error, ValueError) as e4:
                                parse_errors.append(f"Manual structure parse: {e4}")
                
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
        
        return questions  # Return all parsed questions (no artificial limit)
