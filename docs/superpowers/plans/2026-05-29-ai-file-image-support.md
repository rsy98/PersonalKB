# AI File/Image Upload Support — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add file and image upload support to the AI chat so users can send documents and images to DeepSeek/Ollama models directly in chat.

**Architecture:** Extend `ChatMessage` with a `ContentBlock` type for multimodal content (text + image base64). Add a `FileExtractor` for local PDF/DOCX text extraction. DeepSeek and Ollama providers gain multimodal support. A new `/api/ai/upload_attachment` endpoint handles preprocessing; existing chat endpoints accept `attachments`. Frontend adds attachment buttons and preview tags to the chat input area.

**Tech Stack:** Python 3.x, Flask, OpenAI SDK (DeepSeek-compatible), PyPDF2, python-docx, vanilla JavaScript

---

### Task 1: Extend ChatMessage with ContentBlock for multimodal support

**Files:**
- Modify: `ai/provider.py`
- Modify: `tests/ai/test_provider.py`

**Purpose:** Add `ContentBlock` dataclass and make `ChatMessage.content` accept both `str` and `list[ContentBlock]`. Keep backward compatibility.

- [ ] **Step 1: Write tests for ContentBlock and multimodal ChatMessage**

Add to `tests/ai/test_provider.py`:

```python
import pytest
from ai.provider import BaseProvider, ChatMessage, ChatResponse, ContentBlock, create_provider
```

```python
class TestContentBlock:
    def test_create_text_block(self):
        block = ContentBlock(type="text", text="hello")
        assert block.type == "text"
        assert block.text == "hello"
        assert block.image_url is None

    def test_create_image_block(self):
        block = ContentBlock(type="image_url", image_url={"url": "data:image/png;base64,abc"})
        assert block.type == "image_url"
        assert block.text == ""
        assert block.image_url == {"url": "data:image/png;base64,abc"}


class TestChatMessageMultimodal:
    def test_create_pure_text_message(self):
        msg = ChatMessage(role="user", content="hello")
        assert msg.role == "user"
        assert msg.content == "hello"

    def test_text_factory_method(self):
        msg = ChatMessage.text("user", "hello")
        assert msg.role == "user"
        assert msg.content == "hello"

    def test_multimodal_factory_method(self):
        blocks = [
            ContentBlock(type="text", text="analyze this image"),
            ContentBlock(type="image_url", image_url={"url": "data:image/png;base64,abc"}),
        ]
        msg = ChatMessage.multimodal("user", blocks)
        assert msg.role == "user"
        assert isinstance(msg.content, list)
        assert len(msg.content) == 2
        assert msg.content[0].type == "text"
        assert msg.content[0].text == "analyze this image"
        assert msg.content[1].type == "image_url"

    def test_content_is_str_by_default(self):
        msg = ChatMessage(role="assistant", content="response")
        assert isinstance(msg.content, str)
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/ai/test_provider.py::TestContentBlock -v
pytest tests/ai/test_provider.py::TestChatMessageMultimodal -v
```

Expected: FAIL — `ContentBlock` not defined, factory methods not found.

- [ ] **Step 3: Update ai/provider.py**

Modify imports and add `ContentBlock`:

```python
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Union


@dataclass
class ContentBlock:
    """A multimodal content block — text or image."""
    type: str                # "text" | "image_url"
    text: str = ""           # used when type="text"
    image_url: dict = None   # used when type="image_url"


@dataclass
class ChatMessage:
    role: str
    content: Union[str, list[ContentBlock]]

    @staticmethod
    def text(role: str, text: str) -> "ChatMessage":
        """Create a plain-text message."""
        return ChatMessage(role=role, content=text)

    @staticmethod
    def multimodal(role: str, blocks: list[ContentBlock]) -> "ChatMessage":
        """Create a multimodal message from ContentBlocks."""
        return ChatMessage(role=role, content=blocks)
```

Keep `ChatResponse` and `BaseProvider` unchanged.

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/ai/test_provider.py::TestContentBlock -v
pytest tests/ai/test_provider.py::TestChatMessageMultimodal -v
pytest tests/ai/test_provider.py -v
```

Expected: ALL PASS — new tests pass, old tests still pass (backward compatibility).

- [ ] **Step 5: Commit**

```bash
git add ai/provider.py tests/ai/test_provider.py
git commit -m "feat: add ContentBlock and extend ChatMessage for multimodal content"
```

---

### Task 2: Create FileExtractor module for local document text extraction

**Files:**
- Create: `ai/file_extractor.py`
- Create: `tests/ai/test_file_extractor.py`

**Purpose:** `FileExtractor` class that dispatches by file extension to extract text from PDF, DOCX, and plain text files.

- [ ] **Step 1: Write tests for FileExtractor**

Create `tests/ai/test_file_extractor.py`:

```python
import os
import tempfile
import pytest
from ai.file_extractor import FileExtractor


