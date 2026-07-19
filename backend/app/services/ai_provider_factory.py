import os

from app.services.ai_provider import AIProvider
from app.services.mock_ai_provider import MockAIProvider
from app.services.structured_llm_provider import StructuredLLMAnalyzeProvider


def get_ai_provider() -> AIProvider:
    provider_name = os.getenv("AI_PROVIDER", "mock").strip().lower()
    if provider_name == "structured_llm":
        return StructuredLLMAnalyzeProvider()
    return MockAIProvider()
