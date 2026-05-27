from ai.openai_provider import OpenAIProvider


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek Cloud API — OpenAI-compatible protocol, different base URL only"""

    def __init__(self, api_key: str, base_url: str = 'https://api.deepseek.com',
                 models: list[str] = None):
        super().__init__(api_key=api_key, base_url=base_url, models=models)
