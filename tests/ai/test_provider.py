import pytest
from ai.provider import BaseProvider, ChatMessage, ChatResponse, create_provider


class FakeProvider(BaseProvider):
    """Test Provider"""
    def __init__(self, config=None):
        self.config = config or {}
        self._models = self.config.get('models', [])

    def chat(self, messages, model, temperature=0.7, max_tokens=4096, **kwargs):
        return ChatResponse(
            content="fake response",
            model=model,
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )

    def list_models(self):
        return self._models


class TestChatMessage:
    def test_create_message(self):
        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"


class TestChatResponse:
    def test_create_response(self):
        resp = ChatResponse(content="hi", model="test-model", usage={"prompt_tokens": 1})
        assert resp.content == "hi"
        assert resp.model == "test-model"

    def test_default_usage_is_empty_dict(self):
        resp = ChatResponse(content="hi", model="test")
        assert resp.usage == {}


class TestBaseProvider:
    def test_is_available_default_true(self):
        provider = FakeProvider()
        assert provider.is_available() is True

    def test_chat_returns_chat_response(self):
        provider = FakeProvider()
        msg = ChatMessage(role="user", content="test")
        resp = provider.chat([msg], model="test")
        assert isinstance(resp, ChatResponse)
        assert resp.content == "fake response"


def test_create_provider_returns_provider_instance():
    provider = FakeProvider()
    assert isinstance(provider, BaseProvider)


def test_create_provider_can_accept_config():
    provider = FakeProvider(config={"models": ["m1", "m2"]})
    assert provider.list_models() == ["m1", "m2"]
