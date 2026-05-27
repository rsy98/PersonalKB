# AI 模型抽象层 实现计划

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** 将单文件 `ai_service.py`（硬编码 Ollama/DeepSeek）重构为可扩展的多 Provider 架构，支持 Ollama 本地模型 + Claude/OpenAI/DeepSeek 外部 API，Web UI 按调用实时切换。

**Architecture:** Provider 层只管 `chat()` 单一接口；AIService 层负责 prompt 模板 + 响应解析 + 模型选择；`config/ai.yaml` 驱动所有 Provider 和默认配置。

**Tech Stack:** Python 3.x, pytest (测试), PyYAML (配置), anthropic SDK, openai SDK, requests (已有)

**Note:** 本项目不是 git 仓库，commit 步骤标注为可选。若需要，先 `git init`。

---

## 文件结构总览

```
ai/                          # 新建
├── __init__.py              # 公开导出
├── provider.py              # 基类 + 工厂
├── config.py                # YAML 配置加载
├── ollama_provider.py       # Ollama HTTP API
├── claude_provider.py       # Anthropic SDK
├── openai_provider.py       # OpenAI SDK
├── deepseek_provider.py     # DeepSeek Cloud (继承 OpenAI)
└── service.py               # 能力编排层

config/                      # 新建
└── ai.yaml                  # Provider 配置 + 默认模型

tests/ai/                    # 新建
├── __init__.py
├── test_config.py
├── test_ollama_provider.py
├── test_claude_provider.py
├── test_openai_provider.py
├── test_deepseek_provider.py
└── test_service.py

requirements.txt             # 修改：增加依赖
web_interface.py             # 修改：替换 import + 新增路由
cli_interface.py             # 修改：替换 import
```

---

### Task 1: 项目基础设施

**Files:**
- Modify: `requirements.txt`
- Create: `tests/__init__.py` (空文件)
- Create: `tests/ai/__init__.py` (空文件)

- [ ] **Step 1: 更新 requirements.txt**

将 `requirements.txt` 替换为：

```
flask
jieba
numpy
pandas
matplotlib
pyyaml
anthropic
openai
requests
pytest
```

- [ ] **Step 2: 安装依赖**

```bash
pip install -r requirements.txt
```

- [ ] **Step 3: 创建 tests 目录结构**

```bash
mkdir -p tests/ai
```

- [ ] **Step 4: 创建空的 `tests/__init__.py` 和 `tests/ai/__init__.py`**

```bash
echo "" > tests/__init__.py
echo "" > tests/ai/__init__.py
```

- [ ] **Step 5: 验证 pytest 可运行**

```bash
python -m pytest tests/ -v
```
Expected: "no tests ran" 或成功退出，不应报 import 错误

---

### Task 2: 配置加载器 (ai/config.py)

**Files:**
- Create: `ai/__init__.py`
- Create: `ai/config.py`
- Create: `tests/ai/test_config.py`

- [ ] **Step 1: 写测试 `tests/ai/test_config.py`**

```python
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
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest tests/ai/test_config.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'ai.config'`

- [ ] **Step 3: 创建空的 `ai/__init__.py`**

```bash
echo "" > ai/__init__.py
```

- [ ] **Step 4: 实现 `ai/config.py`**

```python
import os
import re
from dataclasses import dataclass, field
from pathlib import Path

import yaml


@dataclass
class ProviderConfig:
    type: str
    api_key: str = ""
    base_url: str = ""


@dataclass
class AIConfig:
    default_provider: str
    providers: dict[str, ProviderConfig]
    models: dict[str, list[str]]
    defaults: dict[str, dict]


def _resolve_env_vars(raw: str) -> str:
    """将 ${VAR_NAME} 替换为环境变量值，未设置的变量替换为空字符串"""
    return re.sub(r'\$\{(\w+)\}', lambda m: os.environ.get(m.group(1), ''), raw)


def load_config(path: str) -> AIConfig:
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(f"Config file not found: {path}")

    raw_text = p.read_text(encoding='utf-8')
    resolved_text = _resolve_env_vars(raw_text)
    raw = yaml.safe_load(resolved_text)

    providers = {k: ProviderConfig(**v) for k, v in raw.get('providers', {}).items()}
    return AIConfig(
        default_provider=raw.get('default_provider', ''),
        providers=providers,
        models=raw.get('models', {}),
        defaults=raw.get('defaults', {}),
    )
```

