# AI知识发现 + AI学习规划 实施计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 新增 4 个 AI 能力（关联发现、缺口分析、学习路径、复习优化），融入现有知识图谱/知识管理/复习面板

**Architecture:** 后端新增 4 个 prompt + 4 个 AIService 方法 + 4 个 API 路由（共用 `_parse_json_response()` 解析器）；前端在 3 个面板增加 AI 入口，通过 JS 调用 API 并在面板内渲染结果

**Tech Stack:** Flask Blueprint, SQLite, CSS 变量, 原生 JS fetch, D3.js（复用）

---

## 文件变更总览

```
修改:
  ai/service.py                   # 新增 4 个 prompt + 5 个方法（含 _parse_json_response）
  web/blueprints/ai.py            # 新增 4 个 API 路由
  config/ai.yaml                  # 新增 4 个默认配置
  web/templates/index.html        # 3 个面板各增加 AI 入口
  web/static/css/style.css        # 新增 ~200 行样式
  web/static/js/app.js            # 新增 ~400 行逻辑

新建:
  tests/ai/test_discovery_learning.py  # 测试
```

---

### Task 1: 后端 — Prompts + Methods + _parse_json_response

**Files:**
- Modify: `ai/service.py`

- [ ] **Step 1: 添加 4 个新 prompt 到 PROMPTS 字典**

在 `PROMPTS['extract']` 的 `},` 之后、`}`（PROMPTS 闭合）之前插入：

```python
    'discover_relationships': {
        'system': '你是一个知识图谱专家，擅长发现知识条目之间的隐藏关联。',
        'user': (
            '以下是知识库中的一些条目。请发现它们之间未被记录的关联关系（最多10条，宁缺毋滥）。\n\n'
            '{items}\n\n'
            '请返回 JSON 数组（只返回 JSON，不要其他内容）：\n'
            '[{{\n'
            '  "source_id": <源条目ID>,\n'
            '  "target_id": <目标条目ID>,\n'
            '  "type": "prerequisite|extends|related_to|contradicts",\n'
            '  "strength": <1-5>,\n'
            '  "reason": "<一句话解释>"\n'
            '}}]'
        ),
    },
    'discover_gaps': {
        'system': '你是一个知识体系专家，擅长识别知识盲区和缺口。',
        'user': (
            '我正在构建"{category}"领域的知识库。以下是已有条目：\n\n'
            '{items}\n\n'
            '请分析这个知识体系，找出重要的缺失主题（3-6个，宁缺毋滥）。返回 JSON：\n'
            '[{{\n'
            '  "topic": "建议添加的主题",\n'
            '  "importance": <1-5>,\n'
            '  "reason": "为什么这个主题重要且缺失",\n'
            '  "suggested_keywords": ["关键词1", "关键词2"]\n'
            '}}]'
        ),
    },
    'generate_learning_path': {
        'system': '你是一个学习规划专家，擅长设计循序渐进的知识学习路线。',
        'user': (
            '学习目标：{goal}\n\n'
            '知识库中相关条目：\n{items}\n\n'
            '请设计一条从基础到精通的学习路径（3-6个阶段）。返回 JSON：\n'
            '{{\n'
            '  "stages": [\n'
            '    {{\n'
            '      "order": <序号，从1开始>,\n'
            '      "title": "<阶段名称>",\n'
            '      "item_ids": [<知识库中已有条目ID>],\n'
            '      "concepts": ["<本阶段应掌握的概念>"],\n'
            '      "prerequisites": ["<前置阶段名称>"],\n'
            '      "estimated_hours": <数字>,\n'
            '      "mastery_criteria": "<如何判断已掌握>"\n'
            '    }}\n'
            '  ],\n'
            '  "missing_topics": ["<知识库中缺少但建议学习的主题>"],\n'
            '  "total_estimated_hours": <总小时数>\n'
            '}}\n\n'
            '原则：从基础到高级，每阶段3-5个概念。item_ids 必须使用上面列出的真实ID。'
        ),
    },
    'optimize_review_plan': {
        'system': '你是一个间隔重复学习专家，擅长个性化复习规划。',
        'user': (
            '以下是当前待复习的知识条目及其历史数据：\n\n'
            '{items}\n\n'
            '请规划未来 {days} 天的复习计划。返回 JSON：\n'
            '{{\n'
            '  "daily_plan": [\n'
            '    {{\n'
            '      "date": "YYYY-MM-DD",\n'
            '      "items": [\n'
            '        {{"id": <条目ID>, "priority": <1-5>, "reason": "<为什么排这个优先级>"}}\n'
            '      ],\n'
            '      "total": <当天总条目数>\n'
            '    }}\n'
            '  ],\n'
            '  "max_daily": <建议每天最大复习量>,\n'
            '  "strategy_notes": "<总体策略说明>"\n'
            '}}\n\n'
            '原则：间隔即将到期 > 已过期 > 未到期；上次评分低的优先巩固；每天总量控制在合理范围。'
        ),
    },
```

- [ ] **Step 2: 在 AIService 类中 `extract_knowledge_item` 方法之后、`get_default` 方法之前添加 `_parse_json_response` 辅助方法**

```python
    def _parse_json_response(self, result: dict) -> dict:
        """解析 AI 返回的 JSON（统一处理 code fence 和解析失败）"""
        try:
            text = result['content'].strip()
            if text.startswith('```'):
                lines = text.split('\n')
                text = '\n'.join(lines[1:])
                if text.rstrip().endswith('```'):
                    text = text.rstrip()[:-3]
            data = json.loads(text)
        except (json.JSONDecodeError, KeyError):
            data = {'error': 'AI 返回格式异常', 'raw': result['content']}
        data['model'] = result['model']
        data['provider'] = result['provider']
        return data
