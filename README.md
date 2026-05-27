# 个人知识管理系统

基于 Flask + SQLite 的个人知识管理 Web 应用，支持知识的增删改查、语义搜索、RAG 问答、知识图谱可视化、间隔重复复习、多格式导出，以及多 Provider AI 集成（Ollama / DeepSeek / Claude / OpenAI）。

## 功能概览

### 知识管理
- **CRUD 操作** — 标题、内容（Markdown + LaTeX）、摘要、标签、分类、重要性（1-5）、理解度（1-5）
- **多关键词搜索** — 逗号分隔 AND 逻辑，支持关键词搜索和语义向量搜索两种模式
- **AI 辅助录入** — 从 URL / 粘贴文本 / 已上传文件 智能提取结构化知识条目，支持快速模式（跳过预览直接保存）
- **批量操作** — 批量添加/移除/设置标签、批量修改分类
- **多格式导出** — JSON（单文件）、Markdown（.zip，每条目一个 .md）、Anki CSV（可直接导入 Anki）
- **JSON 批量导入** — 从任意位置选取 .json 文件，客户端解析后批量导入
- **文件上传** — 拖拽或点击上传图片和文件，内联插入 Markdown 链接，中文文件名安全保留

### 语义搜索 & RAG 问答
- **向量嵌入** — 使用 Ollama embedding 模型（默认 `bge-m3:latest`，1024 维）为知识条目生成向量
- **语义搜索** — 基于余弦相似度的语义检索，结果按相关度排序并显示匹配百分比
- **RAG 问答** — 检索增强生成：语义检索 Top-K 相关条目 → 作为上下文喂给 LLM → 带来源引用的回答
- **一键生成索引** — 搜索栏内置"生成索引"按钮，批量为全库条目生成嵌入向量

### 间隔重复复习
- **SM-2 算法** — 根据评分自动计算下次复习时间和 ease factor
- **两种排序** — 按日期排序 / AI 智能排序（根据内容关联度和优先级优化复习顺序）
- **复习全部** — 不受排期限制，查看全部条目进行复习
- **5 级评分** — 从"完全忘记"到"完全掌握"，颜色编码反馈

### 知识图谱
- **力导向图** — vis-network 可视化，节点按重要性着色，支持拖拽、缩放、聚焦
- **AI 发现关联** — 自动分析条目内容，发现隐藏的知识关联（支持全部/按分类）
- **建议管理** — 预览 AI 发现的关联，逐个采纳或全部采纳/忽略，建议边以虚线显示
- **分类过滤** — 按分类筛选图谱节点

### AI 学习规划
- **独立生成** — 不局限于知识库已有内容，AI 基于专业知识独立设计学习路径
- **结构化输出** — 3-6 个阶段，每阶段含预计时长、前置知识、核心概念、资源推荐、掌握标准
- **本地管理** — 保存路径到 localStorage、导出为 JSON 文件、从 JSON 文件导入、删除旧路径

### AI 助手
- **知识库对话** — 基于知识库内容的智能问答，支持多轮对话历史
- **RAG 模式** — 可切换：开启后自动检索相关条目增强回答质量，关闭则为纯模型对话
- **条目分析** — 对单个条目生成摘要、关键知识点、相关主题和学习建议
- **题目生成** — 基于条目内容生成概念题、应用题、分析题
- **写作改进** — 优化文本清晰度和专业性，可一键采纳结果
- **条目专属对话** — 在条目详情弹窗中，围绕该条目与 AI 对话，拥有独立对话历史

### 多数据库
- 预设 6 个知识库：通用知识、艺术、AI、数学、生活、物理
- 运行时切换数据库，无需重启
- 新数据库自动初始化表结构

### 界面
- **双主题** — CSS 变量驱动的深色/浅色主题，刷新保持选择
- **响应式布局** — 桌面端可折叠侧边栏，移动端自动隐藏为汉堡菜单
- **LaTeX 渲染** — MathJax 客户端渲染，支持行内 `$...$` 和块级 `$$...$$`
- **键盘快捷键** — `Ctrl+F` 聚焦搜索，`Ctrl+G` 图谱面板，`Ctrl+R` 复习面板，`Esc` 关闭弹窗

---

## 快速开始

### 前置要求

