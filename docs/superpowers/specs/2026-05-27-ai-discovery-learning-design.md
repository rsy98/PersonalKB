# AI知识发现 + AI学习规划 设计文档

**日期：** 2026-05-27
**状态：** 已确认

---

## 目标

在 Phase 4A（AI辅助录入）基础上，增加两套 AI 能力：
- **B: AI知识发现** — 自动发现知识条目间的隐藏关联 + 分析分类/主题下的知识缺口
- **C: AI学习规划** — 为目标主题生成结构化学习路径 + 基于间隔重复历史优化复习计划

融入现有面板（知识图谱、知识管理、复习），不新增面板。

---

## 架构

```
修改:
  ai/service.py                   # 新增 4 个 prompt + 4 个方法
  web/blueprints/ai.py            # 新增 4 个 API 路由
  web/templates/index.html        # 知识图谱/知识管理/复习面板各增加 AI 入口
  web/static/js/app.js            # 新增调用逻辑和结果渲染
  web/static/css/style.css        # 新增虚线边、缺口卡片、学习时间线、优先级标注样式
  config/ai.yaml                  # 新增 4 个功能默认配置
```

不新增 Python 依赖、不新增数据库表/字段、不新增前端框架。

---

## API 设计

### `POST /api/ai/discover/relationships`

```json
// Request
{
  "scope": "all",            // "all" | "category"
  "category": "物理",        // 当 scope="category" 时指定
  "limit": 30                // 分析的知识条目上限
}

// Response (200)
{
  "suggestions": [
    {
      "source_id": 1,
      "target_id": 5,
      "type": "prerequisite",
      "strength": 4,
      "reason": "'线性代数'是'量子力学'的数学基础，建议建立前置关系",
      "source_title": "线性代数基础",
      "target_title": "量子力学入门"
    }
  ],
  "analyzed_count": 25,
  "suggestion_count": 6
}
```

关联类型：`prerequisite`（前置知识）, `extends`（扩展深化）, `related_to`（概念相关）, `contradicts`（矛盾/不同观点）

### `POST /api/ai/discover/gaps`

```json
// Request
{
  "category": "物理",
  "existing_items": [         // 前端传入该分类下条目列表（可选，不传则后端查询）
  ]
}

// Response (200)
{
  "category": "物理",
  "gaps": [
    {
      "topic": "热力学第二定律",
      "importance": 5,
      "reason": "当前有'热力学基础'和'熵'两个条目，但缺少核心定律的系统阐述",
      "suggested_keywords": ["热力学第二定律", "熵增原理", "卡诺定理"]
    }
  ],
  "existing_count": 12,
  "gap_count": 4
}
```

### `POST /api/ai/learning/path`

```json
// Request
{
  "goal": "掌握机器学习基础",
  "scope": "all",             // "all" | "category"
  "category": "AI"            // 当 scope="category" 时限定范围
}

// Response (200)
{
  "goal": "掌握机器学习基础",
  "stages": [
    {
      "order": 1,
      "title": "数学基础准备",
      "item_ids": [3, 7],
      "concepts": ["线性代数", "微积分", "概率论"],
      "prerequisites": [],
      "estimated_hours": 10,
      "mastery_criteria": "能推导梯度下降公式，理解贝叶斯定理"
    },
    {
      "order": 2,
      "title": "核心算法入门",
      "item_ids": [12, 15],
      "concepts": ["监督学习", "过拟合与正则化", "交叉验证"],
      "prerequisites": ["数学基础准备"],
      "estimated_hours": 15,
      "mastery_criteria": "能实现线性回归和逻辑回归，理解偏差-方差权衡"
    }
  ],
  "missing_topics": ["深度学习框架实践", "特征工程系统方法"],
  "total_estimated_hours": 40
}
```

### `POST /api/ai/learning/review-plan`

```json
// Request
{
  "days": 7                   // 生成 N 天计划
}

// Response (200)
{
  "daily_plan": [
    {
      "date": "2026-05-28",
      "items": [
        {"id": 5, "priority": 1, "reason": "间隔到期+重要性高(5)"},
        {"id": 12, "priority": 2, "reason": "上次评分仅2分，需巩固"}
      ],
      "total": 5
    }
  ],
  "max_daily": 8,
  "strategy_notes": "当前待复习条目较少（12条），建议每天复习4-6条"
}
```