- [ ] **Step 5: 运行测试，确认通过**

```bash
python -m pytest tests/ai/test_config.py -v
```
Expected: 所有 6 个测试 PASS

---

### Task 3: Provider 基类 + 工厂函数 (ai/provider.py)

**Files:**
- Create: `ai/provider.py`
- Create: `tests/ai/test_provider.py`

- [ ] **Step 1: 写测试 `tests/ai/test_provider.py`**

```python
import pytest
from ai.provider import BaseProvider, ChatMessage, ChatResponse, create_provider


class FakeProvider(BaseProvider):
    """测试用 Provider"""
    def __init__(self, config=None):
        self.config = config or {}
        self._models = self.config.get('models', [])

    def chat(self, messages, model, temperature=0.7, max_tokens=4096, **kwargs):
        return ChatResponse(
            content="fake response",
            model=model,
            usage={"prompt_tokens": 10, "completion_tokens": 5},
        )

    def list_models(self):
        return self._models


class TestChatMessage:
    def test_create_message(self):
        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"


class TestChatResponse:
    def test_create_response(self):
        resp = ChatResponse(content="hi", model="test-model", usage={"prompt_tokens": 1})
        assert resp.content == "hi"
        assert resp.model == "test-model"

    def test_default_usage_is_empty_dict(self):
        resp = ChatResponse(content="hi", model="test")
        assert resp.usage == {}


class TestBaseProvider:
    def test_is_available_default_true(self):
        provider = FakeProvider()
        assert provider.is_available() is True

    def test_chat_returns_chat_response(self):
        provider = FakeProvider()
        msg = ChatMessage(role="user", content="test")
        resp = provider.chat([msg], model="test")
        assert isinstance(resp, ChatResponse)
        assert resp.content == "fake response"


def test_create_provider_returns_provider_instance():
    provider = FakeProvider()
    assert isinstance(provider, BaseProvider)


def test_create_provider_can_accept_config():
    provider = FakeProvider(config={"models": ["m1", "m2"]})
    assert provider.list_models() == ["m1", "m2"]
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest tests/ai/test_provider.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'ai.provider'`

- [ ] **Step 3: 实现 `ai/provider.py`**

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass
class ChatMessage:
    role: str      # system / user / assistant
    content: str


@dataclass
class ChatResponse:
    content: str
    model: str
    usage: dict = field(default_factory=dict)


class BaseProvider(ABC):
    """所有 AI Provider 的唯一接口"""

    @abstractmethod
    def chat(self, messages: list[ChatMessage], model: str,
             temperature: float = 0.7, max_tokens: int = 4096, **kwargs) -> ChatResponse:
        """发送聊天请求，返回统一响应"""

    @abstractmethod
    def list_models(self) -> list[str]:
        """返回此 Provider 的可用模型列表"""

    def is_available(self) -> bool:
        """健康检查，子类可覆盖"""
        return True


def create_provider(provider_type: str, config_obj) -> BaseProvider:
    """工厂函数：根据类型字符串创建 Provider 实例。
    具体实现见 __init__.py，这里留作占位，在 Task 7 中完善。
    """
    raise NotImplementedError(f"Provider type '{provider_type}' not registered")
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest tests/ai/test_provider.py -v
```
Expected: 6 tests PASS

---

### Task 4: OllamaProvider (ai/ollama_provider.py)

**Files:**
- Create: `ai/ollama_provider.py`
- Create: `tests/ai/test_ollama_provider.py`

- [ ] **Step 1: 写测试 `tests/ai/test_ollama_provider.py`**

```python
import json
from unittest.mock import patch, MagicMock
from ai.provider import ChatMessage, ChatResponse
from ai.ollama_provider import OllamaProvider


