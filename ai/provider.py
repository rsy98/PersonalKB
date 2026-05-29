from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Optional, Union


@dataclass
class ContentBlock:
    """A multimodal content block - text or image."""
    type: str
    text: str = ""
    image_url: Optional[dict] = field(default=None)


@dataclass
class ChatMessage:
    role: str
    content: Union[str, list[ContentBlock]]

    @staticmethod
    def text(role: str, text: str) -> "ChatMessage":
        """Create a plain-text message."""
        return ChatMessage(role=role, content=text)

    @staticmethod
    def multimodal(role: str, blocks: list[ContentBlock]) -> "ChatMessage":
        """Create a multimodal message from ContentBlocks."""
        return ChatMessage(role=role, content=blocks)


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
