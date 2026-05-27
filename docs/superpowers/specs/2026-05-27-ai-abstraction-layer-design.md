# AI 模型抽象层设计

**日期：** 2026-05-27
**状态：** 已确认

---

## 目标

将 `ai_service.py`（单一 Ollama/DeepSeek）重构为可扩展的多 Provider 架构，支持：
- 本地模型（Ollama）
- 外部 API（Claude、OpenAI、DeepSeek Cloud）

用户在 Web UI 中可实时切换 Provider 和模型，按每次调用选择。

---

## 配置设计

`config/ai.yaml`：

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
  ollama: [deepseek-r1:8b, deepseek-r1:14b, qwen2.5:7b]
  claude: [claude-opus-4-7, claude-sonnet-4-6, claude-haiku-4-5]
  openai: [gpt-4o, gpt-4o-mini]
  deepseek: [deepseek-chat, deepseek-reasoner]

defaults:
  analyze:           { provider: ollama, model: deepseek-r1:8b }
  generate_questions: { provider: ollama, model: deepseek-r1:8b }
  improve_writing:   { provider: claude, model: claude-sonnet-4-6 }
  chat:              { provider: claude, model: claude-sonnet-4-6 }
```

- `${ENV_VAR}` 引用环境变量，避免 API Key 明文存储
- `models` 显式声明可用模型，控制 UI 中的选择列表
- `defaults` 提供开箱即用的默认绑定

---

## 目录结构

```
ai/
├── __init__.py
├── provider.py          # 抽象基类 + 工厂函数
├── ollama_provider.py   # Ollama HTTP API
├── claude_provider.py   # Anthropic SDK
├── openai_provider.py   # OpenAI SDK
├── deepseek_provider.py # DeepSeek Cloud (OpenAI 兼容协议)
├── service.py           # 能力编排层（prompt 模板 + 响应解析）
└── config.py            # 加载 config/ai.yaml
```

---

## Provider 接口

所有 Provider 实现统一接口，只有一个核心方法：

```python
class BaseProvider(ABC):
    @abstractmethod
    def chat(self, messages: list[ChatMessage], model: str,
             temperature: float, max_tokens: int, **kwargs) -> ChatResponse:
        ...

    @abstractmethod
    def list_models(self) -> list[str]:
        ...

    def is_available(self) -> bool:
        return True
```

每次调用实例化 Provider 或缓存单例均可（Provider 内部管理 HTTP client/SDK）。

---

## 能力编排层 (AIService)

Provider 层只管 `chat()`。AIService 层负责：
- Prompt 模板管理（内聚为字典）
- 响应解析
- 模型选择（默认值 vs UI 指定）

```python
class AIService:
    def execute(self, capability: str, params: dict,
                provider: str = None, model: str = None) -> dict: ...

    def analyze_knowledge_item(self, title, content, tags, category,
                               provider=None, model=None) -> dict: ...
    def generate_questions(self, content, provider=None, model=None) -> list: ...
    def improve_writing(self, content, provider=None, model=None) -> str: ...
    def chat_with_knowledge(self, question, context_items, chat_history=None,
                             provider=None, model=None) -> dict: ...

    def list_providers(self) -> list[dict]: ...
    def get_default(self, capability: str) -> dict: ...
```

---

## 集成现有代码

### web_interface.py

- 旧的 `from ai_service import ai_service` 替换为：
  ```python
  from ai import AIService, load_config
  ai_config = load_config('config/ai.yaml')
  ai_service = AIService(ai_config)
  ```
- 现有 `/api/ai/*` 路由接收可选的 `provider` / `model` JSON 参数
- 新增 `GET /api/ai/providers` 返回可用 Provider 列表

### cli_interface.py

- 同理加载配置，可选 `--provider` / `--model` 参数

### 向后兼容

- `provider=None` / `model=None` 时从 `config/ai.yaml` 的 `defaults` 读取
- 现有路由无需改动即可工作（走默认值）

---

## 不在范围内

- 用户认证 / API Key 加密存储
- Prompt 模板在 Web UI 中的自定义编辑
- 流式响应（streaming）
- Provider 的并发调用或负载均衡