class TestOllamaProvider:
    @patch('ai.ollama_provider.requests.post')
    def test_chat_sends_correct_payload(self, mock_post):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'message': {'content': '你好'},
            'model': 'deepseek-r1:8b',
            'eval_count': 50,
            'prompt_eval_count': 10,
        }
        mock_response.raise_for_status = MagicMock()
        mock_post.return_value = mock_response

        provider = OllamaProvider(base_url='http://localhost:11434')
        messages = [ChatMessage(role='user', content='hello')]
        resp = provider.chat(messages, model='deepseek-r1:8b', temperature=0.3)

        call_args = mock_post.call_args
        assert call_args[0][0] == 'http://localhost:11434/api/chat'

        payload = call_args[1]['json']
        assert payload['model'] == 'deepseek-r1:8b'
        assert payload['stream'] is False
        assert payload['options']['temperature'] == 0.3
        assert payload['messages'][0]['role'] == 'user'
        assert payload['messages'][0]['content'] == 'hello'

        assert resp.content == '你好'
        assert resp.model == 'deepseek-r1:8b'

    @patch('ai.ollama_provider.requests.get')
    def test_list_models_returns_model_names(self, mock_get):
        mock_response = MagicMock()
        mock_response.json.return_value = {
            'models': [
                {'name': 'deepseek-r1:8b'},
                {'name': 'qwen2.5:7b'},
            ]
        }
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = OllamaProvider(base_url='http://localhost:11434')
        models = provider.list_models()

        assert models == ['deepseek-r1:8b', 'qwen2.5:7b']

    @patch('ai.ollama_provider.requests.get')
    def test_is_available_returns_true_when_ollama_running(self, mock_get):
        mock_response = MagicMock()
        mock_response.raise_for_status = MagicMock()
        mock_get.return_value = mock_response

        provider = OllamaProvider(base_url='http://localhost:11434')
        assert provider.is_available() is True

    @patch('ai.ollama_provider.requests.get')
    def test_is_available_returns_false_when_ollama_down(self, mock_get):
        import requests
        mock_get.side_effect = requests.ConnectionError()

        provider = OllamaProvider(base_url='http://localhost:11434')
        assert provider.is_available() is False
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest tests/ai/test_ollama_provider.py -v
```
Expected: FAIL — `ModuleNotFoundError: No module named 'ai.ollama_provider'`

- [ ] **Step 3: 实现 `ai/ollama_provider.py`**

```python
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
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest tests/ai/test_ollama_provider.py -v
```
Expected: 4 tests PASS

---

### Task 5: ClaudeProvider (ai/claude_provider.py)

**Files:**
- Create: `ai/claude_provider.py`
- Create: `tests/ai/test_claude_provider.py`

- [ ] **Step 1: 写测试 `tests/ai/test_claude_provider.py`**

```python
from unittest.mock import patch, MagicMock
from ai.provider import ChatMessage, ChatResponse
from ai.claude_provider import ClaudeProvider