```

- [ ] **Step 3: 在 `_parse_json_response` 方法之后、`get_default` 方法之前添加 4 个业务方法**

```python
    def discover_relationships(self, items: list,
                               provider: str = None, model: str = None) -> dict:
        """发现知识条目间的隐藏关联"""
        items_text = '\n'.join([
            f'ID:{i["id"]} 标题:{i["title"]} 分类:{i.get("category","")} '
            f'标签:{i.get("tag_names","")} 摘要:{i.get("summary","")[:100]}'
            for i in items
        ])
        result = self.execute('discover_relationships', {
            'items': items_text[:4000],
        }, provider=provider, model=model)
        parsed = self._parse_json_response(result)
        suggestions = parsed if isinstance(parsed, list) else parsed.get('suggestions', [])
        if not isinstance(suggestions, list):
            suggestions = []
        return {
            'suggestions': suggestions,
            'analyzed_count': len(items),
            'suggestion_count': len(suggestions),
            'model': result['model'],
            'provider': result['provider'],
        }

    def discover_gaps(self, category: str, items: list,
                      provider: str = None, model: str = None) -> dict:
        """发现知识缺口"""
        items_text = '\n'.join([
            f'- {i["title"]}: {i.get("summary", "")[:80]}'
            for i in items
        ])
        result = self.execute('discover_gaps', {
            'category': category,
            'items': items_text[:3000],
        }, provider=provider, model=model)
        parsed = self._parse_json_response(result)
        gaps = parsed if isinstance(parsed, list) else parsed.get('gaps', [])
        if not isinstance(gaps, list):
            gaps = []
        return {
            'category': category,
            'gaps': gaps,
            'existing_count': len(items),
            'gap_count': len(gaps),
            'model': result['model'],
            'provider': result['provider'],
        }

    def generate_learning_path(self, goal: str, items: list,
                               provider: str = None, model: str = None) -> dict:
        """生成学习路径"""
        items_text = '\n'.join([
            f'ID:{i["id"]} 标题:{i["title"]} 分类:{i.get("category","")} '
            f'摘要:{i.get("summary","")[:100]} 理解程度:{i.get("understanding_level",3)}/5'
            for i in items
        ])
        result = self.execute('generate_learning_path', {
            'goal': goal,
            'items': items_text[:4000],
        }, provider=provider, model=model)
        parsed = self._parse_json_response(result)
        return {
            'goal': goal,
            'stages': parsed.get('stages', []),
            'missing_topics': parsed.get('missing_topics', []),
            'total_estimated_hours': parsed.get('total_estimated_hours', 0),
            'model': result['model'],
            'provider': result['provider'],
        }

    def optimize_review_plan(self, review_items: list, days: int = 7,
                             provider: str = None, model: str = None) -> dict:
        """优化复习计划"""
        items_text = '\n'.join([
            f'ID:{i["id"]} 标题:{i["title"]} 重要性:{i.get("importance_level",3)}/5 '
            f'理解:{i.get("understanding_level",3)}/5 间隔:{i.get("interval_days",0)}天 '
            f'ease:{i.get("ease_factor",2.5):.1f}'
            for i in review_items
        ])
        result = self.execute('optimize_review_plan', {
            'items': items_text[:4000],
            'days': str(days),
        }, provider=provider, model=model)
        parsed = self._parse_json_response(result)
        return {
            'daily_plan': parsed.get('daily_plan', []),
            'max_daily': parsed.get('max_daily', 8),
            'strategy_notes': parsed.get('strategy_notes', ''),
            'model': result['model'],
            'provider': result['provider'],
        }
```

- [ ] **Step 4: 验证语法和导入**

```bash
cd "E:/claude项目/personal_knowledge_mgnt" && PYTHONIOENCODING=utf-8 python -c "
from ai.service import AIService, PROMPTS
for k in ['discover_relationships','discover_gaps','generate_learning_path','optimize_review_plan']:
    print(f'{k}: {\"OK\" if k in PROMPTS else \"MISSING\"}')
svc = AIService.__dict__
for m in ['_parse_json_response','discover_relationships','discover_gaps','generate_learning_path','optimize_review_plan']:
    print(f'method {m}: {\"OK\" if m in svc else \"MISSING\"}')
"
```

Expected: all 8 checks show `OK`

- [ ] **Step 5: Commit**

```bash
git add ai/service.py
git commit -m "feat: add 4 AI prompts and methods for discovery + learning planning"
```

---

### Task 2: 后端 — API 路由

**Files:**
- Modify: `web/blueprints/ai.py`

- [ ] **Step 1: 在文件末尾、`return ai_bp` 之前添加 4 个新路由**

```python
@ai_bp.route('/api/ai/discover/relationships', methods=['POST'])
def api_ai_discover_relationships():
    """AI 发现知识条目间的隐藏关联"""
    try:
        data = request.get_json(silent=True) or {}
        scope = data.get('scope', 'all')
        category = data.get('category', '')
        limit = min(data.get('limit', 30), 50)

        manager = get_manager()
        if scope == 'category' and category:
            all_items = manager.get_items_by_category(category)
        else:
            all_items = manager.search_knowledge('', limit=limit)

        items = all_items[:limit]
        if len(items) < 2:
            return jsonify({'error': '需要至少2个条目才能发现关联'}), 400

        ai_service = get_ai_service()
        result = ai_service.discover_relationships(
            items,
            provider=data.get('provider'),
            model=data.get('model'),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'AI分析失败: {str(e)}'}), 500


@ai_bp.route('/api/ai/discover/gaps', methods=['POST'])
def api_ai_discover_gaps():
    """AI 发现知识缺口"""
    try:
        data = request.get_json(silent=True) or {}
        category = data.get('category', '').strip()
        if not category:
            return jsonify({'error': '请指定分类'}), 400

        manager = get_manager()
        items = manager.get_items_by_category(category)
        if len(items) < 2:
            return jsonify({'error': '该分类条目太少，无法分析缺口'}), 400

        ai_service = get_ai_service()
        result = ai_service.discover_gaps(
            category, items,
            provider=data.get('provider'),
            model=data.get('model'),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'AI分析失败: {str(e)}'}), 500


@ai_bp.route('/api/ai/learning/path', methods=['POST'])
def api_ai_generate_learning_path():
    """AI 生成学习路径"""
    try:
        data = request.get_json(silent=True) or {}
        goal = data.get('goal', '').strip()
        if not goal:
            return jsonify({'error': '请输入学习目标'}), 400

        scope = data.get('scope', 'all')
        category = data.get('category', '')
        manager = get_manager()

        if scope == 'category' and category:
            items = manager.get_items_by_category(category)
        else:
            items = manager.search_knowledge(goal, limit=20)
            if len(items) < 20:
                all_items = manager.search_knowledge('', limit=30)
                existing_ids = {i['id'] for i in items}
                for i in all_items:
                    if i['id'] not in existing_ids:
                        items.append(i)
                        if len(items) >= 30:
                            break

        ai_service = get_ai_service()
        result = ai_service.generate_learning_path(
            goal, items[:30],
            provider=data.get('provider'),
            model=data.get('model'),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'AI分析失败: {str(e)}'}), 500


@ai_bp.route('/api/ai/learning/review-plan', methods=['POST'])
def api_ai_optimize_review_plan():
    """AI 优化复习计划"""
    try:
        data = request.get_json(silent=True) or {}
        days = min(data.get('days', 7), 14)

        manager = get_manager()
        review_items = manager.get_today_reviews()

        if not review_items:
            return jsonify({
                'daily_plan': [],
                'max_daily': 0,
                'strategy_notes': '当前没有待复习条目',
            })

        ai_service = get_ai_service()
        result = ai_service.optimize_review_plan(
            review_items, days=days,
            provider=data.get('provider'),
            model=data.get('model'),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'AI分析失败: {str(e)}'}), 500
