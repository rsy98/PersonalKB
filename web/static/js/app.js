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
    aiConfig: null,
    aiModel: {},  // { capability: {provider, model} }
    semanticMode: false,
    ragMode: true,
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
    getAllReviews: () => api('/api/review?all=1'),
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
    exportData: (format, category) => {
        const params = new URLSearchParams({ format });
        if (category) params.append('category', category);
        return `/api/export?${params.toString()}`;
    },
    generateEmbeddings: () => api('/api/ai/embeddings/generate', { method: 'POST' }),
    semanticSearch: (q, limit) => api(`/api/ai/semantic_search?q=${encodeURIComponent(q)}&limit=${limit || 10}`),
    ragChat: (question, chatHistory, provider, model, attachments) => api('/api/ai/rag_chat', {
        method: 'POST',
        body: JSON.stringify({ question, chat_history: chatHistory, provider, model, attachments }),
    }),
    importFile: (formData) => {
        return fetch(API_BASE + '/api/import', { method: 'POST', body: formData }).then(r => r.json());
    },
    uploadFiles: (formData) => {
        return fetch(API_BASE + '/api/upload', { method: 'POST', body: formData }).then(r => r.json());
    },
    importTextFiles: (formData) => {
        return fetch(API_BASE + '/api/import_text_files', { method: 'POST', body: formData }).then(r => r.json());
    },
    importJSONData: (items) => {
        return api('/api/import/json', { method: 'POST', body: JSON.stringify({ items }) });
    },
    searchItems: (q) => {
        return api('/api/search_items?q=' + encodeURIComponent(q));
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
    contentAnalysis: (id) => api(`/api/ai/analyze/${id}`, { method: 'POST', body: '{}' }),
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
    listExtractableFiles: () => {
        return api('/api/ai/files');
    },
    discoverRelationships: (data) => {
        return api('/api/ai/discover/relationships', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },
    discoverGaps: (category, provider, model) => {
        return api('/api/ai/discover/gaps', {
            method: 'POST',
            body: JSON.stringify({ category, provider, model }),
        });
    },
    generateLearningPath: (goal, category, provider, model) => {
        const data = { goal, provider, model };
        if (category) { data.scope = 'category'; data.category = category; }
        return api('/api/ai/learning/path', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },
    optimizeReviewPlan: (days, provider, model) => {
        return api('/api/ai/learning/review-plan', {
            method: 'POST',
            body: JSON.stringify({ days: days || 7, provider, model }),
        });
    },
    suggestRelated: (itemId, provider, model) => {
        return api(`/api/ai/suggest/related/${itemId}`, {
            method: 'POST',
            body: JSON.stringify({ provider, model }),
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
        container.innerHTML = `<div class="empty-state">
            <div class="empty-state-icon">🎉</div>
            <p>今天没有到期需要复习的内容</p>
            <p style="font-size:12px;color:var(--text-tertiary);">复习系统基于间隔重复算法，新条目会在创建几天后进入复习队列</p>
            <button class="btn btn-primary btn-sm" style="margin-top:8px;" onclick="loadAllReviews()">📚 复习全部条目</button>
        </div>`;
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
        <div style="margin-top:12px;padding:12px;background:var(--bg-tertiary);border-radius:8px;display:flex;gap:8px;align-items:center;flex-wrap:wrap;" onclick="event.stopPropagation()">
            <span style="font-size:12px;color:var(--text-secondary);font-weight:500;">🤖 AI 操作:</span>
            <div style="display:flex;gap:4px;align-items:center;flex-wrap:wrap;font-size:10px;">
                <span style="color:var(--text-tertiary);">分析</span><span id="detailAnalyzeSelector"></span>
                <span style="color:var(--text-tertiary);">出题</span><span id="detailQuestionsSelector"></span>
                <span style="color:var(--text-tertiary);">润色</span><span id="detailImproveSelector"></span>
            </div>
            <button class="btn btn-sm btn-outline" id="btnAnalyzeDetail" onclick="analyzeItem(${item.id})">📊 分析</button>
            <button class="btn btn-sm btn-outline" id="btnGenQuestions" onclick="generateQuestions(${item.id})">📝 生成题目</button>
            <button class="btn btn-sm btn-outline" onclick="improveWritingForItem(${item.id})">✨ 改进写作</button>
            <span id="aiOpResult" style="font-size:12px;color:var(--text-tertiary);width:100%;margin-top:4px;"></span>
        </div>
        <div id="relatedItemsSection" style="margin-top:20px;">
            <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;flex-wrap:wrap;gap:8px;">
                <h4 style="margin:0;">关联条目</h4>
                <div style="display:flex;gap:4px;">
                    <button class="btn btn-sm btn-outline" onclick="showAddRelationship()">+ 添加关联</button>
                    <button class="btn btn-sm btn-outline" id="btnAISuggestRel" onclick="aiSuggestRelated(${item.id})" style="color:var(--accent);">🤖 AI 建议关联</button>
                    <span id="detailSuggestRelSelector" style="display:inline-block;vertical-align:middle;"></span>
                </div>
            </div>
            <div id="aiSuggestResults" style="margin-bottom:8px;"></div>
            <div id="relatedItemsList"><div class="loading"><div class="spinner"></div></div></div>
            <div id="addRelationshipForm" style="display:none;margin-top:12px;padding:12px;background:var(--bg-tertiary);border-radius:8px;">
                <div style="margin-bottom:8px;">
                    <input type="text" class="form-input" id="relSearchInput" placeholder="搜索目标条目..." oninput="searchRelTarget(this.value)">
                </div>
                <div id="relSearchResults" style="max-height:150px;overflow-y:auto;margin-bottom:8px;"></div>
                <div style="display:flex;gap:8px;align-items:center;flex-wrap:wrap;">
                    <select class="form-select" id="relType" style="width:auto;">
                        <option value="related_to">相关</option>
                        <option value="prerequisite">前置知识</option>
                        <option value="extends">扩展深化</option>
                        <option value="contradicts">不同观点</option>
                    </select>
                    <select class="form-select" id="relStrength" style="width:auto;">
                        <option value="3">关联度 3</option>
                        <option value="1">关联度 1</option>
                        <option value="2">关联度 2</option>
                        <option value="4">关联度 4</option>
                        <option value="5">关联度 5</option>
                    </select>
                    <button class="btn btn-primary btn-sm" onclick="confirmAddRelationship()">确认</button>
                    <button class="btn btn-sm btn-outline" onclick="cancelAddRelationship()">取消</button>
                </div>
            </div>
        </div>
        <div style="margin-top:20px;border-top:1px solid var(--border-light);padding-top:16px;">
            <h4 style="margin:0 0 8px 0;display:flex;align-items:center;gap:8px;">
                💬 针对此条目的 AI 对话
                <span id="detailChatSelector" style="display:inline-block;vertical-align:middle;"></span>
            </h4>
            <div id="itemChatMessages" style="max-height:250px;overflow-y:auto;padding:8px;background:var(--bg-secondary);border-radius:8px;margin-bottom:8px;">
                <div class="chat-message assistant" style="font-size:12px;">你可以针对「${escapeHtml(item.title)}」向我提问，我会结合条目内容和我的知识来回答。</div>
            </div>
            <div style="display:flex;gap:6px;">
                <input type="text" id="itemChatInput" class="form-input" placeholder="针对此条目提问..."
                       onkeydown="if(event.key==='Enter'&&!event.shiftKey){sendItemChatMessage(${item.id});event.preventDefault()}"
                       style="flex:1;">
                <button class="btn btn-primary btn-sm" onclick="sendItemChatMessage(${item.id})">发送</button>
                <button class="btn btn-outline btn-sm" onclick="clearItemChat()">清空</button>
            </div>
        </div>
    `;
    document.getElementById('modalTitle').textContent = '条目详情';
    document.getElementById('modalOverlay').style.display = 'flex';
    state.currentItemId = item.id;
    state._itemContent = content;
    state._itemChatHistory = [];
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

function getNodeColor(importanceLevel) {
    const colors = {
        1: '#666666',
        2: '#3498db',
        3: '#bb86fc',
        4: '#f39c12',
        5: '#e74c3c'
    };
    return colors[importanceLevel] || colors[3];
}

function renderKnowledgeGraph(data) {
    const container = document.getElementById('mynetwork');
    if (!container) return;

    if (!data || !data.nodes || data.nodes.length === 0) {
        container.innerHTML = '<div style="text-align:center;padding:50px;color:var(--text-tertiary);">暂无图谱数据，请先添加知识条目和关联关系</div>';
        document.getElementById('graphInfo').textContent = '';
        return;
    }

    const nodes = new vis.DataSet(data.nodes.map(node => ({
        id: node.id,
        label: (node.title || '').length > 18 ? (node.title || '').substring(0, 18) + '...' : (node.title || '未知'),
        group: node.category || '未分类',
        title: `ID: ${node.id}\n标题: ${node.title || '未知'}\n分类: ${node.category || '未分类'}\n重要性: ${node.importance_level || 1}/5\n理解程度: ${node.understanding_level || 1}/5`,
        value: node.importance_level || 1,
        color: getNodeColor(node.importance_level || 1),
        font: { color: '#ffffff' }
    })));

    const edges = new vis.DataSet((data.edges || []).map(edge => ({
        from: edge.source_id,
        to: edge.target_id,
        arrows: 'to',
        color: { color: '#bb86fc', highlight: '#e040fb' },
        title: edge.relationship_type || '关联'
    })));

    const options = {
        nodes: {
            shape: 'dot',
            size: 25,
            font: { size: 14, face: 'Tahoma', color: '#ffffff' },
            borderWidth: 2,
            shadow: true
        },
        edges: {
            width: 2,
            color: { color: '#bb86fc', highlight: '#e040fb' },
            shadow: true,
            smooth: { type: 'continuous' }
        },
        physics: {
            enabled: true,
            solver: 'forceAtlas2Based',
            forceAtlas2Based: {
                gravitationalConstant: -50,
                centralGravity: 0.01,
                springLength: 100,
                springConstant: 0.08,
                damping: 0.4,
                avoidOverlap: 1
            }
        },
        interaction: {
            hover: true,
            tooltipDelay: 200,
            hideEdgesOnDrag: true,
            navigationButtons: true,
            keyboard: true
        },
        layout: {
            improvedLayout: true,
            randomSeed: Math.floor(Math.random() * 1000)
        }
    };

    const network = new vis.Network(container, { nodes, edges }, options);

    network.on('click', function(params) {
        if (params.nodes.length > 0) {
            showItemDetail(params.nodes[0]);
        }
    });

    network.on('doubleClick', function(params) {
        if (params.nodes.length > 0) {
            const connectedNodes = new Set();
            const allEdges = network.body.data.edges.get();
            allEdges.forEach(edge => {
                if (edge.from === params.nodes[0] || edge.to === params.nodes[0]) {
                    connectedNodes.add(edge.from);
                    connectedNodes.add(edge.to);
                }
            });
            const allNodes = network.body.data.nodes.get();
            allNodes.forEach(node => {
                if (connectedNodes.has(node.id)) {
                    network.body.data.nodes.update({ id: node.id, borderWidth: 3, color: { border: '#ffffff' } });
                }
            });
            setTimeout(() => {
                allNodes.forEach(node => {
                    if (connectedNodes.has(node.id)) {
                        network.body.data.nodes.update({ id: node.id, borderWidth: 2, color: { border: '#ffffff' } });
                    }
                });
            }, 2000);
        }
    });

    window.knowledgeGraphNetwork = network;

    document.getElementById('graphInfo').textContent =
        `节点: ${data.nodes.length} | 关系: ${data.edges.length}`;

    // 重建分类筛选器选项
    const categories = [...new Set(data.nodes.map(n => n.category || '未分类'))];
    const filter = document.getElementById('graphCategoryFilter');
    if (filter) {
        while (filter.options.length > 1) filter.remove(1);
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
    else if (name === 'upload') { /* panel activated */ }

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
    const collapseBtn = document.querySelector('.sidebar-collapse');
    if (window.innerWidth < 768) {
        sidebar.classList.toggle('open');
        overlay.classList.toggle('show');
    } else {
        sidebar.classList.toggle('collapsed');
        const collapsed = sidebar.classList.contains('collapsed');
        if (collapseBtn) collapseBtn.textContent = collapsed ? '▶' : '◀';
        localStorage.setItem('sidebarCollapsed', collapsed ? 'true' : 'false');
    }
}

// 页面加载时恢复折叠状态
(function() {
    if (localStorage.getItem('sidebarCollapsed') === 'true') {
        document.getElementById('sidebar').classList.add('collapsed');
        const btn = document.querySelector('.sidebar-collapse');
        if (btn) btn.textContent = '▶';
    }
})();

// ================================================================
// 6. Core Operations
// ================================================================
async function searchItems() {
    const query = document.getElementById('searchInput').value.trim();
    if (!query) { showAllItems(); return; }
    try {
        const gapContainer = document.getElementById('gapAnalysis');
        if (gapContainer) gapContainer.style.display = 'none';
        if (state.semanticMode) {
            const result = await apiService.semanticSearch(query, 20);
            if (result.warning) {
                showToast(result.warning, 'warning');
                // Fall back to keyword search
                const items = await apiService.search(query);
                renderSearchResults(items);
            } else {
                renderSemanticResults(result.items || []);
            }
        } else {
            const items = await apiService.search(query);
            renderSearchResults(items);
        }
        showExportToolbar();
    } catch (e) {}
}

async function showAllItems() {
    try {
        const gapContainer = document.getElementById('gapAnalysis');
        if (gapContainer) gapContainer.style.display = 'none';
        const items = await apiService.getRecent();
        renderSearchResults(items);
        showExportToolbar();
    } catch (e) {}
}

// ── Export ──

function showExportToolbar() {
    const toolbar = document.getElementById('exportToolbar');
    if (toolbar) toolbar.style.display = 'flex';
    // Populate category dropdown
    apiService.getCategories().then(cats => {
        const sel = document.getElementById('exportCategory');
        if (sel && cats) {
            sel.innerHTML = '<option value="">全部分类</option>' +
                cats.map(c => `<option value="${escapeHtml(c.name || c)}">${escapeHtml(c.name || c)}</option>`).join('');
            // Preserve selection
            if (state._exportCategory) sel.value = state._exportCategory;
            sel.onchange = () => { state._exportCategory = sel.value; };
        }
    }).catch(() => {});
}

function exportKnowledge(format) {
    const category = document.getElementById('exportCategory')?.value || '';
    const url = apiService.exportData(format, category);
    // Trigger file download
    const a = document.createElement('a');
    a.href = url;
    a.download = '';
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
}

// ── Semantic Search ──

function toggleSemanticSearch() {
    const toggle = document.getElementById('semanticToggle');
    state.semanticMode = !state.semanticMode;
    if (state.semanticMode) {
        toggle.classList.add('active');
    } else {
        toggle.classList.remove('active');
    }
}

function renderSemanticResults(items) {
    const container = document.getElementById('searchResults');
    if (!items || items.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>未找到相关结果</p></div>';
        return;
    }
    container.innerHTML = `<div style="margin-bottom:8px;font-size:12px;color:var(--text-tertiary);">语义搜索结果 (${items.length} 条)</div><div class="item-list">${items.map(item => `
        <div class="item-card" onclick="showItemDetail(${item.id})">
            <div class="item-card-title">
                ${escapeHtml(item.title)}
                <span style="float:right;font-size:11px;color:var(--accent);">${(item.score * 100).toFixed(0)}%</span>
            </div>
            <div class="item-card-meta">📂 ${escapeHtml(item.category || '')} ${item.summary ? '| ' + escapeHtml(item.summary) : ''}</div>
            <div style="font-size:12px;color:var(--text-secondary);margin-top:4px;line-height:1.5;">${contentPreview(item.content, 150)}</div>
        </div>
    `).join('')}</div>`;
}

async function generateEmbeddings() {
    const btn = document.getElementById('btnGenerateEmbed');
    if (!btn) return;
    btn.disabled = true;
    btn.textContent = '生成中...';
    try {
        const result = await apiService.generateEmbeddings();
        if (result.success) {
            showToast(result.message, 'success');
        } else {
            showToast(result.error || '生成失败', 'error');
        }
    } catch (e) {
        showToast('索引生成失败，请确认 Ollama 正在运行且 bge-m3 模型可用', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '🔧 生成索引';
    }
}

// ── RAG Mode ──

function toggleRAGMode() {
    const toggle = document.getElementById('ragToggle');
    state.ragMode = !state.ragMode;
    if (state.ragMode) {
        toggle.classList.add('active');
    } else {
        toggle.classList.remove('active');
    }
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
        setTimeout(buildDetailModelSelectors, 200);
    } catch (e) {}
}

// ── AI 操作：分析 / 生成题目 / 改进写作 ──

async function analyzeItem(itemId) {
    const resultEl = document.getElementById('aiOpResult');
    resultEl.textContent = '分析中...';
    try {
        const opts = getAIOptions('analyze');
        const result = await apiService.aiAnalyze(itemId, opts.provider, opts.model);
        const text = result.analysis || JSON.stringify(result);
        resultEl.innerHTML = `<div style="max-height:200px;overflow-y:auto;white-space:pre-wrap;">${escapeHtml(text)}</div>`;
    } catch (e) {
        resultEl.textContent = '分析失败';
    }
}

async function generateQuestions(itemId) {
    const resultEl = document.getElementById('aiOpResult');
    resultEl.textContent = '生成中...';
    try {
        const opts = getAIOptions('generate_questions');
        const resp = await apiService.aiGenerateQuestions(itemId, opts.provider, opts.model);
        const questions = resp.questions || [];
        if (questions.length > 0) {
            resultEl.innerHTML = '<ol style="margin:0;padding-left:20px;">' +
                questions.map(q => `<li style="margin-bottom:4px;">${escapeHtml(q)}</li>`).join('') + '</ol>';
        } else {
            resultEl.textContent = '未能生成题目';
        }
    } catch (e) {
        resultEl.textContent = '生成失败';
    }
}

async function improveWritingForItem(itemId) {
    const resultEl = document.getElementById('aiOpResult');
    resultEl.textContent = '改进中...';
    try {
        const item = await apiService.getItem(itemId);
        const content = item.content || '';
        const opts = getAIOptions('improve_writing');
        const resp = await apiService.aiImproveWriting(content, opts.provider, opts.model);
        const improved = resp.improved_content || resp.error || '改进失败';
        state._lastImproved = improved;
        resultEl.innerHTML = `
            <div style="max-height:200px;overflow-y:auto;white-space:pre-wrap;border:1px solid var(--border-light);padding:8px;border-radius:4px;margin-bottom:8px;">${escapeHtml(improved)}</div>
            <div style="display:flex;gap:8px;">
                <button class="btn btn-sm btn-success" onclick="adoptImprovedWriting(${itemId})">✅ 采纳</button>
                <button class="btn btn-sm btn-outline" onclick="document.getElementById('aiOpResult').innerHTML=''">关闭</button>
            </div>`;
    } catch (e) {
        resultEl.textContent = '改进失败';
    }
}

async function adoptImprovedWriting(itemId) {
    if (!state._lastImproved) return;
    try {
        const item = await apiService.getItem(itemId);
        await apiService.updateItem(itemId, {
            title: item.title,
            content: state._lastImproved,
            category: item.category,
            importance_level: item.importance_level || 3,
            understanding_level: item.understanding_level || 3,
            tags: (item.tag_names || '').split(',').filter(Boolean),
        });
        showToast('已采纳改进文本', 'success');
        document.getElementById('aiOpResult').innerHTML = '';
    } catch (e) {
        showToast('采纳失败', 'error');
    }
}

// ── 数据库切换 ──

async function showDBSwitcher() {
    const popup = document.getElementById('dbSwitcherPopup');
    const list = document.getElementById('dbList');
    if (popup.style.display !== 'none') {
        popup.style.display = 'none';
        return;
    }
    const currentDb = document.getElementById('currentDbName').textContent.trim();
    // 从 run.py 预定义的数据库列表
    const presetDbs = ['knowledge.db', 'art.db', 'AI.db', 'math.db', 'life.db', 'physics.db'];
    list.innerHTML = presetDbs.map(db => `
        <div onclick="switchKnowledgeDB('${db}')" style="padding:6px 8px;cursor:pointer;border-radius:4px;font-size:13px;
            ${db === currentDb ? 'background:var(--accent);color:#fff;' : ''}">
            ${db} ${db === currentDb ? ' ✓' : ''}
        </div>`).join('');
    popup.style.display = 'block';
    // 点击外部关闭
    setTimeout(() => {
        const handler = (e) => {
            if (!popup.contains(e.target) && e.target.id !== 'currentDbName') {
                popup.style.display = 'none';
                document.removeEventListener('click', handler);
            }
        };
        document.addEventListener('click', handler);
    }, 100);
}

async function switchKnowledgeDB(dbName) {
    try {
        const result = await apiService.switchDB(dbName);
        if (result.success) {
            document.getElementById('currentDbName').textContent = dbName;
            document.getElementById('dbSwitcherPopup').style.display = 'none';
            showToast(result.message || `已切换到: ${dbName}`, 'success');
            loadStats();
        } else {
            showToast(result.error || '切换失败', 'error');
        }
    } catch (e) {
        showToast('切换失败', 'error');
    }
}

async function createAndSwitchDB() {
    const input = document.getElementById('newDbName');
    const dbName = input.value.trim();
    if (!dbName) { showToast('请输入数据库名', 'warning'); return; }
    if (!dbName.endsWith('.db')) { showToast('数据库名必须以 .db 结尾', 'warning'); return; }
    await switchKnowledgeDB(dbName);
    input.value = '';
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

async function loadAllReviews() {
    try {
        const items = await apiService.getAllReviews();
        if (items.length === 0) {
            document.getElementById('reviewContent').innerHTML =
                '<div class="empty-state"><p>知识库中暂无条目，请先添加知识</p></div>';
            return;
        }
        state.reviewSortMode = 'default';
        document.getElementById('btnSortDefault').className = 'btn btn-outline btn-sm active';
        document.getElementById('btnSortAI').className = 'btn btn-outline btn-sm';
        renderReviews(items);
    } catch (e) {}
}

async function confirmDelete(id) {
    if (!confirm('确定要删除这个知识条目吗？此操作不可撤销。')) return;
    try {
        await apiService.deleteItem(id);
        showToast('条目已删除', 'success');
        closeModal();
        loadStats();
        // 刷新列表和知识图谱
        if (state.currentPanel === 'knowledge') searchItems();
        if (window.knowledgeGraphNetwork) loadKnowledgeGraph();
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
            <div class="item-card" style="margin-bottom:6px;display:flex;align-items:center;justify-content:space-between;">
                <div style="flex:1;cursor:pointer;" onclick="showItemDetail(${item.id})">
                    <div class="item-card-title">${escapeHtml(item.title)}</div>
                    <div class="item-card-meta">📂 ${escapeHtml(item.category || '')}</div>
                </div>
                <button class="btn btn-sm" style="color:#e74c3c;font-size:11px;padding:2px 8px;flex-shrink:0;"
                        onclick="event.stopPropagation();removeRelationship(${item._rel_source}, ${item._rel_target})"
                        title="解除关联">✕ 解除</button>
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
// 9. Knowledge Graph Operations (vis.js)
// ================================================================

async function loadKnowledgeGraph() {
    const filter = document.getElementById('graphCategoryFilter');
    const category = filter?.value || '';
    try {
        const data = await apiService.getGraph(category);
        renderKnowledgeGraph(data);
    } catch (e) {
        console.error('加载知识图谱失败:', e);
    }
}

function resetGraphLayout() {
    const network = window.knowledgeGraphNetwork;
    if (network) {
        network.stabilize();
        setTimeout(() => network.fit(), 1000);
    }
}

function focusOnImportantNodes() {
    const network = window.knowledgeGraphNetwork;
    if (!network) return;
    const nodes = network.body.data.nodes.get();
    nodes.forEach(node => {
        const n = data.nodes.find(n => n.id === node.id);
        // vis.js doesn't support per-node physics toggling like D3 fx/fy,
        // so we just select/fit to important nodes
    });
    const importantIds = nodes.filter(n => (n.value || 0) >= 4).map(n => n.id);
    if (importantIds.length > 0) {
        network.selectNodes(importantIds);
        network.fit({ nodes: importantIds, animation: true });
    } else {
        showToast('没有重要性 >= 4 的节点', 'warning');
    }
    setTimeout(() => network.unselectAll(), 1500);
}

async function filterGraphByCategory() {
    loadKnowledgeGraph();
}

// ================================================================
// 10. AI Model Selector
// ================================================================
async function loadAIStatus() {
    try {
        const resp = await apiService.aiStatus();
        if (resp.data) {
            state.aiConfig = resp.data;
            document.getElementById('chatInput').placeholder = 'AI 就绪 — 输入问题...';
        }
    } catch (e) {}
    renderAllModelSelectors();
}

function getAIOptions(capability) {
    // Return {provider, model} from selector, or defaults
    const sel = state.aiModel[capability];
    if (sel && sel.provider) return sel;
    if (state.aiConfig && state.aiConfig.defaults && state.aiConfig.defaults[capability]) {
        return state.aiConfig.defaults[capability];
    }
    return {};
}

function buildModelSelector(containerId, capability) {
    const container = document.getElementById(containerId);
    if (!container) return;
    // Don't rebuild if already populated
    if (container.querySelector('select')) return;
    if (!state.aiConfig || !state.aiConfig.providers) return;

    const defaults = (state.aiConfig.defaults && state.aiConfig.defaults[capability]) || {};
    const defaultProvider = defaults.provider || '';
    const defaultModel = defaults.model || '';

    const sel = document.createElement('select');
    sel.className = 'form-select ai-model-select';
    sel.style.cssText = 'font-size:11px;padding:2px 6px;width:auto;max-width:200px;';
    sel.title = '选择 AI 模型';

    state.aiConfig.providers.forEach(prov => {
        if (!prov.available) return;
        if (prov.models && prov.models.length > 0) {
            const optgroup = document.createElement('optgroup');
            optgroup.label = prov.name;
            prov.models.forEach(m => {
                const opt = document.createElement('option');
                opt.value = `${prov.name}::${m}`;
                opt.textContent = `${prov.name}/${m}`;
                if (prov.name === defaultProvider && m === defaultModel) {
                    opt.selected = true;
                    state.aiModel[capability] = { provider: prov.name, model: m };
                }
                optgroup.appendChild(opt);
            });
            sel.appendChild(optgroup);
        }
    });

    sel.addEventListener('change', () => {
        const [provider, model] = sel.value.split('::');
        state.aiModel[capability] = { provider, model };
    });

    container.appendChild(sel);
}

function renderAllModelSelectors() {
    buildModelSelector('extractModelSelector', 'extract');
    buildModelSelector('chatModelSelector', 'chat');
    buildModelSelector('graphModelSelector', 'discover_relationships');
    buildModelSelector('gapModelSelector', 'discover_gaps');
    buildModelSelector('learningModelSelector', 'generate_learning_path');
    buildModelSelector('reviewModelSelector', 'optimize_review_plan');
}

// Detail modal selectors (built on-demand in showItemDetail)
function buildDetailModelSelectors() {
    buildModelSelector('detailAnalyzeSelector', 'analyze');
    buildModelSelector('detailQuestionsSelector', 'generate_questions');
    buildModelSelector('detailImproveSelector', 'improve_writing');
    buildModelSelector('detailChatSelector', 'chat');
    buildModelSelector('detailSuggestRelSelector', 'suggest_related');
}

// ================================================================
// 11. AI Chat
// ================================================================
async function sendChatMessage() {
    const input = document.getElementById('chatInput');
    const question = input.value.trim();
    if (!question && state.attachments.length === 0) return;
    input.value = '';

    const attachments = [...state.attachments];
    state.attachments = [];
    renderChatAttachments();

    const messages = document.getElementById('chatMessages');
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
            result = await apiService.ragChat(question, state.chatHistory, opts.provider, opts.model, attachments);
        } else {
            result = await apiService.aiChat({
                question,
                item_id: state.currentItemId,
                chat_history: state.chatHistory,
                provider: opts.provider,
                model: opts.model,
                attachments: attachments,
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

function clearChatHistory() {
    state.chatHistory = [];
    state.attachments = [];
    renderChatAttachments();
    document.getElementById('chatMessages').innerHTML = `
        <div class="chat-message assistant">聊天历史已清空。有什么我可以帮你的？</div>
    `;
}

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

// ── Per-item AI chat ──

async function sendItemChatMessage(itemId) {
    const input = document.getElementById('itemChatInput');
    const question = input.value.trim();
    if (!question) return;
    input.value = '';

    const messages = document.getElementById('itemChatMessages');
    const history = state._itemChatHistory || [];
    history.push({ role: 'user', content: question });

    // Add user message
    const userMsg = document.createElement('div');
    userMsg.className = 'chat-message user';
    userMsg.textContent = question;
    messages.appendChild(userMsg);

    // Add loading placeholder
    const loadingMsg = document.createElement('div');
    loadingMsg.className = 'chat-message assistant';
    loadingMsg.textContent = '思考中...';
    loadingMsg.id = 'itemChatLoading';
    messages.appendChild(loadingMsg);
    messages.scrollTop = messages.scrollHeight;

    try {
        const opts = getAIOptions('chat');
        const resp = await api('/api/ai/chat', {
            method: 'POST',
            body: JSON.stringify({
                question, item_id: itemId,
                chat_history: history.slice(0, -1),
                provider: opts.provider, model: opts.model,
            }),
        });

        loadingMsg.remove();
        const answer = resp.answer || resp.error || '抱歉，无法处理该问题。';
        history.push({ role: 'assistant', content: answer });
        state._itemChatHistory = history;

        const assistantMsg = document.createElement('div');
        assistantMsg.className = 'chat-message assistant';
        assistantMsg.innerHTML = renderMarkdown(answer);
        messages.appendChild(assistantMsg);
    } catch (e) {
        loadingMsg.remove();
        const errMsg = document.createElement('div');
        errMsg.className = 'chat-message assistant';
        errMsg.textContent = 'AI 服务出错，请重试';
        messages.appendChild(errMsg);
    }
    messages.scrollTop = messages.scrollHeight;
}

function clearItemChat() {
    state._itemChatHistory = [];
    const messages = document.getElementById('itemChatMessages');
    if (messages) {
        messages.innerHTML = '<div class="chat-message assistant" style="font-size:12px;">对话已清空。你可以继续提问。</div>';
    }
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

// ── JSON 批量导入 ──

async function importFromJSON() {
    const fileInput = document.getElementById('jsonFileInput');
    const file = fileInput?.files[0];
    if (!file) { showToast('请选择 JSON 文件', 'warning'); return; }

    showUploadProgress('jsonImportProgress', true);
    try {
        // Read file client-side
        const text = await new Promise((resolve, reject) => {
            const reader = new FileReader();
            reader.onload = () => resolve(reader.result);
            reader.onerror = () => reject(new Error('读取文件失败'));
            reader.readAsText(file);
        });

        let items;
        try {
            items = JSON.parse(text);
        } catch (e) {
            showToast('JSON 格式解析失败', 'error');
            showUploadProgress('jsonImportProgress', false);
            return;
        }

        if (!Array.isArray(items)) {
            showToast('JSON 格式错误：应为数组', 'error');
            showUploadProgress('jsonImportProgress', false);
            return;
        }

        const result = await apiService.importJSONData(items);
        if (result.success) {
            showToast(`批量导入完成: 成功 ${result.imported} 条, 跳过 ${result.skipped} 条`, 'success');
            loadStats();
        } else {
            showToast(result.error || '导入失败', 'error');
        }
    } catch (e) {
        showToast('导入失败: ' + (e.message || '未知错误'), 'error');
    } finally {
        showUploadProgress('jsonImportProgress', false);
        fileInput.value = '';
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
        const result = await apiService.listExtractableFiles();
        const files = result.files || [];
        const select = document.getElementById('extractFileSelect');
        if (files.length === 0) {
            select.innerHTML = '<option value="">-- 暂无文件，请先上传 --<option>';
        } else {
            select.innerHTML = '<option value="">-- 选择文件 --</option>' +
                files.map(f => `<option value="${escapeHtml(f.name)}">${escapeHtml(f.name)} (${formatFileSize(f.size)})</option>`).join('');
        }
    } catch (e) {
        const select = document.getElementById('extractFileSelect');
        select.innerHTML = '<option value="">-- 加载失败，请刷新重试 --</option>';
    }
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + 'B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + 'KB';
    return (bytes / (1024 * 1024)).toFixed(1) + 'MB';
}

async function handleExtractFileUpload(input) {
    const file = input.files[0];
    if (!file) return;
    const formData = new FormData();
    formData.append('files', file);
    formData.append('file_type', 'files');
    try {
        const result = await fetch(API_BASE + '/api/upload', { method: 'POST', body: formData }).then(r => r.json());
        if (result.success && result.file_details && result.file_details.length > 0) {
            const uploadedName = result.file_details[0].original_name;
            showToast(`文件已上传: ${uploadedName}`, 'success');
            await loadFileList();
            const select = document.getElementById('extractFileSelect');
            if (select) select.value = uploadedName;
        } else {
            showToast('上传失败: ' + (result.error || '未知错误'), 'error');
        }
    } catch (e) {
        showToast('上传失败', 'error');
    }
    input.value = '';
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
        const opts = getAIOptions('extract');
        const result = await apiService.extractURL(url, opts.provider, opts.model);
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
        const opts = getAIOptions('extract');
        const result = await apiService.extractText(text, opts.provider, opts.model);
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
        const opts = getAIOptions('extract');
        const result = await apiService.extractFile(filename, opts.provider, opts.model);
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
        const gapContainer = document.getElementById('gapAnalysis');
        if (gapContainer) {
            gapContainer.style.display = '';
            gapContainer.innerHTML = `
                <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:12px;">
                    <span style="font-size:13px;color:var(--text-secondary);">分类: <strong>${escapeHtml(cat)}</strong> (${items.length} 条)</span>
                    <span style="display:flex;align-items:center;gap:8px;">
                        <span id="gapModelSelector" style="display:inline-block;"></span>
                        <button class="btn btn-outline btn-sm" onclick="discoverGaps('${escapeHtml(cat)}')" id="btnGapAnalysis">
                            🤖 AI 缺口分析
                        </button>
                    </span>
                </div>
                <div id="gapResults"></div>
            `;
            buildModelSelector('gapModelSelector', 'discover_gaps');
        }
        renderSearchResults(items);
        showExportToolbar();
    } catch (e) {}
}

async function showTagItems(tag) {
    try {
        const items = await apiService.getTagItems(tag);
        renderSearchResults(items);
        showExportToolbar();
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
        const opts = getAIOptions('optimize_review_plan');
        const plan = await apiService.optimizeReviewPlan(7, opts.provider, opts.model);
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

// ── 手动创建关联 ──

async function aiSuggestRelated(itemId) {
    const resultDiv = document.getElementById('aiSuggestResults');
    const btn = document.getElementById('btnAISuggestRel');
    resultDiv.innerHTML = '<div style="padding:8px;font-size:12px;color:var(--text-tertiary);">AI 正在分析知识库...</div>';
    if (btn) { btn.disabled = true; btn.textContent = '分析中...'; }
    try {
        const opts = getAIOptions('suggest_related');
        const resp = await apiService.suggestRelated(itemId, opts.provider, opts.model);
        const suggestions = resp.suggestions || [];
        if (suggestions.length === 0) {
            resultDiv.innerHTML = '<div style="padding:8px;font-size:12px;color:var(--text-tertiary);">未发现合适的关联建议</div>';
        } else {
            resultDiv.innerHTML = '<div style="font-size:12px;color:var(--text-secondary);margin-bottom:4px;font-weight:500;">AI 建议关联以下条目：</div>' +
                suggestions.map((s, i) => `
                    <div style="display:flex;align-items:center;justify-content:space-between;padding:6px 8px;background:var(--bg-secondary);border-radius:6px;margin-bottom:4px;gap:8px;">
                        <div style="flex:1;min-width:0;">
                            <div style="font-size:13px;font-weight:500;">ID:${s.id} — ${escapeHtml(s.type || 'related_to')} (强度:${s.strength || 3})</div>
                            <div style="font-size:11px;color:var(--text-tertiary);">${escapeHtml(s.reason || '')}</div>
                        </div>
                        <button class="btn btn-sm btn-success" style="flex-shrink:0;font-size:11px;"
                            onclick="quickAddRelationship(${itemId}, ${s.id}, '${s.type || 'related_to'}', ${s.strength || 3}, ${i})">✅ 采纳</button>
                    </div>`).join('');
        }
    } catch (e) {
        resultDiv.innerHTML = '<div style="padding:8px;font-size:12px;color:var(--danger);">AI 建议失败</div>';
    }
    if (btn) { btn.disabled = false; btn.textContent = '🤖 AI 建议关联'; }
}

async function quickAddRelationship(sourceId, targetId, relType, strength, resultIndex) {
    try {
        await apiService.createRelationship({
            source_id: sourceId, target_id: targetId,
            relationship_type: relType, strength: strength,
        });
        showToast('关联已添加', 'success');
        loadRelatedItems(sourceId);
        // Remove this suggestion from the list
        const container = document.getElementById('aiSuggestResults');
        const items = container.querySelectorAll('div[style]');
        // Refresh AI suggestions
        const remaining = container.querySelectorAll('button');
        if (remaining.length <= 1) {
            container.innerHTML = '<div style="padding:8px;font-size:12px;color:var(--success);">所有建议已采纳</div>';
        }
        if (window.knowledgeGraphNetwork) loadKnowledgeGraph();
    } catch (e) { showToast('添加失败', 'error'); }
}

function showAddRelationship() {
    document.getElementById('addRelationshipForm').style.display = 'block';
    document.getElementById('relSearchInput').value = '';
    document.getElementById('relSearchResults').innerHTML = '';
    document.getElementById('relSearchInput').focus();
}

function cancelAddRelationship() {
    document.getElementById('addRelationshipForm').style.display = 'none';
}

let _relSearchTimer = null;
async function searchRelTarget(query) {
    clearTimeout(_relSearchTimer);
    _relSearchTimer = setTimeout(async () => {
        const container = document.getElementById('relSearchResults');
        if (!query) { container.innerHTML = ''; return; }
        try {
            const result = await apiService.searchItems(query);
            if (result.success && result.items.length > 0) {
                const currentId = state.currentItemId;
                container.innerHTML = result.items
                    .filter(item => item.id !== currentId)
                    .map(item => `
                        <div onclick="selectRelTarget(${item.id}, '${escapeHtml(item.title.replace(/'/g, "\\'"))}')"
                             style="padding:6px 8px;cursor:pointer;border-bottom:1px solid var(--border-light);font-size:13px;">
                            <span style="font-weight:500;">${escapeHtml(item.title)}</span>
                            <span style="color:var(--text-tertiary);margin-left:8px;font-size:11px;">${escapeHtml(item.category || '')}</span>
                        </div>`).join('');
            } else {
                container.innerHTML = '<p style="padding:8px;color:var(--text-tertiary);font-size:12px;">无匹配条目</p>';
            }
        } catch (e) { container.innerHTML = ''; }
    }, 300);
}

function selectRelTarget(id, title) {
    document.getElementById('relSearchInput').value = title;
    document.getElementById('relSearchInput').dataset.targetId = id;
    document.getElementById('relSearchResults').innerHTML = '';
}

async function confirmAddRelationship() {
    const targetId = parseInt(document.getElementById('relSearchInput').dataset.targetId);
    if (!targetId) { showToast('请先搜索并选择目标条目', 'warning'); return; }
    const sourceId = state.currentItemId;
    const relType = document.getElementById('relType').value;
    const strength = parseInt(document.getElementById('relStrength').value);
    try {
        const result = await apiService.createRelationship({
            source_id: sourceId, target_id: targetId,
            relationship_type: relType, strength: strength,
        });
        if (result.success) {
            showToast('关联已创建', 'success');
            cancelAddRelationship();
            loadRelatedItems(sourceId);
            if (window.knowledgeGraphNetwork) loadKnowledgeGraph();
        } else {
            showToast(result.error || '创建失败', 'error');
        }
    } catch (e) { showToast('创建失败', 'error'); }
}

async function removeRelationship(sourceId, targetId) {
    if (!confirm('确定要解除此关联吗？')) return;
    try {
        const result = await apiService.deleteRelationship({
            source_id: sourceId, target_id: targetId,
        });
        if (result.success) {
            showToast('关联已解除', 'success');
            loadRelatedItems(state.currentItemId);
            if (window.knowledgeGraphNetwork) loadKnowledgeGraph();
        } else {
            showToast(result.error || '解除失败', 'error');
        }
    } catch (e) { showToast('解除失败', 'error'); }
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
        const opts = getAIOptions('discover_relationships');
        const result = await apiService.discoverRelationships({
            scope: filterVal && filterVal.value ? 'category' : 'all',
            category: filterVal ? filterVal.value : '',
            limit: 30,
            provider: opts.provider,
            model: opts.model,
        });

        if (result.suggestions && result.suggestions.length > 0) {
            state.suggestionEdges = result.suggestions;
            document.getElementById('suggestionCount').textContent = result.suggestions.length;
            document.getElementById('graphSuggestionControls').style.display = '';
            renderSuggestedEdges(result.suggestions);
        } else {
            showToast('未发现新的关联建议', 'success');
            state.suggestionEdges = [];
        }
    } catch (e) {
        // Error handled by api()
    }
    btn.disabled = false;
    btn.textContent = '🤖 AI 发现关联';
}

function renderSuggestedEdges(suggestions) {
    const network = window.knowledgeGraphNetwork;
    if (!network) {
        setTimeout(() => renderSuggestedEdges(suggestions), 500);
        return;
    }

    // Remove previous suggested edges
    const existingEdges = network.body.data.edges.get();
    existingEdges.forEach(edge => {
        if (edge.id && String(edge.id).startsWith('sug_')) {
            network.body.data.edges.remove(edge.id);
        }
    });

    // Add suggested edges as dashed
    suggestions.forEach((sug, idx) => {
        try {
            network.body.data.edges.add({
                id: 'sug_' + idx,
                from: sug.source_id,
                to: sug.target_id,
                arrows: 'to',
                dashes: true,
                color: { color: '#f39c12', highlight: '#f1c40f' },
                width: 1.5,
                title: `${sug.type || 'related_to'}: ${sug.reason || ''} (强度: ${sug.strength || 3}/5)`,
            });
        } catch (e) {}
    });

    // Click handler for suggested edges (one-time setup)
    if (!network._sugClickBound) {
        network._sugClickBound = true;
        network.on('click', function(params) {
            if (params.edges.length > 0) {
                const edgeId = params.edges[0];
                if (String(edgeId).startsWith('sug_')) {
                    const idx = parseInt(String(edgeId).replace('sug_', ''));
                    adoptSuggestion(idx);
                }
            }
        });
    }
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
        } else {
            renderSuggestedEdges(state.suggestionEdges);
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
    // Remove suggested edges from vis.js
    const network = window.knowledgeGraphNetwork;
    if (network) {
        const existingEdges = network.body.data.edges.get();
        existingEdges.forEach(edge => {
            if (edge.id && String(edge.id).startsWith('sug_')) {
                network.body.data.edges.remove(edge.id);
            }
        });
    }
}

// ================================================================
// 15. AI Gap Analysis (Knowledge Management)
// ================================================================

async function discoverGaps(category) {
    const btn = document.getElementById('btnGapAnalysis');
    if (btn) {
        btn.disabled = true;
        btn.textContent = '分析中...';
    }

    try {
        const opts = getAIOptions('discover_gaps');
        const result = await apiService.discoverGaps(category, opts.provider, opts.model);
        renderGapResults(result, category);
    } catch (e) {}
    if (btn) {
        btn.disabled = false;
        btn.textContent = '🤖 AI 缺口分析';
    }
}

function renderGapResults(result, category) {
    const container = document.getElementById('gapResults');
    if (!container) return;
    if (!result.gaps || result.gaps.length === 0) {
        container.innerHTML = '<div style="padding:10px;font-size:13px;color:var(--text-secondary);">未发现明显知识缺口，该分类覆盖较完整。</div>';
        return;
    }
    let gapIndex = 0;
    container.innerHTML = result.gaps.map(gap => {
        const idx = gapIndex++;
        const stars = Array.from({length: 5}, (_, i) => {
            return `<span class="star${i < (gap.importance || 3) ? ' filled' : ''}">★</span>`;
        }).join('');
        const keywords = (gap.suggested_keywords || []).map(k =>
            `<span class="kw-tag">${escapeHtml(k)}</span>`
        ).join('');
        return `
        <div class="gap-card" id="gapCard${idx}">
            <div class="gap-card-body">
                <div class="gap-card-topic">
                    ${escapeHtml(gap.topic)}
                    <span class="gap-importance">${stars}</span>
                </div>
                <div class="gap-card-reason">${escapeHtml(gap.reason || '')}</div>
                ${keywords ? `<div class="gap-card-keywords">${keywords}</div>` : ''}
            </div>
            <div class="gap-card-action">
                <button class="btn btn-primary btn-sm" onclick="addFromGap('${escapeHtml(gap.topic).replace(/'/g, "&#39;")}', '${escapeHtml(category).replace(/'/g, "&#39;")}')">添加</button>
                <button class="btn btn-outline btn-sm" onclick="dismissGapCard(${idx})">忽略</button>
            </div>
        </div>`;
    }).join('');
}

function dismissGapCard(idx) {
    const card = document.getElementById('gapCard' + idx);
    if (card) {
        card.style.opacity = '0';
        card.style.transform = 'translateX(20px)';
        card.style.transition = 'all 0.3s ease';
        setTimeout(() => card.remove(), 300);
    }
}

function addFromGap(topic, category) {
    const details = document.getElementById('aiExtractDetails');
    if (details) details.open = true;
    if (typeof switchExtractTab === 'function') switchExtractTab('text');
    const textarea = document.getElementById('extractText');
    if (textarea) {
        textarea.value = `主题: ${topic}\n分类: ${category}\n\n`;
        textarea.focus();
    }
    const extractSection = document.getElementById('aiExtractDetails');
    if (extractSection) extractSection.scrollIntoView({ behavior: 'smooth' });
    if (typeof switchPanel === 'function') switchPanel('knowledge');
}

// ================================================================
// 16. AI Learning Path Generation (Review Panel)
// ================================================================

const LEARNING_PATHS_KEY = 'saved_learning_paths';

function getSavedPaths() {
    try {
        return JSON.parse(localStorage.getItem(LEARNING_PATHS_KEY) || '[]');
    } catch (e) { return []; }
}

function savePathsToStorage(paths) {
    localStorage.setItem(LEARNING_PATHS_KEY, JSON.stringify(paths));
}

async function generateLearningPath() {
    const goal = document.getElementById('learningGoal').value.trim();
    if (!goal) { showToast('请输入学习目标', 'warning'); return; }

    const container = document.getElementById('learningPathContent');
    container.innerHTML = '<div class="loading"><div class="spinner"></div>AI 正在设计学习路径...</div>';

    try {
        const opts = getAIOptions('generate_learning_path');
        const result = await apiService.generateLearningPath(goal, null, opts.provider, opts.model);
        state._lastLearningPath = result;
        renderLearningPath(result);
    } catch (e) {
        container.innerHTML = '<div class="empty-state"><p>生成失败，请重试</p></div>';
    }
}

function renderLearningPath(result) {
    const container = document.getElementById('learningPathContent');
    if (!result.stages || result.stages.length === 0) {
        container.innerHTML = '<div class="empty-state"><p>无法生成学习路径，请尝试更具体的目标</p></div>';
        return;
    }

    let html = `<div style="margin-bottom:12px;font-size:13px;color:var(--text-secondary);display:flex;align-items:center;justify-content:space-between;flex-wrap:wrap;gap:8px;">
        <span>学习目标: <strong>${escapeHtml(result.goal)}</strong> | 预计总时长: <strong>${result.total_estimated_hours || 'N/A'} 小时</strong>
        ${result.provider ? ' | via ' + escapeHtml(result.provider) + '/' + escapeHtml(result.model || '') : ''}</span>
        <span style="display:flex;gap:4px;">
            <button class="btn btn-sm btn-primary" onclick="saveLearningPath()">💾 保存路径</button>
            <button class="btn btn-sm btn-outline" onclick="exportLearningPath()">📥 导出JSON</button>
        </span>
    </div>`;

    html += '<div class="learning-timeline">';
    result.stages.forEach(stage => {
        const concepts = (stage.concepts || []).map(c =>
            `<span class="timeline-concept">${escapeHtml(c)}</span>`
        ).join('');
        const prereqs = (stage.prerequisites && stage.prerequisites.length > 0)
            ? `<div class="timeline-prereqs">前置: ${escapeHtml(stage.prerequisites.join(' → '))}</div>` : '';
        const items = (stage.item_ids || []).map(id =>
            `<span class="timeline-item-link" onclick="showItemDetail(${id})">📄 #${id}</span>`
        ).join('');
        const resources = (stage.resources || []).map(r =>
            `<span style="display:inline-block;margin:2px;padding:2px 6px;background:var(--bg-secondary);border-radius:3px;font-size:11px;">📚 ${escapeHtml(r)}</span>`
        ).join('');

        html += `
        <div class="timeline-stage" data-order="${stage.order || '?'}">
            <div class="timeline-stage-header">
                <span class="timeline-stage-title">${escapeHtml(stage.title || '')}</span>
                <span class="timeline-stage-hours">${stage.estimated_hours || '?'}h</span>
            </div>
            ${prereqs}
            <div class="timeline-concepts">${concepts}</div>
            ${resources ? `<div style="margin-top:4px;">${resources}</div>` : ''}
            ${items ? `<div class="timeline-items">${items}</div>` : ''}
            ${stage.mastery_criteria ? `<div style="font-size:12px;color:var(--text-tertiary);margin-top:8px;">✅ ${escapeHtml(stage.mastery_criteria)}</div>` : ''}
        </div>`;
    });
    html += '</div>';

    if (result.missing_topics && result.missing_topics.length > 0) {
        html += `<div class="timeline-missing-topics">
            <h5>📌 建议补充学习的内容</h5>
            ${result.missing_topics.map(t => `<span class="timeline-item-link missing">${escapeHtml(t)}</span>`).join(' ')}
        </div>`;
    }

    container.innerHTML = html;
    renderSavedPathsList();
}

function saveLearningPath() {
    const result = state._lastLearningPath;
    if (!result || !result.stages) return;
    const paths = getSavedPaths();
    const entry = {
        id: Date.now(),
        goal: result.goal,
        stages: result.stages,
        missing_topics: result.missing_topics || [],
        total_estimated_hours: result.total_estimated_hours || 0,
        saved_at: new Date().toISOString(),
    };
    paths.unshift(entry);
    savePathsToStorage(paths);
    showToast('学习路径已保存', 'success');
    renderSavedPathsList();
}

function deleteSavedPath(id) {
    if (!confirm('确定要删除此学习路径吗？')) return;
    let paths = getSavedPaths();
    paths = paths.filter(p => p.id !== id);
    savePathsToStorage(paths);
    showToast('已删除', 'success');
    renderSavedPathsList();
}

function loadSavedPath(id) {
    const paths = getSavedPaths();
    const entry = paths.find(p => p.id === id);
    if (!entry) return;
    state._lastLearningPath = {
        goal: entry.goal,
        stages: entry.stages,
        missing_topics: entry.missing_topics || [],
        total_estimated_hours: entry.total_estimated_hours || 0,
    };
    renderLearningPath(state._lastLearningPath);
    showToast('已加载学习路径', 'success');
}

function exportLearningPath() {
    const result = state._lastLearningPath;
    if (!result) return;
    const data = {
        goal: result.goal,
        stages: result.stages,
        missing_topics: result.missing_topics || [],
        total_estimated_hours: result.total_estimated_hours || 0,
        exported_at: new Date().toISOString(),
    };
    const blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = `learning_path_${Date.now()}.json`;
    a.click();
    URL.revokeObjectURL(url);
}

function importLearningPath() {
    const input = document.createElement('input');
    input.type = 'file';
    input.accept = '.json';
    input.onchange = async (e) => {
        const file = e.target.files[0];
        if (!file) return;
        try {
            const text = await new Promise((resolve, reject) => {
                const reader = new FileReader();
                reader.onload = () => resolve(reader.result);
                reader.onerror = reject;
                reader.readAsText(file);
            });
            const data = JSON.parse(text);
            if (!data.stages || !data.goal) {
                showToast('JSON 格式错误：缺少 goal 或 stages 字段', 'error');
                return;
            }
            state._lastLearningPath = data;
            renderLearningPath(data);
            showToast('学习路径已导入', 'success');
        } catch (e) {
            showToast('导入失败: JSON 解析错误', 'error');
        }
    };
    input.click();
}

function renderSavedPathsList() {
    const container = document.getElementById('learningPathContent');
    const paths = getSavedPaths();
    if (paths.length === 0) return;

    // Append saved paths list after current content
    const existing = document.getElementById('savedPathsSection');
    if (existing) existing.remove();

    const section = document.createElement('div');
    section.id = 'savedPathsSection';
    section.style.marginTop = '24px';
    section.innerHTML = `
        <div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px;">
            <h4 style="margin:0;">已保存的学习路径 (${paths.length})</h4>
            <button class="btn btn-sm btn-outline" onclick="importLearningPath()">📥 导入路径</button>
        </div>
        ${paths.map(p => `
            <div style="display:flex;align-items:center;justify-content:space-between;padding:8px 12px;margin-bottom:4px;background:var(--bg-tertiary);border-radius:6px;">
                <div style="flex:1;cursor:pointer;" onclick="loadSavedPath(${p.id})">
                    <div style="font-weight:500;font-size:13px;">${escapeHtml(p.goal)}</div>
                    <div style="font-size:11px;color:var(--text-tertiary);">
                        ${p.stages.length} 阶段 | ${p.total_estimated_hours || '?'}h | 保存于 ${formatDate(p.saved_at)}
                    </div>
                </div>
                <button class="btn btn-sm" style="color:#e74c3c;" onclick="deleteSavedPath(${p.id})">🗑</button>
            </div>
        `).join('')}
    `;
    container.appendChild(section);
}

// ================================================================
// 17. Initialization
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
