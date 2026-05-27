from unittest.mock import MagicMock
from ai.provider import ChatMessage, ChatResponse
from ai.service import AIService
from ai.config import AIConfig, ProviderConfig


def make_config():
    return AIConfig(
        default_provider='test',
        providers={
            'test': ProviderConfig(type='test', api_key=''),
        },
        models={
            'test': ['test-model'],
        },
        defaults={
            'analyze': {'provider': 'test', 'model': 'test-model'},
            'chat': {'provider': 'test', 'model': 'test-model'},
        },
    )


def make_mock_provider():
    provider = MagicMock()
    provider.chat.return_value = ChatResponse(
        content='mock response',
        model='test-model',
        usage={},
    )
    provider.list_models.return_value = ['test-model']
    provider.is_available.return_value = True
    return provider


class TestListProviders:
    def test_returns_provider_info(self):
        config = make_config()
        service = AIService(config)
        service._providers['test'] = make_mock_provider()

        result = service.list_providers()
        assert len(result) == 1
        assert result[0]['name'] == 'test'
        assert result[0]['available'] is True
        assert result[0]['models'] == ['test-model']


class TestGetDefault:
    def test_returns_default_provider_and_model(self):
        config = make_config()
        service = AIService(config)
        default = service.get_default('analyze')
        assert default == {'provider': 'test', 'model': 'test-model'}

    def test_returns_empty_for_unknown_capability(self):
        config = make_config()
        service = AIService(config)
        default = service.get_default('nonexistent')
        assert default == {}


class TestExecute:
    def test_execute_uses_default_when_not_specified(self):
        config = make_config()
        service = AIService(config)
        provider = make_mock_provider()
        service._providers['test'] = provider

        result = service.execute('analyze', {'title': 'X', 'content': 'Y', 'category': 'Cat', 'tags': 'tag1'})
        provider.chat.assert_called_once()
        assert result is not None
        assert 'content' in result


class TestAnalyzeKnowledgeItem:
    def test_calls_chat_with_analyze_prompt(self):
        config = make_config()
        service = AIService(config)
        provider = make_mock_provider()
        service._providers['test'] = provider

        result = service.analyze_knowledge_item(
            title='Test', content='Content', tags=['tag1'], category='Tech'
        )
        provider.chat.assert_called_once()
        call_args = provider.chat.call_args
        # assert keyword arguments are used
        messages = call_args.kwargs.get('messages') or call_args.args[0]
        assert len(messages) >= 2
        assert messages[0].role == 'system'
        assert 'Test' in messages[1].content
        assert 'Content' in messages[1].content


class TestGenerateQuestions:
    def test_calls_chat_with_question_prompt(self):
        config = make_config()
        service = AIService(config)
        provider = make_mock_provider()
        service._providers['test'] = provider

        result = service.generate_questions(content='Python basics')
        provider.chat.assert_called_once()
        call_args = provider.chat.call_args
        messages = call_args.kwargs.get('messages') or call_args.args[0]
        assert messages[0].role == 'system'


class TestImproveWriting:
    def test_returns_improved_text(self):
        config = make_config()
        service = AIService(config)
        provider = make_mock_provider()
        provider.chat.return_value = ChatResponse(
            content='Improved text version',
            model='test-model',
            usage={},
        )
        service._providers['test'] = provider

        result = service.improve_writing(content='original text')
        assert result == 'Improved text version'

    def test_falls_back_to_original_on_error(self):
        config = make_config()
        service = AIService(config)
        provider = make_mock_provider()
        provider.chat.side_effect = Exception('API error')
        service._providers['test'] = provider

        result = service.improve_writing(content='original text')
        assert result == 'original text'


class TestChatWithKnowledge:
    def test_includes_context_in_prompt(self):
        config = make_config()
        service = AIService(config)
        provider = make_mock_provider()
        service._providers['test'] = provider

        result = service.chat_with_knowledge(
            question='What is X?',
            context_items=[{'title': 'X topic', 'content': 'X is a letter'}],
        )
        provider.chat.assert_called_once()
        call_args = provider.chat.call_args
        messages = call_args.kwargs.get('messages') or call_args.args[0]
        user_msg = messages[1].content
        assert 'What is X?' in user_msg
        assert 'X topic' in user_msg

    def test_includes_chat_history_when_provided(self):
        config = make_config()
        service = AIService(config)
        provider = make_mock_provider()
        service._providers['test'] = provider

        history = [
            {'role': 'user', 'content': 'previous question'},
            {'role': 'assistant', 'content': 'previous answer'},
        ]
        service.chat_with_knowledge(
            question='follow up',
            context_items=[],
            chat_history=history,
        )
        call_args = provider.chat.call_args
        messages = call_args.kwargs.get('messages') or call_args.args[0]
        # Chat history is embedded in the user message context, not as separate messages.
        # messages[0] is system, messages[1] is user.
        assert len(messages) == 2
        assert messages[0].role == 'system'
        assert 'previous question' in messages[1].content
        assert 'previous answer' in messages[1].content
