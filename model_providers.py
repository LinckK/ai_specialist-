"""
Model provider abstraction for supporting multiple AI models.
"""

from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
import os
import litellm

class ModelProvider(ABC):
    """Abstract base class for model providers."""
    
    @abstractmethod
    def get_api_key(self) -> Optional[str]:
        """Get API key for this provider."""
        pass
    
    @abstractmethod
    def get_model_name(self) -> str:
        """Get the litellm model name."""
        pass
    
    def completion(self, messages: list, tools: list = None, **kwargs) -> Any:
        """Make a completion request using litellm."""
        api_key = self.get_api_key()
        if not api_key:
            raise ValueError(f"API key not configured for {self.__class__.__name__}")
        
        return litellm.completion(
            model=self.get_model_name(),
            messages=messages,
            tools=tools,
            api_key=api_key,
            **kwargs
        )


class GeminiProvider(ModelProvider):
    """Provider for Google Gemini models."""
    
    def __init__(self, model_name: str = "gemini/gemini-3-flash-001", api_key: Optional[str] = None):
        self.model_name = model_name
        self._api_key = api_key
    
    def get_api_key(self) -> Optional[str]:
        if self._api_key:
            return self._api_key
        return os.getenv("GEMINIFLASH_API_KEY") or os.getenv("GEMINI_API_KEY")
    
    def get_model_name(self) -> str:
        return self.model_name


class ClaudeProvider(ModelProvider):
    """Provider for Anthropic Claude models."""
    
    def __init__(self, model_name: str = "claude-3-haiku-20240307", api_key: Optional[str] = None):
        self.model_name = model_name
        self._api_key = api_key
    
    def get_api_key(self) -> Optional[str]:
        if self._api_key:
            return self._api_key
        return os.getenv("ANTHROPIC_API_KEY") or os.getenv("CLAUDE_API_KEY")
    
    def get_model_name(self) -> str:
        return self.model_name


class OpenAIProvider(ModelProvider):
    """Provider for OpenAI models."""
    
    def __init__(self, model_name: str = "gpt-4", api_key: Optional[str] = None):
        self.model_name = model_name
        self._api_key = api_key
    
    def get_api_key(self) -> Optional[str]:
        if self._api_key:
            return self._api_key
        return os.getenv("OPENAI_API_KEY")
    
    def get_model_name(self) -> str:
        return self.model_name


def get_provider_for_model(model_name: str, api_key: Optional[str] = None) -> ModelProvider:
    """
    Get the appropriate provider for a given model name.
    
    Args:
        model_name: Litellm model name (e.g., "gemini/gemini-2.5-flash-lite", "claude-3-haiku-20240307")
        api_key: Optional API key (overrides environment variable)
        
    Returns:
        ModelProvider instance
    """
    if model_name.startswith("gemini/"):
        return GeminiProvider(model_name, api_key)
    elif model_name.startswith("claude-") or "claude" in model_name.lower():
        return ClaudeProvider(model_name, api_key)
    elif model_name.startswith("gpt-") or "openai" in model_name.lower():
        return OpenAIProvider(model_name, api_key)
    else:
        # Default to Gemini if unknown
        return GeminiProvider(model_name, api_key)


# Available models list
AVAILABLE_MODELS = {
    "gemini": [
        "gemini/gemini-3-pro-preview",
        "gemini/gemini-3-flash-001",
    ],
    "claude": [
        "claude-3-haiku-20240307",
        "claude-3-sonnet-20240229",
        "claude-3-opus-20240229",
    ],
    "openai": [
        "gpt-4",
        "gpt-4-turbo",
        "gpt-3.5-turbo",
    ],
}

def list_available_models() -> Dict[str, list]:
    """List all available models by provider."""
    return AVAILABLE_MODELS.copy()

