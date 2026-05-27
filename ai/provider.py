from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    role: str      # system / user / assistant
    content: str


@dataclass
class ChatResponse:
    content: str
    model: str
    usage: dict = field(default_factory=dict)


class BaseProvider(ABC):
    """Base interface for all AI providers"""

    @abstractmethod
    def chat(self, messages: list[ChatMessage], model: str,
             temperature: float = 0.7, max_tokens: int = 4096, **kwargs) -> ChatResponse:
        """Send a chat request, return unified response"""

    @abstractmethod
    def list_models(self) -> list[str]:
        """Return list of available model names for this provider"""

    def is_available(self) -> bool:
        """Health check, subclasses may override"""
        return True


def create_provider(provider_type: str, config_obj) -> BaseProvider:
    """Factory function: creates a Provider instance by type string.
    Real implementation is in __init__.py, this is a placeholder until Task 7.
    """
    raise NotImplementedError(f"Provider type '{provider_type}' not registered")
