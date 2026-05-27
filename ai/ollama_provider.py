import requests
from ai.provider import BaseProvider, ChatMessage, ChatResponse


class OllamaProvider(BaseProvider):
    def __init__(self, base_url: str = 'http://localhost:11434'):
        self.base_url = base_url.rstrip('/')

    def chat(self, messages: list[ChatMessage], model: str,
             temperature: float = 0.7, max_tokens: int = 4096, **kwargs) -> ChatResponse:
        payload = {
            'model': model,
            'messages': [{'role': m.role, 'content': m.content} for m in messages],
            'stream': False,
            'options': {
                'temperature': temperature,
                'top_p': kwargs.get('top_p', 0.9),
                'top_k': kwargs.get('top_k', 40),
            }
        }

        resp = requests.post(f'{self.base_url}/api/chat', json=payload, timeout=120)
        resp.raise_for_status()
        data = resp.json()

        return ChatResponse(
            content=data['message']['content'],
            model=data.get('model', model),
            usage={
                'prompt_tokens': data.get('prompt_eval_count', 0),
                'completion_tokens': data.get('eval_count', 0),
            }
        )

    def list_models(self) -> list[str]:
        resp = requests.get(f'{self.base_url}/api/tags', timeout=10)
        resp.raise_for_status()
        data = resp.json()
        return [m['name'] for m in data.get('models', [])]

    def is_available(self) -> bool:
        try:
            requests.get(f'{self.base_url}/api/tags', timeout=5)
            return True
        except requests.RequestException:
            return False
