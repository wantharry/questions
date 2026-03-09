"""
Prompt templates for question generation and answering.
"""
from typing import Dict
from app.models import Subject, DifficultyLevel, QuestionType


class PromptTemplates:
    """Collection of prompt templates for various tasks."""
    
    # System prompts
    QUESTION_GENERATOR_SYSTEM = """You are an expert educational content creator specializing in {subject}. 
Your task is to generate high-quality, accurate questions based on the provided context.
Ensure questions are clear, unambiguous, and test understanding rather than rote memorization."""
    
    RAG_ANSWERING_SYSTEM = """You are a knowledgeable assistant. Answer the user's question based on the provided context.
If the context doesn't contain enough information, acknowledge this and provide the best answer you can.
Always cite which parts of the context you used in your answer."""
    
    # Question generation templates
    QUESTION_GENERATION_TEMPLATES: Dict[Subject, Dict[DifficultyLevel, str]] = {
        Subject.MATHEMATICS: {
            DifficultyLevel.EASY: """Based on this mathematical content:

{context}

Generate {num_questions} EASY mathematics questions that test basic understanding and fundamental concepts.
For each question, provide:
1. The question text
2. Multiple choice options (if applicable)
3. The correct answer
4. A clear explanation

Format your response as a JSON array.""",
            
            DifficultyLevel.MEDIUM: """Based on this mathematical content:

{context}

Generate {num_questions} MEDIUM difficulty mathematics questions that require application of concepts and multi-step reasoning.
For each question, provide:
1. The question text
2. Multiple choice options (if applicable)
3. The correct answer
4. A detailed step-by-step explanation

Format your response as a JSON array.""",
            
            DifficultyLevel.HARD: """Based on this mathematical content:

{context}

Generate {num_questions} HARD mathematics questions that require deep understanding, creative problem-solving, and synthesis of multiple concepts.
For each question, provide:
1. The question text
2. Multiple choice options (if applicable)
3. The correct answer
4. A comprehensive explanation with multiple solution approaches where applicable

Format your response as a JSON array.""",
        },
        
        Subject.PHYSICS: {
            DifficultyLevel.EASY: """Based on this physics content:

{context}

Generate {num_questions} EASY physics questions testing fundamental laws, basic definitions, and simple applications.
For each question, provide:
1. The question text
2. Multiple choice options (if applicable)
3. The correct answer with units
4. A clear explanation referencing physical principles

Format your response as a JSON array.""",
            
            DifficultyLevel.MEDIUM: """Based on this physics content:

{context}

Generate {num_questions} MEDIUM difficulty physics questions requiring quantitative problem-solving and understanding of relationships between concepts.
For each question, provide:
1. The question text with all necessary values and units
2. Multiple choice options (if applicable)
3. The correct answer with proper units
4. A step-by-step solution showing equations and reasoning

Format your response as a JSON array.""",
            
            DifficultyLevel.HARD: """Based on this physics content:

{context}

Generate {num_questions} HARD physics questions involving complex scenarios, multiple concepts, and advanced problem-solving.
For each question, provide:
1. The detailed question text
2. Multiple choice options (if applicable)
3. The correct answer with units
4. A comprehensive solution with diagrams descriptions, equations, and physical reasoning

Format your response as a JSON array.""",
        },
        
        Subject.CHEMISTRY: {
            DifficultyLevel.EASY: """Based on this chemistry content:

{context}

Generate {num_questions} EASY chemistry questions testing basic concepts, nomenclature, and fundamental reactions.
For each question, provide:
1. The question text
2. Multiple choice options (if applicable)
3. The correct answer
4. A clear explanation with chemical reasoning

Format your response as a JSON array.""",
            
            DifficultyLevel.MEDIUM: """Based on this chemistry content:

{context}

Generate {num_questions} MEDIUM difficulty chemistry questions requiring understanding of mechanisms, calculations, and conceptual applications.
For each question, provide:
1. The question text with relevant data
2. Multiple choice options (if applicable)
3. The correct answer
4. A detailed solution with chemical equations and reasoning

Format your response as a JSON array.""",
            
            DifficultyLevel.HARD: """Based on this chemistry content:

{context}

Generate {num_questions} HARD chemistry questions involving complex mechanisms, multi-step synthesis, or advanced theoretical concepts.
For each question, provide:
1. The detailed question text
2. Multiple choice options (if applicable)
3. The correct answer
4. A comprehensive explanation with mechanisms, equations, and theoretical background

Format your response as a JSON array.""",
        },
        
        Subject.GENERAL: {
            DifficultyLevel.EASY: """Based on this content:

{context}

Generate {num_questions} EASY questions testing basic comprehension and recall.
For each question, provide:
1. The question text
2. Multiple choice options (if applicable)
3. The correct answer
4. A brief explanation

Format your response as a JSON array.""",
            
            DifficultyLevel.MEDIUM: """Based on this content:

{context}

Generate {num_questions} MEDIUM difficulty questions requiring analysis and application of concepts.
For each question, provide:
1. The question text
2. Multiple choice options (if applicable)
3. The correct answer
4. A detailed explanation

Format your response as a JSON array.""",
            
            DifficultyLevel.HARD: """Based on this content:

{context}

Generate {num_questions} HARD questions requiring synthesis, evaluation, and critical thinking.
For each question, provide:
1. The question text
2. Multiple choice options (if applicable)
3. The correct answer
4. A comprehensive explanation

Format your response as a JSON array.""",
        },
    }
    
    # RAG answering template
    RAG_ANSWER_TEMPLATE = """Context information:
{context}

Question: {question}

Based on the context above, provide a detailed and accurate answer to the question.
If the context contains relevant information, cite it in your response.
If the context is insufficient, state this clearly and provide the best answer you can based on your knowledge."""
    
    @classmethod
    def get_question_prompt(
        cls,
        subject: Subject,
        difficulty: DifficultyLevel,
        context: str,
        num_questions: int = 5,
        question_type: QuestionType = QuestionType.MULTIPLE_CHOICE,
    ) -> tuple[str, str]:
        """
        Get the system and user prompts for question generation.
        
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system_prompt = cls.QUESTION_GENERATOR_SYSTEM.format(subject=subject.value)
        
        user_prompt = cls.QUESTION_GENERATION_TEMPLATES[subject][difficulty].format(
            context=context,
            num_questions=num_questions,
        )
        
        # Add question type specification
        if question_type != QuestionType.MULTIPLE_CHOICE:
            user_prompt += f"\n\nNote: Generate {question_type.value.replace('_', ' ')} questions."
        
        return system_prompt, user_prompt
    
    @classmethod
    def get_answer_prompt(cls, context: str, question: str) -> tuple[str, str]:
        """
        Get the system and user prompts for answering questions.
        
        Returns:
            Tuple of (system_prompt, user_prompt)
        """
        system_prompt = cls.RAG_ANSWERING_SYSTEM
        user_prompt = cls.RAG_ANSWER_TEMPLATE.format(
            context=context,
            question=question,
        )
        return system_prompt, user_prompt
