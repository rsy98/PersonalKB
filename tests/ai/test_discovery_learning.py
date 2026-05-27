import json
from unittest.mock import MagicMock
from ai.provider import ChatResponse
from ai.service import AIService
from ai.config import AIConfig, ProviderConfig


def make_config():
    return AIConfig(
        default_provider='test',
        providers={'test': ProviderConfig(type='test', api_key='')},
        models={'test': ['test-model']},
        defaults={
            'discover_relationships': {'provider': 'test', 'model': 'test-model'},
            'discover_gaps': {'provider': 'test', 'model': 'test-model'},
            'generate_learning_path': {'provider': 'test', 'model': 'test-model'},
            'optimize_review_plan': {'provider': 'test', 'model': 'test-model'},
        },
    )


def make_mock_provider(content):
    provider = MagicMock()
    provider.chat.return_value = ChatResponse(
        content=content, model='test-model', usage={},
    )
    provider.is_available.return_value = True
    return provider


class TestParseJsonResponse:

    def test_parses_valid_json_dict(self):
        config = make_config()
        service = AIService(config)
        result = service._parse_json_response(
            {'content': '{"a": 1, "b": "hello"}', 'model': 'm', 'provider': 'p'}
        )
        assert result['a'] == 1
        assert result['b'] == 'hello'
        assert result['model'] == 'm'

    def test_wraps_json_array_in_items(self):
        config = make_config()
        service = AIService(config)
        result = service._parse_json_response(
            {'content': '[{"id": 1}, {"id": 2}]', 'model': 'm', 'provider': 'p'}
        )
        assert 'items' in result
        assert len(result['items']) == 2
        assert result['model'] == 'm'

    def test_handles_code_fenced_json(self):
        config = make_config()
        service = AIService(config)
        result = service._parse_json_response(
            {'content': '```json\n{"x": 42}\n```', 'model': 'm', 'provider': 'p'}
        )
        assert result['x'] == 42

    def test_falls_back_on_invalid_json(self):
        config = make_config()
        service = AIService(config)
        result = service._parse_json_response(
            {'content': 'not valid json at all', 'model': 'm', 'provider': 'p'}
        )
        assert 'error' in result
        assert result['raw'] == 'not valid json at all'

    def test_handles_none_content(self):
        config = make_config()
        service = AIService(config)
        result = service._parse_json_response(
            {'content': None, 'model': 'm', 'provider': 'p'}
        )
        assert 'error' in result


class TestDiscoverRelationships:

    def test_returns_structured_result(self):
        config = make_config()
        service = AIService(config)
        suggestions = json.dumps([
            {'source_id': 1, 'target_id': 5, 'type': 'prerequisite', 'strength': 4,
             'reason': '线性代数是量子力学基础'},
        ])
        provider = make_mock_provider(suggestions)
        service._providers['test'] = provider

        items = [
            {'id': 1, 'title': '线性代数', 'category': '数学', 'tag_names': '数学', 'summary': ''},
            {'id': 5, 'title': '量子力学', 'category': '物理', 'tag_names': '物理', 'summary': ''},
        ]
        result = service.discover_relationships(items)

        assert result['analyzed_count'] == 2
        assert result['suggestion_count'] == 1
        assert result['suggestions'][0]['type'] == 'prerequisite'


class TestDiscoverGaps:

    def test_returns_gaps(self):
        config = make_config()
        service = AIService(config)
        gaps_json = json.dumps([
            {'topic': '热力学第二定律', 'importance': 5,
             'reason': '缺少核心定律阐述', 'suggested_keywords': ['热力学', '熵']},
        ])
        provider = make_mock_provider(gaps_json)
        service._providers['test'] = provider

        items = [{'id': 1, 'title': '物理基础', 'summary': '基础概念'}]
        result = service.discover_gaps('物理', items)

        assert result['category'] == '物理'
        assert result['gap_count'] == 1
        assert result['gaps'][0]['topic'] == '热力学第二定律'


class TestGenerateLearningPath:

    def test_returns_learning_path(self):
        config = make_config()
        service = AIService(config)
        path_json = json.dumps({
            'stages': [{
                'order': 1, 'title': '基础', 'item_ids': [1],
                'concepts': ['概念A'], 'prerequisites': [],
                'estimated_hours': 5, 'mastery_criteria': '理解概念A',
            }],
            'missing_topics': ['进阶主题'],
            'total_estimated_hours': 20,
        })
        provider = make_mock_provider(path_json)
        service._providers['test'] = provider

        items = [{'id': 1, 'title': '基础', 'category': '', 'summary': '', 'understanding_level': 3}]
        result = service.generate_learning_path('学习目标', items)

        assert result['goal'] == '学习目标'
        assert len(result['stages']) == 1
        assert result['total_estimated_hours'] == 20


class TestOptimizeReviewPlan:

    def test_returns_review_plan(self):
        config = make_config()
        service = AIService(config)
        plan_json = json.dumps({
            'daily_plan': [{
                'date': '2026-05-28',
                'items': [{'id': 1, 'priority': 1, 'reason': '间隔到期'}],
                'total': 1,
            }],
            'max_daily': 6,
            'strategy_notes': '合理安排',
        })
        provider = make_mock_provider(plan_json)
        service._providers['test'] = provider

        items = [{'id': 1, 'title': '条目', 'importance_level': 3,
                  'understanding_level': 3, 'interval_days': 1, 'ease_factor': 2.5}]
        result = service.optimize_review_plan(items, days=3)

        assert len(result['daily_plan']) == 1
        assert result['max_daily'] == 6


class TestAPIRoutes:

    def test_discover_gaps_no_category_returns_400(self):
        from web import create_app
        app = create_app()
        client = app.test_client()
        resp = client.post('/api/ai/discover/gaps', json={})
        assert resp.status_code == 400

    def test_learning_path_no_goal_returns_400(self):
        from web import create_app
        app = create_app()
        client = app.test_client()
        resp = client.post('/api/ai/learning/path', json={})
        assert resp.status_code == 400

    def test_discover_relationships_route_accepts_post(self):
        from web import create_app
        app = create_app()
        client = app.test_client()
        resp = client.post('/api/ai/discover/relationships', json={'scope': 'all'})
        assert resp.status_code == 200