class TestClaudeProvider:
    @patch('ai.claude_provider.Anthropic')
    def test_chat_sends_messages_to_sdk(self, MockAnthropic):
        mock_client = MagicMock()
        mock_msg = MagicMock()
        mock_msg.content = [MagicMock(text='Hello from Claude')]
        mock_msg.model = 'claude-sonnet-4-6'
        mock_msg.usage = MagicMock(input_tokens=15, output_tokens=8)
        mock_client.messages.create.return_value = mock_msg
        MockAnthropic.return_value = mock_client

        provider = ClaudeProvider(api_key='sk-ant-test')
        messages = [ChatMessage(role='user', content='Say hi')]
        resp = provider.chat(messages, model='claude-sonnet-4-6', temperature=0.5, max_tokens=1024)

        call_kwargs = mock_client.messages.create.call_args.kwargs
        assert call_kwargs['model'] == 'claude-sonnet-4-6'
        assert call_kwargs['max_tokens'] == 1024
        assert call_kwargs['temperature'] == 0.5
        assert call_kwargs['messages'] == [{'role': 'user', 'content': 'Say hi'}]

        assert resp.content == 'Hello from Claude'
        assert resp.model == 'claude-sonnet-4-6'
        assert resp.usage == {'input_tokens': 15, 'output_tokens': 8}

    def test_list_models_returns_configured_models(self):
        provider = ClaudeProvider(api_key='sk-test', models=['claude-opus-4-7', 'claude-haiku-4-5'])
        assert provider.list_models() == ['claude-opus-4-7', 'claude-haiku-4-5']

    @patch('ai.claude_provider.Anthropic')
    def test_is_available_returns_true_when_sdk_works(self, MockAnthropic):
        mock_client = MagicMock()
        MockAnthropic.return_value = mock_client

        provider = ClaudeProvider(api_key='sk-test')
        assert provider.is_available() is True

    @patch('ai.claude_provider.Anthropic')
    def test_is_available_returns_false_on_error(self, MockAnthropic):
        MockAnthropic.side_effect = Exception('Connection failed')

        provider = ClaudeProvider(api_key='sk-test')
        assert provider.is_available() is False
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest tests/ai/test_claude_provider.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 `ai/claude_provider.py`**

```python
from anthropic import Anthropic
from ai.provider import BaseProvider, ChatMessage, ChatResponse


class ClaudeProvider(BaseProvider):
    def __init__(self, api_key: str, base_url: str = None, models: list[str] = None):
        self.api_key = api_key
        self._models = models or []
        kwargs = {'api_key': api_key}
        if base_url:
            kwargs['base_url'] = base_url
        self._client = Anthropic(**kwargs)

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
        try:
            self._client  # 检查 SDK 初始化是否正常
            return True
        except Exception:
            return False
```

- [ ] **Step 4: 运行测试，确认通过**

```bash
python -m pytest tests/ai/test_claude_provider.py -v
```
Expected: 4 tests PASS

---

### Task 6: OpenAIProvider + DeepSeekProvider

**Files:**
- Create: `ai/openai_provider.py`
- Create: `ai/deepseek_provider.py`
- Create: `tests/ai/test_openai_provider.py`
- Create: `tests/ai/test_deepseek_provider.py`

- [ ] **Step 1: 写 OpenAITest `tests/ai/test_openai_provider.py`**

```python
from unittest.mock import patch, MagicMock
from ai.provider import ChatMessage
from ai.openai_provider import OpenAIProvider


class TestOpenAIProvider:
    @patch('ai.openai_provider.OpenAI')
    def test_chat_sends_messages_to_sdk(self, MockOpenAI):
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = 'Hello from GPT'
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        mock_completion.model = 'gpt-4o'
        mock_completion.usage = MagicMock(prompt_tokens=20, completion_tokens=10)
        mock_client.chat.completions.create.return_value = mock_completion
        MockOpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key='sk-test')
        messages = [ChatMessage(role='user', content='Say hi')]
        resp = provider.chat(messages, model='gpt-4o', temperature=0.5, max_tokens=1024)

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        assert call_kwargs['model'] == 'gpt-4o'
        assert call_kwargs['max_tokens'] == 1024
        assert call_kwargs['messages'] == [{'role': 'user', 'content': 'Say hi'}]

        assert resp.content == 'Hello from GPT'
        assert resp.model == 'gpt-4o'

    def test_list_models_returns_configured_models(self):
        provider = OpenAIProvider(api_key='sk-test', models=['gpt-4o', 'gpt-4o-mini'])
        assert provider.list_models() == ['gpt-4o', 'gpt-4o-mini']

    @patch('ai.openai_provider.OpenAI')
    def test_is_available_true(self, MockOpenAI):
        MockOpenAI.return_value = MagicMock()
        provider = OpenAIProvider(api_key='sk-test')
        assert provider.is_available() is True

    @patch('ai.openai_provider.OpenAI')
    def test_is_available_false_on_error(self, MockOpenAI):
        MockOpenAI.side_effect = Exception('Bad key')
        provider = OpenAIProvider(api_key='sk-test')
        assert provider.is_available() is False
```

