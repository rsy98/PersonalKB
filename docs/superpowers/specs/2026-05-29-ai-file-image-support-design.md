# AI Module File/Image Upload Support — Design Doc

**Date:** 2026-05-29
**Goal:** Add file and image upload support to the AI chat so backend and models can process uploaded documents and images directly.

## 1. Motivation

The AI chat module currently only accepts text input. Users want to upload files (PDF, DOCX, Markdown) and images (PNG, JPG) so AI models can analyze their content. Target provider: DeepSeek API (deepseek-v4-pro/flash).

## 2. Approach

**Chosen: Approach B — Multimodal ChatMessage + local file extraction.**

- Extend `ChatMessage` to support multimodal content (text + image base64)
- Images are sent natively to DeepSeek vision as base64
- Documents (PDF/DOCX) are extracted to text locally, then sent as text blocks
- Backward compatible — existing pure-text calls require no changes

## 3. Data Model

New `ContentBlock` dataclass in `ai/provider.py`:

```python
@dataclass
class ContentBlock:
    type: str                # "text" | "image_url"
    text: str = ""           # used when type=text
    image_url: dict = None   # used when type=image_url, e.g. {"url": "data:image/png;base64,..."}

@dataclass
class ChatMessage:
    role: str
    content: str | list[ContentBlock]
```

`content` accepts both `str` (existing behavior) and `list[ContentBlock]` (multimodal). Two factory methods: `ChatMessage.text()`, `ChatMessage.multimodal()`.

## 4. File Extractor (new module `ai/file_extractor.py`)

`FileExtractor` class with a single entry point:

| Method | Purpose |
|--------|---------|
| `extract(filepath: str) -> str` | Dispatch by extension, return text |

Internally: plain text reads directly; PDF uses `PyPDF2`; DOCX uses `python-docx`. Image files are not processed by the extractor — they are read as base64 and embedded as `ContentBlock(type="image_url")`.

New pip dependencies: `PyPDF2`, `python-docx`.

## 5. Provider Changes

### 5.1 DeepSeek Provider (`ai/deepseek_provider.py`)

`chat()` checks message content type:
- `str` → `{"role": r, "content": str}`
- `list[ContentBlock]` → `{"role": r, "content": [{"type": b.type, ...}, ...]}`

Exactly matches DeepSeek's OpenAI-compatible multimodal format.

### 5.2 Ollama Provider (`ai/ollama_provider.py`)

Same detection; adds `images` field per message for Ollama's multimodal chat API.

### 5.3 Claude / OpenAI Providers

No changes this iteration (Claude/OpenAI vision can reuse the same `ContentBlock` model later).

## 6. API Changes

### 6.1 NEW `POST /api/ai/upload_attachment`

**Request:** `multipart/form-data` with `file` field.
**Response:**

```json
{
  "type": "image",
  "filename": "photo.png",
  "base64": "iVBORw...",
  "mime_type": "image/png"
}
```

or for files:

```json
{
  "type": "file",
  "filename": "report.pdf",
  "text": "extracted text content..."
}
```

Images saved to `static/images/` and base64-encoded. Files save to `static/files/`, then text-extracted.

### 6.2 Modified `POST /api/ai/chat` and `POST /api/ai/rag_chat`

Request body gains optional `attachments` array (same objects as 6.1 response). Backend builds `ChatMessage` from `question` text + attachment blocks:

```
[TextBlock(question), ImageBlock(base64) for each image, TextBlock(text) for each file]
```

## 7. Frontend

### 7.1 HTML (`web/templates/index.html`)

Chat input row gains two buttons: "🖼 图片" and "📎 文件", each wired to hidden `<input type="file">` elements. An attachment preview area above the input shows selected files as removable tags.

### 7.2 JavaScript (`web/static/js/app.js`)

- `state.attachments = []` — pending attachments
- `handleChatImageAttach(input)` — upload image to `/api/ai/upload_attachment`, push to `state.attachments`
- `handleChatFileAttach(input)` — same for documents
- `sendChatMessage()` — includes `state.attachments` in the chat/rag_chat request, then clears them

## 8. Files Changed

| File | Action | Summary |
|------|--------|---------|
| `ai/provider.py` | Modify | Add ContentBlock, extend ChatMessage |
| `ai/deepseek_provider.py` | Modify | Multimodal content in chat() |
| `ai/ollama_provider.py` | Modify | Multimodal content in chat() |
| `ai/file_extractor.py` | **New** | FileExtractor class |
| `web/blueprints/ai.py` | Modify | Add upload_attachment route; handle attachments in chat/rag_chat |
| `web/templates/index.html` | Modify | Attachment buttons and preview area in chat UI |
| `web/static/js/app.js` | Modify | Attachment handling functions |
| `requirements.txt` | Modify | Add PyPDF2, python-docx |

## 9. Edge Cases & Error Handling

- **Unsupported file type** — return 400 "不支持的文件类型"
- **File too large** — server config + client-side 10MB limit per file
- **PDF extraction fails** (e.g., scanned image PDF) — warn "无法从此PDF提取文本，请使用图片方式上传"
- **Image too large for base64** — resize client-side before encoding (>2048px → downscale)
- **Model doesn't support vision** — if attachments contain images but model lacks vision, return clear error
- **Multiple attachments** — supported, but total message size capped at API's context limit
