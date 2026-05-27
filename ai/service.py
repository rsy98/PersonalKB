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
        'system': '你是一个知识库助手。请结合提供的知识内容和你的专业知识来回答用户问题。如果知识内容与问题相关，优先引用其中的信息；如果知识内容不够充分，可以运用你自己的知识来补充回答。',
        'user': '{context}\n\n用户问题：{question}',
    },
    'extract': {
        'system': '你是一个知识管理专家，擅长从原始材料中提取结构化知识条目。你的首要原则是：保留原材料的实质内容，不要概括、压缩或改写。',
        'user': (
            '请从以下材料中提取一个知识条目，返回 JSON 格式（只返回 JSON，不要其他内容）：\n\n'
            '{source}\n\n'
            '重要原则（按优先级排序）：\n'
            '1. content 字段必须逐段保留原文——每段之间用两个换行（\\n\\n）分隔，保持原文的段落节奏\n'
            '2. 段落内的文字不要改写、不要概括、不要删减——原样保留\n'
            '3. 只删除以下纯格式噪声：HTML标签/CSS/JS代码、导航菜单、广告、页脚版权信息\n'
            '4. 原文中的标题（# ## ### 等 Markdown 标题）必须保留，作为段落间的小标题\n'
            '5. 列表项、代码块、引用块等结构化内容必须原样保留\n'
            '6. 如果原文是中文，段落开头不要加空格缩进\n\n'
            '返回格式：\n'
            '{{\n'
            '  "title": "条目标题（简洁准确，10-30字）",\n'
            '  "content": "逐段保留的完整正文（段落间用\\\\n\\\\n分隔，保持原文段落结构）",\n'
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
        'system': '你是一个学习规划专家，擅长设计循序渐进的知识学习路线。你可以基于自己的知识独立生成完整的学习路径，不局限于提供的参考资料。',
        'user': (
            '学习目标：{goal}\n\n'
            '参考资料（知识库中已有条目，可参考但不要受限于此）：\n{items}\n\n'
            '请基于你的专业知识，设计一条从基础到精通的学习路径（3-6个阶段）。返回 JSON：\n'
            '{{\n'
            '  "stages": [\n'
            '    {{\n'
            '      "order": <序号，从1开始>,\n'
            '      "title": "<阶段名称>",\n'
            '      "item_ids": [<参考资料中已有的条目ID，没有则留空数组>],\n'
            '      "concepts": ["<本阶段应掌握的核心概念，3-5个>"],\n'
            '      "resources": ["<推荐学习资源：书籍/课程/网站>"],\n'
            '      "prerequisites": ["<前置阶段名称>"],\n'
            '      "estimated_hours": <数字>,\n'
            '      "mastery_criteria": "<如何判断已掌握>"\n'
            '    }}\n'
            '  ],\n'
            '  "missing_topics": ["<建议补充学习的主题>"],\n'
            '  "total_estimated_hours": <总小时数>\n'
            '}}\n\n'
            '原则：\n'
            '1. 从基础知识到高级应用，每阶段3-5个核心概念\n'
            '2. 每个阶段推荐1-3个具体的学习资源（书名、课程名等）\n'
            '3. 如果参考资料中有相关条目，将其ID填入对应阶段的 item_ids\n'
            '4. 即使用户知识库中条目很少，也要基于你的知识生成完整路径'
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
    'suggest_related': {
        'system': '你是一个知识图谱专家，擅长发现知识条目之间的关联关系。',
        'user': (
            '给定一个目标条目，从候选条目列表中找出与它最可能相关的条目。\n\n'
            '目标条目：\n{source_item}\n\n'
            '候选条目列表：\n{candidate_items}\n\n'
            '请找出与目标条目最相关的条目（2-5个，宁缺毋滥）。返回 JSON：\n'
            '[{{\n'
            '  "id": <候选条目ID>,\n'
            '  "type": "prerequisite|extends|related_to|contradicts",\n'
            '  "strength": <1-5>,\n'
            '  "reason": "<一句话解释为什么相关>"\n'
            '}}]\n\n'
            '只返回 JSON 数组，不要其他内容。ID 必须是上面候选列表中的真实 ID。'
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
            if not line:
                continue
            # 匹配常见格式：数字前缀、中文"问题N"、字母前缀、markdown 列表
            import re
            match = re.match(r'^(\d+[\.\)\、\s]+|问题\s*\d+[：:]|Q\s*\d+[：:]|[-\*\•]\s+)', line)
            if match:
                q = line[match.end():].strip()
            elif line[0].isdigit() or line[0] in '-*•':
                q = line.lstrip('0123456789.-*• ').strip()
            else:
                continue
            if q and len(q) > 3:
                questions.append(q)
        return questions if questions else ['AI 未生成可用题目，请检查 AI 服务连接']

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
            f"标题: {item.get('title', '')}\n内容: {item.get('content', '')[:2000]}"
            for item in context_items[:3]
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
        items_list = parsed.get('items')
        suggestions = items_list if isinstance(items_list, list) else parsed.get('suggestions', [])
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
        # _parse_json_response wraps bare arrays in {'items': ...}
        items_list = parsed.get('items')
        gaps = items_list if isinstance(items_list, list) else parsed.get('gaps', [])
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

    def suggest_related_items(self, source_item: dict, candidate_items: list,
                              provider: str = None, model: str = None) -> dict:
        """AI 为指定条目推荐可能关联的候选条目"""
        source_text = (
            f'ID: {source_item["id"]}\n'
            f'标题: {source_item.get("title", "")}\n'
            f'分类: {source_item.get("category", "")}\n'
            f'内容: {(source_item.get("content", "") or "")[:500]}\n'
            f'标签: {", ".join(source_item.get("tag_names", "").split(",") if source_item.get("tag_names") else [])}'
        )
        candidate_texts = []
        for item in candidate_items:
            candidate_texts.append(
                f'ID: {item["id"]} | 标题: {item.get("title", "")} | 分类: {item.get("category", "")} | '
                f'内容摘要: {(item.get("content", "") or "")[:120]}'
            )
        result = self.execute('suggest_related', {
            'source_item': source_text,
            'candidate_items': '\n'.join(candidate_texts),
        }, provider=provider, model=model)

        suggestions = self._parse_json_response(result)
        # _parse_json_response wraps bare arrays in {'items': ...}
        if isinstance(suggestions, dict) and 'items' in suggestions:
            suggestions = suggestions['items']
        if not isinstance(suggestions, list):
            suggestions = []
        return {
            'suggestions': suggestions,
            'model': result['model'],
            'provider': result['provider'],
        }

    # ── Embedding & Semantic Search ──

    def _get_embedding_provider_and_model(self):
        """Get the configured embedding provider and model"""
        emb_config = getattr(self.config, 'embedding', None) or {}
        provider_name = emb_config.get('provider', 'ollama')
        model = emb_config.get('model', 'bge-m3:latest')
        return self._get_provider(provider_name), model

    def embed_text(self, text: str) -> list[float]:
        """Generate embedding vector for a single text"""
        provider, model = self._get_embedding_provider_and_model()
        return provider.embed(text, model)

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embedding vectors for multiple texts"""
        provider, model = self._get_embedding_provider_and_model()
        return provider.embed_batch(texts, model)

    @staticmethod
    def cosine_similarity(a: list[float], b: list[float]) -> float:
        """Compute cosine similarity between two vectors (pure Python)"""
        dot = sum(x * y for x, y in zip(a, b))
        norm_a = sum(x * x for x in a) ** 0.5
        norm_b = sum(x * x for x in b) ** 0.5
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return dot / (norm_a * norm_b)

    def semantic_search(self, query: str, items_with_vectors: list[dict],
                        top_k: int = 10) -> list[dict]:
        """Search items by semantic similarity to query.

        Args:
            query: Search query text
            items_with_vectors: List of dicts, each must have 'vector' key
            top_k: Number of top results to return

        Returns:
            Same list sorted by similarity, with 'score' field added
        """
        if not items_with_vectors:
            return []

        query_vec = self.embed_text(query)
        scored = []
        for item in items_with_vectors:
            score = self.cosine_similarity(query_vec, item['vector'])
            scored.append({**item, 'score': round(score, 4)})

        scored.sort(key=lambda x: -x['score'])
        return scored[:top_k]

    def rag_chat(self, question: str, items_with_vectors: list[dict],
                 chat_history: list[dict] = None,
                 provider: str = None, model: str = None,
                 top_k: int = 5) -> dict:
        """RAG-style chat: retrieve relevant items via semantic search, then generate answer.

        Returns dict with 'answer', 'sources' (list of matched items), and 'thinking'.
        """
        # Step 1: Retrieve relevant context via semantic search
        relevant = self.semantic_search(question, items_with_vectors, top_k=top_k)

        # Step 2: Build context from retrieved items
        context = '以下是与用户问题相关的知识库内容：\n\n'
        for i, item in enumerate(relevant):
            context += f'【资料{i+1}】标题: {item.get("title", "")}\n'
            context += f'内容: {(item.get("content", "") or "")[:500]}\n'
            context += f'相关度: {item["score"]:.2f}\n\n'

        # Step 3: Build messages with chat history
        chat_context = ''
        if chat_history:
            chat_context = '对话历史:\n'
            for msg in chat_history[-6:]:
                role_label = '用户' if msg.get('role') == 'user' else '助手'
                chat_context += f'{role_label}: {msg.get("content", "")}\n'
            chat_context += '\n'

        system_prompt = (
            '你是一个知识库助手。请基于提供的参考资料回答用户问题。\n'
            '如果参考资料包含了相关信息，请引用具体的资料编号。\n'
            '如果参考资料不够充分，可以结合你的知识进行补充，但要明确说明哪些来自资料、哪些来自你的知识。'
        )

        messages = [
            ChatMessage(role='system', content=system_prompt),
            ChatMessage(role='user', content=chat_context + context + f'\n用户问题：{question}'),
        ]

        p_name, m_name = self._resolve('chat', provider, model)
        prov = self._get_provider(p_name)
        resp = prov.chat(messages, model=m_name)

        # Build sources summary
        sources = [{
            'id': item['id'],
            'title': item.get('title', ''),
            'score': item['score'],
            'snippet': (item.get('content', '') or '')[:150],
        } for item in relevant]

        return {
            'answer': resp.content,
            'thinking': '',
            'sources': sources,
            'model': resp.model,
            'provider': p_name,
        }

    def get_default(self, capability: str) -> dict:
        return dict(self.config.defaults.get(capability, {}))