class TestFileExtractor:
    def test_extract_txt(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False, encoding='utf-8') as f:
            f.write("Hello world\n这是中文内容")
            path = f.name
        try:
            text = FileExtractor.extract(path)
            assert "Hello world" in text
            assert "这是中文内容" in text
        finally:
            os.unlink(path)

    def test_extract_markdown(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.md', delete=False, encoding='utf-8') as f:
            f.write("# Title\n\nSome content here.")
            path = f.name
        try:
            text = FileExtractor.extract(path)
            assert "# Title" in text
        finally:
            os.unlink(path)

    def test_extract_python(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.py', delete=False, encoding='utf-8') as f:
            f.write("def hello():\n    return 'world'\n")
            path = f.name
        try:
            text = FileExtractor.extract(path)
            assert "def hello()" in text
        finally:
            os.unlink(path)

    def test_extract_unsupported_returns_none(self):
        with tempfile.NamedTemporaryFile(mode='w', suffix='.xyz', delete=False) as f:
            f.write("data")
            path = f.name
        try:
            text = FileExtractor.extract(path)
            assert text is None
        finally:
            os.unlink(path)

    def test_is_supported(self):
        assert FileExtractor.is_supported("doc.pdf") is True
        assert FileExtractor.is_supported("doc.docx") is True
        assert FileExtractor.is_supported("doc.txt") is True
        assert FileExtractor.is_supported("doc.md") is True
        assert FileExtractor.is_supported("doc.xyz") is False

    def test_is_image(self):
        assert FileExtractor.is_image("photo.png") is True
        assert FileExtractor.is_image("photo.jpg") is True
        assert FileExtractor.is_image("photo.jpeg") is True
        assert FileExtractor.is_image("photo.gif") is True
        assert FileExtractor.is_image("photo.webp") is True
        assert FileExtractor.is_image("doc.pdf") is False
```

- [ ] **Step 2: Run tests to verify they fail**

```
pytest tests/ai/test_file_extractor.py -v
```

Expected: FAIL — module not found.

- [ ] **Step 3: Create ai/file_extractor.py**

```python
import os


TEXT_EXTENSIONS = {
    '.txt', '.md', '.py', '.js', '.java', '.cpp', '.c', '.html',
    '.css', '.json', '.yaml', '.yml', '.xml', '.csv', '.rst', '.tex',
    '.vim', '.sty', '.bib', '.def',
}

DOCX_EXTENSIONS = {'.docx'}
PDF_EXTENSIONS = {'.pdf'}
IMAGE_EXTENSIONS = {'.png', '.jpg', '.jpeg', '.gif', '.bmp', '.webp'}


class FileExtractor:
    """Extract text content from files by extension."""

    @staticmethod
    def is_supported(filename: str) -> bool:
        ext = os.path.splitext(filename)[1].lower()
        return ext in TEXT_EXTENSIONS | DOCX_EXTENSIONS | PDF_EXTENSIONS

    @staticmethod
    def is_image(filename: str) -> bool:
        ext = os.path.splitext(filename)[1].lower()
        return ext in IMAGE_EXTENSIONS

    @staticmethod
    def extract(filepath: str) -> str | None:
        """Extract text from a file. Returns None if unsupported."""
        ext = os.path.splitext(filepath)[1].lower()

        if ext in TEXT_EXTENSIONS:
            with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
                return f.read()

        if ext in PDF_EXTENSIONS:
            try:
                from PyPDF2 import PdfReader
                reader = PdfReader(filepath)
                pages = []
                for page in reader.pages:
                    text = page.extract_text()
                    if text:
                        pages.append(text)
                return '\n\n'.join(pages)
            except ImportError:
                return None
            except Exception:
                return None

        if ext in DOCX_EXTENSIONS:
            try:
                from docx import Document
                doc = Document(filepath)
                paragraphs = [p.text for p in doc.paragraphs if p.text.strip()]
                return '\n\n'.join(paragraphs)
            except ImportError:
                return None
            except Exception:
                return None

        return None
```

- [ ] **Step 4: Run tests to verify they pass**

```
pytest tests/ai/test_file_extractor.py -v
```

Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add ai/file_extractor.py tests/ai/test_file_extractor.py
git commit -m "feat: add FileExtractor for PDF/DOCX/text file extraction"
```

---

### Task 3: Update OpenAIProvider chat() for multimodal messages (DeepSeek inherits)

**Files:**
- Modify: `ai/openai_provider.py`
- Modify: `tests/ai/test_openai_provider.py`

**Purpose:** OpenAIProvider.chat() checks if content is `str` (existing) or `list[ContentBlock]` (multimodal). DeepSeekProvider inherits this automatically.

- [ ] **Step 1: Write test for multimodal chat in OpenAI provider**

Add to `tests/ai/test_openai_provider.py`:

```python
from ai.provider import ContentBlock
```

```python
    @patch('ai.openai_provider.OpenAI')
    def test_chat_sends_multimodal_messages(self, MockOpenAI):
        mock_client = MagicMock()
        mock_choice = MagicMock()
        mock_choice.message.content = 'I see an image'
        mock_completion = MagicMock()
        mock_completion.choices = [mock_choice]
        mock_completion.model = 'gpt-4o'
        mock_completion.usage = MagicMock(prompt_tokens=30, completion_tokens=15)
        mock_client.chat.completions.create.return_value = mock_completion
        MockOpenAI.return_value = mock_client

        provider = OpenAIProvider(api_key='sk-test')
        messages = [
            ChatMessage.multimodal("user", [
                ContentBlock(type="text", text="Describe this image"),
                ContentBlock(type="image_url", image_url={"url": "data:image/png;base64,abc123"}),
            ])
        ]
        resp = provider.chat(messages, model='gpt-4o')

        call_kwargs = mock_client.chat.completions.create.call_args.kwargs
        sent_messages = call_kwargs['messages']
        assert len(sent_messages) == 1
        assert sent_messages[0]['role'] == 'user'
        assert isinstance(sent_messages[0]['content'], list)
        assert sent_messages[0]['content'][0] == {'type': 'text', 'text': 'Describe this image'}
        assert sent_messages[0]['content'][1] == {'type': 'image_url', 'image_url': {'url': 'data:image/png;base64,abc123'}}
        assert resp.content == 'I see an image'
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/ai/test_openai_provider.py::TestOpenAIProvider::test_chat_sends_multimodal_messages -v
```

Expected: FAIL — multimodal content not handled, `{'role': 'user', 'content': [...]}` not constructed.

- [ ] **Step 3: Update ai/openai_provider.py chat() method**

Replace the `chat()` method in `OpenAIProvider`:

```python
    def _format_message(self, m: ChatMessage) -> dict:
        """Format a ChatMessage for the OpenAI/DeepSeek API."""
        if isinstance(m.content, str):
            return {'role': m.role, 'content': m.content}
        # Multimodal: list[ContentBlock]
        content_list = []
        for block in m.content:
            if block.type == 'text':
                content_list.append({'type': 'text', 'text': block.text})
            elif block.type == 'image_url':
                content_list.append({'type': 'image_url', 'image_url': block.image_url})
        return {'role': m.role, 'content': content_list}

    def chat(self, messages: list[ChatMessage], model: str,
             temperature: float = 0.7, max_tokens: int = 4096, **kwargs) -> ChatResponse:
        formatted = [self._format_message(m) for m in messages]
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
```

- [ ] **Step 4: Run all OpenAI tests**

```
pytest tests/ai/test_openai_provider.py -v
```

Expected: ALL PASS — existing plain-text test + new multimodal test.

- [ ] **Step 5: Commit**

```bash
git add ai/openai_provider.py tests/ai/test_openai_provider.py
git commit -m "feat: add multimodal message support to OpenAI/DeepSeek provider chat()"
```

---

### Task 4: Update OllamaProvider chat() for multimodal messages

**Files:**
- Modify: `ai/ollama_provider.py`
- Modify: `tests/ai/test_ollama_provider.py`

**Purpose:** Ollama's chat API supports images via a separate `images` field. Extract base64 data from `ContentBlock(type="image_url")` and pass to Ollama's `images` array.

- [ ] **Step 1: Write test for Ollama multimodal chat**

Add to `tests/ai/test_ollama_provider.py`:

```python
from unittest.mock import patch, MagicMock
from ai.provider import ChatMessage, ContentBlock
from ai.ollama_provider import OllamaProvider


class TestOllamaMultimodal:
    @patch('ai.ollama_provider.requests')
    def test_chat_sends_images_field_for_multimodal(self, mock_requests):
        from ai.provider import ChatResponse
        mock_resp = MagicMock()
        mock_resp.json.return_value = {
            'message': {'content': 'I see a cat'},
            'model': 'llava:latest',
            'prompt_eval_count': 10,
            'eval_count': 5,
        }
        mock_requests.post.return_value = mock_resp

        provider = OllamaProvider()
        messages = [
            ChatMessage.multimodal("user", [
                ContentBlock(type="text", text="What is in this image?"),
                ContentBlock(type="image_url", image_url={"url": "data:image/png;base64,iVBORw0KGgo"}),
            ])
        ]
        resp = provider.chat(messages, model='llava:latest')

        call_kwargs = mock_requests.post.call_args
        payload = call_kwargs[1]['json']
        # Text should be extracted from text blocks
        assert payload['messages'][0]['content'] == 'What is in this image?'
        # Images should be in the images array
        assert 'images' in payload['messages'][0]
        assert payload['messages'][0]['images'] == ['iVBORw0KGgo']
        assert resp.content == 'I see a cat'
```

- [ ] **Step 2: Run test to verify it fails**

```
pytest tests/ai/test_ollama_provider.py::TestOllamaMultimodal -v
```

Expected: FAIL — no multimodal handling.

- [ ] **Step 3: Update ai/ollama_provider.py chat() method**

Replace the `chat()` method:

```python
    def chat(self, messages: list[ChatMessage], model: str,
             temperature: float = 0.7, max_tokens: int = 4096, **kwargs) -> ChatResponse:
        api_messages = []
        for m in messages:
            if isinstance(m.content, str):
                api_messages.append({'role': m.role, 'content': m.content})
            else:
                # Multimodal: separate text and images
                text_parts = []
                img_b64s = []
                for block in m.content:
                    if block.type == 'text':
                        text_parts.append(block.text)
                    elif block.type == 'image_url':
                        url = block.image_url.get('url', '')
                        if url.startswith('data:'):
                            # Strip the "data:image/png;base64," prefix
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
```

- [ ] **Step 4: Run all Ollama tests**

```
pytest tests/ai/test_ollama_provider.py -v
```

Expected: ALL PASS.

- [ ] **Step 5: Commit**

```bash
git add ai/ollama_provider.py tests/ai/test_ollama_provider.py
git commit -m "feat: add multimodal message support to Ollama provider chat()"
```

---

### Task 5: Add upload_attachment API endpoint

**Files:**
- Modify: `web/blueprints/ai.py`

**Purpose:** New endpoint `POST /api/ai/upload_attachment` — uploads a file, extracts text (documents) or reads base64 (images), returns the processed data.

- [ ] **Step 1: Add the route to web/blueprints/ai.py**

After the imports, add the file_extractor import. Then add the route before `api_ai_recommendations`:

At the top, add to imports (after the existing `import os`):

```python
from ai.file_extractor import FileExtractor
```

Add the route after `list_uploaded_files()`:

```python
@ai_bp.route('/api/ai/upload_attachment', methods=['POST'])
def api_ai_upload_attachment():
    """Upload a file or image for AI chat attachment.
    Returns processed data: base64 for images, extracted text for files."""
    try:
        if 'file' not in request.files:
            return jsonify({'error': '没有选择文件'}), 400

        file = request.files['file']
        if not file or file.filename == '':
            return jsonify({'error': '没有选择文件'}), 400

        filename = file.filename
        ext = os.path.splitext(filename)[1].lower()

        if FileExtractor.is_image(filename):
            import base64
            file_data = file.read()
            # 10MB limit
            if len(file_data) > 10 * 1024 * 1024:
                return jsonify({'error': '图片文件过大，最大10MB'}), 400
            mime_type = {
                '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.gif': 'image/gif', '.bmp': 'image/bmp', '.webp': 'image/webp',
            }.get(ext, 'image/png')
            b64 = base64.b64encode(file_data).decode('ascii')
            data_url = f'data:{mime_type};base64,{b64}'

            # Also save the image
            static_dir = os.path.join(current_app.static_folder, 'images')
            os.makedirs(static_dir, exist_ok=True)
            save_path = os.path.join(static_dir, filename)
            with open(save_path, 'wb') as f:
                f.write(file_data)

            return jsonify({
                'type': 'image',
                'filename': filename,
                'base64': data_url,
                'mime_type': mime_type,
            })

        elif FileExtractor.is_supported(filename):
            # Save to temp then extract
            import tempfile
            file_data = file.read()
            if len(file_data) > 10 * 1024 * 1024:
                return jsonify({'error': '文件过大，最大10MB'}), 400

            # Save file to static/files/
            static_dir = os.path.join(current_app.static_folder, 'files')
            os.makedirs(static_dir, exist_ok=True)
            save_path = os.path.join(static_dir, filename)
            with open(save_path, 'wb') as f:
                f.write(file_data)

            text = FileExtractor.extract(save_path)
            if text is None:
                return jsonify({'error': f'无法从此文件提取文本: {filename}'}), 400

            return jsonify({
                'type': 'file',
                'filename': filename,
                'text': text[:8000],  # cap at 8000 chars
            })

        else:
            return jsonify({'error': f'不支持的文件类型: {ext}'}), 400

    except Exception as e:
        return jsonify({'error': f'上传处理失败: {str(e)}'}), 500
```

- [ ] **Step 2: Verify the route is registered**

Run the app and check the route:

```bash
python -c "from web.app import create_app; app = create_app(); print([r.rule for r in app.url_map.iter_rules() if 'upload_attachment' in str(r)])"
```

Expected: `['/api/ai/upload_attachment']`

- [ ] **Step 3: Commit**

```bash
git add web/blueprints/ai.py
git commit -m "feat: add POST /api/ai/upload_attachment endpoint for file/image preprocessing"
```

---

### Task 6: Update chat and rag_chat endpoints to handle attachments

**Files:**
- Modify: `web/blueprints/ai.py`

**Purpose:** Modify `api_ai_chat` and `api_ai_rag_chat` to accept optional `attachments` array and build multimodal `ChatMessage` when present.

- [ ] **Step 1: Update api_ai_chat to accept attachments**

Replace the message-building section in `api_ai_chat()` (lines ~220-228) with multimodal support. The full updated function:

```python
@ai_bp.route('/api/ai/chat', methods=['POST'])
def api_ai_chat():
    """AI对话"""
    try:
        data = request.json
        question = data.get('question', '')
        item_id = data.get('item_id')
        chat_history = data.get('chat_history', [])
        provider = data.get('provider')
        model = data.get('model')
        attachments = data.get('attachments', [])  # NEW

        context_items = []
        if item_id:
            manager = get_manager()
            item = manager.get_item_by_id(item_id)
            if item:
                context_items.append(item)
            related_items = manager.get_related_items(item_id)
            context_items.extend(related_items)
        else:
            manager = get_manager()
            recent_items = manager.get_recent_items(limit=5)
            context_items.extend(recent_items)

        ai_service = get_ai_service()

        # Build the user message (multimodal if attachments present)
        user_blocks = [ContentBlock(type="text", text=question)]
        for att in attachments:
            if att.get('type') == 'image':
                user_blocks.append(ContentBlock(
                    type="image_url",
                    image_url={"url": att.get('base64', '')},
                ))
            elif att.get('type') == 'file':
                text = att.get('text', '')
                if text:
                    user_blocks.append(ContentBlock(
                        type="text",
                        text=f"\n[文件: {att.get('filename', '')}]\n{text}",
                    ))

        # Build context
        context = ''
        if chat_history:
            context += '对话历史:\n'
            for msg in chat_history[-6:]:
                role_label = '用户' if msg.get('role') == 'user' else '助手'
                context += f"{role_label}: {msg.get('content', '')}\n"
            context += '\n'
        context += '当前知识上下文:\n'
        context += '\n'.join([
            f"标题: {item.get('title', '')}\n内容: {item.get('content', '')[:2000]}"
            for item in context_items[:3]
        ])

        # Resolve provider/model
        p_name, m_name = ai_service._resolve('chat', provider, model)
        prov = ai_service._get_provider(p_name)
        prompt = PROMPTS['chat']

        system_msg = ChatMessage.text('system', prompt['system'])
        user_msg = ChatMessage.multimodal('user', user_blocks)

        resp = prov.chat([system_msg, user_msg], model=m_name)

        return jsonify({
            'answer': resp.content,
            'thinking': '',
            'full_response': resp.content,
            'model': resp.model,
            'provider': p_name,
        })

    except Exception as e:
        print(f"AI对话错误: {str(e)}")
        return jsonify({
            "thinking": "",
            "answer": f"AI服务错误: {str(e)}"
        }), 500
```

Note: Remove the old `ai_service.chat_with_knowledge()` call — replace with direct `prov.chat()` since we need to control message construction for multimodal.

- [ ] **Step 2: Update api_ai_rag_chat similarly**

Replace the message-building section in `api_ai_rag_chat()` (lines ~580-590). The system prompt and user message construction — add attachments:

```python
@ai_bp.route('/api/ai/rag_chat', methods=['POST'])
def api_ai_rag_chat():
    """RAG 对话：语义检索 + AI 生成"""
    try:
        data = request.get_json(silent=True) or {}
        question = data.get('question', '').strip()
        if not question:
            return jsonify({'error': '问题不能为空'}), 400

        chat_history = data.get('chat_history', [])
        provider = data.get('provider')
        model = data.get('model')
        top_k = min(data.get('top_k', 5), 10)
        attachments = data.get('attachments', [])  # NEW

        manager = get_manager()

        if not manager.has_embeddings():
            return jsonify({
                'answer': '知识库尚未建立索引，请先在知识管理页面点击"生成索引"按钮。',
                'thinking': '',
                'sources': [],
            })

        items_with_vec = manager.get_all_embeddings()
        ai_service = get_ai_service()

        # Semantic search
        relevant = ai_service.semantic_search(question, items_with_vec, top_k=top_k)

        context = '以下是与用户问题相关的知识库内容：\n\n'
        for i, item in enumerate(relevant):
            context += f'【资料{i+1}】标题: {item.get("title", "")}\n'
            context += f'内容: {(item.get("content", "") or "")[:500]}\n'
            context += f'相关度: {item["score"]:.2f}\n\n'

        chat_context = ''
        if chat_history:
            chat_context = '对话历史:\n'
            for msg in chat_history[-6:]:
                role_label = '用户' if msg.get('role') == 'user' else '助手'
                chat_context += f'{role_label}: {msg.get("content", "")}\n'
            chat_context += '\n'

        system_prompt = (
            '你是一个知识库助手。请基于提供的参考资料回答用户问题。\n'
            '如果参考资料包含了相关信息，请引用具体的资料编号。\n'
            '如果参考资料不够充分，可以结合你的知识进行补充，但要明确说明哪些来自资料、哪些来自你的知识。'
        )

        # Build multimodal user message if attachments present
        user_blocks = [ContentBlock(type="text", text=chat_context + context + f'\n用户问题：{question}')]
        for att in attachments:
            if att.get('type') == 'image':
                user_blocks.append(ContentBlock(
                    type="image_url",
                    image_url={"url": att.get('base64', '')},
                ))
            elif att.get('type') == 'file':
                text = att.get('text', '')
                if text:
                    user_blocks.append(ContentBlock(
                        type="text",
                        text=f"\n[文件: {att.get('filename', '')}]\n{text}",
                    ))

        p_name, m_name = ai_service._resolve('chat', provider, model)
        prov = ai_service._get_provider(p_name)

        system_msg = ChatMessage.text('system', system_prompt)
        user_msg = ChatMessage.multimodal('user', user_blocks)

        resp = prov.chat([system_msg, user_msg], model=m_name)

        sources = [{
            'id': item['id'],
            'title': item.get('title', ''),
            'score': item['score'],
            'snippet': (item.get('content', '') or '')[:150],
        } for item in relevant]

        return jsonify({
            'answer': resp.content,
            'thinking': '',
            'sources': sources,
            'model': resp.model,
            'provider': p_name,
        })
    except Exception as e:
        return jsonify({
            'answer': f'RAG对话出错: {str(e)}',
            'thinking': '',
            'sources': [],
        }), 500
```

- [ ] **Step 3: Verify imports at top of ai.py**

Ensure `ContentBlock` and `ChatMessage` are imported. Add at top:

```python
from ai.provider import ChatMessage, ContentBlock
```

- [ ] **Step 4: Commit**

```bash
git add web/blueprints/ai.py
git commit -m "feat: update chat/rag_chat endpoints to accept multimodal attachments"
```

---

### Task 7: Update frontend HTML — add attachment buttons to chat input

**Files:**
- Modify: `web/templates/index.html`

**Purpose:** Add file/image buttons, hidden inputs, and attachment preview area to the AI chat input row.

- [ ] **Step 1: Read the current chat input row to locate it**

The current HTML is at approximately lines 320-326:

```html
<div class="chat-input-row">
    <input type="text" class="chat-input" id="chatInput"
           placeholder="输入问题..." autocomplete="off"
           onkeydown="if(event.key==='Enter'&&!event.shiftKey){sendChatMessage();event.preventDefault()}">
    <button class="btn btn-primary" onclick="sendChatMessage()">发送</button>
    <button class="btn btn-outline btn-sm" onclick="clearChatHistory()">清空</button>
</div>
```

- [ ] **Step 2: Replace the chat-input-row with the enhanced version**

Replace the existing `<div class="chat-input-row">...</div>` block with:

```html
<div class="chat-input-row" style="flex-direction:column;gap:8px;align-items:stretch;">
    <div id="chatAttachmentPreviews" style="display:flex;gap:6px;flex-wrap:wrap;min-height:0;"></div>
    <div style="display:flex;align-items:center;gap:8px;">
        <input type="file" id="chatImageInput" accept="image/*" style="display:none;" onchange="handleChatImageAttach(this)">
        <button type="button" class="btn btn-outline btn-sm" onclick="document.getElementById('chatImageInput').click()" title="上传图片">🖼 图片</button>

        <input type="file" id="chatFileInput" accept=".pdf,.docx,.txt,.md,.py,.json,.csv,.html,.css,.js,.java,.xml,.yaml,.yml,.tex,.rst,.vim" style="display:none;" onchange="handleChatFileAttach(this)">
        <button type="button" class="btn btn-outline btn-sm" onclick="document.getElementById('chatFileInput').click()" title="上传文件">📎 文件</button>

        <input type="text" class="chat-input" id="chatInput"
               placeholder="输入问题..." autocomplete="off" style="flex:1;"
               onkeydown="if(event.key==='Enter'&&!event.shiftKey){sendChatMessage();event.preventDefault()}">
        <button class="btn btn-primary" onclick="sendChatMessage()">发送</button>
        <button class="btn btn-outline btn-sm" onclick="clearChatHistory()">清空</button>
    </div>
</div>
```

- [ ] **Step 3: Commit**

```bash
git add web/templates/index.html
git commit -m "feat: add attachment buttons and preview area to AI chat input"
```

---

### Task 8: Update frontend JS — attachment handling functions

**Files:**
- Modify: `web/static/js/app.js`

**Purpose:** Add `handleChatImageAttach()`, `handleChatFileAttach()`, update `sendChatMessage()` to include attachments, and add `removeChatAttachment()` helper.

- [ ] **Step 1: Add attachment state and functions**

Insert after the `clearChatHistory()` function (around line 1273):

```javascript
// ── Chat Attachment Handling ──

state.attachments = [];

function removeChatAttachment(index) {
    state.attachments.splice(index, 1);
    renderChatAttachments();
}

function renderChatAttachments() {
    const container = document.getElementById('chatAttachmentPreviews');
    if (!container) return;
    container.innerHTML = state.attachments.map((att, i) => {
        const icon = att.type === 'image' ? '🖼' : '📄';
        const name = escapeHtml(att.filename || 'attachment');
        return `<span style="display:inline-flex;align-items:center;gap:4px;background:var(--bg-tertiary);border:1px solid var(--border);border-radius:4px;padding:2px 8px;font-size:12px;">
            ${icon} ${name}
            <span onclick="removeChatAttachment(${i})" style="cursor:pointer;color:var(--text-tertiary);margin-left:2px;">×</span>
        </span>`;
    }).join('');
}

async function handleChatImageAttach(input) {
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    // Client-side size check: 10MB
    if (file.size > 10 * 1024 * 1024) {
        showToast('图片文件过大，最大10MB', 'error');
        input.value = '';
        return;
    }
    const formData = new FormData();
    formData.append('file', file);
    showToast('处理图片中...', 'success');
    try {
        const resp = await fetch('/api/ai/upload_attachment', { method: 'POST', body: formData });
        const result = await resp.json();
        if (result.error) {
            showToast(result.error, 'error');
        } else {
            state.attachments.push({
                type: result.type,
                filename: result.filename,
                base64: result.base64,
                mime_type: result.mime_type,
            });
            renderChatAttachments();
            showToast(`图片已添加: ${result.filename}`, 'success');
        }
    } catch (e) {
        showToast('上传失败: ' + e.message, 'error');
    }
    input.value = '';
}

async function handleChatFileAttach(input) {
    if (!input.files || input.files.length === 0) return;
    const file = input.files[0];
    if (file.size > 10 * 1024 * 1024) {
        showToast('文件过大，最大10MB', 'error');
        input.value = '';
        return;
    }
    const formData = new FormData();
    formData.append('file', file);
    showToast('处理文件中...', 'success');
    try {
        const resp = await fetch('/api/ai/upload_attachment', { method: 'POST', body: formData });
        const result = await resp.json();
        if (result.error) {
            showToast(result.error, 'error');
        } else {
            state.attachments.push({
                type: result.type,
                filename: result.filename,
                text: result.text,
            });
            renderChatAttachments();
            showToast(`文件已添加: ${result.filename}`, 'success');
        }
    } catch (e) {
        showToast('上传失败: ' + e.message, 'error');
    }
    input.value = '';
}
```

- [ ] **Step 2: Update sendChatMessage() to include attachments**

Insert at the beginning of `sendChatMessage()` (after getting `question`), add the attachments array and clear it. Also update the AI chat and RAG chat API calls to include `attachments`.

Replace the `sendChatMessage` function:

```javascript
async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const question = input.value.trim();
    if (!question && state.attachments.length === 0) return;
    input.value = '';

    const attachments = [...state.attachments];  // snapshot
    state.attachments = [];
    renderChatAttachments();

    const messages = document.getElementById('chatMessages');
    // Show user message with attachment indicators
    let userMsgHtml = escapeHtml(question);
    if (attachments.length > 0) {
        userMsgHtml += '<div style="margin-top:4px;font-size:11px;color:var(--text-tertiary);">';
        userMsgHtml += attachments.map(a => {
            const icon = a.type === 'image' ? '🖼' : '📎';
            return icon + ' ' + escapeHtml(a.filename || 'attachment');
        }).join(' ');
        userMsgHtml += '</div>';
    }
    messages.innerHTML += `<div class="chat-message user">${userMsgHtml}</div>`;
    const modeLabel = state.ragMode ? 'RAG 检索中...' : '思考中...';
    messages.innerHTML += `<div class="chat-message assistant" id="chatLoading"><div class="spinner"></div> ${modeLabel}</div>`;
    messages.scrollTop = messages.scrollHeight;

    try {
        const opts = getAIOptions('chat');
        let result;
        if (state.ragMode) {
            result = await apiService.ragChat(question, state.chatHistory, opts.provider, opts.model);
        } else {
            result = await apiService.aiChat({
                question,
                item_id: state.currentItemId,
                chat_history: state.chatHistory,
                provider: opts.provider,
                model: opts.model,
                attachments: attachments,  // NEW
            });
        }
        document.getElementById('chatLoading')?.remove();
        const answer = result.answer || result.content || JSON.stringify(result);
        const thinking = result.thinking || '';
        let html = '';
        if (thinking) {
            html += `<details style="margin-bottom:8px;"><summary style="cursor:pointer;color:var(--text-tertiary);font-size:12px;">思考过程</summary><p style="color:var(--text-tertiary);font-size:12px;white-space:pre-wrap;">${escapeHtml(thinking)}</p></details>`;
        }
        html += `<div style="white-space:pre-wrap;">${simpleMarkdownRender(answer)}</div>`;

        if (result.sources && result.sources.length > 0) {
            html += `<details style="margin-top:8px;"><summary style="cursor:pointer;color:var(--accent);font-size:11px;">📚 参考来源 (${result.sources.length})</summary>`;
            html += result.sources.map((s, i) => `
                <div style="margin:4px 0;padding:4px 8px;background:var(--bg-tertiary);border-radius:4px;font-size:11px;cursor:pointer;"
                     onclick="showItemDetail(${s.id})">
                    <span style="color:var(--accent);">${(s.score * 100).toFixed(0)}%</span>
                    <span style="font-weight:500;">${escapeHtml(s.title)}</span>
                    ${s.snippet ? `<span style="color:var(--text-tertiary);"> — ${escapeHtml(s.snippet)}</span>` : ''}
                </div>`).join('');
            html += '</details>';
        }

        messages.innerHTML += `<div class="chat-message assistant">${html}</div>`;
        state.chatHistory.push({ role: 'user', content: question }, { role: 'assistant', content: answer });
    } catch (e) {
        document.getElementById('chatLoading')?.remove();
        messages.innerHTML += `<div class="chat-message assistant" style="color:var(--danger);">错误: ${escapeHtml(e.message)}</div>`;
    }
    messages.scrollTop = messages.scrollHeight;
}
```

- [ ] **Step 3: Update clearChatHistory() to clear attachments too**

```javascript
function clearChatHistory() {
    state.chatHistory = [];
    state.attachments = [];
    renderChatAttachments();
    document.getElementById('chatMessages').innerHTML = `
        <div class="chat-message assistant">聊天历史已清空。有什么我可以帮你的？</div>
    `;
}
```

- [ ] **Step 4: Update the ragChat API call path to include attachments**

The `ragChat` API function in the `apiService` object needs to accept attachments. Update line ~135:

```javascript
ragChat: (question, chatHistory, provider, model, attachments) => api('/api/ai/rag_chat', {
    method: 'POST',
    body: JSON.stringify({ question, chat_history: chatHistory, provider, model, attachments }),
}),
```

And where it's called in sendChatMessage (line ~1227):

```javascript
result = await apiService.ragChat(question, state.chatHistory, opts.provider, opts.model, attachments);
```

- [ ] **Step 5: Commit**

```bash
git add web/static/js/app.js
git commit -m "feat: add chat attachment upload, preview, and send logic"
```

---

### Task 9: Add PyPDF2 and python-docx to requirements

**Files:**
- Modify: `requirements.txt`

**Purpose:** Add new pip dependencies for PDF and DOCX text extraction.

- [ ] **Step 1: Update requirements.txt**

Add to the end:

```
PyPDF2
python-docx
```

- [ ] **Step 2: Install dependencies**

```bash
pip install PyPDF2 python-docx
```

- [ ] **Step 3: Commit**

```bash
git add requirements.txt
git commit -m "chore: add PyPDF2 and python-docx dependencies"
```

---

### Task 10: Integration test — manual smoke test

**Files:** None (manual testing)

**Purpose:** Verify the full flow works end-to-end: upload image/file → send chat → AI response.

- [ ] **Step 1: Start the app**

```bash
python run.py --db knowledge.db
```

- [ ] **Step 2: Open browser to http://127.0.0.1:5000**

- [ ] **Step 3: Test image attachment**
  1. Click "🖼 图片" button in chat input
  2. Select a PNG or JPG image
  3. Verify attachment preview tag appears below input
  4. Type "描述这张图片" in the text input
  5. Click "发送"
  6. Verify AI responds with image description

- [ ] **Step 4: Test file attachment**
  1. Click "📎 文件" button
  2. Select a PDF, TXT, or DOCX file
  3. Verify attachment preview tag appears
  4. Type "总结这个文件的内容" and send
  5. Verify AI responds with file content analysis

- [ ] **Step 5: Test multiple attachments**
  1. Add both an image and a file
  2. Send with a question
  3. Verify both are processed

- [ ] **Step 6: Test error cases**
  1. Try uploading an unsupported file type (.exe) — should get error toast
  2. Try sending empty message with no attachments — should not send

- [ ] **Step 7: Run all existing tests**

```bash
pytest tests/ -v
```

Expected: ALL PASS — no regressions.

---

## Self-Review

**1. Spec coverage:**
- Data model (ContentBlock, ChatMessage) → Task 1 ✓
- FileExtractor (PDF/DOCX/text) → Task 2 ✓
- DeepSeek Provider multimodal → Task 3 (OpenAI provider, inherited by DeepSeek) ✓
- Ollama Provider multimodal → Task 4 ✓
- upload_attachment API → Task 5 ✓
- chat/rag_chat API attachment handling → Task 6 ✓
- Frontend HTML → Task 7 ✓
- Frontend JS → Task 8 ✓
- requirements.txt → Task 9 ✓
- Edge cases (unsupported type, file too large) → Task 5 + Task 8 (client-side checks) ✓

**2. Placeholder scan:** No TBD/TODO. All code is concrete. ✓

**3. Type consistency:**
- `ContentBlock` fields (`type`, `text`, `image_url`) consistent across all tasks ✓
- `ChatMessage.text()` and `ChatMessage.multimodal()` signatures consistent ✓
- `state.attachments` shape (`{type, filename, base64, text}`) consistent between JS (Task 8) and API consumption (Task 6) ✓
- `FileExtractor.extract()` returns `str | None` — handled in Task 5 ✓