---

## Prompt 设计

### `discover_relationships`

```
系统：你是一个知识图谱专家，擅长发现知识条目之间的隐藏关联。

用户：
以下是知识库中的一些条目。请发现它们之间未被记录的关联关系。

{items}

请返回 JSON 数组（只返回 JSON，不要其他内容）：
[{
  "source_id": <源条目ID>,
  "target_id": <目标条目ID>,
  "type": "prerequisite|extends|related_to|contradicts",
  "strength": <1-5>,
  "reason": "<一句话解释为什么它们相关>"
}]
```

### `discover_gaps`

```
系统：你是一个知识体系专家，擅长识别知识盲区和缺口。

用户：
我正在构建"{category}"领域的知识库。以下是已有条目：

{items}

请分析这个知识体系，找出重要的缺失主题。返回 JSON 数组：
[{{
  "topic": "建议添加的主题",
  "importance": <1-5>,
  "reason": "为什么这个主题重要且缺失",
  "suggested_keywords": ["关键词1", "关键词2"]
}}]

注意：只返回真正重要的缺口（4-8个），不要为了凑数而建议。
```

### `generate_learning_path`

```
系统：你是一个学习规划专家，擅长设计循序渐进的知识学习路线。

用户：
学习目标：{goal}

知识库中相关条目：
{items}

请设计一条从基础到精通的学习路径。返回 JSON：
{{
  "stages": [
    {{
      "order": <序号，从1开始>,
      "title": "<阶段名称>",
      "item_ids": [<知识库中已有条目ID>],
      "concepts": ["<本阶段应掌握的概念>"],
      "prerequisites": ["<前置阶段名称>"],
      "estimated_hours": <数字>,
      "mastery_criteria": "<如何判断已掌握>"
    }}
  ],
  "missing_topics": ["<知识库中缺少但建议学习的主题>"],
  "total_estimated_hours": <总小时数>
}}

原则：从基础到高级，每阶段3-5个概念，结合实际已有内容。
```

### `optimize_review_plan`

```
系统：你是一个间隔重复学习专家，擅长个性化复习规划。

用户：
以下是当前待复习的知识条目及其历史数据：

{items}

请规划未来 {days} 天的复习计划。返回 JSON：
{{
  "daily_plan": [
    {{
      "date": "YYYY-MM-DD",
      "items": [
        {{"id": <条目ID>, "priority": <1-5>, "reason": "<为什么排这个优先级>"}}
      ],
      "total": <当天总条目数>
    }}
  ],
  "max_daily": <建议每天最大复习量>,
  "strategy_notes": "<总体策略说明>"
}}

原则：
- 间隔即将到期 > 间隔已过期 > 间隔未到期
- 重要性低但快到期 > 重要性高但还有时间
- 上次评分低的优先加固
- 每天总量控制在合理范围内
```

---

## AIService 新增方法