```

- [ ] **Step 2: 验证路由注册成功**

```bash
cd "E:/claude项目/personal_knowledge_mgnt" && PYTHONIOENCODING=utf-8 python -c "
from web import create_app
app = create_app()
client = app.test_client()
routes = [
    ('POST', '/api/ai/discover/relationships'),
    ('POST', '/api/ai/discover/gaps'),
    ('POST', '/api/ai/learning/path'),
    ('POST', '/api/ai/learning/review-plan'),
]
for method, route in routes:
    resp = client.post(route, json={})
    print(f'{route}: {resp.status_code} (not 404 = OK)')
"
```

Expected: all return status codes != 404 (4xx is fine, routes are registered)

- [ ] **Step 3: Commit**

```bash
git add web/blueprints/ai.py
git commit -m "feat: add 4 API routes for AI discovery and learning planning"
```

---

### Task 3: 配置文件

**Files:**
- Modify: `config/ai.yaml`

- [ ] **Step 1: 在 defaults 部分添加 4 个新配置**

Edit `config/ai.yaml`，在 `defaults:` 部分的 `extract:` 之后添加：

```yaml
  discover_relationships:
    provider: deepseek
    model: deepseek-v4-flash
  discover_gaps:
    provider: deepseek
    model: deepseek-v4-flash
  generate_learning_path:
    provider: deepseek
    model: deepseek-v4-flash
  optimize_review_plan:
    provider: deepseek
    model: deepseek-v4-flash
```

- [ ] **Step 2: 验证配置加载**

```bash
cd "E:/claude项目/personal_knowledge_mgnt" && PYTHONIOENCODING=utf-8 python -c "
from ai.config import load_config
cfg = load_config('config/ai.yaml')
for k in ['discover_relationships','discover_gaps','generate_learning_path','optimize_review_plan']:
    d = cfg.defaults.get(k, {})
    print(f'{k}: provider={d.get(\"provider\")}, model={d.get(\"model\")}')
"
```

Expected: all 4 show `provider=deepseek, model=deepseek-v4-flash`

- [ ] **Step 3: Commit**

```bash
git add config/ai.yaml
git commit -m "config: add defaults for discovery and learning planning features"
```

---

### Task 4: 测试

**Files:**
- Create: `tests/ai/test_discovery_learning.py`

- [ ] **Step 1: 创建测试文件**

```python
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

    def test_parses_valid_json(self):
        config = make_config()
        service = AIService(config)
        result = service._parse_json_response(
            {'content': '{"a": 1, "b": "hello"}', 'model': 'm', 'provider': 'p'}
        )
        assert result['a'] == 1
        assert result['b'] == 'hello'
        assert result['model'] == 'm'

    def test_parses_code_fenced_json(self):
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

    def test_handles_non_list_response(self):
        config = make_config()
        service = AIService(config)
        # AI might return dict with "suggestions" key or just a list
        provider = make_mock_provider(json.dumps({'suggestions': []}))
        service._providers['test'] = provider
        result = service.discover_relationships([{'id': 1, 'title': 'T', 'category': '', 'tag_names': '', 'summary': ''}])
        assert result['suggestion_count'] == 0


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

    def test_review_plan_no_reviews_returns_empty(self):
        from web import create_app
        app = create_app()
        client = app.test_client()
        resp = client.post('/api/ai/learning/review-plan', json={'days': 3})
        assert resp.status_code == 200
        data = resp.get_json()
        assert 'daily_plan' in data
```

- [ ] **Step 2: 运行新测试确保通过**

```bash
cd "E:/claude项目/personal_knowledge_mgnt" && PYTHONIOENCODING=utf-8 python -m pytest tests/ai/test_discovery_learning.py -v
```

Expected: 10 tests pass

- [ ] **Step 3: 确保已有测试全部通过**

```bash
cd "E:/claude项目/personal_knowledge_mgnt" && PYTHONIOENCODING=utf-8 python -m pytest tests/ -v
```

Expected: all tests pass (existing + 10 new)

- [ ] **Step 4: Commit**

```bash
git add tests/ai/test_discovery_learning.py
git commit -m "test: add tests for AI discovery and learning planning"
```

---

### Task 5: 前端 CSS

**Files:**
- Modify: `web/static/css/style.css`

- [ ] **Step 1: 在 style.css 末尾追加新样式**

```css
/* ============================================
   AI Discovery & Learning Planning
   ============================================ */

/* -- Gap analysis cards -- */
.gap-card {
    background: var(--bg-secondary);
    border: 1px dashed var(--accent);
    border-radius: var(--radius);
    padding: 14px 16px;
    margin-bottom: 10px;
    display: flex;
    align-items: flex-start;
    gap: 12px;
    transition: border-color var(--transition);
}

.gap-card:hover {
    border-color: var(--accent);
    border-style: solid;
}

.gap-card-body {
    flex: 1;
    min-width: 0;
}

.gap-card-topic {
    font-size: 15px;
    font-weight: 600;
    color: var(--text-primary);
    margin-bottom: 4px;
}

.gap-card-reason {
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 6px;
    line-height: 1.5;
}

.gap-card-keywords {
    display: flex;
    flex-wrap: wrap;
    gap: 4px;
}

.gap-card-keywords .kw-tag {
    padding: 2px 8px;
    font-size: 11px;
    background: var(--bg-tertiary);
    border-radius: 10px;
    color: var(--text-secondary);
}

.gap-card-action {
    flex-shrink: 0;
}

/* Importance stars in gap cards */
.gap-importance {
    display: inline-flex;
    gap: 1px;
    margin-left: 8px;
}

.gap-importance .star {
    color: var(--text-tertiary);
    font-size: 11px;
}

.gap-importance .star.filled {
    color: #f0ad4e;
}

/* -- Learning timeline -- */
.learning-timeline {
    position: relative;
    padding-left: 32px;
    margin: 20px 0;
}

.learning-timeline::before {
    content: '';
    position: absolute;
    left: 11px;
    top: 0;
    bottom: 0;
    width: 2px;
    background: var(--border);
}

.timeline-stage {
    position: relative;
    margin-bottom: 24px;
    padding: 16px;
    background: var(--bg-secondary);
    border-radius: var(--radius);
    border: 1px solid var(--border);
}

