from unittest.mock import patch, MagicMock
from ai.provider import ContentBlock, ChatMessage
from ai.openai_provider import OpenAIProvider


class TestOpenAIProvider:
    @patch('ai.openai_provider.OpenAI')
    def test_chat_sends_messages_to_sdk(self, MockOpenAI):
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = 'Hello from GPT'
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        mock_completion.model = 'gpt-4o'
        mock_completion.usage = MagicMock(prompt_tokens=20, completion_tokens=10)
        mock_client.chat.completions.create.return_value = mock_completion
        MockOpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key='sk-test')
        messages = [ChatMessage(role='user', content='Say hi')]
        resp = provider.chat(messages, model='gpt-4o', temperature=0.5, max_tokens=1024)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs['model'] == 'gpt-4o'
        assert call_kwargs['max_tokens'] == 1024
        assert call_kwargs['messages'] == [{'role': 'user', 'content': 'Say hi'}]

        assert resp.content == 'Hello from GPT'
        assert resp.model == 'gpt-4o'

    def test_list_models_returns_configured_models(self):
        provider = OpenAIProvider(api_key='sk-test', models=['gpt-4o', 'gpt-4o-mini'])
        assert provider.list_models() == ['gpt-4o', 'gpt-4o-mini']

    @patch('ai.openai_provider.OpenAI')
    def test_is_available_true(self, MockOpenAI):
        MockOpenAI.return_value = MagicMock()
        provider = OpenAIProvider(api_key='sk-test')
        assert provider.is_available() is True

    @patch('ai.openai_provider.OpenAI')
    def test_is_available_false_on_error(self, MockOpenAI):
        MockOpenAI.side_effect = Exception('Bad key')
        provider = OpenAIProvider(api_key='sk-test')
        assert provider.is_available() is False

    @patch('ai.openai_provider.OpenAI')
    def test_chat_sends_multimodal_messages(self, MockOpenAI):
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = 'I see an image'
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        mock_completion.model = 'gpt-4o'
        mock_completion.usage = MagicMock(prompt_tokens=30, completion_tokens=15)
        mock_client.chat.completions.create.return_value = mock_completion
        MockOpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key='sk-test')
        messages = [
            ChatMessage.multimodal("user", [
                ContentBlock(type="text", text="Describe this image"),
                ContentBlock(type="image_url", image_url={"url": "data:image/png;base64,abc123"}),
            ])
        ]
        resp = provider.chat(messages, model='gpt-4o')

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        sent_messages = call_kwargs['messages']
        assert len(sent_messages) == 1
        assert sent_messages[0]['role'] == 'user'
        assert isinstance(sent_messages[0]['content'], list)
        assert sent_messages[0]['content'][0] == {'type': 'text', 'text': 'Describe this image'}
        assert sent_messages[0]['content'][1] == {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,abc123'}}
        assert resp.content == 'I see an image'
