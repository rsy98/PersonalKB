from ai.config import load_config, AIConfig, ProviderConfig
from ai.provider import BaseProvider, ChatMessage, ChatResponse
from ai.service import AIService


def create_provider(provider_type: str, config: ProviderConfig,
                    models: list[str]) -> BaseProvider:
    """Factory function: creates a Provider instance by type string"""
    if provider_type == 'ollama':
        from ai.ollama_provider import OllamaProvider
        return OllamaProvider(base_url=config.base_url or 'http://localhost:11434')
    elif provider_type == 'claude':
        from ai.claude_provider import ClaudeProvider
        return ClaudeProvider(
            api_key=config.api_key,
            base_url=config.base_url or None,
            models=models,
        )
    elif provider_type == 'openai':
        from ai.openai_provider import OpenAIProvider
        return OpenAIProvider(
            api_key=config.api_key,
            base_url=config.base_url or None,
            models=models,
        )
    elif provider_type == 'deepseek':
        from ai.deepseek_provider import DeepSeekProvider
        return DeepSeekProvider(
            api_key=config.api_key,
            base_url=config.base_url or 'https://api.deepseek.com',
            models=models,
        )
    else:
        raise ValueError(f"Unknown provider type: {provider_type}")
