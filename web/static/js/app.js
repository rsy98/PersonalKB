/* ================================================================
   Personal Knowledge Management System - Main Application JS
   Self-contained, no framework. All data via /api/* JSON endpoints.
   ================================================================ */

// ================================================================
// 1. Configuration & State
// ================================================================
const API_BASE = '';

const state = {
    currentPanel: 'knowledge',
    currentDB: 'knowledge.db',
    selectedItems: new Set(),
    chatHistory: [],
    currentItemId: null,
    quickMode: false,
    extractTab: 'url',
    lastExtracted: null,
    reviewSortMode: 'default',
    reviewTab: 'review-plan',
    suggestionEdges: [],
    cachedReviewPlan: null,
};

// ================================================================
// 2. Utility Functions
// ================================================================
function escapeHtml(str) {
    if (!str) return '';
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

function formatDate(dateStr) {
    if (!dateStr) return '';
    const d = new Date(dateStr);
    return d.toLocaleDateString('zh-CN', { year: 'numeric', month: '2-digit', day: '2-digit' });
}

function contentPreview(content, maxLen) {
    // Strip markdown headers/syntax for clean preview
    let text = content
        .replace(/^#{1,6}\s+/gm, '')
        .replace(/\*\*(.+?)\*\*/g, '$1')
        .replace(/\*(.+?)\*/g, '$1')
        .replace(/`(.+?)`/g, '$1')
        .replace(/```[\s\S]*?```/g, '[代码块]')
        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')
        .replace(/\n+/g, ' ')
        .trim();
    if (text.length > maxLen) text = text.slice(0, maxLen) + '...';
    return escapeHtml(text);
}

function showToast(msg, type='success') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = msg;
    container.appendChild(toast);
    setTimeout(() => { toast.remove(); }, 3000);
}

// ================================================================
// 3. API Module
// ================================================================
async function api(path, options={}) {
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 60000);
    try {
        const resp = await fetch(API_BASE + path, {
            headers: { 'Content-Type': 'application/json', ...options.headers },
            signal: controller.signal,
            ...options,
        });
        clearTimeout(timeout);
        if (!resp.ok) {
            const err = await resp.json().catch(() => ({}));
            throw new Error(err.error || `HTTP ${resp.status}`);
        }
        return resp.json();
    } catch (e) {
        clearTimeout(timeout);
        if (e.name === 'AbortError') {
            showToast('请求超时，AI 服务响应较慢，请重试', 'warning');
        } else if (e.message === 'Failed to fetch') {
            showToast('无法连接服务器，请确认服务已启动', 'error');
        } else {
            showToast(e.message, 'error');
        }
        throw e;
    }
}