.timeline-stage::before {
    content: attr(data-order);
    position: absolute;
    left: -28px;
    top: 16px;
    width: 24px;
    height: 24px;
    background: var(--accent);
    color: #fff;
    border-radius: 50%;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 12px;
    font-weight: 700;
}

.timeline-stage-header {
    display: flex;
    align-items: center;
    justify-content: space-between;
    margin-bottom: 8px;
}

.timeline-stage-title {
    font-size: 16px;
    font-weight: 600;
    color: var(--text-primary);
}

.timeline-stage-hours {
    font-size: 12px;
    color: var(--text-tertiary);
    background: var(--bg-tertiary);
    padding: 2px 8px;
    border-radius: 10px;
}

.timeline-concepts {
    display: flex;
    flex-wrap: wrap;
    gap: 6px;
    margin: 8px 0;
}

.timeline-concept {
    padding: 3px 10px;
    background: var(--accent-light);
    color: var(--accent);
    border-radius: 12px;
    font-size: 12px;
}

.timeline-prereqs {
    font-size: 12px;
    color: var(--text-tertiary);
    margin-bottom: 4px;
}

.timeline-items {
    margin-top: 8px;
}

.timeline-item-link {
    display: inline-block;
    padding: 2px 8px;
    margin: 2px;
    font-size: 12px;
    background: var(--bg-primary);
    border: 1px solid var(--border);
    border-radius: 4px;
    color: var(--accent);
    cursor: pointer;
    text-decoration: none;
}

.timeline-item-link:hover {
    background: var(--accent);
    color: #fff;
}

.timeline-item-link.missing {
    border-style: dashed;
    color: var(--text-tertiary);
    cursor: default;
}

.timeline-missing-topics {
    margin-top: 16px;
    padding: 12px;
    background: var(--bg-tertiary);
    border-radius: var(--radius);
}

.timeline-missing-topics h5 {
    font-size: 13px;
    color: var(--text-secondary);
    margin: 0 0 8px 0;
}

/* -- Suggested edges (knowledge graph) -- */
.graph-suggestion-controls {
    display: flex;
    gap: 8px;
    margin-top: 8px;
    padding: 10px 14px;
    background: var(--bg-secondary);
    border: 1px dashed var(--accent);
    border-radius: var(--radius);
    align-items: center;
    font-size: 13px;
    color: var(--text-secondary);
}

.graph-suggestion-controls .suggestion-count {
    font-weight: 700;
    color: var(--accent);
}

/* Dashed edge for suggestions in D3 */
line.suggested-edge {
    stroke: #f0ad4e;
    stroke-opacity: 0.7;
    stroke-dasharray: 6, 3;
    stroke-width: 2;
}

/* Edge tooltip */
.edge-tooltip {
    position: absolute;
    background: var(--bg-secondary);
    border: 1px solid var(--accent);
    border-radius: var(--radius);
    padding: 8px 12px;
    font-size: 12px;
    max-width: 250px;
    pointer-events: none;
    z-index: 100;
    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
}

/* -- Review priority badges -- */
.priority-badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 10px;
    font-size: 11px;
    font-weight: 600;
}

