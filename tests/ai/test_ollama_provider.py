import json
from unittest.mock import patch, MagicMock
from ai.provider import ChatMessage, ChatResponse, ContentBlock
from ai.ollama_provider import OllamaProvider


class TestOllamaProvider:
    @patch('ai.ollama_provider.requests.post')
    def test_chat_sends_correct_payload(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'message': {'content': 'Hello'},
            'model': 'deepseek-r1:8b',
            'eval_count': 50,
            'prompt_eval_count': 10,
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        provider = OllamaProvider(base_url='http://localhost:11434')
        messages = [ChatMessage(role='user', content='hello')]
        resp = provider.chat(messages, model='deepseek-r1:8b', temperature=0.3)

        call_args = mock_post.call_args
        assert call_args[0][0] == 'http://localhost:11434/api/chat'

        payload = call_args[1]['json']
        assert payload['model'] == 'deepseek-r1:8b'
        assert payload['stream'] is False
        assert payload['options']['temperature'] == 0.3
        assert payload['messages'][0]['role'] == 'user'
        assert payload['messages'][0]['content'] == 'hello'

        assert resp.content == 'Hello'
        assert resp.model == 'deepseek-r1:8b'

    @patch('ai.ollama_provider.requests.get')
    def test_list_models_returns_model_names(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'models': [
                {'name': 'deepseek-r1:8b'},
                {'name': 'qwen2.5:7b'},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = OllamaProvider(base_url='http://localhost:11434')
        models = provider.list_models()

        assert models == ['deepseek-r1:8b', 'qwen2.5:7b']

    @patch('ai.ollama_provider.requests.get')
    def test_is_available_returns_true_when_ollama_running(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = OllamaProvider(base_url='http://localhost:11434')
        assert provider.is_available() is True

    @patch('ai.ollama_provider.requests.get')
    def test_is_available_returns_false_when_ollama_down(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError()

        provider = OllamaProvider(base_url='http://localhost:11434')
        assert provider.is_available() is False


class TestOllamaMultimodal:
    @patch('ai.ollama_provider.requests')
    def test_chat_sends_images_field_for_multimodal(self, mock_requests):
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            'message': {'content': 'I see a cat'},
            'model': 'llava:latest',
            'prompt_eval_count': 10,
            'eval_count': 5,
        }
        mock_requests.post.return_value = mock_resp

        provider = OllamaProvider()
        messages = [
            ChatMessage.multimodal("user", [
                ContentBlock(type="text", text="What is in this image?"),
                ContentBlock(type="image_url", image_url={"url": "data:image/png;base64,iVBORw0KGgo"}),
            ])
        ]
        resp = provider.chat(messages, model='llava:latest')

        call_kwargs = mock_requests.post.call_args
        payload = call_kwargs[1]['json']
        assert payload['messages'][0]['content'] == 'What is in this image?'
        assert 'images' in payload['messages'][0]
        assert payload['messages'][0]['images'] == ['iVBORw0KGgo']
        assert resp.content == 'I see a cat'
