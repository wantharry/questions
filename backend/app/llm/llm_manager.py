"""
LLM Manager - Factory for creating pluggable LLM instances.
"""
from typing import Optional
from app.config import settings
from app.llm.base_llm import BaseLLM
from app.llm.ollama_llm import OllamaLLM
from app.llm.openai_llm import OpenAILLM
from app.utils.logger import app_logger


class LLMManager:
    """Factory for creating and managing LLM instances."""
    
    _instance: Optional[BaseLLM] = None
    
    @classmethod
    def get_llm(cls, provider: Optional[str] = None) -> BaseLLM:
        """
        Get or create an LLM instance based on configuration.
        
        Args:
            provider: Override the configured provider (ollama, openai, llama_cpp, vllm)
        
        Returns:
            BaseLLM instance
        """
        if cls._instance is not None:
            return cls._instance
        
        provider = provider or settings.llm_provider
        
        app_logger.info(f"Initializing LLM provider: {provider}")
        
        if provider == "ollama":
            cls._instance = OllamaLLM(
                model_name=settings.llm_model,
                base_url=settings.llm_base_url,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                timeout=settings.llm_timeout,
            )
        
        elif provider in ["openai", "vllm"]:
            if not settings.openai_api_key:
                raise ValueError(f"{provider} provider requires OPENAI_API_KEY")
            
            base_url = settings.openai_base_url or "https://api.openai.com/v1"
            cls._instance = OpenAILLM(
                model_name=settings.llm_model,
                api_key=settings.openai_api_key,
                base_url=base_url,
                temperature=settings.llm_temperature,
                max_tokens=settings.llm_max_tokens,
                timeout=settings.llm_timeout,
            )
        
        elif provider == "llama_cpp":
            # TODO: Implement llama.cpp provider
            raise NotImplementedError("llama.cpp provider not yet implemented")
        
        else:
            raise ValueError(f"Unknown LLM provider: {provider}")
        
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset the LLM instance (useful for switching providers)."""
        if cls._instance:
            if hasattr(cls._instance, 'close'):
                import asyncio
                try:
                    loop = asyncio.get_running_loop()
                    loop.create_task(cls._instance.close())
                except RuntimeError:
                    asyncio.run(cls._instance.close())
        cls._instance = None
    
    @classmethod
    async def health_check(cls) -> bool:
        """Check if the current LLM is available."""
        try:
            llm = cls.get_llm()
            return await llm.is_available()
        except Exception as e:
            app_logger.error(f"LLM health check failed: {e}")
            return False