const apiService = {
    search: (q) => api(`/api/search?q=${encodeURIComponent(q)}`),
    advancedSearch: (params) => {
        const qs = new URLSearchParams(params).toString();
        return api(`/api/advanced_search?${qs}`);
    },
    getItem: (id) => api(`/api/item/${id}`),
    addItem: (data) => api('/api/add', { method: 'POST', body: JSON.stringify(data) }),
    updateItem: (id, data) => api(`/api/update/${id}`, { method: 'PUT', body: JSON.stringify(data) }),
    deleteItem: (id) => api(`/api/delete/${id}`, { method: 'DELETE' }),
    getRecent: () => api('/api/recent'),
    getStats: () => api('/api/stats'),
    getReviews: () => api('/api/review'),
    reviewSession: (data) => api('/api/review_session', { method: 'POST', body: JSON.stringify(data) }),
    getGraph: (category) => {
        const qs = category ? `?category=${encodeURIComponent(category)}` : '';
        return api(`/api/knowledge_graph${qs}`);
    },
    getRelated: (id) => api(`/api/related/${id}`),
    createRelationship: (data) => api('/api/relationship', { method: 'POST', body: JSON.stringify(data) }),
    deleteRelationship: (data) => api('/api/relationship', { method: 'DELETE', body: JSON.stringify(data) }),
    getCategories: () => api('/api/categories'),
    getTags: () => api('/api/tags'),
    getCategoryItems: (cat) => api(`/api/category/${encodeURIComponent(cat)}`),
    getTagItems: (tag) => api(`/api/tag/${encodeURIComponent(tag)}`),
    batchEdit: (data) => api('/api/batch_edit', { method: 'POST', body: JSON.stringify(data) }),
    exportData: () => api('/api/export'),
    importFile: (formData) => {
        return fetch(API_BASE + '/api/import', { method: 'POST', body: formData }).then(r => r.json());
    },
    uploadFiles: (formData) => {
        return fetch(API_BASE + '/api/upload', { method: 'POST', body: formData }).then(r => r.json());
    },
    importTextFiles: (formData) => {
        return fetch(API_BASE + '/api/import_text_files', { method: 'POST', body: formData }).then(r => r.json());
    },
    switchDB: (db) => api('/api/switch_database', { method: 'POST', body: JSON.stringify({ database: db }) }),
    currentDB: () => api('/api/current_database'),
    aiStatus: () => api('/api/ai/status'),
    aiProviders: () => api('/api/ai/providers'),
    aiAnalyze: (id, provider, model) => {
        return api(`/api/ai/analyze/${id}`,
            { method: 'GET', body: JSON.stringify({ provider, model }),
              headers: { 'Content-Type': 'application/json' } });
    },
    aiGenerateQuestions: (id, provider, model) => {
        return api(`/api/ai/generate_questions/${id}`,
            { method: 'GET', body: JSON.stringify({ provider, model }),
              headers: { 'Content-Type': 'application/json' } });
    },
    aiImproveWriting: (content, provider, model) => {
        return api('/api/ai/improve_writing',
            { method: 'POST', body: JSON.stringify({ content, provider, model }) });
    },
    aiChat: (data) => api('/api/ai/chat', { method: 'POST', body: JSON.stringify(data) }),
    contentAnalysis: (id) => api(`/api/content_analysis/${id}`),
    aiRecommendations: (id) => api(`/api/ai_recommendations/${id}`),
    extractURL: (url, provider, model) => {
        return api('/api/ai/extract/url', {
            method: 'POST',
            body: JSON.stringify({ url, provider, model }),
        });
    },
    extractText: (text, provider, model) => {
        return api('/api/ai/extract/text', {
            method: 'POST',
            body: JSON.stringify({ text, provider, model }),
        });
    },
    extractFile: (filename, provider, model) => {
        return api('/api/ai/extract/file/' + encodeURIComponent(filename), {
            method: 'POST',
            body: JSON.stringify({ provider, model }),
        });
    },
    discoverRelationships: (data) => {
        return api('/api/ai/discover/relationships', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },
    discoverGaps: (category) => {
        return api('/api/ai/discover/gaps', {
            method: 'POST',
            body: JSON.stringify({ category }),
        });
    },
    generateLearningPath: (goal, category) => {
        const data = { goal };
        if (category) { data.scope = 'category'; data.category = category; }
        return api('/api/ai/learning/path', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },
    optimizeReviewPlan: (days) => {
        return api('/api/ai/learning/review-plan', {
            method: 'POST',
            body: JSON.stringify({ days: days || 7 }),
        });
    },
};

// ================================================================
// 4. Render Module
// ================================================================
function renderSearchResults(items) {
    const container = document.getElementById('searchResults');
    if (!items || items.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">📭</div><p>没有找到匹配的知识条目</p></div>';
        return;
    }
    container.innerHTML = `<div class="item-list">${items.map(item => `
        <div class="item-card" onclick="showItemDetail(${item.id})">
            <div class="item-card-title">
                ${escapeHtml(item.title)}
                <span style="font-size:11px;color:var(--text-tertiary);">#${item.id}</span>
            </div>
            <div class="item-card-meta">
                <span>📂 ${escapeHtml(item.category || '未分类')}</span>
                <span>⭐ ${item.importance_level}/5</span>
                <span>📖 ${item.understanding_level}/5</span>
                <span>🕐 ${formatDate(item.created_date)}</span>
            </div>
            ${item.content ? `<div class="item-card-preview md-content">${contentPreview(item.content, 200)}</div>` : ''}
            ${item.tag_names ? `<div style="margin-top:6px;">${item.tag_names.split(',').map(t =>
                `<span class="tag">${escapeHtml(t.trim())}</span>`).join('')}</div>` : ''}
        </div>
    `).join('')}</div>`;
    refreshMath();
}

function renderStats(stats) {
    document.getElementById('statTotal').textContent = stats.total_items || 0;
    document.getElementById('statTodayNew').textContent = stats.today_new || 0;
    document.getElementById('statReviews').textContent = stats.today_reviews || 0;
    document.getElementById('statCategories').textContent = stats.categories_count || 0;
    document.getElementById('statTags').textContent = stats.tags_count || 0;
}

function renderReviews(items) {
    const container = document.getElementById('reviewContent');
    if (!items || items.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🎉</div><p>今天没有需要复习的内容！</p></div>';
        return;
    }
    container.innerHTML = items.map((item, i) => `
        <div class="item-card" id="review-item-${item.id}">
            <div class="item-card-title">${i + 1}. ${escapeHtml(item.title)}</div>
            <div class="item-card-meta">
                <span>理解程度: ${item.understanding_level}/5</span>
                <span>📝 ${escapeHtml(item.summary || '')}</span>
            </div>
            <div style="margin-top:8px;display:flex;gap:8px;align-items:center;" onclick="event.stopPropagation()">
                ${[0,1,2,3,4,5].map(r => `
                    <button class="btn ${r >= 4 ? 'btn-success' : r >= 2 ? 'btn-outline' : 'btn-danger'} btn-sm"
                            onclick="rateReview(${item.id}, ${r})">${r}</button>
                `).join('')}
            </div>
        </div>
    `).join('');
}

function renderItemDetail(item) {
    const body = document.getElementById('modalBody');
    const content = item.content || '';
    body.innerHTML = `
        <div style="display:flex;justify-content:space-between;align-items:start;margin-bottom:16px;">
            <div>
                <h3 style="font-size:20px;margin-bottom:4px;">${escapeHtml(item.title)}</h3>
                <div style="font-size:13px;color:var(--text-secondary);">
                    ID: ${item.id} | 📂 ${escapeHtml(item.category || '未分类')} |
                    ⭐ ${item.importance_level}/5 | 📖 ${item.understanding_level}/5
                </div>
            </div>
            <div style="display:flex;gap:6px;">
                <button class="btn btn-outline btn-sm" onclick="editItem(${item.id})">编辑</button>
                <button class="btn btn-danger btn-sm" onclick="confirmDelete(${item.id})">删除</button>
            </div>
        </div>
        ${item.tag_names ? `<div style="margin-bottom:12px;">${item.tag_names.split(',').map(t =>
            `<span class="tag">${escapeHtml(t.trim())}</span>`).join('')}</div>` : ''}
        <div style="display:flex;align-items:center;gap:8px;margin-bottom:8px;">
            <span style="font-size:12px;color:var(--text-secondary);">查看模式:</span>
            <button class="btn btn-sm active" id="btnViewRendered" onclick="switchContentView('rendered', ${item.id})">渲染</button>
            <button class="btn btn-sm btn-outline" id="btnViewSource" onclick="switchContentView('source', ${item.id})">源文本</button>
        </div>
        <div class="md-content" id="detailContent">${renderMarkdown(content)}</div>
        <pre class="md-source" id="detailSource" style="display:none;">${escapeHtml(content)}</pre>
        <div style="margin-top:16px;font-size:12px;color:var(--text-tertiary);">
            创建: ${formatDate(item.created_date)} | 更新: ${formatDate(item.updated_date)}
            ${item.next_review_date ? ` | 下次复习: ${formatDate(item.next_review_date)}` : ''}
        </div>
        <div id="relatedItemsSection" style="margin-top:20px;">
            <h4 style="margin-bottom:8px;">关联条目</h4>
            <div id="relatedItemsList"><div class="loading"><div class="spinner"></div></div></div>
        </div>
    `;
    document.getElementById('modalTitle').textContent = '条目详情';
    document.getElementById('modalOverlay').style.display = 'flex';
    state.currentItemId = item.id;
    state._itemContent = content;
    loadRelatedItems(item.id);
    refreshMath();
}

function switchContentView(mode, itemId) {
    const renderedBtn = document.getElementById('btnViewRendered');
    const sourceBtn = document.getElementById('btnViewSource');
    const contentDiv = document.getElementById('detailContent');
    const sourcePre = document.getElementById('detailSource');

    if (mode === 'rendered') {
        contentDiv.style.display = '';
        sourcePre.style.display = 'none';
        renderedBtn.className = 'btn btn-sm';
        sourceBtn.className = 'btn btn-sm btn-outline';
        refreshMath();
    } else {
        contentDiv.style.display = 'none';
        sourcePre.style.display = '';
        renderedBtn.className = 'btn btn-sm btn-outline';
        sourceBtn.className = 'btn btn-sm';
    }

    // AI analyze button - update onclick if needed
    const analyzeBtn = document.getElementById('btnAnalyze');
    if (analyzeBtn) {
        analyzeBtn.onclick = () => showItemDetail(itemId);
    }
}

function renderKnowledgeGraph(data) {
    const container = document.getElementById('graphContainer');
    if (!data || !data.nodes || data.nodes.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🕸</div><p>暂无图谱数据，请先添加知识条目和关联关系</p></div>';
        return;
    }
    container.innerHTML = '';

    const width = container.clientWidth || 800;
    const height = container.clientHeight || 500;

    const svg = d3.select(container).append('svg')
        .attr('width', width).attr('height', height);

    const g = svg.append('g');

    svg.call(d3.zoom().scaleExtent([0.1, 4]).on('zoom', (event) => {
        g.attr('transform', event.transform);
    }));

    const categories = [...new Set(data.nodes.map(n => n.category || '未分类'))];
    const colorScale = d3.scaleOrdinal(d3.schemeCategory10).domain(categories);

    const links = g.append('g').selectAll('line')
        .data(data.edges).join('line')
        .attr('stroke', 'var(--text-tertiary)').attr('stroke-opacity', 0.4)
        .attr('stroke-width', d => d.strength || 1);

    const nodes = g.append('g').selectAll('circle')
        .data(data.nodes).join('g')
        .attr('cursor', 'pointer')
        .call(d3.drag()
            .on('start', (event, d) => { if (!event.active) graphSimulation.alphaTarget(0.3).restart(); d.fx = d.x; d.fy = d.y; })
            .on('drag', (event, d) => { d.fx = event.x; d.fy = event.y; })
            .on('end', (event, d) => { if (!event.active) graphSimulation.alphaTarget(0); d.fx = null; d.fy = null; }));

    nodes.append('circle')
        .attr('r', d => 5 + (d.importance_level || 3) * 3)
        .attr('fill', d => colorScale(d.category || '未分类'))
        .attr('stroke', 'var(--bg-primary)').attr('stroke-width', 1.5);

    nodes.append('text')
        .text(d => (d.title || '').length > 8 ? (d.title || '').slice(0, 8) + '...' : (d.title || ''))
        .attr('font-size', 10).attr('dx', 12).attr('dy', 4)
        .attr('fill', 'var(--text-secondary)');

    nodes.on('click', (event, d) => showItemDetail(d.id))
         .on('mouseenter', function() { d3.select(this).select('circle').attr('stroke', 'var(--accent)').attr('stroke-width', 3); })
         .on('mouseleave', function() { d3.select(this).select('circle').attr('stroke', 'var(--bg-primary)').attr('stroke-width', 1.5); });

    graphSimulation = d3.forceSimulation(data.nodes)
        .force('link', d3.forceLink(data.edges).id(d => d.id).distance(80))
        .force('charge', d3.forceManyBody().strength(-200))
        .force('center', d3.forceCenter(width / 2, height / 2))
        .on('tick', () => {
            links.attr('x1', d => d.source.x).attr('y1', d => d.source.y)
                 .attr('x2', d => d.target.x).attr('y2', d => d.target.y);
            nodes.attr('transform', d => `translate(${d.x},${d.y})`);
            g.selectAll('line.suggested-edge').each(function() {
                const sid = parseInt(this.getAttribute('data-sid'));
                const tid = parseInt(this.getAttribute('data-tid'));
                const s = data.nodes.find(n => n.id === sid);
                const t = data.nodes.find(n => n.id === tid);
                if (s && t) {
                    d3.select(this).attr('x1', s.x).attr('y1', s.y).attr('x2', t.x).attr('y2', t.y);
                }
            });
        });

    const filter = document.getElementById('graphCategoryFilter');
    if (filter && filter.options.length <= 1) {
        categories.forEach(cat => {
            const opt = document.createElement('option');
            opt.value = cat;
            opt.textContent = cat;
            filter.appendChild(opt);
        });
    }
}

// ================================================================
// 5. Panel Switching, Theme, Sidebar
// ================================================================
function switchPanel(name) {
    state.currentPanel = name;
    document.querySelectorAll('.panel').forEach(p => p.classList.remove('active'));
    document.querySelectorAll('.nav-item').forEach(n => n.classList.remove('active'));

    const panel = document.getElementById('panel-' + name);
    if (panel) panel.classList.add('active');

    const navItem = document.querySelector(`[data-panel="${name}"]`);
    if (navItem) navItem.classList.add('active');

    if (name === 'review') loadReviews();
    else if (name === 'graph') loadKnowledgeGraph();
    else if (name === 'ai') loadAIStatus();

    window.location.hash = name;
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme');
    const next = current === 'light' ? 'dark' : 'light';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
}

function toggleSidebar() {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (window.innerWidth < 768) {
        sidebar.classList.toggle('open');
        overlay.classList.toggle('show');
    } else {
        sidebar.classList.toggle('collapsed');
        // Persist collapse state
        const collapsed = sidebar.classList.contains('collapsed');
        localStorage.setItem('sidebarCollapsed', collapsed ? 'true' : 'false');
    }
}

// ================================================================
// 6. Core Operations
// ================================================================
async function searchItems() {
    const query = document.getElementById('searchInput').value.trim();
    if (!query) { showAllItems(); return; }
    try {
        const items = await apiService.search(query);
        renderSearchResults(items);
    } catch (e) {}
}

async function showAllItems() {
    try {
        const items = await apiService.getRecent();
        renderSearchResults(items);
    } catch (e) {}
}

async function addNewItem() {
    const title = document.getElementById('newTitle').value.trim();
    const content = document.getElementById('newContent').value.trim();
    if (!title || !content) {
        showToast('标题和内容不能为空', 'warning');
        return;
    }
    const tags = document.getElementById('newTags').value.split(',').map(t => t.trim()).filter(Boolean);
    const data = {
        title,
        content,
        tags,
        category: document.getElementById('newCategory').value.trim() || '未分类',
        importance_level: parseInt(document.getElementById('newImportance').value),
        understanding_level: parseInt(document.getElementById('newUnderstanding').value),
    };
    try {
        const result = await apiService.addItem(data);
        if (result.success) {
            showToast(`知识条目已添加! ID: ${result.item_id}`, 'success');
            document.getElementById('newTitle').value = '';
            document.getElementById('newContent').value = '';
            document.getElementById('newTags').value = '';
            document.getElementById('addFormPanel').open = false;
            loadStats();
        }
    } catch (e) {}
}

async function showItemDetail(id) {
    try {
        const item = await apiService.getItem(id);
        renderItemDetail(item);
        refreshMath();
    } catch (e) {}
}

async function loadStats() {
    try {
        const stats = await apiService.getStats();
        renderStats(stats);
    } catch (e) {}
}

async function loadReviews() {
    try {
        const items = await apiService.getReviews();
        if (state.reviewSortMode === 'ai' && state.cachedReviewPlan) {
            const priorityMap = {};
            const plan = state.cachedReviewPlan;
            if (plan.daily_plan && plan.daily_plan.length > 0) {
                (plan.daily_plan[0].items || []).forEach(it => { priorityMap[it.id] = { p: it.priority, r: it.reason }; });
            }
            const sorted = [...items].sort((a, b) => {
                const pa = (priorityMap[a.id] && priorityMap[a.id].p) || 99;
                const pb = (priorityMap[b.id] && priorityMap[b.id].p) || 99;
                return pa - pb;
            });
            renderReviewsWithPriority(sorted, priorityMap);
        } else {
            renderReviews(items);
        }
        const badge = document.getElementById('reviewBadge');
        if (badge) {
            badge.textContent = items.length;
            badge.style.display = items.length > 0 ? 'inline' : 'none';
        }
    } catch (e) {}
}

async function confirmDelete(id) {
    if (!confirm('确定要删除这个知识条目吗？此操作不可撤销。')) return;
    try {
        await apiService.deleteItem(id);
        showToast('条目已删除', 'success');
        closeModal();
        loadStats();
    } catch (e) {}
}

function closeModal() {
    document.getElementById('modalOverlay').style.display = 'none';
    state.currentItemId = null;
}

// ================================================================
// 7. Edit Item
// ================================================================
async function editItem(id) {
    try {
        const item = await apiService.getItem(id);
        const body = document.getElementById('modalBody');
        body.innerHTML = `
            <div class="form-group">
                <label class="form-label">标题</label>
                <input type="text" class="form-input" id="editTitle" value="${escapeHtml(item.title)}">
            </div>
            <div class="form-group">
                <label class="form-label">
                    内容
                    <span style="float:right;font-weight:400;">
                        <button class="btn btn-outline btn-sm" onclick="uploadImageToInsert('editContent')" title="上传图片">🖼 图片</button>
                        <button class="btn btn-outline btn-sm" onclick="uploadFileToInsert('editContent')" title="上传文件">📎 文件</button>
                    </span>
                </label>
                <textarea class="form-textarea" id="editContent">${escapeHtml(item.content || '')}</textarea>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">分类</label>
                    <input type="text" class="form-input" id="editCategory" value="${escapeHtml(item.category || '')}">
                </div>
                <div class="form-group">
                    <label class="form-label">标签（逗号分隔）</label>
                    <input type="text" class="form-input" id="editTags" value="${escapeHtml(item.tag_names || '')}">
                </div>
            </div>
            <div class="form-row">
                <div class="form-group">
                    <label class="form-label">重要程度</label>
                    <select class="form-select" id="editImportance">
                        ${[1,2,3,4,5].map(v => `<option value="${v}" ${v === item.importance_level ? 'selected' : ''}>${v}</option>`).join('')}
                    </select>
                </div>
                <div class="form-group">
                    <label class="form-label">理解程度</label>
                    <select class="form-select" id="editUnderstanding">
                        ${[1,2,3,4,5].map(v => `<option value="${v}" ${v === item.understanding_level ? 'selected' : ''}>${v}</option>`).join('')}
                    </select>
                </div>
            </div>
            <button class="btn btn-primary" onclick="saveItem(${id})">保存修改</button>
        `;
        document.getElementById('modalTitle').textContent = '编辑条目';
        document.getElementById('modalOverlay').style.display = 'flex';
    } catch (e) {}
}

async function saveItem(id) {
    const tags = document.getElementById('editTags').value.split(',').map(t => t.trim()).filter(Boolean);
    const data = {
        title: document.getElementById('editTitle').value.trim(),
        content: document.getElementById('editContent').value.trim(),
        category: document.getElementById('editCategory').value.trim(),
        importance_level: parseInt(document.getElementById('editImportance').value),
        understanding_level: parseInt(document.getElementById('editUnderstanding').value),
        tags,
    };
    try {
        await apiService.updateItem(id, data);
        showToast('条目已更新', 'success');
        closeModal();
        loadStats();
    } catch (e) {}
}

// ================================================================
// 8. Related Items + Review Rating
// ================================================================
async function loadRelatedItems(id) {
    try {
        const items = await apiService.getRelated(id);
        const container = document.getElementById('relatedItemsList');
        if (!items || items.length === 0) {
            container.innerHTML = '<p style="color:var(--text-tertiary);font-size:13px;">暂无关联条目</p>';
            return;
        }
        container.innerHTML = items.map(item => `
            <div class="item-card" onclick="showItemDetail(${item.id})" style="margin-bottom:6px;">
                <div class="item-card-title">${escapeHtml(item.title)}</div>
                <div class="item-card-meta">📂 ${escapeHtml(item.category || '')}</div>
            </div>
        `).join('');
    } catch (e) {}
}

async function rateReview(itemId, rating) {
    try {
        await apiService.reviewSession({ item_id: itemId, rating });
        const card = document.getElementById('review-item-' + itemId);
        if (card) {
            card.style.opacity = '0.5';
            card.style.transition = 'opacity 0.3s';
        }
        showToast(`评分 ${rating}/5 已记录`, 'success');
    } catch (e) {}
}

// ================================================================
// 9. Knowledge Graph Operations
// ================================================================
let graphSimulation = null;

async function loadKnowledgeGraph() {
    const category = document.getElementById('graphCategoryFilter')?.value || '';
    try {
        const data = await apiService.getGraph(category);
        renderKnowledgeGraph(data);
    } catch (e) {}
    if (state.suggestionEdges.length > 0) {
        setTimeout(() => renderSuggestedEdges(state.suggestionEdges), 1000);
    }
}

function resetGraphLayout() {
    if (graphSimulation) {
        graphSimulation.nodes().forEach(n => { n.fx = null; n.fy = null; });
        graphSimulation.alpha(1).restart();
    }
}

function focusOnImportantNodes() {
    if (graphSimulation) {
        const nodes = graphSimulation.nodes();
        nodes.forEach(n => {
            if ((n.importance_level || 0) >= 4) {
                n.fx = null; n.fy = null;
            } else {
                n.fx = n.x; n.fy = n.y;
            }
        });
        graphSimulation.alpha(0.5).restart();
    }
}

async function filterGraphByCategory() {
    loadKnowledgeGraph();
}

// ================================================================
// 10. AI Chat
// ================================================================
async function loadAIStatus() {
    try {
        const resp = await apiService.aiStatus();
        if (resp.data && resp.data.providers) {
            const available = resp.data.providers.filter(p => p.available).map(p => p.name);
            if (available.length > 0) {
                document.getElementById('chatInput').placeholder = `AI 就绪 (${available.join(', ')}) — 输入问题...`;
            }
        }
    } catch (e) {}
}

async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const question = input.value.trim();
    if (!question) return;
    input.value = '';

    const messages = document.getElementById('chatMessages');
    messages.innerHTML += `<div class="chat-message user">${escapeHtml(question)}</div>`;
    messages.innerHTML += '<div class="chat-message assistant" id="chatLoading"><div class="spinner"></div> 思考中...</div>';
    messages.scrollTop = messages.scrollHeight;

    try {
        const result = await apiService.aiChat({
            question,
            item_id: state.currentItemId,
            chat_history: state.chatHistory,
        });
        document.getElementById('chatLoading')?.remove();
        const answer = result.answer || result.content || JSON.stringify(result);
        const thinking = result.thinking || '';
        let html = '';
        if (thinking) {
            html += `<details style="margin-bottom:8px;"><summary style="cursor:pointer;color:var(--text-tertiary);font-size:12px;">思考过程</summary><p style="color:var(--text-tertiary);font-size:12px;white-space:pre-wrap;">${escapeHtml(thinking)}</p></details>`;
        }
        html += `<div style="white-space:pre-wrap;">${simpleMarkdownRender(answer)}</div>`;
        messages.innerHTML += `<div class="chat-message assistant">${html}</div>`;
        state.chatHistory.push({ role: 'user', content: question }, { role: 'assistant', content: answer });
    } catch (e) {
        document.getElementById('chatLoading')?.remove();
        messages.innerHTML += `<div class="chat-message assistant" style="color:var(--danger);">错误: ${escapeHtml(e.message)}</div>`;
    }
    messages.scrollTop = messages.scrollHeight;
}

function clearChatHistory() {
    state.chatHistory = [];
    document.getElementById('chatMessages').innerHTML = `
        <div class="chat-message assistant">聊天历史已清空。有什么我可以帮你的？</div>
    `;
}

function renderMarkdown(text) {
    if (!text) return '';
    const lines = text.split('\n');
    let html = '';
    let inCodeBlock = false;
    let codeContent = '';
    let codeLang = '';
    let inList = false;
    let listType = '';

    for (let i = 0; i < lines.length; i++) {
        const line = lines[i];

        // Code block
        if (line.trimStart().startsWith('```')) {
            if (inCodeBlock) {
                html += `<pre><code class="language-${escapeHtml(codeLang)}">${escapeHtml(codeContent.trimEnd())}</code></pre>`;
                codeContent = '';
                codeLang = '';
                inCodeBlock = false;
            } else {
                inCodeBlock = true;
                codeLang = line.trimStart().slice(3).trim();
                // Close any open list
                if (inList) { html += listType === 'ul' ? '</ul>' : '</ol>'; inList = false; listType = ''; }
            }
            continue;
        }

        if (inCodeBlock) {
            codeContent += line + '\n';
            continue;
        }

        // Empty line
        if (line.trim() === '') {
            if (inList) { html += listType === 'ul' ? '</ul>' : '</ol>'; inList = false; listType = ''; }
            continue;
        }

        // Headings
        const headingMatch = line.match(/^(#{1,6})\s+(.+)$/);
        if (headingMatch) {
            if (inList) { html += listType === 'ul' ? '</ul>' : '</ol>'; inList = false; listType = ''; }
            const level = headingMatch[1].length;
            html += `<h${level} class="md-heading">${inlineMarkdown(headingMatch[2])}</h${level}>`;
            continue;
        }

        // Horizontal rule
        if (/^(-{3,}|\*{3,}|_{3,})\s*$/.test(line.trim())) {
            if (inList) { html += listType === 'ul' ? '</ul>' : '</ol>'; inList = false; listType = ''; }
            html += '<hr class="md-hr">';
            continue;
        }

        // Blockquote
        if (line.trimStart().startsWith('> ')) {
            if (inList) { html += listType === 'ul' ? '</ul>' : '</ol>'; inList = false; listType = ''; }
            html += `<blockquote class="md-blockquote"><p>${inlineMarkdown(line.trimStart().slice(2))}</p></blockquote>`;
            continue;
        }

        // Unordered list
        const ulMatch = line.match(/^(\s*)[-*+]\s+(.+)$/);
        if (ulMatch) {
            if (!inList || listType !== 'ul') {
                if (inList) html += listType === 'ul' ? '</ul>' : '</ol>';
                html += '<ul class="md-list">';
                inList = true; listType = 'ul';
            }
            html += `<li>${inlineMarkdown(ulMatch[2])}</li>`;
            continue;
        }

        // Ordered list
        const olMatch = line.match(/^(\s*)\d+\.\s+(.+)$/);
        if (olMatch) {
            if (!inList || listType !== 'ol') {
                if (inList) html += listType === 'ul' ? '</ul>' : '</ol>';
                html += '<ol class="md-list">';
                inList = true; listType = 'ol';
            }
            html += `<li>${inlineMarkdown(olMatch[2])}</li>`;
            continue;
        }

        // Regular paragraph
        if (inList) { html += listType === 'ul' ? '</ul>' : '</ol>'; inList = false; listType = ''; }
        html += `<p class="md-p">${inlineMarkdown(line)}</p>`;
    }

    if (inCodeBlock) {
        html += `<pre><code class="language-${escapeHtml(codeLang)}">${escapeHtml(codeContent.trimEnd())}</code></pre>`;
    }
    if (inList) { html += listType === 'ul' ? '</ul>' : '</ol>'; }

    return html;
}

function inlineMarkdown(text) {
    if (!text) return '';
    let t = escapeHtml(text);
    // Images (must be before links)
    t = t.replace(/!\[([^\]]*)\]\(([^)]+)\)/g, '<img src="$2" alt="$1" class="md-img">');
    // Links
    t = t.replace(/\[([^\]]+)\]\(([^)]+)\)/g, '<a href="$2" target="_blank" rel="noopener" class="md-link">$1</a>');
    // Bold
    t = t.replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>');
    // Italic
    t = t.replace(/\*(.+?)\*/g, '<em>$1</em>');
    // Inline code
    t = t.replace(/`([^`]+)`/g, '<code class="md-inline-code">$1</code>');
    // Strikethrough
    t = t.replace(/~~(.+?)~~/g, '<del>$1</del>');
    return t;
}

// Keep old simpleMarkdownRender for chat (lightweight)
function simpleMarkdownRender(text) {
    if (!text) return '';
    return escapeHtml(text)
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\*(.+?)\*/g, '<em>$1</em>')
        .replace(/`(.+?)`/g, '<code style="background:var(--bg-tertiary);padding:1px 4px;border-radius:3px;">$1</code>')
        .replace(/\n/g, '<br>');
}

// ================================================================
// 11. File Upload + MathJax + Categories/Tags
// ================================================================
function handleDragOver(e) { e.preventDefault(); e.currentTarget.classList.add('dragover'); }

function handleFileDrop(e) {
    e.preventDefault();
    e.currentTarget.classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) uploadFilesToServer(files);
}

function handleFileUpload() {
    const files = document.getElementById('fileInput').files;
    if (files.length > 0) uploadFilesToServer(files);
}

async function uploadFilesToServer(files) {
    const formData = new FormData();
    for (const f of files) formData.append('files', f);
    formData.append('file_type', 'files');

    showUploadProgress('uploadProgress', true);
    try {
        const result = await apiService.uploadFiles(formData);
        if (result.success) {
            showToast(`上传成功: ${result.uploaded_count} 个文件`, 'success');
        } else {
            showToast(result.error || '上传失败', 'error');
        }
    } catch (e) {} finally {
        showUploadProgress('uploadProgress', false);
    }
}

function showUploadProgress(id, show) {
    const el = document.getElementById(id);
    if (el) el.innerHTML = show ? '<div class="loading"><div class="spinner"></div>上传中...</div>' : '';
}

async function importFromTextFiles() {
    const files = document.getElementById('textFileInput').files;
    if (files.length === 0) return;
    const formData = new FormData();
    for (const f of files) formData.append('files', f);
    formData.append('use_filename_as_title', 'true');
    formData.append('auto_detect_tags', 'true');

    showUploadProgress('textImportProgress', true);
    try {
        const result = await apiService.importTextFiles(formData);
        if (result.success) {
            showToast(`导入完成: ${result.imported_count} 条, 失败: ${result.failed_count} 条`, 'success');
            loadStats();
        }
    } catch (e) {} finally {
        showUploadProgress('textImportProgress', false);
    }
}

function refreshMath() {
    if (typeof MathJax !== 'undefined' && MathJax.typesetPromise) {
        MathJax.typesetPromise().catch(() => {});
    }
}

// ================================================================
// 11B. Inline Image/File Upload for Content
// ================================================================

let _uploadTargetId = 'newContent';

function uploadImageToInsert(textareaId) {
    _uploadTargetId = textareaId;
    document.getElementById('inlineImageInput').click();
}

function uploadFileToInsert(textareaId) {
    _uploadTargetId = textareaId;
    document.getElementById('inlineFileInput').click();
}

async function handleInlineImageUpload(input) {
    if (!input.files || input.files.length === 0) return;
    const formData = new FormData();
    for (const f of input.files) formData.append('files', f);
    formData.append('file_type', 'images');

    showToast('上传中...', 'success');
    try {
        const resp = await fetch(API_BASE + '/api/upload', { method: 'POST', body: formData });
        const result = await resp.json();
        if (result.success && result.file_urls && result.file_urls.length > 0) {
            const url = result.file_urls[0];
            const filename = result.file_details[0].filename;
            insertAtCursor(_uploadTargetId, `![${filename}](${url})`);
            showToast('图片已插入', 'success');
        } else {
            showToast(result.error || '上传失败', 'error');
        }
    } catch (e) {
        showToast('上传失败: ' + e.message, 'error');
    }
    input.value = '';
}

async function handleInlineFileUpload(input) {
    if (!input.files || input.files.length === 0) return;
    const formData = new FormData();
    for (const f of input.files) formData.append('files', f);
    formData.append('file_type', 'files');

    showToast('上传中...', 'success');
    try {
        const resp = await fetch(API_BASE + '/api/upload', { method: 'POST', body: formData });
        const result = await resp.json();
        if (result.success && result.file_urls && result.file_urls.length > 0) {
            const url = result.file_urls[0];
            const filename = result.file_details[0].filename;
            insertAtCursor(_uploadTargetId, `[${filename}](${url})`);
            showToast('文件已插入', 'success');
        } else {
            showToast(result.error || '上传失败', 'error');
        }
    } catch (e) {
        showToast('上传失败: ' + e.message, 'error');
    }
    input.value = '';
}

function insertAtCursor(textareaId, text) {
    const ta = document.getElementById(textareaId);
    if (!ta) return;
    const start = ta.selectionStart;
    const end = ta.selectionEnd;
    ta.value = ta.value.slice(0, start) + text + ta.value.slice(end);
    ta.focus();
    ta.selectionStart = ta.selectionEnd = start + text.length;
}

// ================================================================
// 12. AI Extraction Module
// ================================================================

function toggleQuickMode() {
    state.quickMode = !state.quickMode;
    const toggle = document.getElementById('quickModeToggle');
    if (state.quickMode) {
        toggle.classList.add('active');
    } else {
        toggle.classList.remove('active');
    }
    localStorage.setItem('quickMode', state.quickMode ? 'true' : 'false');
}

function switchExtractTab(tab) {
    state.extractTab = tab;
    document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
    document.querySelector(`.tab-btn[data-tab="${tab}"]`).classList.add('active');
    document.getElementById('extractUrlRow').style.display = tab === 'url' ? 'flex' : 'none';
    document.getElementById('extractTextRow').style.display = tab === 'text' ? 'flex' : 'none';
    document.getElementById('extractFileRow').style.display = tab === 'file' ? 'flex' : 'none';
    document.getElementById('aiPreview').style.display = 'none';
    state.lastExtracted = null;
    if (tab === 'file') loadFileList();
}

async function loadFileList() {
    try {
        const items = await apiService.getRecent();
        const files = [];
        const seen = new Set();
        for (const item of items) {
            if (item.source_details && item.source_type === 'file') {
                const name = item.source_details.replace(/^files[\\/]/, '');
                if (!seen.has(name)) {
                    seen.add(name);
                    files.push(name);
                }
            }
        }
        const select = document.getElementById('extractFileSelect');
        select.innerHTML = '<option value="">-- 选择文件 --</option>' +
            files.map(f => `<option value="${escapeHtml(f)}">${escapeHtml(f)}</option>`).join('');
    } catch (e) {}
}

function showExtractLoading() {
    document.getElementById('extractLoading').style.display = 'block';
    document.getElementById('aiPreview').style.display = 'none';
}

function hideExtractLoading() {
    document.getElementById('extractLoading').style.display = 'none';
}

function showExtractPreview(result) {
    state.lastExtracted = result;
    document.getElementById('aiPreviewTitle').value = result.title || '';
    document.getElementById('aiPreviewContent').value = result.content || '';
    document.getElementById('aiPreviewSummary').value = result.summary || '';
    document.getElementById('aiPreviewCategory').value = result.category || '未分类';
    document.getElementById('extractModel').textContent =
        `via ${result.provider || 'AI'}/${result.model || ''}`;
    renderPreviewTags(result.tags || []);
    hideExtractLoading();
    document.getElementById('aiPreview').style.display = 'block';
}

function renderPreviewTags(tags) {
    const container = document.getElementById('aiPreviewTags');
    state._previewTags = [...tags];
    container.innerHTML = tags.map((tag, i) =>
        `<span class="ai-tag">${escapeHtml(tag)}<span class="tag-remove" onclick="removePreviewTag(${i})">×</span></span>`
    ).join('');
}

function addPreviewTag() {
    const input = document.getElementById('aiPreviewNewTag');
    const tag = input.value.trim();
    if (!tag) return;
    if (!state._previewTags) state._previewTags = [];
    state._previewTags.push(tag);
    renderPreviewTags(state._previewTags);
    input.value = '';
}

function removePreviewTag(index) {
    state._previewTags.splice(index, 1);
    renderPreviewTags(state._previewTags);
}

async function extractFromURL() {
    const url = document.getElementById('extractUrl').value.trim();
    if (!url) { showToast('请输入URL', 'warning'); return; }
    showExtractLoading();
    try {
        const result = await apiService.extractURL(url);
        if (state.quickMode) {
            await saveExtractedItem(result);
        } else {
            showExtractPreview(result);
        }
    } catch (e) { hideExtractLoading(); }
}

async function extractFromText() {
    const text = document.getElementById('extractText').value.trim();
    if (!text) { showToast('请输入文本内容', 'warning'); return; }
    showExtractLoading();
    try {
        const result = await apiService.extractText(text);
        if (state.quickMode) {
            await saveExtractedItem(result);
        } else {
            showExtractPreview(result);
        }
    } catch (e) { hideExtractLoading(); }
}

async function extractFromFile() {
    const filename = document.getElementById('extractFileSelect').value;
    if (!filename) { showToast('请选择文件', 'warning'); return; }
    showExtractLoading();
    try {
        const result = await apiService.extractFile(filename);
        if (state.quickMode) {
            await saveExtractedItem(result);
        } else {
            showExtractPreview(result);
        }
    } catch (e) { hideExtractLoading(); }
}

async function confirmAIExtract() {
    const data = {
        title: document.getElementById('aiPreviewTitle').value.trim(),
        content: document.getElementById('aiPreviewContent').value.trim(),
        summary: document.getElementById('aiPreviewSummary').value.trim(),
        tags: state._previewTags || [],
        category: document.getElementById('aiPreviewCategory').value.trim() || '未分类',
        importance_level: 3,
        understanding_level: 3,
    };
    if (!data.title || !data.content) {
        showToast('标题和内容不能为空', 'warning');
        return;
    }
    try {
        const result = await apiService.addItem({
            ...data,
            summary: data.summary,
            tags: data.tags,
        });
        if (result.success) {
            showToast(`知识条目已添加! ID: ${result.item_id}`, 'success');
            document.getElementById('aiPreview').style.display = 'none';
            state.lastExtracted = null;
            loadStats();
        }
    } catch (e) {}
}

async function saveExtractedItem(extracted) {
    try {
        const result = await apiService.addItem({
            title: extracted.title || '未命名条目',
            content: extracted.content || '',
            summary: extracted.summary || '',
            tags: extracted.tags || [],
            category: extracted.category || '未分类',
            importance_level: 3,
            understanding_level: 3,
        });
        if (result.success) {
            hideExtractLoading();
            showToast(`已保存: ${extracted.title || '未命名条目'}`, 'success');
            loadStats();
        }
    } catch (e) { hideExtractLoading(); }
}

async function retryAIExtract() {
    document.getElementById('aiPreview').style.display = 'none';
    if (state.extractTab === 'url') await extractFromURL();
    else if (state.extractTab === 'text') await extractFromText();
    else if (state.extractTab === 'file') await extractFromFile();
}

async function showCategories() {
    try {
        const cats = await apiService.getCategories();
        const container = document.getElementById('searchResults');
        if (!cats || cats.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>暂无分类</p></div>';
            return;
        }
        container.innerHTML = `<div class="item-list">${cats.map(c => `
            <div class="item-card" onclick="showCategoryItems('${escapeHtml(c.name || c)}')">
                <span style="font-size:24px;margin-right:8px;">📂</span>
                ${escapeHtml(c.name || c)}
                ${c.count ? `<span style="color:var(--text-tertiary);font-size:12px;">(${c.count})</span>` : ''}
            </div>
        `).join('')}</div>`;
    } catch (e) {}
}

async function showTags() {
    try {
        const tags = await apiService.getTags();
        const container = document.getElementById('searchResults');
        if (!tags || tags.length === 0) {
            container.innerHTML = '<div class="empty-state"><p>暂无标签</p></div>';
            return;
        }
        container.innerHTML = `<div style="display:flex;flex-wrap:wrap;gap:8px;">${tags.map(t => `
            <span class="tag" style="cursor:pointer;padding:6px 12px;font-size:13px;" onclick="showTagItems('${escapeHtml(t.name || t)}')">
                ${escapeHtml(t.name || t)}
                ${t.count ? ` (${t.count})` : ''}
            </span>
        `).join('')}</div>`;
    } catch (e) {}
}

async function showCategoryItems(cat) {
    try {
        const items = await apiService.getCategoryItems(cat);
        renderSearchResults(items);
    } catch (e) {}
}

async function showTagItems(tag) {
    try {
        const items = await apiService.getTagItems(tag);
        renderSearchResults(items);
    } catch (e) {}
}

// ================================================================
// 12. Keyboard Shortcuts
// ================================================================
document.addEventListener('keydown', function(e) {
    const active = document.activeElement;
    const isTextInput = active && (active.tagName === 'INPUT' || active.tagName === 'TEXTAREA');

    if (isTextInput) {
        if (e.ctrlKey || e.metaKey) {
            if (e.key.toLowerCase() === 'enter' &&
                (active.id === 'newContent' || active.id === 'editContent')) {
                e.preventDefault(); addNewItem();
            }
        }
        if (e.key === 'Enter' && active.id === 'searchInput') {
            e.preventDefault(); searchItems();
        }
        return;
    }

    if (e.ctrlKey || e.metaKey) {
        switch (e.key.toLowerCase()) {
            case 'f': e.preventDefault(); document.getElementById('searchInput')?.focus(); break;
            case 'g': e.preventDefault(); switchPanel('graph'); break;
            case 'r': e.preventDefault(); switchPanel('review'); break;
        }
    } else if (e.key === 'Escape') {
        closeModal();
    }
});

// ================================================================
// 13. Review Tab & Sort Switching
// ================================================================

function switchReviewTab(tab) {
    state.reviewTab = tab;
    document.querySelectorAll('.review-tab-btn').forEach(b => b.classList.remove('active'));
    const btn = document.querySelector(`.review-tab-btn[data-review-tab="${tab}"]`);
    if (btn) btn.classList.add('active');
    document.getElementById('reviewPlanPanel').style.display = tab === 'review-plan' ? '' : 'none';
    document.getElementById('learningPathPanel').style.display = tab === 'learning-path' ? '' : 'none';
    if (tab === 'review-plan') loadReviews();
}

function switchReviewSort(mode) {
    state.reviewSortMode = mode;
    const btnDefault = document.getElementById('btnSortDefault');
    const btnAI = document.getElementById('btnSortAI');
    if (btnDefault) btnDefault.className = mode === 'default' ? 'btn btn-sm' : 'btn btn-outline btn-sm';
    if (btnAI) btnAI.className = mode === 'ai' ? 'btn btn-sm' : 'btn btn-outline btn-sm';
    if (mode === 'ai') {
        loadAIReviewPlan();
    } else {
        document.getElementById('strategyNotes').style.display = 'none';
        state.cachedReviewPlan = null;
        loadReviews();
    }
}

async function loadAIReviewPlan() {
    try {
        const items = await apiService.getReviews();
        if (!items || items.length === 0) {
            renderReviews([]);
            return;
        }
        const plan = await apiService.optimizeReviewPlan(7);
        state.cachedReviewPlan = plan;

        const notes = document.getElementById('strategyNotes');
        if (notes) {
            notes.textContent = plan.strategy_notes || '';
            notes.style.display = '';
        }

        const priorityMap = {};
        if (plan.daily_plan && plan.daily_plan.length > 0) {
            (plan.daily_plan[0].items || []).forEach(it => { priorityMap[it.id] = { p: it.priority, r: it.reason }; });
        }

        const sorted = [...items].sort((a, b) => {
            const pa = (priorityMap[a.id] && priorityMap[a.id].p) || 99;
            const pb = (priorityMap[b.id] && priorityMap[b.id].p) || 99;
            return pa - pb;
        });

        renderReviewsWithPriority(sorted, priorityMap);
    } catch (e) {}
}

function renderReviewsWithPriority(items, priorityMap) {
    const container = document.getElementById('reviewContent');
    if (!items || items.length === 0) {
        container.innerHTML = '<div class="empty-state"><div class="empty-state-icon">🎉</div><p>今天没有需要复习的内容！</p></div>';
        return;
    }
    container.innerHTML = items.map((item, i) => {
        const pri = (priorityMap && priorityMap[item.id]) || { p: 3, r: '' };
        return `
        <div class="item-card" id="review-item-${item.id}">
            <div class="item-card-title">
                ${i + 1}. ${escapeHtml(item.title)}
                <span class="priority-badge p${pri.p}">P${pri.p}</span>
            </div>
            ${pri.r ? `<div style="font-size:11px;color:var(--text-tertiary);margin-top:2px;">💡 ${escapeHtml(pri.r)}</div>` : ''}
            <div class="item-card-meta">
                <span>理解程度: ${item.understanding_level}/5</span>
                <span>📝 ${escapeHtml(item.summary || '')}</span>
            </div>
            <div style="margin-top:8px;display:flex;gap:8px;align-items:center;" onclick="event.stopPropagation()">
                ${[0,1,2,3,4,5].map(r => `
                    <button class="btn ${r >= 4 ? 'btn-success' : r >= 2 ? 'btn-outline' : 'btn-danger'} btn-sm"
                            onclick="rateReview(${item.id}, ${r})">${r}</button>
                `).join('')}
            </div>
        </div>
        `;
    }).join('');
}

// ================================================================
// 14. AI Relationship Discovery (Knowledge Graph)
// ================================================================

async function discoverRelationships() {
    const btn = document.getElementById('btnDiscoverRel');
    if (!btn) return;
    btn.disabled = true;
    btn.textContent = '分析中...';

    try {
        const graphData = await apiService.getGraph('');
        if (!graphData || !graphData.nodes || graphData.nodes.length < 2) {
            showToast('需要至少2个条目才能发现关联', 'warning');
            return;
        }

        const filterVal = document.getElementById('graphCategoryFilter');
        const result = await apiService.discoverRelationships({
            scope: filterVal && filterVal.value ? 'category' : 'all',
            category: filterVal ? filterVal.value : '',
            limit: 30,
        });

        if (result.suggestions && result.suggestions.length > 0) {
            state.suggestionEdges = result.suggestions;
            document.getElementById('suggestionCount').textContent = result.suggestions.length;
            document.getElementById('graphSuggestionControls').style.display = '';
            // Reload graph first, then overlay suggested edges
            loadKnowledgeGraph();
            setTimeout(() => renderSuggestedEdges(result.suggestions), 1200);
        } else {
            showToast('未发现新的关联建议', 'success');
            state.suggestionEdges = [];
        }
    } catch (e) {
        // Error toast handled by api()
    }
    btn.disabled = false;
    btn.textContent = '🤖 AI 发现关联';
}

function renderSuggestedEdges(suggestions) {
    const container = document.getElementById('graphContainer');
    const svg = container ? container.querySelector('svg') : null;
    if (!svg) return;

    const g = svg.querySelector('g');
    if (!g) return;

    // Remove old suggested edges
    g.querySelectorAll('line.suggested-edge').forEach(l => l.remove());

    const nodes = graphSimulation ? graphSimulation.nodes() : [];

    suggestions.forEach((sug, idx) => {
        const src = nodes.find(n => n.id === sug.source_id);
        const tgt = nodes.find(n => n.id === sug.target_id);
        if (!src || !tgt) return;

        const line = document.createElementNS('http://www.w3.org/2000/svg', 'line');
        line.setAttribute('class', 'suggested-edge');
        line.setAttribute('x1', src.x);
        line.setAttribute('y1', src.y);
        line.setAttribute('x2', tgt.x);
        line.setAttribute('y2', tgt.y);
        line.setAttribute('data-sid', sug.source_id);
        line.setAttribute('data-tid', sug.target_id);
        line.setAttribute('data-idx', idx);

        line.addEventListener('mouseenter', (e) => {
            const tooltip = document.createElement('div');
            tooltip.className = 'edge-tooltip';
            tooltip.id = 'edgeTooltip';
            tooltip.innerHTML = `<strong>${escapeHtml(sug.type || 'related_to')}</strong><br>${escapeHtml(sug.reason || '')}<br><span style="font-size:10px;color:var(--text-tertiary);">强度: ${sug.strength || 3}/5 | 点击采纳</span>`;
            document.body.appendChild(tooltip);
            tooltip.style.left = (e.clientX + 10) + 'px';
            tooltip.style.top = (e.clientY - 10) + 'px';
        });

        line.addEventListener('mouseleave', () => {
            const tt = document.getElementById('edgeTooltip');
            if (tt) tt.remove();
        });

        line.addEventListener('click', () => adoptSuggestion(idx));

        g.appendChild(line);
    });
}

async function adoptSuggestion(idx) {
    const sug = state.suggestionEdges[idx];
    if (!sug) return;
    try {
        await apiService.createRelationship({
            source_id: sug.source_id,
            target_id: sug.target_id,
            relationship_type: sug.type || 'related_to',
            strength: sug.strength || 3,
        });
        state.suggestionEdges.splice(idx, 1);
        showToast('关联已添加', 'success');
        document.getElementById('suggestionCount').textContent = state.suggestionEdges.length;
        if (state.suggestionEdges.length === 0) {
            clearSuggestions();
            loadKnowledgeGraph();
        } else {
            loadKnowledgeGraph();
            setTimeout(() => renderSuggestedEdges(state.suggestionEdges), 1200);
        }
    } catch (e) {}
}

async function adoptAllSuggestions() {
    const count = state.suggestionEdges.length;
    for (const sug of state.suggestionEdges) {
        try {
            await apiService.createRelationship({
                source_id: sug.source_id,
                target_id: sug.target_id,
                relationship_type: sug.type || 'related_to',
                strength: sug.strength || 3,
            });
        } catch (e) {}
    }
    clearSuggestions();
    showToast(`已添加 ${count} 条关联`, 'success');
    loadKnowledgeGraph();
}

function clearSuggestions() {
    state.suggestionEdges = [];
    const controls = document.getElementById('graphSuggestionControls');
    if (controls) controls.style.display = 'none';
    const svg = document.querySelector('#graphContainer svg');
    if (svg) {
        const g = svg.querySelector('g');
        if (g) g.querySelectorAll('line.suggested-edge').forEach(l => l.remove());
    }
    const tt = document.getElementById('edgeTooltip');
    if (tt) tt.remove();
}

// ================================================================
// 15. Initialization
// ================================================================
async function init() {
    // Restore last panel from URL hash
    const hash = window.location.hash.slice(1);
    if (hash) switchPanel(hash);

    // Restore sidebar state
    if (localStorage.getItem('sidebarCollapsed') === 'true' && window.innerWidth >= 768) {
        document.getElementById('sidebar').classList.add('collapsed');
    }

    // Load stats
    loadStats();

    // Load current database info
    try {
        const dbInfo = await apiService.currentDB();
        state.currentDB = dbInfo.current_database || 'knowledge.db';
        document.getElementById('currentDbName').textContent = state.currentDB;
    } catch (e) {}

    // Load AI status
    loadAIStatus();

    // Restore quick mode
    if (localStorage.getItem('quickMode') === 'true') {
        state.quickMode = true;
        const toggle = document.getElementById('quickModeToggle');
        if (toggle) toggle.classList.add('active');
    }
}

// Handle window resize
window.addEventListener('resize', () => {
    const sidebar = document.getElementById('sidebar');
    const overlay = document.getElementById('sidebarOverlay');
    if (window.innerWidth >= 768) {
        sidebar.classList.remove('open');
        overlay.classList.remove('show');
    }
});

// Handle modal overlay click to close
document.getElementById('modalOverlay').addEventListener('click', function(e) {
    if (e.target === this) closeModal();
});

// Handle hash change for browser back/forward
window.addEventListener('hashchange', function() {
    const hash = window.location.hash.slice(1);
    if (hash && hash !== state.currentPanel) switchPanel(hash);
});

document.addEventListener('DOMContentLoaded', init);
