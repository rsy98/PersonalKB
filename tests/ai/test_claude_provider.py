from unittest.mock import patch, MagicMock
from ai.provider import ChatMessage, ChatResponse
from ai.claude_provider import ClaudeProvider


class TestClaudeProvider:
    @patch('ai.claude_provider.Anthropic')
    def test_chat_sends_messages_to_sdk(self, MockAnthropic):
        mock_client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='Hello from Claude')]
        mock_msg.model = 'claude-sonnet-4-6'
        mock_msg.usage = MagicMock(input_tokens=15, output_tokens=8)
        mock_client.messages.create.return_value = mock_msg
        MockAnthropic.return_value = mock_client

        provider = ClaudeProvider(api_key='sk-ant-test')
        messages = [ChatMessage(role='user', content='Say hi')]
        resp = provider.chat(messages, model='claude-sonnet-4-6', temperature=0.5, max_tokens=1024)

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs['model'] == 'claude-sonnet-4-6'
        assert call_kwargs['max_tokens'] == 1024
        assert call_kwargs['temperature'] == 0.5
        assert call_kwargs['messages'] == [{'role': 'user', 'content': 'Say hi'}]

        assert resp.content == 'Hello from Claude'
        assert resp.model == 'claude-sonnet-4-6'
        assert resp.usage == {'input_tokens': 15, 'output_tokens': 8}

    @patch('ai.claude_provider.Anthropic')
    def test_chat_extracts_system_message(self, MockAnthropic):
        mock_client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='Response')]
        mock_msg.model = 'claude-opus-4-7'
        mock_msg.usage = MagicMock(input_tokens=5, output_tokens=3)
        mock_client.messages.create.return_value = mock_msg
        MockAnthropic.return_value = mock_client

        provider = ClaudeProvider(api_key='sk-test')
        messages = [
            ChatMessage(role='system', content='You are helpful'),
            ChatMessage(role='user', content='Hello'),
        ]
        resp = provider.chat(messages, model='claude-opus-4-7')

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs['system'] == 'You are helpful'
        assert call_kwargs['messages'] == [{'role': 'user', 'content': 'Hello'}]

    def test_list_models_returns_configured_models(self):
        provider = ClaudeProvider(api_key='sk-test', models=['claude-opus-4-7', 'claude-haiku-4-5'])
        assert provider.list_models() == ['claude-opus-4-7', 'claude-haiku-4-5']

    @patch('ai.claude_provider.Anthropic')
    def test_is_available_returns_true_when_sdk_works(self, MockAnthropic):
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client

        provider = ClaudeProvider(api_key='sk-test')
        assert provider.is_available() is True

    @patch('ai.claude_provider.Anthropic')
    def test_is_available_returns_false_on_error(self, MockAnthropic):
        MockAnthropic.side_effect = Exception('Connection failed')

        provider = ClaudeProvider(api_key='sk-test')
        assert provider.is_available() is False