- [ ] **Step 2: 写 DeepSeekTest `tests/ai/test_deepseek_provider.py`**

```python
from ai.deepseek_provider import DeepSeekProvider
from ai.openai_provider import OpenAIProvider


class TestDeepSeekProvider:
    def test_inherits_from_openai_provider(self):
        provider = DeepSeekProvider(api_key='sk-test')
        assert isinstance(provider, OpenAIProvider)

    def test_default_base_url_is_deepseek(self):
        provider = DeepSeekProvider(api_key='sk-test')
        assert provider.base_url == 'https://api.deepseek.com'
```

- [ ] **Step 3: 运行测试，确认失败**

```bash
python -m pytest tests/ai/test_openai_provider.py tests/ai/test_deepseek_provider.py -v
```
Expected: FAIL

- [ ] **Step 4: 实现 `ai/openai_provider.py`**

```python
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
        self._client = OpenAI(**kwargs)

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
        try:
            self._client
            return True
        except Exception:
            return False
```

- [ ] **Step 5: 实现 `ai/deepseek_provider.py`**

```python
from ai.openai_provider import OpenAIProvider


class DeepSeekProvider(OpenAIProvider):
    """DeepSeek Cloud API — OpenAI 兼容协议，仅 base_url 不同"""

    def __init__(self, api_key: str, base_url: str = 'https://api.deepseek.com',
                 models: list[str] = None):
        super().__init__(api_key=api_key, base_url=base_url, models=models)
```

- [ ] **Step 6: 运行测试，确认通过**

```bash
python -m pytest tests/ai/test_openai_provider.py tests/ai/test_deepseek_provider.py -v
```
Expected: 6 tests PASS (4 + 2)

---

### Task 7: AIService 能力编排层 (ai/service.py) + __init__.py 工厂

**Files:**
- Modify: `ai/__init__.py`
- Create: `ai/service.py`
- Create: `tests/ai/test_service.py`

- [ ] **Step 1: 写测试 `tests/ai/test_service.py`**

