import json
from unittest.mock import MagicMock
from ai.provider import ChatMessage, ChatResponse
from ai.service import AIService
from ai.config import AIConfig, ProviderConfig


def make_config():
    return AIConfig(
        default_provider='test',
        providers={'test': ProviderConfig(type='test', api_key='')},
        models={'test': ['test-model']},
        defaults={'extract': {'provider': 'test', 'model': 'test-model'}},
    )


def make_mock_provider(content):
    provider = MagicMock()
    provider.chat.return_value = ChatResponse(
        content=content, model='test-model', usage={},
    )
    provider.is_available.return_value = True
    return provider


class TestExtractKnowledgeItem:

    def test_extracts_valid_json(self):
        config = make_config()
        service = AIService(config)
        json_content = json.dumps({
            'title': '量子力学入门',
            'content': '量子力学是研究微观粒子运动的物理学分支。',
            'summary': '量子力学基础概念介绍',
            'tags': ['物理', '量子', '科学'],
            'category': '物理',
        }, ensure_ascii=False)
        provider = make_mock_provider(json_content)
        service._providers['test'] = provider

        result = service.extract_knowledge_item('some source text about quantum mechanics')

        assert result['title'] == '量子力学入门'
        assert result['content'] == '量子力学是研究微观粒子运动的物理学分支。'
        assert result['summary'] == '量子力学基础概念介绍'
        assert result['tags'] == ['物理', '量子', '科学']
        assert result['category'] == '物理'
        assert result['model'] == 'test-model'
        assert result['provider'] == 'test'

    def test_extracts_json_with_code_fence(self):
        config = make_config()
        service = AIService(config)
        json_content = '```json\n' + json.dumps({
            'title': 'Test Title',
            'content': 'Test Content',
            'summary': 'Test Summary',
            'tags': ['tag1'],
            'category': 'Cat',
        }, ensure_ascii=False) + '\n```'
        provider = make_mock_provider(json_content)
        service._providers['test'] = provider

        result = service.extract_knowledge_item('source text')

        assert result['title'] == 'Test Title'
        assert result['content'] == 'Test Content'

    def test_falls_back_on_invalid_json(self):
        config = make_config()
        service = AIService(config)
        provider = make_mock_provider('Invalid response, not JSON at all.')
        service._providers['test'] = provider

        result = service.extract_knowledge_item('source text')

        assert result['title'] == ''
        assert result['content'] == 'Invalid response, not JSON at all.'
        assert result['summary'] == ''
        assert result['tags'] == []
        assert result['category'] == '未分类'

    def test_truncates_source_to_4000_chars(self):
        config = make_config()
        service = AIService(config)
        provider = make_mock_provider(json.dumps({'title': 'T', 'content': 'C', 'summary': 'S', 'tags': [], 'category': 'Cat'}))
        service._providers['test'] = provider

        long_text = 'x' * 5000
        service.extract_knowledge_item(long_text)

        call_args = provider.chat.call_args
        messages = call_args.kwargs.get('messages') or call_args.args[0]
        user_msg = messages[1].content
        assert len(long_text) > 4000
        assert 'x' * 4000 in user_msg

    def test_calls_chat_with_extract_prompt(self):
        config = make_config()
        service = AIService(config)
        provider = make_mock_provider(json.dumps({'title': 'T', 'content': 'C', 'summary': 'S', 'tags': [], 'category': 'Cat'}))
        service._providers['test'] = provider

        service.extract_knowledge_item('test source')

        provider.chat.assert_called_once()
        call_args = provider.chat.call_args
        messages = call_args.kwargs.get('messages') or call_args.args[0]
        assert len(messages) >= 2
        assert messages[0].role == 'system'
        assert '知识管理专家' in messages[0].content
        assert 'test source' in messages[1].content


class TestExtractAPIRoutes:

    def test_extract_text_empty_returns_400(self):
        from web import create_app
        app = create_app()
        client = app.test_client()
        resp = client.post('/api/ai/extract/text', json={'text': ''})
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data

    def test_extract_url_empty_returns_400(self):
        from web import create_app
        app = create_app()
        client = app.test_client()
        resp = client.post('/api/ai/extract/url', json={'url': ''})
        assert resp.status_code == 400
        data = resp.get_json()
        assert 'error' in data

    def test_extract_file_not_found_returns_404(self):
        from web import create_app
        app = create_app()
        client = app.test_client()
        resp = client.post('/api/ai/extract/file/nonexistent_file.txt')
        assert resp.status_code == 404
        data = resp.get_json()
        assert 'error' in data
