import os
import tempfile
from ai.config import load_config, AIConfig, ProviderConfig

SAMPLE_YAML = """
default_provider: ollama

providers:
  ollama:
    type: ollama
    base_url: http://localhost:11434
  claude:
    type: claude
    api_key: ${CLAUDE_API_KEY}

models:
  ollama:
    - deepseek-r1:8b
  claude:
    - claude-opus-4-7
    - claude-sonnet-4-6

defaults:
  analyze:
    provider: ollama
    model: deepseek-r1:8b
  chat:
    provider: claude
    model: claude-sonnet-4-6
"""


class TestLoadConfig:
    def test_loads_providers_from_yaml(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write(SAMPLE_YAML)
            path = f.name

        try:
            config = load_config(path)
            assert config.default_provider == 'ollama'
            assert 'ollama' in config.providers
            assert 'claude' in config.providers
            assert config.providers['ollama'].type == 'ollama'
            assert config.providers['ollama'].base_url == 'http://localhost:11434'
        finally:
            os.unlink(path)

    def test_resolves_env_var_in_api_key(self):
        os.environ['TEST_API_KEY'] = 'sk-test-123'
        yaml_content = """
default_provider: claude
providers:
  claude:
    type: claude
    api_key: ${TEST_API_KEY}
models:
  claude: [claude-opus-4-7]
defaults: {}
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write(yaml_content)
            path = f.name

        try:
            config = load_config(path)
            assert config.providers['claude'].api_key == 'sk-test-123'
        finally:
            os.unlink(path)
            del os.environ['TEST_API_KEY']

    def test_unresolved_env_var_becomes_empty(self):
        yaml_content = """
default_provider: claude
providers:
  claude:
    type: claude
    api_key: ${NONEXISTENT_VAR_XYZ}
models:
  claude: [claude-opus-4-7]
defaults: {}
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write(yaml_content)
            path = f.name

        try:
            config = load_config(path)
            assert config.providers['claude'].api_key == ''
        finally:
            os.unlink(path)

    def test_loads_models_list(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write(SAMPLE_YAML)
            path = f.name

        try:
            config = load_config(path)
            assert config.models['ollama'] == ['deepseek-r1:8b']
            assert len(config.models['claude']) == 2
        finally:
            os.unlink(path)

    def test_loads_defaults(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write(SAMPLE_YAML)
            path = f.name

        try:
            config = load_config(path)
            assert config.defaults['analyze']['provider'] == 'ollama'
            assert config.defaults['chat']['model'] == 'claude-sonnet-4-6'
        finally:
            os.unlink(path)

    def test_empty_defaults_is_valid(self):
        yaml_content = """
default_provider: ollama
providers:
  ollama:
    type: ollama
    base_url: http://localhost:11434
models:
  ollama: [deepseek-r1:8b]
defaults: {}
"""
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False, encoding='utf-8') as f:
            f.write(yaml_content)
            path = f.name

        try:
            config = load_config(path)
            assert config.defaults == {}
        finally:
            os.unlink(path)

    def test_load_config_file_not_found_raises(self):
        import pytest
        with pytest.raises(FileNotFoundError):
            load_config('nonexistent_config_test.yaml')