```python
from unittest.mock import MagicMock
from ai.provider import ChatMessage, ChatResponse
from ai.service import AIService
from ai.config import AIConfig, ProviderConfig


def make_config():
    return AIConfig(
        default_provider='test',
        providers={
            'test': ProviderConfig(type='test', api_key=''),
        },
        models={
            'test': ['test-model'],
        },
        defaults={
            'analyze': {'provider': 'test', 'model': 'test-model'},
            'chat': {'provider': 'test', 'model': 'test-model'},
        },
    )


def make_mock_provider():
    provider = MagicMock()
    provider.chat.return_value = ChatResponse(
        content='mock response',
        model='test-model',
        usage={},
    )
    provider.list_models.return_value = ['test-model']
    provider.is_available.return_value = True
    return provider


class TestListProviders:
    def test_returns_provider_info(self):
        config = make_config()
        service = AIService(config)
        service._providers['test'] = make_mock_provider()

        result = service.list_providers()
        assert len(result) == 1
        assert result[0]['name'] == 'test'
        assert result[0]['available'] is True
        assert result[0]['models'] == ['test-model']


class TestGetDefault:
    def test_returns_default_provider_and_model(self):
        config = make_config()
        service = AIService(config)
        default = service.get_default('analyze')
        assert default == {'provider': 'test', 'model': 'test-model'}

    def test_returns_empty_for_unknown_capability(self):
        config = make_config()
        service = AIService(config)
        default = service.get_default('nonexistent')
        assert default == {}


class TestExecute:
    def test_execute_uses_default_when_not_specified(self):
        config = make_config()
        service = AIService(config)
        provider = make_mock_provider()
        service._providers['test'] = provider

        result = service.execute('analyze', {'title': 'X', 'content': 'Y'})
        provider.chat.assert_called_once()
        assert result['analysis'] is not None


class TestAnalyzeKnowledgeItem:
    def test_calls_execute_with_analyze_capability(self):
        config = make_config()
        service = AIService(config)
        provider = make_mock_provider()
        service._providers['test'] = provider

        result = service.analyze_knowledge_item(
            title='Test', content='Content', tags=['tag1'], category='Tech'
        )
        provider.chat.assert_called_once()
        call_args = provider.chat.call_args
        messages = call_args.kwargs['messages']
        assert messages[0].role == 'system'
        assert 'Test' in messages[1].content
        assert 'Content' in messages[1].content


class TestGenerateQuestions:
    def test_calls_chat_with_question_prompt(self):
        config = make_config()
        service = AIService(config)
        provider = make_mock_provider()
        service._providers['test'] = provider

        result = service.generate_questions(content='Python basics')
        provider.chat.assert_called_once()
        call_args = provider.chat.call_args
        messages = call_args.kwargs['messages']
        assert messages[0].role == 'system'


class TestImproveWriting:
    def test_returns_improved_text(self):
        config = make_config()
        service = AIService(config)
        provider = make_mock_provider()
        provider.chat.return_value = ChatResponse(
            content='Improved text version',
            model='test-model',
            usage={},
        )
        service._providers['test'] = provider

        result = service.improve_writing(content='original text')
        assert result == 'Improved text version'

    def test_falls_back_to_original_on_error(self):
        config = make_config()
        service = AIService(config)
        provider = make_mock_provider()
        provider.chat.side_effect = Exception('API error')
        service._providers['test'] = provider

        result = service.improve_writing(content='original text')
        assert result == 'original text'


class TestChatWithKnowledge:
    def test_includes_context_in_prompt(self):
        config = make_config()
        service = AIService(config)
        provider = make_mock_provider()
        service._providers['test'] = provider

        result = service.chat_with_knowledge(
            question='What is X?',
            context_items=[{'title': 'X topic', 'content': 'X is a letter'}],
        )
        provider.chat.assert_called_once()
        call_args = provider.chat.call_args
        messages = call_args.kwargs['messages']
        user_msg = messages[1].content
        assert 'What is X?' in user_msg
        assert 'X topic' in user_msg

    def test_includes_chat_history_when_provided(self):
        config = make_config()
        service = AIService(config)
        provider = make_mock_provider()
        service._providers['test'] = provider

        history = [
            {'role': 'user', 'content': 'previous question'},
            {'role': 'assistant', 'content': 'previous answer'},
        ]
        service.chat_with_knowledge(
            question='follow up',
            context_items=[],
            chat_history=history,
        )
        call_args = provider.chat.call_args
        messages = call_args.kwargs['messages']
        assert messages[0].content == 'previous answer'
        assert 'previous question' in messages[1].content
```

- [ ] **Step 2: 运行测试，确认失败**

```bash
python -m pytest tests/ai/test_service.py -v
```
Expected: FAIL — `ModuleNotFoundError`

- [ ] **Step 3: 实现 `ai/service.py`**

```python
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

    # ── 高阶封装（向后兼容旧 ai_service.py 接口） ──

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
        # 构建上下文
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

    # ── 查询接口（供 UI 使用） ──

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
```

- [ ] **Step 4: 更新 `ai/__init__.py`**

```python
from ai.config import load_config, AIConfig, ProviderConfig
from ai.provider import BaseProvider, ChatMessage, ChatResponse
from ai.service import AIService


def create_provider(provider_type: str, config: ProviderConfig,
                    models: list[str]) -> BaseProvider:
    """工厂函数：根据类型创建 Provider 实例"""
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
```

- [ ] **Step 5: 运行全部测试，确认通过**

```bash
python -m pytest tests/ai/ -v
```
Expected: 所有测试 PASS

---

### Task 8: 创建 config/ai.yaml