```python
def discover_relationships(self, items: list, provider=None, model=None) -> dict:
    """发现知识条目间的隐藏关联"""
    items_text = '\n'.join([
        f'ID:{i["id"]} 标题:{i["title"]} 分类:{i.get("category","")} 标签:{i.get("tags","")} 摘要:{i.get("summary","")[:100]}'
        for i in items
    ])
    result = self.execute('discover_relationships', {'items': items_text}, provider=provider, model=model)
    return self._parse_json_response(result)

def discover_gaps(self, category: str, items: list, provider=None, model=None) -> dict:
    """发现知识缺口"""
    items_text = '\n'.join([
        f'- {i["title"]}: {i.get("summary", "")[:80]}'
        for i in items
    ])
    result = self.execute('discover_gaps', {
        'category': category,
        'items': items_text,
    }, provider=provider, model=model)
    return self._parse_json_response(result)

def generate_learning_path(self, goal: str, items: list, provider=None, model=None) -> dict:
    """生成学习路径"""
    items_text = '\n'.join([
        f'ID:{i["id"]} 标题:{i["title"]} 分类:{i.get("category","")} '
        f'摘要:{i.get("summary","")[:100]} 理解程度:{i.get("understanding_level",3)}/5'
        for i in items
    ])
    result = self.execute('generate_learning_path', {
        'goal': goal,
        'items': items_text,
    }, provider=provider, model=model)
    return self._parse_json_response(result)

def optimize_review_plan(self, review_items: list, days: int = 7, provider=None, model=None) -> dict:
    """优化复习计划"""
    items_text = '\n'.join([
        f'ID:{i["id"]} 标题:{i["title"]} 重要性:{i.get("importance_level",3)}/5 '
        f'理解:{i.get("understanding_level",3)}/5 间隔:{i.get("interval_days",0)}天 '
        f'上次复习:{i.get("last_review_date","N/A")} ease:{i.get("ease_factor",2.5):.1f}'
        for i in review_items
    ])
    result = self.execute('optimize_review_plan', {
        'items': items_text,
        'days': str(days),
    }, provider=provider, model=model)
    return self._parse_json_response(result)

def _parse_json_response(self, result: dict) -> dict:
    """解析 AI 返回的 JSON（统一处理 code fence 和解析失败）"""
    try:
        text = result['content'].strip()
        if text.startswith('```'):
            lines = text.split('\n')
            text = '\n'.join(lines[1:])
            if text.rstrip().endswith('```'):
                text = text.rstrip()[:-3]
        data = json.loads(text)
    except (json.JSONDecodeError, KeyError):
        data = {'error': 'AI 返回格式异常', 'raw': result['content']}
    data['model'] = result['model']
    data['provider'] = result['provider']
    return data
```

所有方法的 JSON 解析逻辑与 `extract_knowledge_item()` 一致（处理 code fence、解析失败降级）。

---

## 前端 UI 设计

### 知识图谱面板 — 关联发现

- 分类筛选下拉框旁新增「AI 发现关联」按钮
- 点击后显示 loading，AI 分析后在图谱中以**虚线黄色边**显示建议关联
- hover 边显示 tooltip（关联类型 + 理由）
- 两条操作按钮浮在图上：
  - 「全部采纳」— 批量创建所有建议关联
  - 「逐条审核」— 每个建议边旁出现 ✓/✗ 按钮
- 确认的关联写入 `knowledge_relationships` 后边变为实线

### 知识管理面板 — 缺口分析

- 按分类浏览时（点击分类或搜索某分类），结果列表顶部出现醒目卡片：
  > "AI 发现了 **N** 个可能的缺口" [查看详情] [忽略]
- 点击展开缺口列表，每条显示：主题名、重要性星级、理由、建议搜索关键词
- 每条旁的「添加」按钮跳转到 AI 辅助录入（复用 extract prompt），预设标题为主题名

### 复习面板 — 学习路径 & 复习优化

- 面板顶部新增两个子 tab：「复习计划」「学习路径」
- **学习路径 tab：**
  - 输入框 + 生成按钮
  - 时间线展示阶段（类似进度条），已完成阶段/当前阶段/未来阶段用不同颜色
  - 每阶段展开显示条目列表和掌握标准
  - 缺失主题用虚线卡片展示，点击跳转到缺口分析或 AI 录入
- **复习计划 tab（原复习列表升级）：**
  - 顶部切换：「按日期排序」/ 「AI 智能排序」
  - AI 模式下显示策略说明文字
  - 每条复习卡片增加 `priority` 标签和简短 `reason`
  - 保留原有复习打分功能，新增打分后 AI 自动更新当日计划

---

## 配置变更

`config/ai.yaml` 的 `defaults` 新增：

```yaml
defaults:
  # ... 原有配置
  discover_relationships:
    provider: deepseek
    model: deepseek-v4-flash
  discover_gaps:
    provider: deepseek
    model: deepseek-v4-flash
  generate_learning_path:
    provider: deepseek
    model: deepseek-v4-flash
  optimize_review_plan:
    provider: deepseek
    model: deepseek-v4-flash
```

---

## 不在范围

- 自动定时执行关联发现/缺口分析（用户手动触发）
- AI 自动创建条目（缺口只建议，不自动添加）
- 学习路径的进度追踪和持久化（本次只生成展示）
- 多人协作 / 社交学习功能
- 修改数据库 schema
