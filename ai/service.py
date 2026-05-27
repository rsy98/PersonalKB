from ai.provider import BaseProvider, ChatMessage
from ai.config import AIConfig

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

    def get_default(self, capability: str) -> dict:
        return dict(self.config.defaults.get(capability, {}))