- Python 3.9+
- [Ollama](https://ollama.com)（可选，使用本地 AI 功能时需要）
- 拉取所需模型：`ollama pull bge-m3:latest`（语义搜索专用）、`ollama pull qwen3:8b`（对话用）

### 安装运行

```bash
# 克隆仓库
git clone <repo-url>
cd <repo-name>

# 安装依赖
pip install -r requirements.txt

# 启动（交互式选择数据库）
python run.py

# 或指定数据库启动
python run.py --db knowledge.db

# 或跳过数据库选择
python run.py --auto
```

启动后自动打开浏览器访问 `http://localhost:5000`。

### Windows

双击项目根目录下的 `运行程序.bat` 一键启动。

### 配置 API Key（可选）

如需使用云端 AI 服务，复制并配置环境变量：

```bash
export DEEPSEEK_API_KEY=your_key    # DeepSeek
export CLAUDE_API_KEY=your_key      # Anthropic Claude
export OPENAI_API_KEY=your_key      # OpenAI
```

---

## AI 配置

配置文件 `config/ai.yaml`，每个 AI 能力可独立指定 provider 和 model：

```yaml
default_provider: ollama

providers:
  ollama:
    type: ollama
    base_url: http://localhost:11434
  deepseek:
    type: deepseek
    api_key: ${DEEPSEEK_API_KEY}
  claude:
    type: claude
    api_key: ${CLAUDE_API_KEY}
  openai:
    type: openai
    api_key: ${OPENAI_API_KEY}

embedding:
  provider: ollama
  model: bge-m3:latest

defaults:
  chat:
    provider: ollama
    model: qwen3:8b
  extract:
    provider: ollama
    model: deepseek-r1:8b
  analyze:
    provider: ollama
    model: qwen3:8b
  generate_questions:
    provider: ollama
    model: qwen3:8b
  improve_writing:
    provider: ollama
    model: qwen3:8b
  discover_relationships:
    provider: ollama
    model: qwen3:8b
  discover_gaps:
    provider: ollama
    model: qwen3:8b
  generate_learning_path:
    provider: ollama
    model: qwen3:8b
  optimize_review_plan:
    provider: ollama
    model: qwen3:8b
```

API Key 支持 `${环境变量名}` 语法引用，避免在配置文件中明文泄露。

---

## 应用配置

`config/app.yaml`：

```yaml
database:
  path: knowledge.db

flask:
  host: 127.0.0.1
  port: 5000
  debug: false

upload:
  image_extensions: [png, jpg, jpeg, gif, bmp, webp]
  file_extensions: [pdf, doc, docx, txt, zip, rar, xls, xlsx, ppt, pptx, vim, py, yaml, tex, md, sty, bib, def]
  text_extensions: [md, txt, tex, rst, vim, csv, py, js, java, cpp, c, html, css, json, yaml, yml, xml]
```

---

## API 一览

### 知识 CRUD

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/search?q=关键词` | 关键词搜索（逗号分隔 = AND），空参数返回最近 50 条 |
| GET | `/api/advanced_search` | 高级搜索：分类、标签、重要性/理解度范围 |
| GET | `/api/semantic_search?q=&limit=` | 语义向量搜索，返回带相关度分数的结果 |
| GET | `/api/item/<id>` | 获取单条知识条目 |
| POST | `/api/add` | 新增条目 |
| PUT | `/api/update/<id>` | 更新条目 |
| DELETE | `/api/delete/<id>` | 删除条目 |
| POST | `/api/import/json` | 批量导入 JSON |
| GET | `/api/export?format=json\|markdown\|anki&category=` | 多格式导出 |
| POST | `/api/batch_edit` | 批量编辑标签/分类 |

### 知识图谱

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/knowledge_graph?category=` | 获取图谱数据（节点 + 边） |
| GET | `/api/related/<id>` | 获取条目的关联条目 |
| POST | `/api/relationship` | 创建关联 |
| DELETE | `/api/relationship` | 删除关联 |

### 复习

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/review?all=0\|1` | 获取待复习条目 |
| POST | `/api/review_session` | 记录复习评分 |
| GET | `/api/categories` | 列出所有分类及计数 |
| GET | `/api/tags` | 列出所有标签及计数 |
| GET | `/api/category/<name>` | 按分类获取条目 |
| GET | `/api/tag/<name>` | 按标签获取条目 |

### AI

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/ai/status` | AI 服务状态（可用 provider、模型、默认值） |
| POST | `/api/ai/chat` | 知识库对话（支持多轮历史和条目上下文） |
| POST | `/api/ai/rag_chat` | RAG 问答（检索 + 生成，带来源引用） |
| GET/POST | `/api/ai/analyze/<id>` | 条目内容分析 |
| GET/POST | `/api/ai/generate_questions/<id>` | 生成测试题 |
| POST | `/api/ai/improve_writing` | 改进写作 |
| POST | `/api/ai/extract/url` | 从 URL 提取知识条目 |
| POST | `/api/ai/extract/text` | 从文本提取知识条目 |
| POST | `/api/ai/extract/file/<filename>` | 从文件提取知识条目 |
| POST | `/api/ai/discover/relationships` | AI 发现知识关联 |
| POST | `/api/ai/discover/gaps` | AI 发现知识缺口 |
| POST | `/api/ai/learning/path` | 生成学习路径 |
| POST | `/api/ai/learning/review-plan` | AI 优化复习计划 |
| POST | `/api/ai/embeddings/generate` | 批量生成嵌入向量 |
| POST | `/api/ai/suggest/related/<id>` | 为条目推荐关联 |

### 系统 & 上传

| 方法 | 路由 | 说明 |
|------|------|------|
| GET | `/api/stats` | 统计：总数、今日新增、待复习、分类数、标签数 |
| GET | `/api/current_database` | 当前数据库路径 |
| POST | `/api/switch_database` | 切换数据库（自动初始化新库） |
| POST | `/api/upload` | 上传文件/图片 |
| POST | `/api/import_text_files` | 导入文本文件为知识条目 |

---

## 项目结构

```
├── run.py                    # 入口：参数解析、数据库选择、启动服务
├── setup.py                  # 数据库 Schema + 索引 + 默认数据 + 迁移
├── knowledge_manager.py      # 核心：CRUD、搜索、去重、图谱、复习引擎、嵌入存储
├── interactive_mode.py       # 交互式数据库选择菜单
├── cli_interface.py          # 命令行界面
│
├── ai/                       # AI 抽象层
│   ├── provider.py           # BaseProvider 基类
│   ├── service.py            # 9 种 AI 能力 + 嵌入 + 语义搜索 + RAG
│   ├── config.py             # YAML 配置 + 环境变量解析
│   ├── ollama_provider.py    # Ollama（本地 HTTP API + 嵌入）
│   ├── deepseek_provider.py  # DeepSeek
│   ├── openai_provider.py    # OpenAI
│   └── claude_provider.py    # Anthropic Claude
│
├── web/                      # Flask 应用
│   ├── app.py                # Flask 工厂
│   ├── blueprints/
│   │   ├── knowledge.py      # 知识 CRUD + 搜索 + 图谱 + 导出
│   │   ├── review.py         # 间隔重复复习
│   │   ├── ai.py             # 20 条 AI 路由
│   │   ├── upload.py         # 文件上传 + 文本导入
│   │   └── system.py         # 统计 + 数据库切换
│   ├── templates/
│   │   ├── base.html         # 布局、侧边栏、弹窗、主题初始化
│   │   └── index.html        # 5 个功能面板
│   └── static/
│       ├── css/style.css     # 双主题 + 响应式 + 完整组件样式
│       └── js/app.js         # 前端逻辑（~2700 行）
│
├── config/
│   ├── ai.yaml               # AI Provider 和模型配置
│   └── app.yaml              # 应用设置
│
├── tests/                    # 测试套件
│   └── ai/                   # AI 模块单元测试
│
└── uploads/                  # JSON 导入示例文件
```

---

## 数据库结构

| 表 | 说明 |
|----|------|
| `knowledge_items` | 知识条目主表，含 MD5 内容去重、重要性/理解度评级、复习排期、来源类型 |
| `tags` | 标签表，含颜色和使用计数 |
| `knowledge_tags` | 条目-标签多对多关联 |
| `knowledge_relationships` | 条目间关系：`related_to` / `prerequisite` / `extends` / `contradicts`，含强度 1-5 |
| `review_sessions` | 复习记录，含 ease factor、间隔天数、评分历史 |
| `embeddings` | 向量嵌入存储，JSON 序列化，关联 `knowledge_items` |

---

## 技术栈

- **后端：** Python 3 / Flask（Blueprint 模块化）/ SQLite
- **前端：** 原生 JavaScript / vis-network（知识图谱）/ MathJax（LaTeX 渲染）/ CSS 自定义属性（双主题 + 响应式）
- **AI：** 多 Provider 架构 — Ollama（本地）/ DeepSeek / Claude / OpenAI，支持嵌入向量和 RAG
- **中文：** jieba 分词
