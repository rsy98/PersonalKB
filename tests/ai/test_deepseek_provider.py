from ai.deepseek_provider import DeepSeekProvider
from ai.openai_provider import OpenAIProvider


class TestDeepSeekProvider:
    def test_inherits_from_openai_provider(self):
        provider = DeepSeekProvider(api_key='sk-test')
        assert isinstance(provider, OpenAIProvider)

    def test_default_base_url_is_deepseek(self):
        provider = DeepSeekProvider(api_key='sk-test')
        assert provider.base_url == 'https://api.deepseek.com'
