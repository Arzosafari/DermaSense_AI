# app/llm/factories/llm_factory.py
from app.config import settings
from app.llm.adapters.fallback_llm import FallbackLLM
from app.llm.adapters.groq_adapter import GroqLLM
from app.llm.adapters.huggingface_adapter import HuggingFaceLLM
from app.llm.adapters.lmstudio_adapter import LMStudioLLM
from app.llm.adapters.ollama_adapter import OllamaLLM


class LLMFactory:
    """
    LLM factory with Groq-first + Gemma (LM Studio) fallback.
    Set LLM_USE_GROQ_FIRST=false to force local Gemma only.
    """

    PROVIDERS = {
        "groq": GroqLLM,
        "ollama": OllamaLLM,
        "huggingface": HuggingFaceLLM,
        "local": LMStudioLLM,
        "lmstudio": LMStudioLLM,
    }

    @staticmethod
    def for_agent(agent_name: str):
        try:
            provider, model = settings.AGENT_MODEL_MAP[agent_name]
        except KeyError:
            provider, model = "groq", settings.GROQ_MODEL_REASONING

        if settings.LLM_USE_GROQ_FIRST and provider == "groq" and settings.GROQ_API_KEY:
            return FallbackLLM(primary_model=model, fallback_model=settings.LM_STUDIO_MODEL)

        if provider == "groq" and not settings.GROQ_API_KEY:
            return LMStudioLLM(settings.LM_STUDIO_MODEL, host=settings.LM_STUDIO_HOST)

        if provider not in LLMFactory.PROVIDERS:
            return LMStudioLLM(settings.LM_STUDIO_MODEL, host=settings.LM_STUDIO_HOST)

        return LLMFactory.PROVIDERS[provider](model)
