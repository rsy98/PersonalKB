from anthropic import Anthropic
from ai.provider import BaseProvider, ChatMessage, ChatResponse


class ClaudeProvider(BaseProvider):
    def __init__(self, api_key: str, base_url: str = None, models: list[str] = None):
        self.api_key = api_key
        self._models = models or []
        kwargs = {'api_key': api_key}
        if base_url:
            kwargs['base_url'] = base_url
        try:
            self._client = Anthropic(**kwargs)
        except Exception:
            self._client = None

    def chat(self, messages: list[ChatMessage], model: str,
             temperature: float = 0.7, max_tokens: int = 4096, **kwargs) -> ChatResponse:
        system = None
        user_messages = []
        for m in messages:
            if m.role == 'system':
                system = m.content
            else:
                user_messages.append({'role': m.role, 'content': m.content})

        create_kwargs = {
            'model': model,
            'max_tokens': max_tokens,
            'temperature': temperature,
            'messages': user_messages,
        }
        if system:
            create_kwargs['system'] = system

        resp = self._client.messages.create(**create_kwargs)

        content = ''.join(
            block.text for block in resp.content if hasattr(block, 'text')
        )
        return ChatResponse(
            content=content,
            model=resp.model,
            usage={
                'input_tokens': resp.usage.input_tokens,
                'output_tokens': resp.usage.output_tokens,
            }
        )

    def list_models(self) -> list[str]:
        return list(self._models)

    def is_available(self) -> bool:
        return self._client is not None
