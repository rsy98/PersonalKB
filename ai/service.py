from ai.provider import BaseProvider, ChatMessage
from ai.config import AIConfig
import json

PROMPTS = {
    'analyze': {
        'system': '你是一个专业的知识管理助手，擅长分析和总结知识内容。',
        'user': (
            '请分析以下知识条目：\n\n'
            '标题：{title}\n'
            '分类：{category}\n'
            '标签：{tags}\n'
            '内容：{content}\n\n'
            '请提供：\n'
            '1. 内容摘要\n'
            '2. 关键知识点\n'
            '3. 相关主题建议\n'
            '4. 学习建议'
        ),
    },
    'generate_questions': {
        'system': '你是一个教育专家，擅长设计有启发性的测试问题。',
        'user': (
            '基于以下内容生成3-5个测试问题：\n\n'
            '内容：{content}\n\n'
            '请生成多种类型的问题（概念理解、应用实践、分析评价等）：'
        ),
    },
    'improve_writing': {
        'system': '你是一个专业的编辑，擅长改进文本的清晰度和专业性。',
        'user': '请改进以下内容的写作，使其更清晰、专业：\n\n{content}\n\n请直接返回改进后的文本：',
    },
    'chat': {
        'system': '你是一个知识库助手，请基于提供的知识内容回答用户问题。',
        'user': '{context}\n\n请基于以上信息回答用户问题：{question}',
    },
    'extract': {
        'system': '你是一个知识管理专家，擅长从原始材料中提取结构化知识条目。',
        'user': (
            '请从以下材料中提取一个知识条目，返回 JSON 格式（只返回 JSON，不要其他内容）：\n\n'
            '{source}\n\n'
            '返回格式：\n'
            '{{\n'
            '  "title": "条目标题（简洁准确，10-30字）",\n'
            '  "content": "整理后的正文内容（保持关键信息，去除冗余）",\n'
            '  "summary": "一句话摘要（50字以内）",\n'
            '  "tags": ["标签1", "标签2", "标签3"],\n'
            '  "category": "分类名称"\n'
            '}}'
        ),
    },
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
}


