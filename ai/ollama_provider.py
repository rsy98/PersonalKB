import requests
from ai.provider import BaseProvider, ChatMessage, ChatResponse


class OllamaProvider(BaseProvider):
    def __init__(self, base_url: str = 'http://localhost:11434'):
        self.base_url = base_url.rstrip('/')

    def chat(self, messages: list[ChatMessage], model: str,
             temperature: float = 0.7, max_tokens: int = 4096, **kwargs) -> ChatResponse:
        api_messages = []
        for m in messages:
            if isinstance(m.content, str):
                api_messages.append({'role': m.role, 'content': m.content})
            else:
                text_parts = []
                img_b64s = []
                for block in m.content:
                    if block.type == 'text':
                        text_parts.append(block.text)
                    elif block.type == 'image_url':
                        url = block.image_url.get('url', '') if block.image_url else ''
                        if url.startswith('data:'):
                            b64 = url.split(',', 1)[-1] if ',' in url else url
                            img_b64s.append(b64)
                entry = {'role': m.role, 'content': '\n'.join(text_parts)}
                if img_b64s:
                    entry['images'] = img_b64s
                api_messages.append(entry)

        payload = {
            'model': model,
            'messages': api_messages,
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

    def embed(self, text: str, model: str) -> list[float]:
        """Generate embedding vector for text"""
        resp = requests.post(f'{self.base_url}/api/embeddings', json={
            'model': model,
            'prompt': text,
        }, timeout=60)
        resp.raise_for_status()
        return resp.json()['embedding']

    def embed_batch(self, texts: list[str], model: str) -> list[list[float]]:
        """Generate embeddings for multiple texts"""
        results = []
        for text in texts:
            results.append(self.embed(text, model))
        return results

    def is_available(self) -> bool:
        try:
            requests.get(f'{self.base_url}/api/tags', timeout=5)
            return True
        except requests.RequestException:
            return False
