from openai import OpenAI
from ai.provider import BaseProvider, ChatMessage, ChatResponse


class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str, base_url: str = None, models: list[str] = None):
        self.api_key = api_key
        self.base_url = base_url
        self._models = models or []
        kwargs = {'api_key': api_key}
        if base_url:
            kwargs['base_url'] = base_url
        try:
            self._client = OpenAI(**kwargs)
        except Exception:
            self._client = None

    def chat(self, messages: list[ChatMessage], model: str,
             temperature: float = 0.7, max_tokens: int = 4096, **kwargs) -> ChatResponse:
        formatted = [{'role': m.role, 'content': m.content} for m in messages]
        completion = self._client.chat.completions.create(
            model=model,
            messages=formatted,
            temperature=temperature,
            max_tokens=max_tokens,
        )
        choice = completion.choices[0]
        return ChatResponse(
            content=choice.message.content or '',
            model=completion.model,
            usage={
                'prompt_tokens': completion.usage.prompt_tokens,
                'completion_tokens': completion.usage.completion_tokens,
            },
        )

    def list_models(self) -> list[str]:
        return list(self._models)

    def is_available(self) -> bool:
        return self._client is not None