class AIService:
    def __init__(self, config: AIConfig):
        self.config = config
        self._providers: dict[str, BaseProvider] = {}

    def _get_provider(self, name: str) -> BaseProvider:
        if name not in self._providers:
            from ai import create_provider
            provider_config = self.config.providers[name]
            models = self.config.models.get(name, [])
            self._providers[name] = create_provider(
                provider_config.type, provider_config, models
            )
        return self._providers[name]

    def _resolve(self, capability: str, provider: str = None, model: str = None) -> tuple:
        defaults = self.config.defaults.get(capability, {})
        p = provider or defaults.get('provider', self.config.default_provider)
        m = model or defaults.get('model', '')
        return p, m

    def execute(self, capability: str, params: dict,
                provider: str = None, model: str = None) -> dict:
        p_name, m_name = self._resolve(capability, provider, model)
        prov = self._get_provider(p_name)
        prompt = PROMPTS[capability]

        messages = [
            ChatMessage(role='system', content=prompt['system']),
            ChatMessage(role='user', content=prompt['user'].format(**params)),
        ]

        resp = prov.chat(messages, model=m_name)
        return {
            'content': resp.content,
            'model': resp.model,
            'provider': p_name,
            'usage': resp.usage,
        }

    # ── High-level wrappers (backward-compatible with old ai_service.py) ──

    def analyze_knowledge_item(self, title, content, tags, category,
                                provider=None, model=None) -> dict:
        tags_str = ', '.join(tags) if tags else '无'
        result = self.execute('analyze', {
            'title': title,
            'content': content[:2000],
            'tags': tags_str,
            'category': category,
        }, provider=provider, model=model)
        return {
            'analysis': result['content'],
            'summary': f"AI分析完成: {title}",
            'related_topics': ['相关主题1', '相关主题2'],
            'model': result['model'],
            'provider': result['provider'],
        }

    def generate_questions(self, content, provider=None, model=None) -> list:
        result = self.execute('generate_questions', {
            'content': content[:1500],
        }, provider=provider, model=model)
        text = result['content']
        questions = []
        for line in text.split('\n'):
            line = line.strip()
            if line and (line[0].isdigit() or line.startswith(('-', '•'))):
                q = line.lstrip('12345.-• ').strip()
                if q:
                    questions.append(q)
        return questions if questions else ['请基于内容自行设计问题']

    def improve_writing(self, content, provider=None, model=None) -> str:
        try:
            result = self.execute('improve_writing', {
                'content': content,
            }, provider=provider, model=model)
            return result['content']
        except Exception:
            return content

    def chat_with_knowledge(self, question, context_items, chat_history=None,
                             provider=None, model=None) -> dict:
        context = ''
        if chat_history:
            context += '对话历史:\n'
            for msg in chat_history[-6:]:
                role_label = '用户' if msg.get('role') == 'user' else '助手'
                context += f"{role_label}: {msg.get('content', '')}\n"
            context += '\n'

        context += '当前知识上下文:\n'
        context += '\n'.join([
            f"标题: {item.get('title', '')}\n内容: {item.get('content', '')[:300]}"
            for item in context_items[:2]
        ])

        result = self.execute('chat', {
            'context': context,
            'question': question,
        }, provider=provider, model=model)

        return {
            'answer': result['content'],
            'thinking': '',
            'full_response': result['content'],
            'model': result['model'],
            'provider': result['provider'],
        }

    # ── Query interface (for UI use) ──

    def list_providers(self) -> list[dict]:
        result = []
        for name in self.config.providers:
            prov = self._get_provider(name)
            result.append({
                'name': name,
                'available': prov.is_available(),
                'models': self.config.models.get(name, []),
            })
        return result

    def extract_knowledge_item(self, source_text: str,
                               provider: str = None, model: str = None) -> dict:
        """从原始材料提取结构化知识条目"""
        result = self.execute('extract', {
            'source': source_text[:4000],
        }, provider=provider, model=model)

        try:
            text = result['content'].strip()
            if text.startswith('```'):
                lines = text.split('\n')
                text = '\n'.join(lines[1:])
                if text.rstrip().endswith('```'):
                    text = text.rstrip()[:-3]
            extracted = json.loads(text)
        except (json.JSONDecodeError, KeyError):
            extracted = {
                'title': '',
                'content': result['content'],
                'summary': '',
                'tags': [],
                'category': '未分类',
            }

        return {
            'title': extracted.get('title', ''),
            'content': extracted.get('content', result['content']),
            'summary': extracted.get('summary', ''),
            'tags': extracted.get('tags', []),
            'category': extracted.get('category', '未分类'),
            'model': result['model'],
            'provider': result['provider'],
        }

    def _parse_json_response(self, result: dict) -> dict:
        """解析 AI 返回的 JSON（统一处理 code fence 和解析失败）"""
        try:
            text = result.get('content')
            if not isinstance(text, str):
                data = {'error': 'AI 返回非文本内容', 'raw': str(text)}
            else:
                text = text.strip()
                if text.startswith('```'):
                    lines = text.split('\n')
                    text = '\n'.join(lines[1:])
                    if text.rstrip().endswith('```'):
                        text = text.rstrip()[:-3]
                data = json.loads(text)
                if isinstance(data, list):
                    data = {'items': data}
        except (json.JSONDecodeError, KeyError):
            data = {'error': 'AI 返回格式异常', 'raw': result.get('content', '')}
        if isinstance(data, list):
            data = {'items': data}
        data['model'] = result.get('model', 'unknown')
        data['provider'] = result.get('provider', 'unknown')
        return data

    def discover_relationships(self, items: list,
                               provider: str = None, model: str = None) -> dict:
        """发现知识条目间的隐藏关联"""
        items_text = '\n'.join([
            f'ID:{i["id"]} 标题:{i["title"]} 分类:{i.get("category","")} '
            f'标签:{i.get("tag_names","")} 摘要:{i.get("summary","")[:100]}'
            for i in items
        ])
        try:
            result = self.execute('discover_relationships', {
                'items': items_text[:4000],
            }, provider=provider, model=model)
        except Exception as e:
            return {
                'suggestions': [], 'analyzed_count': len(items), 'suggestion_count': 0,
                'model': model or '', 'provider': provider or '', 'error': str(e),
            }
        parsed = self._parse_json_response(result)
        if isinstance(parsed, dict) and 'error' in parsed:
            return {
                'suggestions': [], 'analyzed_count': len(items), 'suggestion_count': 0,
                'model': result['model'], 'provider': result['provider'],
            }
        # _parse_json_response wraps bare arrays in {'items': ...}
        suggestions = parsed.get('items', parsed) if isinstance(parsed.get('items'), list) else parsed.get('suggestions', [])
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
        try:
            result = self.execute('discover_gaps', {
                'category': category,
                'items': items_text[:3000],
            }, provider=provider, model=model)
        except Exception as e:
            return {
                'category': category, 'gaps': [], 'existing_count': len(items), 'gap_count': 0,
                'model': model or '', 'provider': provider or '', 'error': str(e),
            }
        parsed = self._parse_json_response(result)
        if isinstance(parsed, dict) and 'error' in parsed:
            return {
                'category': category, 'gaps': [], 'existing_count': len(items), 'gap_count': 0,
                'model': result['model'], 'provider': result['provider'],
            }
        gaps = parsed.get('items', parsed) if isinstance(parsed.get('items'), list) else parsed.get('gaps', [])
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
        try:
            result = self.execute('generate_learning_path', {
                'goal': goal,
                'items': items_text[:4000],
            }, provider=provider, model=model)
        except Exception as e:
            return {
                'goal': goal, 'stages': [], 'missing_topics': [],
                'total_estimated_hours': 0, 'model': model or '', 'provider': provider or '',
                'error': str(e),
            }
        parsed = self._parse_json_response(result)
        if isinstance(parsed, dict) and 'error' in parsed:
            return {
                'goal': goal, 'stages': [], 'missing_topics': [],
                'total_estimated_hours': 0, 'model': result['model'], 'provider': result['provider'],
            }
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
        try:
            result = self.execute('optimize_review_plan', {
                'items': items_text[:4000],
                'days': str(days),
            }, provider=provider, model=model)
        except Exception as e:
            return {
                'daily_plan': [], 'max_daily': 8, 'strategy_notes': '',
                'model': model or '', 'provider': provider or '', 'error': str(e),
            }
        parsed = self._parse_json_response(result)
        if isinstance(parsed, dict) and 'error' in parsed:
            return {
                'daily_plan': [], 'max_daily': 8, 'strategy_notes': '',
                'model': result['model'], 'provider': result['provider'],
            }
        return {
            'daily_plan': parsed.get('daily_plan', []),
            'max_daily': parsed.get('max_daily', 8),
            'strategy_notes': parsed.get('strategy_notes', ''),
            'model': result['model'],
            'provider': result['provider'],
        }

    def get_default(self, capability: str) -> dict:
        return dict(self.config.defaults.get(capability, {}))