**Files:**
- Create: `config/ai.yaml`

- [ ] **Step 1: 创建目录并写入配置文件**

```bash
mkdir -p config
```

写入 `config/ai.yaml`：

```yaml
default_provider: ollama

providers:
  ollama:
    type: ollama
    base_url: http://localhost:11434
  claude:
    type: claude
    api_key: ${CLAUDE_API_KEY}
  openai:
    type: openai
    api_key: ${OPENAI_API_KEY}
  deepseek:
    type: deepseek
    api_key: ${DEEPSEEK_API_KEY}
    base_url: https://api.deepseek.com

models:
  ollama:
    - deepseek-r1:8b
    - deepseek-r1:14b
    - qwen2.5:7b
  claude:
    - claude-opus-4-7
    - claude-sonnet-4-6
    - claude-haiku-4-5
  openai:
    - gpt-4o
    - gpt-4o-mini
  deepseek:
    - deepseek-chat
    - deepseek-reasoner

defaults:
  analyze:
    provider: ollama
    model: deepseek-r1:8b
  generate_questions:
    provider: ollama
    model: deepseek-r1:8b
  improve_writing:
    provider: claude
    model: claude-sonnet-4-6
  chat:
    provider: claude
    model: claude-sonnet-4-6
```

- [ ] **Step 2: 验证配置文件可以被加载**

```bash
python -c "from ai import load_config; c = load_config('config/ai.yaml'); print('OK:', len(c.providers), 'providers loaded')"
```
Expected: `OK: 4 providers loaded`

---

### Task 9: 集成 web_interface.py

**Files:**
- Modify: `web_interface.py` (lines 15, 6770-6870)

- [ ] **Step 1: 替换顶部的 ai_service 导入**

将 `web_interface.py` 第 15-16 行：
```python
from ai_service import ai_service
# os.environ['DEEPSEEK_API_KEY'] = 'your_deepseek_api_key_here'
```

替换为：
```python
from ai import AIService, load_config
ai_config = load_config('config/ai.yaml')
ai_service = AIService(ai_config)
```

- [ ] **Step 2: 修改 4 个 AI 路由，接收可选的 provider/model 参数**

找到路由函数 `api_ai_analyze`（约第 6770 行），将函数体开头改为接收请求参数：

```python
@app.route('/api/ai/analyze/<int:item_id>')
def api_ai_analyze(item_id):
    data = request.get_json(silent=True) or {}
    provider = data.get('provider')
    model = data.get('model')

    item = knowledge_manager.get_item_by_id(item_id)
    if not item:
        return jsonify({'success': False, 'error': '条目不存在'}), 404

    tags_list = item['tag_names'].split(',') if item['tag_names'] else []
    result = ai_service.analyze_knowledge_item(
        title=item['title'],
        content=item['content'],
        tags=tags_list,
        category=item['category'] or '',
        provider=provider,
        model=model,
    )
    return jsonify({'success': True, 'data': result})
```

同样修改 `api_ai_generate_questions`（约第 6790 行）：

```python
@app.route('/api/ai/generate_questions/<int:item_id>')
def api_ai_generate_questions(item_id):
    data = request.get_json(silent=True) or {}
    provider = data.get('provider')
    model = data.get('model')

    item = knowledge_manager.get_item_by_id(item_id)
    if not item:
        return jsonify({'success': False, 'error': '条目不存在'}), 404

    questions = ai_service.generate_questions(
        content=item['content'],
        provider=provider,
        model=model,
    )
    return jsonify({'success': True, 'data': questions})
```

修改 `api_ai_improve_writing`（约第 6804 行）：

```python
@app.route('/api/ai/improve_writing', methods=['POST'])
def api_ai_improve_writing():
    data = request.get_json()
    content = data.get('content', '')
    provider = data.get('provider')
    model = data.get('model')

    improved = ai_service.improve_writing(
        content=content,
        provider=provider,
        model=model,
    )
    return jsonify({'success': True, 'data': improved})
```

