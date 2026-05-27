# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Personal Knowledge Management System (个人知识管理系统) — a Flask web app backed by SQLite for organizing, searching, reviewing, and analyzing knowledge entries. Supports multiple domain-specific databases, LaTeX math rendering, file uploads, and local LLM integration via Ollama.

## Commands

```bash
# Start the web app (interactive DB selection)
python run.py

# Start with a specific database
python run.py --db knowledge.db

# Start CLI interface
python cli_interface.py

# Initialize/upgrade a database
python setup.py
```

No test suite, linter, or type checker is configured in this project.

## Architecture

**Data layer:** SQLite with per-thread connections (`_get_connection()`). Schema: `knowledge_items` (core table with content hash dedup), `tags`, `knowledge_tags` (many-to-many), `knowledge_relationships` (edges between items), `review_sessions` (spaced repetition history). The `KnowledgeDatabase` class in `setup.py` handles schema creation/migration; `KnowledgeManager` in `knowledge_manager.py` handles all CRUD and queries.

**Web layer:** `web_interface.py` — a single-file Flask app (~7200 lines). Frontend is inline HTML/CSS/JS served from the `/` route. ~35 API routes under `/api/*` provide JSON endpoints for search, CRUD, file upload, AI features, knowledge graph, import/export, and database switching. LaTeX formulas (`$...$`, `$$...$$`, `\[...\]`) are preprocessed for client-side MathJax rendering.

**AI integration:** `ai_service.py` talks to a local Ollama instance (`localhost:11434`) running `deepseek-r1:8b`. Provides content analysis, test question generation, writing improvement, and a knowledge-grounded chat. The `_parse_thinking_and_answer()` method separates the DeepSeek reasoning traces from final answers.

**CLI:** `cli_interface.py` mirrors the web functionality in terminal form.

**Multi-DB support:** The app can operate against multiple SQLite databases (`knowledge.db`, `art.db`, `AI.db`, `math.db`, `life.db`, `physics.db`). The active database is set via the `_current_db` module-level variable in `web_interface.py` or the `CURRENT_DATABASE` environment variable.

**Entry point:** `run.py` handles argument parsing, DB selection (via `interactive_mode.py`), initialization, and web server startup.

## Key Implementation Details

- Database connections are **not** thread-safe by design — `KnowledgeManager._get_connection()` creates a new connection per call. Callers must close connections.
- Content deduplication uses MD5 hash stored in `content_hash` (UNIQUE constraint).
- Spaced repetition uses a simplified SM-2 algorithm in `_calculate_next_interval()`.
- Chinese text support throughout: `jieba` for segmentation (listed in requirements but usage is minimal in current code), custom `secure_filename_with_chinese()` preserves CJK characters in upload filenames.
- File upload encoding detection uses `chardet` for text files.
- The `static/` directory has `files/` and `images/` subdirectories for uploads. The `uploads/` directory contains sample JSON import files.
