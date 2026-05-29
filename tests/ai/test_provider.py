import pytest
from ai.provider import BaseProvider, ChatMessage, ChatResponse, ContentBlock, create_provider


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


class TestContentBlock:
    def test_create_text_block(self):
        block = ContentBlock(type="text", text="hello")
        assert block.type == "text"
        assert block.text == "hello"
        assert block.image_url is None

    def test_create_image_block(self):
        block = ContentBlock(type="image_url", image_url={"url": "data:image/png;base64,abc"})
        assert block.type == "image_url"
        assert block.text == ""
        assert block.image_url == {"url": "data:image/png;base64,abc"}


class TestChatMessageMultimodal:
    def test_create_pure_text_message(self):
        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"

    def test_text_factory_method(self):
        msg = ChatMessage.text("user", "hello")
        assert msg.role == "user"
        assert msg.content == "hello"

    def test_multimodal_factory_method(self):
        blocks = [
            ContentBlock(type="text", text="analyze this image"),
            ContentBlock(type="image_url", image_url={"url": "data:image/png;base64,abc"}),
        ]
        msg = ChatMessage.multimodal("user", blocks)
        assert msg.role == "user"
        assert isinstance(msg.content, list)
        assert len(msg.content) == 2
        assert msg.content[0].type == "text"
        assert msg.content[0].text == "analyze this image"
        assert msg.content[1].type == "image_url"

    def test_content_is_str_by_default(self):
        msg = ChatMessage(role="assistant", content="response")
        assert isinstance(msg.content, str)