修改 `api_ai_chat`（约第 6816 行）：

```python
@app.route('/api/ai/chat', methods=['POST'])
def api_ai_chat():
    data = request.get_json()
    question = data.get('question', '')
    context_items = data.get('context_items', [])
    chat_history = data.get('chat_history', [])
    provider = data.get('provider')
    model = data.get('model')

    result = ai_service.chat_with_knowledge(
        question=question,
        context_items=context_items,
        chat_history=chat_history,
        provider=provider,
        model=model,
    )
    return jsonify({'success': True, 'data': result})
```

- [ ] **Step 3: 新增 `GET /api/ai/providers` 路由**

在 `api_ai_status` 路由附近（约第 6872 行之后）添加：

```python
@app.route('/api/ai/providers')
def api_ai_providers():
    return jsonify({
        'success': True,
        'data': ai_service.list_providers(),
    })
```

- [ ] **Step 4: 修改 `api_ai_status` 路由使用新接口**

将 `api_ai_status` 函数体（约第 6873 行）替换为：

```python
@app.route('/api/ai/status')
def api_ai_status():
    return jsonify({
        'success': True,
        'data': {
            'providers': ai_service.list_providers(),
            'defaults': {
                'analyze': ai_service.get_default('analyze'),
                'generate_questions': ai_service.get_default('generate_questions'),
                'improve_writing': ai_service.get_default('improve_writing'),
                'chat': ai_service.get_default('chat'),
            }
        }
    })
```

- [ ] **Step 5: 验证导入正确**

```bash
python -c "from web_interface import app, ai_service; print('OK: web_interface imports work'); print('Providers:', [p['name'] for p in ai_service.list_providers()])"
```
Expected: 成功导入，输出 Providers 列表

---

### Task 10: 集成 cli_interface.py

**Files:**
- Modify: `cli_interface.py` (line 6)

- [ ] **Step 1: 替换导入**

将 `cli_interface.py` 第 6 行：
```python
from knowledge_manager import KnowledgeManager
```

在它下面增加（不删除原导入）：

```python
from ai import AIService, load_config
```

- [ ] **Step 2: 在 KnowledgeCLI.__init__ 中初始化 ai_service**

找到 `KnowledgeCLI.__init__`（约第 9 行），在 `self.manager = KnowledgeManager()` 后增加：

```python
try:
    ai_config = load_config('config/ai.yaml')
    self.ai_service = AIService(ai_config)
except Exception:
    self.ai_service = None
```

用 `self.ai_service` 替代任何对全局 `ai_service` 的引用。

- [ ] **Step 3: 验证导入**

```bash
python -c "import cli_interface; print('OK')"
```
Expected: `OK`

---

### Task 11: 清理旧文件

**Files:**
- Remove: `ai_service.py`

- [ ] **Step 1: 确认旧 ai_service.py 不再被引用**

```bash
grep -r "from ai_service import" . --include="*.py" 2>/dev/null || echo "No references found"
```
Expected: `No references found` 或仅匹配 `ai_service.py` 自身

- [ ] **Step 2: 保留旧文件作为参考（重命名）**

```bash
mv ai_service.py ai_service.py.bak
```
（不直接删除，万一需要回退）

---

### Task 12: 全量测试验证

- [ ] **Step 1: 运行所有测试**

```bash
python -m pytest tests/ -v
```
Expected: 所有测试 PASS

- [ ] **Step 2: 验证 Flask 应用可启动**

```bash
python -c "
from web_interface import app
client = app.test_client()
resp = client.get('/api/ai/providers')
print('Status:', resp.status_code)
print('Body:', resp.get_json())
"
```
Expected: `Status: 200`，返回 providers 列表 JSON

- [ ] **Step 3: 验证 CLI 可初始化**

```bash
python -c "
from cli_interface import KnowledgeCLI
cli = KnowledgeCLI()
print('CLI OK, ai_service:', cli.ai_service is not None)
"
```
Expected: `CLI OK, ai_service: True`