.priority-badge.p1 { background: #e74c3c; color: #fff; }
.priority-badge.p2 { background: #f39c12; color: #fff; }
.priority-badge.p3 { background: #3498db; color: #fff; }
.priority-badge.p4, .priority-badge.p5 { background: var(--bg-tertiary); color: var(--text-secondary); }

.review-ai-controls {
    display: flex;
    align-items: center;
    gap: 8px;
    margin-bottom: 16px;
    padding: 10px 14px;
    background: var(--bg-secondary);
    border-radius: var(--radius);
    font-size: 13px;
    color: var(--text-secondary);
}

/* Review tab bar (inside review panel) */
.review-tab-bar {
    display: flex;
    gap: 0;
    margin-bottom: 16px;
    border-bottom: 1px solid var(--border);
}

.review-tab-btn {
    padding: 8px 20px;
    font-size: 13px;
    font-weight: 500;
    background: transparent;
    border: none;
    color: var(--text-secondary);
    cursor: pointer;
    border-bottom: 2px solid transparent;
    transition: color var(--transition), border-color var(--transition);
}

.review-tab-btn:hover { color: var(--text-primary); }

.review-tab-btn.active {
    color: var(--accent);
    border-bottom-color: var(--accent);
}

/* AI badge indicator */
.ai-badge {
    display: inline-block;
    font-size: 10px;
    font-weight: 700;
    padding: 1px 6px;
    border-radius: 8px;
    background: var(--accent);
    color: #fff;
    margin-left: 4px;
    vertical-align: middle;
    text-transform: uppercase;
}

/* Strategy notes */
.strategy-notes {
    padding: 10px 14px;
    background: var(--bg-secondary);
    border-left: 3px solid var(--accent);
    border-radius: 0 var(--radius) var(--radius) 0;
    font-size: 12px;
    color: var(--text-secondary);
    margin-bottom: 12px;
    line-height: 1.6;
}
```

- [ ] **Step 2: Commit**

```bash
git add web/static/css/style.css
git commit -m "style: add CSS for AI discovery and learning planning UI"
```

---

### Task 6: 前端 HTML

**Files:**
- Modify: `web/templates/index.html`

- [ ] **Step 1: 知识图谱面板 — 添加 AI 关联发现按钮和控制区**

在知识图谱面板的 `<div class="graph-controls">` 中、分类筛选 `</select>` 之后添加：

```html
            <button class="btn btn-outline btn-sm" onclick="discoverRelationships()" id="btnDiscoverRel">
                🤖 AI 发现关联
            </button>
```

在 `<div class="graph-container" id="graphContainer">` 之后添加：

```html
        <div class="graph-suggestion-controls" id="graphSuggestionControls" style="display:none;">
            <span>AI 发现了 <span class="suggestion-count" id="suggestionCount">0</span> 个潜在关联</span>
            <button class="btn btn-primary btn-sm" onclick="adoptAllSuggestions()">全部采纳</button>
            <button class="btn btn-outline btn-sm" onclick="clearSuggestions()">忽略全部</button>
        </div>
```

- [ ] **Step 2: 知识管理面板 — 添加缺口分析容器**

在 `<div id="searchResults">` 之前添加：

```html
        <!-- AI gap analysis results -->
        <div id="gapAnalysis" style="display:none;margin-bottom:16px;"></div>
```

- [ ] **Step 3: 复习面板 — 重构为双 tab（复习计划 + 学习路径）**

将复习面板的 `<div id="reviewContent">` 及其内容替换为：

```html
        <!-- Review sub-tabs -->
        <div class="review-tab-bar">
            <button class="review-tab-btn active" data-review-tab="review-plan" onclick="switchReviewTab('review-plan')">复习计划</button>
            <button class="review-tab-btn" data-review-tab="learning-path" onclick="switchReviewTab('learning-path')">学习路径</button>
        </div>

        <!-- Review Plan sub-panel -->
        <div class="review-sub-panel" id="reviewPlanPanel">
            <div class="review-ai-controls">
                <span>排序方式:</span>
                <button class="btn btn-outline btn-sm" id="btnSortDefault" onclick="switchReviewSort('default')">按日期</button>
                <button class="btn btn-outline btn-sm" id="btnSortAI" onclick="switchReviewSort('ai')">🤖 AI 智能排序</button>
            </div>
            <div class="strategy-notes" id="strategyNotes" style="display:none;"></div>
            <div id="reviewContent">
                <div class="loading"><div class="spinner"></div>加载中...</div>
            </div>
        </div>

        <!-- Learning Path sub-panel -->
        <div class="review-sub-panel" id="learningPathPanel" style="display:none;">
            <div class="ai-input-row" style="margin-bottom:12px;">
                <input type="text" class="form-input" id="learningGoal" placeholder="输入学习目标，如：掌握机器学习基础"
                       onkeydown="if(event.key==='Enter')generateLearningPath()">
                <button class="btn btn-primary" onclick="generateLearningPath()">生成路径</button>
            </div>
            <div id="learningPathContent">
                <div class="empty-state">
                    <div class="empty-state-icon">🗺</div>
                    <p>输入一个学习目标，AI 将基于知识库为你生成结构化学习路径</p>
                </div>
            </div>
        </div>
```

- [ ] **Step 4: 验证模板包含所有关键元素**

```bash
cd "E:/claude项目/personal_knowledge_mgnt" && PYTHONIOENCODING=utf-8 python -c "
from web import create_app
app = create_app()
with app.test_client() as client:
    resp = client.get('/')
    content = resp.data.decode('utf-8')
    checks = ['btnDiscoverRel','graphSuggestionControls','gapAnalysis','reviewPlanPanel',
              'learningPathPanel','learningGoal','switchReviewTab','switchReviewSort']
    for c in checks:
        print(f'{c}: {\"OK\" if c in content else \"MISSING\"}')"
```

Expected: all 8 checks show `OK`

- [ ] **Step 5: Commit**

```bash
git add web/templates/index.html
git commit -m "feat: add AI discovery and learning planning UI to panels"
```

---

### Task 7: 前端 JS — API 方法 + State + Review Tab

**Files:**
- Modify: `web/static/js/app.js`

- [ ] **Step 1: 在 state 对象中添加新属性**

在 `state` 对象末尾添加：

```javascript
    reviewSortMode: 'default',      // 'default' | 'ai'
    reviewTab: 'review-plan',       // 'review-plan' | 'learning-path'
    suggestionEdges: [],            // AI-discovered edges
    cachedReviewPlan: null,         // last AI review plan result
};
```

- [ ] **Step 2: 在 apiService 对象中添加 4 个新方法**

在 `extractFile` 方法之后、`};`（apiService 闭合）之前添加：

```javascript
    discoverRelationships: (data) => {
        return api('/api/ai/discover/relationships', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },
    discoverGaps: (category) => {
        return api('/api/ai/discover/gaps', {
            method: 'POST',
            body: JSON.stringify({ category }),
        });
    },
    generateLearningPath: (goal, category) => {
        const data = { goal };
        if (category) { data.scope = 'category'; data.category = category; }
        return api('/api/ai/learning/path', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },
    optimizeReviewPlan: (days) => {
        return api('/api/ai/learning/review-plan', {
            method: 'POST',
            body: JSON.stringify({ days: days || 7 }),
        });
    },
```

- [ ] **Step 3: 添加 review tab 切换和排序切换函数**

在文件末尾、`init()` 之前添加：

```javascript
// ================================================================
// 13. Review Tab & Sort Switching
// ================================================================

function switchReviewTab(tab) {
    state.reviewTab = tab;
    document.querySelectorAll('.review-tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`.review-tab-btn[data-review-tab="${tab}"]`).classList.add('active');
    document.getElementById('reviewPlanPanel').style.display = tab === 'review-plan' ? '' : 'none';
    document.getElementById('learningPathPanel').style.display = tab === 'learning-path' ? '' : 'none';
    if (tab === 'review-plan') loadReviews();
}

function switchReviewSort(mode) {
    state.reviewSortMode = mode;
    document.getElementById('btnSortDefault').className = mode === 'default' ? 'btn btn-sm' : 'btn btn-outline btn-sm';
    document.getElementById('btnSortAI').className = mode === 'ai' ? 'btn btn-sm' : 'btn btn-outline btn-sm';
    if (mode === 'ai') {
        loadAIReviewPlan();
    } else {
        document.getElementById('strategyNotes').style.display = 'none';
        state.cachedReviewPlan = null;
        loadReviews();
    }
}

async function loadAIReviewPlan() {
    try {
        const items = await apiService.getReviews();
        if (!items || items.length === 0) {
            renderReviews([]);
            return;
        }
        const plan = await apiService.optimizeReviewPlan(7);
        state.cachedReviewPlan = plan;

        const notes = document.getElementById('strategyNotes');
        notes.textContent = plan.strategy_notes || '';
        notes.style.display = '';

        // Build priority lookup
        const priorityMap = {};
        if (plan.daily_plan && plan.daily_plan.length > 0) {
            const today = plan.daily_plan[0];
            (today.items || []).forEach(it => { priorityMap[it.id] = { p: it.priority, r: it.reason }; });
        }

        // Sort reviews by AI priority
        const sorted = [...items].sort((a, b) => {
            const pa = (priorityMap[a.id] && priorityMap[a.id].p) || 99;
            const pb = (priorityMap[b.id] && priorityMap[b.id].p) || 99;
            return pa - pb;
        });

        renderReviewsWithPriority(sorted, priorityMap);
    } catch (e) {}
}
```

- [ ] **Step 4: 添加 renderReviewsWithPriority 函数**

```javascript
function renderReviewsWithPriority(items, priorityMap) {
    const container = document.getElementById('reviewContent');
    if (!items || items.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🎉</div><p>今天没有需要复习的内容！</p></div>';
        return;
    }
    container.innerHTML = items.map((item, i) => {
        const pri = (priorityMap[item.id] && priorityMap[item.id]) || { p: 3, r: '' };
        return `
        <div class="item-card" id="review-item-${item.id}">
            <div class="item-card-title">
                ${i + 1}. ${escapeHtml(item.title)}
                <span class="priority-badge p${pri.p}">P${pri.p}</span>
            </div>
            ${pri.r ? `<div style="font-size:11px;color:var(--text-tertiary);margin-top:2px;">💡 ${escapeHtml(pri.r)}</div>` : ''}
            <div class="item-card-meta">
                <span>理解程度: ${item.understanding_level}/5</span>
                <span>📝 ${escapeHtml(item.summary || '')}</span>
            </div>
            <div style="margin-top:8px;display:flex;gap:8px;align-items:center;" onclick="event.stopPropagation()">
                ${[0,1,2,3,4,5].map(r => `
                    <button class="btn ${r >= 4 ? 'btn-success' : r >= 2 ? 'btn-outline' : 'btn-danger'} btn-sm"
                            onclick="rateReview(${item.id}, ${r})">${r}</button>
                `).join('')}
            </div>
        </div>
        `;
    }).join('');
}
```

- [ ] **Step 5: 更新 loadReviews 函数，根据 reviewSortMode 选择渲染方式**

将现有 `loadReviews` 函数修改为：

```javascript
async function loadReviews() {
    try {
        const items = await apiService.getReviews();
        if (state.reviewSortMode === 'ai' && state.cachedReviewPlan) {
            const priorityMap = {};
            const plan = state.cachedReviewPlan;
            if (plan.daily_plan && plan.daily_plan.length > 0) {
                (plan.daily_plan[0].items || []).forEach(it => { priorityMap[it.id] = { p: it.priority, r: it.reason }; });
            }
            const sorted = [...items].sort((a, b) => {
                const pa = (priorityMap[a.id] && priorityMap[a.id].p) || 99;
                const pb = (priorityMap[b.id] && priorityMap[b.id].p) || 99;
                return pa - pb;
            });
            renderReviewsWithPriority(sorted, priorityMap);
        } else {
            renderReviews(items);
        }
        const badge = document.getElementById('reviewBadge');
        if (badge) {
            badge.textContent = items.length;
            badge.style.display = items.length > 0 ? 'inline' : 'none';
        }
    } catch (e) {}
}
```

- [ ] **Step 6: 验证新函数存在**

```bash
cd "E:/claude项目/personal_knowledge_mgnt" && PYTHONIOENCODING=utf-8 python -c "
with open('web/static/js/app.js', 'r', encoding='utf-8') as f:
    content = f.read()
funcs = ['switchReviewTab','switchReviewSort','loadAIReviewPlan','renderReviewsWithPriority',
         'discoverRelationships','discoverGaps','generateLearningPath','optimizeReviewPlan']
for fn in funcs:
    found = f'function {fn}' in content or f'async function {fn}' in content or f'{fn}:' in content
    print(f'{fn}: {\"OK\" if found else \"MISSING\"}')"
```

Expected: all 8 show `OK`

- [ ] **Step 7: Commit**

```bash
git add web/static/js/app.js
git commit -m "feat: add JS API methods, review tab switching, and AI review sort"
```

---

### Task 8: 前端 JS — 知识图谱关联发现

**Files:**
- Modify: `web/static/js/app.js`

- [ ] **Step 1: 在文件末尾、`init()` 之前添加关联发现函数**

```javascript
// ================================================================
// 14. AI Relationship Discovery (Knowledge Graph)
// ================================================================

async function discoverRelationships() {
    const btn = document.getElementById('btnDiscoverRel');
    btn.disabled = true;
    btn.textContent = '分析中...';

    try {
        const graphData = await apiService.getGraph('');
        if (!graphData || !graphData.nodes || graphData.nodes.length < 2) {
            showToast('需要至少2个条目才能发现关联', 'warning');
            btn.disabled = false;
            btn.textContent = '🤖 AI 发现关联';
            return;
        }

        const result = await apiService.discoverRelationships({
            scope: document.getElementById('graphCategoryFilter').value ? 'category' : 'all',
            category: document.getElementById('graphCategoryFilter').value,
            limit: 30,
        });

        if (result.suggestions && result.suggestions.length > 0) {
            state.suggestionEdges = result.suggestions;
            renderSuggestedEdges(result.suggestions);
            document.getElementById('suggestionCount').textContent = result.suggestions.length;
            document.getElementById('graphSuggestionControls').style.display = '';
        } else {
            showToast('未发现新的关联建议', 'success');
            state.suggestionEdges = [];
        }
    } catch (e) {
        // Error toast handled by api()
    }
    btn.disabled = false;
    btn.textContent = '🤖 AI 发现关联';
}

function renderSuggestedEdges(suggestions) {
    const container = document.getElementById('graphContainer');
    const svg = container.querySelector('svg');
    if (!svg) { loadKnowledgeGraph(); setTimeout(() => renderSuggestedEdges(suggestions), 500); return; }

    const g = svg.querySelector('g');
    // Remove old suggested edges
    g.querySelectorAll('line.suggested-edge').forEach(l => l.remove());
    g.querySelectorAll('text.suggested-label').forEach(l => l.remove());

    const nodes = graphSimulation ? graphSimulation.nodes() : [];

    suggestions.forEach((sug, idx) => {
        const src = nodes.find(n => n.id === sug.source_id);
        const tgt = nodes.find(n => n.id === sug.target_id);
        if (!src || !tgt) return;

        // Dashed line
        g.insertAdjacentHTML('beforeend',
            `<line class="suggested-edge" x1="${src.x}" y1="${src.y}" x2="${tgt.x}" y2="${tgt.y}"
                   data-sid="${sug.source_id}" data-tid="${sug.target_id}" data-idx="${idx}">`
        );

        // Tooltip
        const line = g.querySelector(`line.suggested-edge[data-idx="${idx}"]`);
        if (line) {
            line.addEventListener('mouseenter', (e) => {
                const tooltip = document.createElement('div');
                tooltip.className = 'edge-tooltip';
                tooltip.id = 'edgeTooltip';
                tooltip.innerHTML = `<strong>${escapeHtml(sug.type)}</strong><br>${escapeHtml(sug.reason)}<br>
                    <span style="font-size:10px;color:var(--text-tertiary);">强度: ${sug.strength}/5 | 点击采纳 ✓</span>`;
                document.body.appendChild(tooltip);
                tooltip.style.left = (e.clientX + 10) + 'px';
                tooltip.style.top = (e.clientY - 10) + 'px';
            });
            line.addEventListener('mouseleave', () => {
                document.getElementById('edgeTooltip')?.remove();
            });
            line.addEventListener('click', () => adoptSuggestion(idx));
        }
    });
}

async function adoptSuggestion(idx) {
    const sug = state.suggestionEdges[idx];
    if (!sug) return;
    try {
        await apiService.createRelationship({
            source_id: sug.source_id,
            target_id: sug.target_id,
            relationship_type: sug.type || 'related_to',
            strength: sug.strength || 3,
        });
        state.suggestionEdges.splice(idx, 1);
        showToast('关联已添加', 'success');
        loadKnowledgeGraph();
        // Re-render remaining suggestions
        document.getElementById('suggestionCount').textContent = state.suggestionEdges.length;
        if (state.suggestionEdges.length === 0) {
            clearSuggestions();
        } else {
            setTimeout(() => renderSuggestedEdges(state.suggestionEdges), 800);
        }
    } catch (e) {}
}

async function adoptAllSuggestions() {
    const count = state.suggestionEdges.length;
    for (const sug of state.suggestionEdges) {
        try {
            await apiService.createRelationship({
                source_id: sug.source_id,
                target_id: sug.target_id,
                relationship_type: sug.type || 'related_to',
                strength: sug.strength || 3,
            });
        } catch (e) {}
    }
    state.suggestionEdges = [];
    clearSuggestions();
    showToast(`已添加 ${count} 条关联`, 'success');
    loadKnowledgeGraph();
}

function clearSuggestions() {
    state.suggestionEdges = [];
    document.getElementById('graphSuggestionControls').style.display = 'none';
    const svg = document.querySelector('#graphContainer svg');
    if (svg) {
        svg.querySelectorAll('line.suggested-edge').forEach(l => l.remove());
    }
    document.getElementById('edgeTooltip')?.remove();
}
```

- [ ] **Step 2: 更新 loadKnowledgeGraph 函数，重新加载后恢复建议边**

在 `loadKnowledgeGraph` 函数末尾、`}` 之前添加：

```javascript
    // Restore suggested edges after graph reload
    if (state.suggestionEdges.length > 0) {
        setTimeout(() => renderSuggestedEdges(state.suggestionEdges), 1000);
    }
```

- [ ] **Step 3: 更新 D3 tick 函数，让建议边随节点移动**

在 `renderKnowledgeGraph` 函数中，D3 tick 回调添加对 suggested edges 的更新。在 `.on('tick', () => {` 的回调末尾添加：

```javascript
            // Update suggested edges
            g.selectAll('line.suggested-edge')
                .attr('x1', function() { return this.getAttribute('x1'); })
                .attr('y1', function() { return this.getAttribute('y1'); })
                .attr('x2', function() { return this.getAttribute('x2'); })
                .attr('y2', function() { return this.getAttribute('y2'); });
```

这需要在 tick 中动态计算，改为：

在 `renderKnowledgeGraph` 函数中，将 tick 回调改为：

```javascript
        .on('tick', () => {
            links.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
                 .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
            nodes.attr('transform', d => `translate(${d.x},${d.y})`);
            // Update suggested edges to follow node positions
            g.selectAll('line.suggested-edge').each(function() {
                const sid = parseInt(this.getAttribute('data-sid'));
                const tid = parseInt(this.getAttribute('data-tid'));
                const s = data.nodes.find(n => n.id === sid);
                const t = data.nodes.find(n => n.id === tid);
                if (s && t) {
                    d3.select(this).attr('x1', s.x).attr('y1', s.y).attr('x2', t.x).attr('y2', t.y);
                }
            });
        });
```

- [ ] **Step 4: Commit**

```bash
git add web/static/js/app.js
git commit -m "feat: add AI relationship discovery to knowledge graph"
```

---

### Task 9: 前端 JS — 缺口分析

**Files:**
- Modify: `web/static/js/app.js`

- [ ] **Step 1: 增强 showCategoryItems 函数，添加缺口分析按钮和结果区**

修改 `showCategoryItems` 函数：

```javascript
async function showCategoryItems(cat) {
    try {
        const items = await apiService.getCategoryItems(cat);
        const container = document.getElementById('searchResults');
        const gapContainer = document.getElementById('gapAnalysis');

        // Render gap analysis section
        gapContainer.style.display = '';
        gapContainer.innerHTML = `
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
                <span style="font-size:13px;color:var(--text-secondary);">分类: <strong>${escapeHtml(cat)}</strong> (${items.length} 条)</span>
                <button class="btn btn-outline btn-sm" onclick="discoverGaps('${escapeHtml(cat)}')" id="btnGapAnalysis">
                    🤖 AI 缺口分析
                </button>
            </div>
            <div id="gapResults"></div>
        `;

        renderSearchResults(items);
    } catch (e) {}
}
```

- [ ] **Step 2: 在文件末尾、init() 之前添加缺口分析函数**

```javascript
// ================================================================
// 15. AI Gap Analysis (Knowledge Management)
// ================================================================

async function discoverGaps(category) {
    const btn = document.getElementById('btnGapAnalysis');
    btn.disabled = true;
    btn.textContent = '分析中...';

    try {
        const result = await apiService.discoverGaps(category);
        renderGapResults(result, category);
    } catch (e) {}
    btn.disabled = false;
    btn.textContent = '🤖 AI 缺口分析';
}

function renderGapResults(result, category) {
    const container = document.getElementById('gapResults');
    if (!result.gaps || result.gaps.length === 0) {
        container.innerHTML = '<div style="padding:10px;font-size:13px;color:var(--text-secondary);">未发现明显知识缺口，该分类覆盖较完整。</div>';
        return;
    }
    container.innerHTML = result.gaps.map(gap => {
        const stars = Array.from({length: 5}, (_, i) => {
            return `<span class="star${i < (gap.importance || 3) ? ' filled' : ''}">★</span>`;
        }).join('');
        const keywords = (gap.suggested_keywords || []).map(k =>
            `<span class="kw-tag">${escapeHtml(k)}</span>`
        ).join('');
        return `
        <div class="gap-card">
            <div class="gap-card-body">
                <div class="gap-card-topic">
                    ${escapeHtml(gap.topic)}
                    <span class="gap-importance">${stars}</span>
                </div>
                <div class="gap-card-reason">${escapeHtml(gap.reason || '')}</div>
                ${keywords ? `<div class="gap-card-keywords">${keywords}</div>` : ''}
            </div>
            <div class="gap-card-action">
                <button class="btn btn-primary btn-sm" onclick="addFromGap('${escapeHtml(gap.topic)}', '${escapeHtml(category)}')">添加</button>
            </div>
        </div>`;
    }).join('');
}

function addFromGap(topic, category) {
    // Open AI extract details and switch to text tab
    const details = document.getElementById('aiExtractDetails');
    if (details) details.open = true;
    switchExtractTab('text');
    const textarea = document.getElementById('extractText');
    if (textarea) {
        textarea.value = `主题: ${topic}\n分类: ${category}\n\n`;
        textarea.focus();
    }
    // Scroll to AI extract section
    document.getElementById('aiExtractDetails')?.scrollIntoView({ behavior: 'smooth' });
    // Switch to knowledge panel
    switchPanel('knowledge');
}
```

- [ ] **Step 3: Commit**

```bash
git add web/static/js/app.js
git commit -m "feat: add AI gap analysis to knowledge management panel"
```

---

### Task 10: 前端 JS — 学习路径生成

**Files:**
- Modify: `web/static/js/app.js`

- [ ] **Step 1: 在文件末尾、init() 之前添加学习路径函数**

```javascript
// ================================================================
// 16. AI Learning Path Generation (Review Panel)
// ================================================================

async function generateLearningPath() {
    const goal = document.getElementById('learningGoal').value.trim();
    if (!goal) { showToast('请输入学习目标', 'warning'); return; }

    const container = document.getElementById('learningPathContent');
    container.innerHTML = '<div class="loading"><div class="spinner"></div>AI 正在设计学习路径...</div>';

    try {
        const result = await apiService.generateLearningPath(goal);
        renderLearningPath(result);
    } catch (e) {
        container.innerHTML = '<div class="empty-state"><p>生成失败，请重试</p></div>';
    }
}

function renderLearningPath(result) {
    const container = document.getElementById('learningPathContent');
    if (!result.stages || result.stages.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>无法生成学习路径，请尝试更具体的目标</p></div>';
        return;
    }

    let html = `<div style="margin-bottom:12px;font-size:13px;color:var(--text-secondary);">
        学习目标: <strong>${escapeHtml(result.goal)}</strong> |
        预计总时长: <strong>${result.total_estimated_hours || 'N/A'} 小时</strong>
        ${result.provider ? ` | via ${escapeHtml(result.provider)}/${escapeHtml(result.model || '')}` : ''}
    </div>`;

    html += '<div class="learning-timeline">';
    result.stages.forEach(stage => {
        const concepts = (stage.concepts || []).map(c =>
            `<span class="timeline-concept">${escapeHtml(c)}</span>`
        ).join('');
        const prereqs = (stage.prerequisites && stage.prerequisites.length > 0)
            ? `<div class="timeline-prereqs">前置: ${escapeHtml(stage.prerequisites.join(' → '))}</div>` : '';
        const items = (stage.item_ids || []).map(id =>
            `<span class="timeline-item-link" onclick="showItemDetail(${id})">📄 #${id}</span>`
        ).join('');

        html += `
        <div class="timeline-stage" data-order="${stage.order || '?'}">
            <div class="timeline-stage-header">
                <span class="timeline-stage-title">${escapeHtml(stage.title || '')}</span>
                <span class="timeline-stage-hours">${stage.estimated_hours || '?'}h</span>
            </div>
            ${prereqs}
            <div class="timeline-concepts">${concepts}</div>
            ${items ? `<div class="timeline-items">${items}</div>` : ''}
            ${stage.mastery_criteria ? `<div style="font-size:12px;color:var(--text-tertiary);margin-top:8px;">✅ ${escapeHtml(stage.mastery_criteria)}</div>` : ''}
        </div>`;
    });
    html += '</div>';

    if (result.missing_topics && result.missing_topics.length > 0) {
        html += `<div class="timeline-missing-topics">
            <h5>📌 建议补充学习的内容</h5>
            ${result.missing_topics.map(t => `<span class="timeline-item-link missing">${escapeHtml(t)}</span>`).join(' ')}
        </div>`;
    }

    container.innerHTML = html;
}
```

- [ ] **Step 2: Commit**

```bash
git add web/static/js/app.js
git commit -m "feat: add AI learning path generation to review panel"
```

---

### Task 11: 全量验证

- [ ] **Step 1: 运行所有测试**

```bash
cd "E:/claude项目/personal_knowledge_mgnt" && PYTHONIOENCODING=utf-8 python -m pytest tests/ -v
```

Expected: all tests pass

- [ ] **Step 2: 验证所有 API 路由**

```bash
cd "E:/claude项目/personal_knowledge_mgnt" && PYTHONIOENCODING=utf-8 python -c "
from web import create_app
app = create_app()
client = app.test_client()

routes = ['/','/api/search?q=test','/api/stats','/api/categories','/api/tags',
          '/api/recent','/api/knowledge_graph','/api/ai/status','/api/review',
          '/api/current_database']
print('--- existing routes ---')
for route in routes:
    status = client.get(route).status_code
    print(f'{\"OK\" if status == 200 else \"FAIL\"}: GET {route} ({status})')

print('--- new routes ---')
new_routes = [
    ('POST', '/api/ai/discover/relationships', {'scope': 'all'}),
    ('POST', '/api/ai/discover/gaps', {'category': 'test'}),
    ('POST', '/api/ai/learning/path', {'goal': 'test goal'}),
    ('POST', '/api/ai/learning/review-plan', {'days': 3}),
]
for method, route, body in new_routes:
    resp = client.post(route, json=body)
    ok = resp.status_code != 404
    print(f'{\"OK\" if ok else \"FAIL\"}: POST {route} ({resp.status_code})')
"
```

Expected: all existing routes 200, all new routes != 404

- [ ] **Step 3: 验证静态文件和模板**

```bash
cd "E:/claude项目/personal_knowledge_mgnt" && PYTHONIOENCODING=utf-8 python -c "
from web import create_app
app = create_app()
client = app.test_client()
assert client.get('/static/css/style.css').status_code == 200
assert client.get('/static/js/app.js').status_code == 200
print('Static files OK')
resp = client.get('/')
content = resp.data.decode('utf-8')
checks = ['btnDiscoverRel','graphSuggestionControls','gapAnalysis','reviewPlanPanel','learningPathPanel']
for c in checks:
    assert c in content, f'MISSING: {c}'
print('All template checks OK')
"
```

Expected: `Static files OK` `All template checks OK`

- [ ] **Step 4: 统计变更**

```bash
cd "E:/claude项目/personal_knowledge_mgnt" && git diff --stat HEAD~10
```

---

## 验证清单

完成后确认：
- [ ] `python run.py --auto` 正常启动
- [ ] 知识图谱面板可见"AI 发现关联"按钮
- [ ] 按分类浏览知识条目可见"AI 缺口分析"按钮
- [ ] 复习面板有"复习计划"/"学习路径"两个子 tab
- [ ] 学习路径 tab 有输入框和生成按钮
- [ ] 复习计划 tab 有"按日期"/"AI 智能排序"切换
- [ ] 所有已有功能不受影响
