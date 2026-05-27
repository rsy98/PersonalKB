#!/usr/bin/env python3
# web_interface.py - 支持LaTeX数学公式和高级功能的Web界面（完整修复版）

from flask import Flask, request, jsonify, redirect, render_template, url_for
from flask import send_from_directory
from knowledge_manager import KnowledgeManager
from setup import KnowledgeDatabase
import os
import re
import urllib.parse
import uuid
from werkzeug.utils import secure_filename
import chardet
import tempfile
from ai import AIService, load_config
ai_config = load_config('config/ai.yaml')
ai_service = AIService(ai_config)

# 全局变量存储当前数据库
_current_db = os.environ.get('CURRENT_DATABASE', 'knowledge.db')
# _current_db = 'work_knowledge.db'

# 禁用Flask开发服务器的警告
import warnings
warnings.filterwarnings("ignore", message="This is a development server.")

# 允许上传的文件类型
ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'bmp', 'webp'}
ALLOWED_FILE_EXTENSIONS = {'pdf', 'doc', 'docx', 'txt', 'zip', 'rar', 'xls', 'xlsx', 'ppt', 'pptx','vim','py','yaml','tex','md','sty','bib','def'}


# 允许的文本文件扩展名
ALLOWED_TEXT_EXTENSIONS = {
    'md', 'txt', 'tex', 'rst', 'vim','csv',
    'py', 'js', 'java', 'cpp', 'c', 'html', 'css',  # 代码文件
    'json', 'yaml', 'yml', 'xml',  # 配置文件
}


def allowed_file(filename, file_type):
    """检查文件类型是否允许"""
    if '.' not in filename:
        return False

    ext = filename.rsplit('.', 1)[1].lower()
    if file_type == 'images':
        return ext in ALLOWED_IMAGE_EXTENSIONS
    elif file_type == 'files':
        return ext in ALLOWED_FILE_EXTENSIONS
    return False

def secure_filename_with_chinese(filename):
    """
    安全地处理文件名，同时保留中文字符。
    移除了操作系统路径分隔符等危险字符，但保留了中文、字母、数字、下划线、连字符和点。
    """
    if not filename:
        return "file"

    # 定义一个更安全的模式，主要移除路径分隔符和其他可能引起问题的字符
    # 允许：中文字符 (\u4e00-\u9fa5)、字母、数字、下划线、连字符、点
    dangerous_chars = r'[\/\\:*?"<>|\x00]'  # 移除这些危险字符
    safe_name = re.sub(dangerous_chars, '_', filename)

    # 确保文件名不以点或空格开头（在某些系统上可能有问题）
    safe_name = safe_name.lstrip('. ')

    return safe_name if safe_name else "file"

app = Flask(__name__)
app.config['ENV'] = 'production'  # 设置为生产环境

def preprocess_latex(content):
    """预处理LaTeX公式，将所有公式统一转换为$和$$格式"""
    if not content:
        return content

    import re

    # 将 \[ ... \] 格式转换为 $$ ... $$
    content = re.sub(r'\\\\\[(.*?)\\\\\]', r'$$\1$$', content, flags=re.DOTALL)
    content = re.sub(r'\\\[(.*?)\\\]', r'$$\1$$', content, flags=re.DOTALL)

    # 将 \( ... \) 格式转换为 $ ... $
    content = re.sub(r'\\\\\((.*?)\\\\\)', r'$\1$', content, flags=re.DOTALL)
    content = re.sub(r'\\\((.*?)\\\)', r'$\1$', content, flags=re.DOTALL)

    # 处理多行公式：确保 $$ 分隔符在同一行
    content = re.sub(r'\n\s*\$\$', r'$$', content)
    content = re.sub(r'\$\$\s*\n', r'$$', content)

    return content

@app.route('/')
def index():
    """主页 - 返回支持LaTeX和高级功能的HTML界面"""
    html = r"""
    <!DOCTYPE html>
    <html>
    <head>
        <script>
        // 平衡的解决方案：保留标准快捷键同时支持功能快捷键
        (function() {
            // 保存原始的事件处理函数
            const originalAddEventListener = EventTarget.prototype.addEventListener;

            // 用于存储我们自己的事件监听器，以便可以移除它们
            const myEventListeners = new WeakMap();

            // 重写addEventListener，以便我们可以控制键盘事件
            EventTarget.prototype.addEventListener = function(type, listener, options) {
                // 如果是键盘事件，我们进行特殊处理
                if (type === 'keydown' || type === 'keyup' || type === 'keypress') {
                    // 存储原始监听器
                    if (!myEventListeners.has(this)) {
                        myEventListeners.set(this, []);
                    }
                    myEventListeners.get(this).push({type, listener, options});

                    // 不立即添加，等待我们的统一处理
                    return;
                }

                // 非键盘事件正常添加
                return originalAddEventListener.call(this, type, listener, options);
            };

            // 页面加载完成后设置我们自己的键盘事件处理
            window.addEventListener('DOMContentLoaded', function() {
                // 恢复原始的addEventListener
                EventTarget.prototype.addEventListener = originalAddEventListener;

                // 添加我们自己的键盘事件处理
                document.addEventListener('keydown', function(e) {
                    const activeElement = document.activeElement;
                    const isTextInput = activeElement && (
                        activeElement.tagName === 'INPUT' ||
                        activeElement.tagName === 'TEXTAREA'
                    );

                    // 如果在文本输入框中
                    if (isTextInput) {
                        // 允许所有标准编辑快捷键正常工作
                        if (e.ctrlKey || e.metaKey) {
                            switch(e.key.toLowerCase()) {
                                case 'c': // 复制
                                case 'v': // 粘贴
                                case 'x': // 剪切
                                case 'a': // 全选
                                case 'z': // 撤销
                                case 'y': // 重做
                                    // 完全不处理，让浏览器执行默认行为
                                    return;
                                case 'enter':
                                    // 只在特定的文本区域处理 Ctrl+Enter
                                    if (activeElement.id === 'newContent' || activeElement.id === 'editContent') {
                                        e.preventDefault();
                                        addNewItem();
                                    }
                                    // 其他情况让浏览器处理
                                    return;
                            }
                        }

                        // 文本输入区域的特殊处理：回车键搜索
                        if (e.key === 'Enter' && activeElement.id === 'searchInput') {
                            e.preventDefault();
                            searchItems();
                            return;
                        }

                        // 其他文本输入区域的按键不处理，让浏览器处理
                        return;
                    }

                    // 非文本输入区域的全局快捷键（原有功能）
                    if (e.ctrlKey || e.metaKey) {
                        e.preventDefault(); // 只在全局快捷键时阻止默认行为

                        switch(e.key.toLowerCase()) {
                            case 'f':
                                searchItems();
                                break;
                            case 'a':
                                showAllItems();
                                break;
                            case 'r':
                                showTodayReviews();
                                break;
                            case 's':
                                const titleInput = document.getElementById('newTitle');
                                if (titleInput) {
                                    titleInput.focus();
                                }
                                break;
                            case 'g':
                                switchTab('graph');
                                break;
                            case 'i':
                                const importInput = document.getElementById('importFile');
                                if (importInput) importInput.click();
                                break;
                            case 'enter':
                                // 全局的 Ctrl+Enter 添加新项目
                                addNewItem();
                                break;
                            case 'c': // Ctrl+C 显示分类
                                showCategories();
                                break;
                            case 'o': // Ctrl+o 显示标签
                                showTags();
                                break;
                        }
                    }
                    // 功能键
                    else if (e.key === 'F1') {
                        e.preventDefault();
                        showShortcutHelp();
                    }
                    // Escape 键
                    else if (e.key === 'Escape') {
                        closeDetailModal();
                        closeEditModal();
                    }
                });

                // 现在添加之前被我们拦截的键盘事件监听器
                // 但只添加非冲突的监听器
                document.querySelectorAll('*').forEach(element => {
                    if (myEventListeners.has(element)) {
                        const listeners = myEventListeners.get(element);
                        listeners.forEach(({type, listener, options}) => {
                            // 只添加非键盘事件或非冲突的键盘事件
                            if (type !== 'keydown' && type !== 'keyup' && type !== 'keypress') {
                                element.addEventListener(type, listener, options);
                            }
                        });
                    }
                });

                // 清理
                myEventListeners.delete(document);
            });
        })();
        </script>

        <title>个人知识管理系统 - 高级版</title>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">

        <!-- KaTeX CSS -->
        <link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.css" integrity="sha384-n8MVd4RsNIU0tAv4ct0nTaAbDJwPJzDEaqSD1odI+WdtXRGWt2kTvGFasHpSy3SV" crossorigin="anonymous">

        <!-- Marked.js - Markdown 解析 -->
        <script src="https://cdn.jsdelivr.net/npm/marked/marked.min.js"></script>

        <!-- Vis.js 用于知识图谱 -->
        <script src="https://unpkg.com/vis-network@9.1.6/standalone/umd/vis-network.min.js"></script>
        <link rel="stylesheet" type="text/css" href="https://unpkg.com/vis-network@9.1.6/styles/vis-network.min.css" />


        <style type="text/css">
/* 知识图谱容器样式 */
#mynetwork {
    width: 100%;
    height: 600px;
    border: 2px solid #444;
    border-radius: 8px;
    background: var(--bg-primary);
}

/* 图谱控制按钮样式 */
.graph-container button {
    padding: 8px 16px;
    font-size: 12px;
}

/* 节点提示样式 */
.vis-tooltip {
    background: rgba(45, 45, 45, 0.95) !important;
    color: white !important;
    border: 1px solid #bb86fc !important;
    border-radius: 5px !important;
    padding: 8px 12px !important;
    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif !important;
}
</style>

        <!-- Chart.js 用于统计图表 -->
        <script src="https://cdn.jsdelivr.net/npm/chart.js"></script>

        <!-- KaTeX JS -->
        <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/katex.min.js" integrity="sha384-XjKyOOlGwcjNTAIQHIpgOno0Hl1YQqzUOEleOLALmuqehneUG+vnGctmUb0ZY0l8" crossorigin="anonymous"></script>

        <!-- KaTeX Auto-render -->
        <script defer src="https://cdn.jsdelivr.net/npm/katex@0.16.9/dist/contrib/auto-render.min.js" integrity="sha384-+VBxd3r6XgURycqtZ117nYw44OOcIax56Z4dCRWbxyPt0Koah1uHoK0o4+/RRE05" crossorigin="anonymous"></script>

        <style>
            :root {
                --bg-primary: #1a1a1a;
                --bg-secondary: #2d2d2d;
                --bg-tertiary: #3d3d3d;
                --text-primary: #ffffff;
                --text-secondary: #b0b0b0;
                --accent-primary: #bb86fc;
                --accent-secondary: #03dac6;
                --danger: #cf6679;
                --success: #03dac6;
                --warning: #ffb74d;
            }

            * {
                box-sizing: border-box;
            }

            body {
                font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                margin: 0;
                padding: 20px;
                background: var(--bg-primary);
                color: var(--text-primary);
                line-height: 1.6;
                min-height: 100vh;
            }

            .container {
                max-width: 1600px;
                margin: 0 auto;
                background: var(--bg-secondary);
                padding: 20px;
                border-radius: 15px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            }

            /* 响应式网格布局 */
            .dashboard-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(300px, 1fr));
                gap: 20px;
                margin: 20px 0;
            }

            .header {
                text-align: center;
                margin-bottom: 30px;
                border-bottom: 2px solid var(--bg-tertiary);
                padding-bottom: 20px;
            }

            .search-box {
                margin: 20px 0;
                padding: 25px;
                background: var(--bg-tertiary);
                border-radius: 10px;
                border: 1px solid #444;
            }

            .advanced-search-panel {
                background: var(--bg-primary);
                padding: 20px;
                border-radius: 10px;
                margin: 15px 0;
                border: 1px solid #444;
                display: none;
            }

            .filter-grid {
                display: grid;
                grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
                gap: 15px;
                margin: 15px 0;
            }

            .item {
                border: 1px solid #444;
                padding: 20px;
                margin: 15px 0;
                border-radius: 10px;
                background: var(--bg-secondary);
                transition: all 0.3s ease;
            }

            .item:hover {
                border-color: var(--accent-primary);
                transform: translateY(-2px);
                box-shadow: 0 5px 15px rgba(0,0,0,0.4);
            }

            .stats {
                background: linear-gradient(135deg, var(--accent-primary), var(--accent-secondary));
                color: var(--bg-primary);
                padding: 20px;
                margin: 20px 0;
                border-radius: 10px;
                font-weight: bold;
            }

            .graph-container {
                background: var(--bg-tertiary);
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
            }

            .ai-panel {
                background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
                padding: 20px;
                border-radius: 10px;
                margin: 20px 0;
            }

            .tab-container {
                margin: 20px 0;
            }

            .tab-buttons {
                display: flex;
                flex-wrap: wrap;
                gap: 10px;
                margin-bottom: 15px;
            }

            .tab-button {
                padding: 10px 20px;
                background: var(--bg-tertiary);
                border: none;
                border-radius: 5px;
                color: var(--text-primary);
                cursor: pointer;
                transition: all 0.3s ease;
            }

            .tab-button.active {
                background: var(--accent-primary);
                color: var(--bg-primary);
            }

            .tab-content {
                display: none;
            }

            .tab-content.active {
                display: block;
            }

            input[type="text"], textarea, select {
                padding: 12px;
                border: 1px solid #555;
                border-radius: 6px;
                width: 100%;
                margin: 5px 0;
                font-family: inherit;
                background: var(--bg-tertiary);
                color: var(--text-primary);
            }

            textarea {
                min-height: 300px;
                resize: vertical;
            }

            button {
                padding: 12px 24px;
                background: var(--accent-primary);
                color: var(--bg-primary);
                border: none;
                border-radius: 6px;
                cursor: pointer;
                margin: 5px;
                font-size: 14px;
                font-weight: bold;
                transition: all 0.3s ease;
            }

            button:hover {
                background: var(--accent-secondary);
                transform: translateY(-2px);
            }

            .btn-danger {
                background: var(--danger);
            }

            .btn-danger:hover {
                background: #b00020;
            }

            .btn-success {
                background: var(--success);
                color: var(--bg-primary);
            }

            .btn-warning {
                background: var(--warning);
                color: var(--bg-primary);
            }

            .btn-small {
                padding: 8px 16px;
                font-size: 12px;
            }

            .item h4 {
                margin: 0 0 10px 0;
                color: var(--text-primary);
                font-size: 1.2em;
            }

            .item .content {
                color: var(--text-secondary);
                margin: 10px 0;
                font-size: 14px;
            }

            .item small {
                color: #888;
                font-size: 12px;
            }

            .success { color: var(--success); font-weight: bold; }
            .error { color: var(--danger); font-weight: bold; }
            .warning { color: var(--warning); font-weight: bold; }

            .tag {
                display: inline-block;
                background: var(--accent-primary);
                color: var(--bg-primary);
                padding: 4px 12px;
                margin: 2px;
                border-radius: 15px;
                font-size: 12px;
                font-weight: bold;
            }

            .tag-ai {
                background: #9b59b6;
            }

            .tag-important {
                background: var(--danger);
            }

            .drop-zone {
                border: 2px dashed var(--accent-primary);
                border-radius: 10px;
                padding: 20px;
                text-align: center;
                transition: all 0.3s ease;
                background: var(--bg-tertiary);
                margin: 10px 0;
            }

            .drop-zone.dragover {
                background: var(--accent-primary);
                color: var(--bg-primary);
            }

            .katex { font-size: 1.1em; }
            .katex-display { margin: 1em 0; }

            .analysis-panel {
                background: var(--bg-tertiary);
                padding: 15px;
                border-radius: 8px;
                margin: 10px 0;
                font-size: 14px;
            }

            .recommendation-item {
                border-left: 4px solid var(--accent-primary);
                padding-left: 15px;
                margin: 10px 0;
                background: var(--bg-secondary);
                padding: 10px;
                border-radius: 5px;
                cursor: pointer;
                transition: all 0.3s ease;
            }

            .recommendation-item:hover {
                background: var(--bg-tertiary);
                transform: translateX(5px);
            }

            .form-grid {
                display: grid;
                grid-template-columns: 5fr 1fr;
                gap: 20px;
                margin: 20px 0;
            }

            .button-container {
                width: 100%;
                clear: both;
                margin-top: 15px;
                text-align: center;
            }

            .import-container {
                border: 1px solid #444;
                padding: 20px;
                margin: 15px 0;
                border-radius: 10px;
                background: var(--bg-secondary);
            }

            /* 移动端优化 */
            @media (max-width: 767px) {
                body {
                    padding: 10px;
                }

                .container {
                    padding: 15px;
                }

                .header h1 {
                    font-size: 1.5em;
                }

                .search-box {
                    padding: 15px;
                }

                .filter-grid {
                    grid-template-columns: 1fr;
                }

                .form-grid {
                    grid-template-columns: 1fr;
                }

                button {
                    padding: 10px 15px;
                    font-size: 12px;
                    margin: 2px;
                }

                .tab-buttons {
                    flex-direction: column;
                }
            }

            .modal {
                display: none;
                position: fixed;
                z-index: 1000;
                left: 0;
                top: 0;
                width: 100%;
                height: 100%;
                background-color: rgba(0,0,0,0.9); /* 加深背景 */
            }

            .modal-content {
                background-color: var(--bg-secondary);
                margin: 0; /* 移除边距 */
                padding: 20px;
                border-radius: 0; /* 移除圆角 */
                width: 100%;
                height: 100%;
                overflow-y: auto;
                position: relative;
            }

            /* 全屏模态框的关闭按钮 */
            .modal .close {
                color: #fff;
                float: right;
                font-size: 36px;
                font-weight: bold;
                cursor: pointer;
                position: fixed;
                top: 20px;
                right: 30px;
                z-index: 1001;
                background: rgba(0,0,0,0.5);
                border-radius: 50%;
                width: 50px;
                height: 50px;
                display: flex;
                align-items: center;
                justify-content: center;
            }

            .modal .close:hover {
                color: var(--accent-primary);
                background: rgba(0,0,0,0.7);
            }



            /* 修改链接样式为更醒目的颜色 */
            a {
                color: #FFD700 !important; /* 亮黄色 */
                text-decoration: none;
                border-bottom: 2px solid #FFD700;
                padding: 2px 6px;
                border-radius: 4px;
                font-weight: bold;
                transition: all 0.3s ease;
            }

            a:hover {
                background-color: #FFD700 !important;
                color: #1a1a1a !important; /* 黑色背景上的黄色文字 */
                border-bottom-color: transparent;
                transform: translateY(-1px);
                box-shadow: 0 2px 8px rgba(255, 215, 0, 0.3);
            }

            /* 确保模态框中的链接也应用样式 */
            .modal-content a {
                color: #FFD700 !important;
                border-bottom: 2px solid #FFD700;
            }

            .modal-content a:hover {
                background-color: #FFD700 !important;
                color: #1a1a1a !important;
            }

            /* 添加上传进度条样式 */
            .upload-progress {
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: var(--bg-secondary);
                padding: 30px;
                border-radius: 10px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.5);
                z-index: 10000;
                text-align: center;
                border: 2px solid var(--accent-primary);
                min-width: 200px;
            }

            .upload-spinner {
                border: 3px solid #f3f3f3;
                border-top: 3px solid #3498db;
                border-radius: 50%;
                width: 40px;
                height: 40px;
                animation: spin 1s linear infinite;
                margin: 0 auto 15px;
            }

            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            /* AI相关样式 */
            .ai-message {
                background: rgba(52, 152, 219, 0.1);
                padding: 10px 15px;
                border-radius: 10px;
                margin: 10px 0;
                border-left: 3px solid #3498db;
            }

            .user-message {
                background: rgba(155, 89, 182, 0.1);
                padding: 10px 15px;
                border-radius: 10px;
                margin: 10px 0;
                border-left: 3px solid #9b59b6;
            }

            .ai-thinking {
                color: #7f8c8d;
                font-style: italic;
                padding: 10px 15px;
            }

            .error-message {
                background: rgba(231, 76, 60, 0.1);
                border: 1px solid #e74c3c;
                border-radius: 5px;
            }

            .success-message {
                background: rgba(39, 174, 96, 0.1);
                border: 1px solid #27ae60;
                border-radius: 5px;
            }

            /* 动画效果 */
            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            /* 文件导入样式 */
            .import-container {
                border: 1px solid #444;
                padding: 20px;
                margin: 15px 0;
                border-radius: 10px;
                background: var(--bg-secondary);
            }

            .import-container h3 {
                margin-top: 0;
                color: var(--accent-primary);
            }

            .import-container label {
                color: var(--text-secondary);
                font-size: 14px;
                cursor: pointer;
            }

            .import-container input[type="checkbox"] {
                margin-right: 5px;
            }

            .file-import-status {
                margin-top: 10px;
                padding: 10px;
                border-radius: 5px;
                font-size: 14px;
            }

            .file-import-status.success {
                background: rgba(39, 174, 96, 0.1);
                border: 1px solid #27ae60;
                color: #27ae60;
            }

            .file-import-status.error {
                background: rgba(231, 76, 60, 0.1);
                border: 1px solid #e74c3c;
                color: #e74c3c;
            }

            .file-import-status.info {
                background: rgba(52, 152, 219, 0.1);
                border: 1px solid #3498db;
                color: #3498db;
            }
            /* 增强选中状态的视觉效果 */
            .item-selected {
                border: 3px solid #3498db !important;
                background: rgba(52, 152, 219, 0.2) !important;
                box-shadow: 0 0 15px rgba(52, 152, 219, 0.7) !important;
                transform: scale(1.02) !important;
                transition: all 0.3s ease !important;
            }

            /* 添加选中指示器 */
            .item-selected::before {
                content: "✓ 已选中";
                position: absolute;
                top: 10px;
                right: 10px;
                background: #3498db;
                color: white;
                padding: 4px 8px;
                border-radius: 4px;
                font-size: 12px;
                font-weight: bold;
            }

            /* 思考过程样式 */
            .thinking-process {
                border-left: 3px solid #e74c3c;
                padding-left: 10px;
                margin: 10px 0;
            }

            .thinking-content {
                background: rgba(231, 76, 60, 0.05);
                padding: 10px;
                border-radius: 5px;
                border: 1px solid rgba(231, 76, 60, 0.2);
                color: #7f8c8d;
                font-style: italic;
            }

            .final-answer {
                background: rgba(52, 152, 219, 0.05);
                padding: 12px;
                border-radius: 5px;
                border: 1px solid rgba(52, 152, 219, 0.2);
                margin-top: 8px;
            }

            @keyframes spin {
                0% { transform: rotate(0deg); }
                100% { transform: rotate(360deg); }
            }

            /* 移动端适配 */
            @media (max-width: 768px) {
                .modal-content {
                    padding: 10px;
                }

                .modal .close {
                    top: 10px;
                    right: 15px;
                    width: 40px;
                    height: 40px;
                    font-size: 28px;
                }

                #detailSearchInput {
                    min-width: 200px;
                }

                .modal-content > div:first-child > div {
                    grid-template-columns: 1fr;
                    gap: 20px;
                }
            }

            /* Markdown 样式 */
            .markdown-content {
                line-height: 1.7;
                font-size: 15px;
            }

            .markdown-content h1,
            .markdown-content h2,
            .markdown-content h3,
            .markdown-content h4,
            .markdown-content h5,
            .markdown-content h6 {
                color: var(--accent-primary);
                margin: 1.5em 0 0.5em 0;
                border-bottom: 1px solid #444;
                padding-bottom: 0.3em;
            }

            .markdown-content h1 { font-size: 1.8em; }
            .markdown-content h2 { font-size: 1.6em; }
            .markdown-content h3 { font-size: 1.4em; }
            .markdown-content h4 { font-size: 1.2em; }
            .markdown-content h5 { font-size: 1.1em; }
            .markdown-content h6 { font-size: 1em; }

            .markdown-content p {
                margin: 1em 0;
            }

            .markdown-content blockquote {
                border-left: 4px solid var(--accent-primary);
                background: rgba(187, 134, 252, 0.1);
                margin: 1em 0;
                padding: 0.5em 1em;
                border-radius: 0 5px 5px 0;
            }

            .markdown-content code {
                background: rgba(255, 255, 255, 0.1);
                padding: 0.2em 0.4em;
                border-radius: 3px;
                font-family: 'Courier New', monospace;
                font-size: 0.9em;
            }

            .markdown-content pre {
                background: var(--bg-primary);
                border: 1px solid #444;
                border-radius: 5px;
                padding: 1em;
                overflow-x: auto;
                margin: 1em 0;
            }

            .markdown-content pre code {
                background: none;
                padding: 0;
            }

            .markdown-content ul,
            .markdown-content ol {
                margin: 1em 0;
                padding-left: 2em;
            }

            .markdown-content li {
                margin: 0.5em 0;
            }

            .markdown-content table {
                border-collapse: collapse;
                width: 100%;
                margin: 1em 0;
            }

            .markdown-content th,
            .markdown-content td {
                border: 1px solid #555;
                padding: 0.5em;
                text-align: left;
            }

            .markdown-content th {
                background: var(--bg-tertiary);
                font-weight: bold;
            }

            .markdown-content tr:nth-child(even) {
                background: rgba(255, 255, 255, 0.05);
            }

            .markdown-content a {
                color: #FFD700 !important;
                text-decoration: none;
                border-bottom: 1px solid #FFD700;
                padding: 0 2px;
            }

            .markdown-content a:hover {
                background-color: #FFD700 !important;
                color: #1a1a1a !important;
            }

            .markdown-content img {
                max-width: 100%;
                height: auto;
                border-radius: 5px;
                margin: 1em 0;
            }

            .markdown-content hr {
                border: none;
                border-top: 2px solid #444;
                margin: 2em 0;
            }

            /* Markdown 预览样式 */
            .markdown-preview {
                font-size: 14px;
                line-height: 1.5;
                max-height: 100px;
                overflow: hidden;
            }

            .markdown-preview h1,
            .markdown-preview h2,
            .markdown-preview h3 {
                font-size: 1em;
                margin: 0.5em 0;
                font-weight: bold;
            }

            .markdown-preview code {
                background: rgba(255, 255, 255, 0.1);
                padding: 0.1em 0.3em;
                border-radius: 2px;
                font-size: 0.9em;
            }

            .markdown-preview ul,
            .markdown-preview ol {
                margin: 0.5em 0;
                padding-left: 1.5em;
            }
            .category-item:hover, .tag-item:hover {
                transform: translateY(-2px);
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            }

            .category-item:hover {
                border-color: var(--accent-primary) !important;
            }
            /* 限制预览中图片的最大高度 */
            .markdown-preview img,
            .item .content img {
                max-height: 200px !important; /* 限制图片最大高度 */
                width: auto !important; /* 保持宽高比 */
                max-width: 100% !important; /* 确保响应式 */
                object-fit: contain; /* 保持图片比例 */
                border-radius: 5px;
                box-shadow: 0 2px 8px rgba(0,0,0,0.2);
                margin: 5px 0;
                cursor: pointer;
                transition: all 0.3s ease;
            }

            /* 图片悬停效果 */
            .markdown-preview img:hover,
            .item .content img:hover {
                transform: scale(1.02);
                box-shadow: 0 4px 12px rgba(0,0,0,0.3);
            }

            /* 模态框中的图片不限制高度 */
            .modal-content .markdown-content img {
                max-height: none !important; /* 详情页不限制高度 */
                max-width: 100% !important;
            }

            /* 批量编辑模态框样式 */
            #batchEditModal .modal-content {
                background: var(--bg-secondary);
                border-radius: 10px;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            }

            /* 操作选项样式 */
            .batch-option {
                background: var(--bg-tertiary);
                padding: 15px;
                border-radius: 8px;
                margin-bottom: 15px;
                border: 1px solid #444;
            }

            .batch-option h4 {
                margin-top: 0;
                color: var(--accent-primary);
                border-bottom: 1px solid #444;
                padding-bottom: 8px;
            }

            /* 输入框样式 */
            #batchEditModal input[type="text"],
            #batchEditModal select {
                background: var(--bg-primary);
                border: 1px solid #555;
                color: var(--text-primary);
                padding: 10px;
                border-radius: 5px;
                font-size: 14px;
            }

            #batchEditModal input[type="text"]:focus,
            #batchEditModal select:focus {
                border-color: var(--accent-primary);
                outline: none;
            }

            /* 番茄时钟样式 */
            #pomodoroModal .modal-content {
                background: var(--bg-secondary);
                border-radius: 15px;
                box-shadow: 0 8px 32px rgba(0,0,0,0.3);
            }

            #pomodoroTimer {
                text-shadow: 0 2px 10px rgba(231, 76, 60, 0.3);
                font-family: 'Courier New', monospace;
            }

            #progressCircle {
                transition: stroke-dashoffset 1s linear, stroke 0.3s ease;
            }

            /* 迷你时钟动画 */
            #miniPomodoro {
                transition: all 0.3s ease;
                animation: pulse 2s infinite;
            }

            #miniPomodoro:hover {
                transform: scale(1.05);
                border-color: var(--accent-primary);
            }

            @keyframes pulse {
                0% { box-shadow: 0 4px 12px rgba(231, 76, 60, 0.3); }
                50% { box-shadow: 0 4px 20px rgba(231, 76, 60, 0.6); }
                100% { box-shadow: 0 4px 12px rgba(231, 76, 60, 0.3); }
            }

            /* 专注阶段的特殊样式 */
            .focus-phase {
                background: linear-gradient(135deg, #e74c3c, #c0392b);
            }

            .break-phase {
                background: linear-gradient(135deg, #27ae60, #229954);
            }

            .long-break-phase {
                background: linear-gradient(135deg, #3498db, #2980b9);
            }

        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>个人知识管理系统</h1>
                <p>支持LaTeX数学公式的知识管理工具</p>
                <!-- 添加数据库切换控件 -->
                <div style="margin-top: 15px; padding: 10px; background: var(--bg-tertiary); border-radius: 8px; max-width: 500px; margin-left: auto; margin-right: auto;">
                    <div style="display: flex; align-items: center; justify-content: center; gap: 10px; flex-wrap: wrap;">
                        <span style="color: var(--text-primary); font-weight: bold;">当前数据库:</span>
                        <span id="currentDbDisplay" style="color: var(--accent-primary); font-weight: bold;">加载中...</span>
                        <button onclick="showDatabaseManager()" style="background: #3498db; padding: 8px 16px; font-size: 14px;">切换数据库</button>
                    </div>
                </div>
            </div>

            <div class="stats" id="stats">
                <h3>📊 系统统计</h3>
                <div id="statsContent">加载中...</div>
            </div>

            <div class="search-box">
                <h3>🔍 搜索知识</h3>
                <input type="text" id="searchInput" placeholder="输入关键词搜索知识...">
                <div style="margin-top: 10px; display: flex; flex-wrap: wrap; gap: 10px;">
                    <button onclick="searchItems()">搜索 (Ctrl+F)</button>
                    <button onclick="showAllItems()" style="background: #28a745;">显示全部 (Ctrl+A)</button>
                    <button onclick="showCategories()" style="background: #17a2b8;">📂 分类</button>
                    <button onclick="showTags()" style="background: #6f42c1;">🏷️ 标签</button>
                    <button onclick="togglePomodoro()" style="background: #e74c3c;">🍅 番茄时钟</button>  <!-- 新增番茄时钟按钮 -->
                    <button onclick="showTodayReviews()" style="background: #ffc107; color: black;">今日复习 (Ctrl+R)</button>
                    <button onclick="switchTab('add')" style="background: #17a2b8;">添加知识 (Ctrl+S)</button>
                    <button onclick="switchTab('graph')" style="background: #6f42c1;">知识图谱 (Ctrl+G)</button>
                    <button onclick="toggleMathRendering()" id="mathToggleBtn" style="background: #20c997;"> 🔢 渲染公式 </button>
                    <button onclick="toggleMarkdownRendering()" id="markdownToggleBtn" style="background: #17a2b8;"> 📝 渲染Markdown </button>
                    <button onclick="showShortcutHelp()" style="background: #6c757d;">快捷键帮助 (F1)</button>
                </div>

            <div id="results"></div>

            <div class="tab-container">
                <div class="tab-buttons">
                    <button class="tab-button active" onclick="switchTab('add')">📝 添加/导入知识</button>
                    <button class="tab-button" onclick="switchTab('graph')">🕸️ 知识图谱</button>
                    <button class="tab-button" onclick="switchTab('review')">📚 复习模式</button>
                </div>

                <!-- 添加知识标签页 -->
                <div id="add-tab" class="tab-content active">
                    <div class="add-knowledge-container">
                        <h3>📝 添加新知识（支持LaTeX公式）</h3>
                        <div class="form-grid">
                            <div>
                                <input type="text" id="newTitle" placeholder="标题（如：勾股定理）">
                                <textarea id="newContent" placeholder="内容（使用 $E = mc^2$ 表示行内公式，$$\\frac{1}{2}$$ 表示块级公式）"></textarea>
                                <div style="margin-top: 10px;">
                                    <button onclick="insertLocalImage()" style="background: #6c757d;">插入图片链接</button>
                                    <button onclick="insertFileLink()" style="background: #6c757d;">插入文件链接</button>
                                    <!-- 在编辑模态框中也添加上传按钮 -->
                                    <button type="button" onclick="uploadImages()" style="background: #3498db;">上传图片</button>
                                    <button type="button" onclick="uploadFiles()" style="background: #3498db;">上传文件</button>
                                    <button onclick="importTextToEditor('add')" style="background: #9b59b6;">📄 导入文件</button>
                                </div>
                                <!-- 添加隐藏的文件输入框 -->
                                <input type="file" id="imageUploadInput" accept="image/*" multiple style="display: none;" onchange="handleImageUpload(this.files, getCurrentContext())">
                                <input type="file" id="fileUploadInput" multiple style="display: none;" onchange="handleFileUpload(this.files, getCurrentContext())">
                                <input type="file" id="textEditorImportInput" accept=".txt,.md,.tex,.rst,.vim,.csv,.py,.js,.java,.cpp,.c,.html,.css,.json,.yaml,.yml,.xml,.sty,.bib,.def" multiple style="display: none;" onchange="handleTextEditorImport(this.files, getCurrentContext())">
                            </div>
                            <div>
                                <input type="text" id="newTags" placeholder="标签（逗号分隔，如：数学,几何,公式）">
                                <input type="text" id="newCategory" placeholder="分类（如：数学笔记）" value="未分类">
                                <div style="margin: 15px 0;">
                                    <label>重要程度:</label>
                                    <select id="newImportance">
                                        <option value="1">1 - 一般</option>
                                        <option value="2">2 - 有用</option>
                                        <option value="3">3 - 重要</option>
                                        <option value="4">4 - 很重要</option>
                                        <option value="5" selected>5 - 极其重要</option>
                                    </select>
                                </div>
                                <div style="margin: 15px 0;">
                                    <label>理解程度:</label>
                                    <select id="newUnderstanding">
                                        <option value="1">1 - 刚接触</option>
                                        <option value="2">2 - 基本了解</option>
                                        <option value="3">3 - 理解</option>
                                        <option value="4">4 - 熟练掌握</option>
                                        <option value="5" selected>5 - 精通</option>
                                    </select>
                                </div>
                            </div>
                        </div>


                        <div class="button-container">
                            <button onclick="addNewItem()" class="btn-success">添加知识 (Ctrl+Enter)</button>
                            <span id="addResult"></span>
                        </div>
                    </div>

                    <!-- 文件导入部分 -->
                    <div class="import-container">
                        <h3>📁 从文件导入知识库</h3>
                        <input type="file" id="importFile" accept=".json,.yaml,.yml" style="margin: 10px 0; display: block;">
                        <button onclick="importFromFile()" style="background: #17a2b8;">导入文件 (Ctrl+I)</button>
                        <span id="importResult" style="margin-left: 10px;"></span>
                        <div style="margin-top: 10px; font-size: 12px; color: #b0b0b0;">
                            <p>支持导入JSON、YAML格式的知识库文件。</p>
                        </div>

                        <h3>📄 从文本文件导入知识</h3>
                        <div style="margin: 15px 0;">
                            <input type="file" id="textFileImport" accept=".md,.txt,.tex,.rst,.vim,.csv,.py,.docx,.pdf" multiple style="margin: 10px 0; display: block;">
                            <div style="margin: 10px 0;">
                                <label>
                                    <input type="checkbox" id="useFilenameAsTitle" checked> 使用文件名作为标题
                                </label>
                                <label style="margin-left: 15px;">
                                    <input type="checkbox" id="autoDetectTags" checked> 自动检测标签
                                </label>
                            </div>
                            <button onclick="importFromTextFiles()" style="background: #17a2b8;">导入文本文件</button>
                            <span id="textImportResult" style="margin-left: 10px;"></span>
                        </div>
                        <div style="margin-top: 10px; font-size: 12px; color: #b0b0b0;">
                            <p>支持导入 Markdown(.md)、Text(.txt)、LaTeX(.tex)、reStructuredText(.rst)、Word(.docx)、PDF(.pdf) 等格式文件。</p>
                            <p>文件名将作为知识条目标题，文件内容作为知识内容。</p>
                        </div>
                    </div>
                </div>

                <!-- 知识图谱标签页 -->
                <div id="graph-tab" class="tab-content">
                    <div class="graph-container">
                        <h3>🕸️ 知识图谱可视化</h3>
                        <div style="margin-bottom: 15px; display: flex; gap: 10px; flex-wrap: wrap;">
                            <button onclick="loadKnowledgeGraph()">刷新图谱</button>
                            <button onclick="resetGraphHighlight()" style="background: #6c757d;">重置视图</button>
                            <button onclick="exportGraphData()" class="btn-success">导出数据</button>
                            <button onclick="focusOnImportantNodes()" style="background: #e74c3c;">聚焦重要节点</button>
                            <button onclick="showGraphHelp()" style="background: #3498db;">使用帮助</button>
                        </div>
                        <div id="mynetwork"></div>
                        <div style="margin-top: 15px;">
                            <span id="graphInfo" style="color: var(--text-secondary);"></span>
                        </div>
                    </div>
                </div>



                <!-- 复习模式标签页 -->
                <div id="review-tab" class="tab-content">
                    <div style="padding: 20px; background: var(--bg-tertiary); border-radius: 10px;">
                        <h3>📚 智能复习模式</h3>
                        <div id="reviewContent">
                            <p>点击下方按钮开始复习</p>
                            <button onclick="startReviewSession()" class="btn-success">开始复习</button>
                        </div>
                    </div>
                </div>
            </div>

            <div class="ai-panel">
                <h3>🤖 AI智能分析</h3>
                <div id="aiInsights">点击知识条目查看AI分析...</div>
            </div>
        </div>


            <!-- 在现有的AI分析面板后面添加AI功能按钮 -->
            <div class="ai-panel">
                <h3>🤖 AI智能助手 (DeepSeek)</h3>
                <div style="margin-bottom: 15px;">
                    <button onclick="showAIChat()" style="background: #9b59b6;">💬 AI对话</button>
                    <button onclick="analyzeWithAI()" style="background: #3498db;">🔍 AI分析</button>
                    <button onclick="generateQuestions()" style="background: #e74c3c;">❓ 生成问题</button>
                    <button onclick="improveWriting()" style="background: #2ecc71;">✍️ 改进写作</button>
                    <button onclick="showAISettings()" style="background: #95a5a6;">⚙️ AI设置</button>
                </div>
                <div style="font-size: 12px; color: #b0b0b0; margin-bottom: 10px;">
                    💡 提示：先点击知识条目选中（边框会高亮），然后使用AI功能
                </div>
                <div id="aiInsights">选择AI功能开始使用...</div>
            </div>

        <!-- 知识详情模态框 -->
        <div id="detailModal" class="modal">
            <div class="modal-content">
                <span class="close" onclick="closeDetailModal()">&times;</span>
                <div id="modalContent"></div>
            </div>
        </div>

        <!-- 编辑模态框 -->
        <div id="editModal" class="modal">
            <div class="modal-content">
                <span class="close" onclick="closeEditModal()">&times;</span>
                <div id="editModalContent"></div>
            </div>
        </div>

        <!-- ========== 在这里添加番茄时钟模态框 ========== -->
        <div id="pomodoroModal" class="modal">
            <div class="modal-content" style="max-width: 500px; text-align: center;">
                <span class="close" onclick="closePomodoro()">&times;</span>
                <h2>🍅 番茄时钟</h2>

                <div id="pomodoroContainer">
                    <!-- 时钟显示区域 -->
                    <div id="pomodoroTimer" style="font-size: 4em; font-weight: bold; margin: 20px 0; color: var(--accent-primary);">
                        25:00
                    </div>

                    <!-- 进度环 -->
                    <div id="pomodoroProgress" style="width: 200px; height: 200px; margin: 0 auto 20px; position: relative;">
                        <svg width="200" height="200" viewBox="0 0 200 200">
                            <circle cx="100" cy="100" r="90" stroke="#444" stroke-width="8" fill="none"/>
                            <circle id="progressCircle" cx="100" cy="100" r="90" stroke="#e74c3c" stroke-width="8"
                                    fill="none" stroke-linecap="round" transform="rotate(-90 100 100)"
                                    stroke-dasharray="565.48" stroke-dashoffset="0"/>
                        </svg>
                        <div style="position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%);">
                            <div id="pomodoroPhase" style="font-size: 1.2em; font-weight: bold; color: var(--text-primary);">专注时间</div>
                            <div id="pomodoroCycles" style="font-size: 0.9em; color: var(--text-secondary);">已完成: 0 个番茄</div>
                        </div>
                    </div>

                    <!-- 控制按钮 -->
                    <div style="display: flex; justify-content: center; gap: 10px; margin: 20px 0;">
                        <button id="startPomodoroBtn" onclick="startPomodoro()" style="background: #27ae60; padding: 12px 24px;">
                            🎯 开始专注
                        </button>
                        <button id="pausePomodoroBtn" onclick="pausePomodoro()" style="background: #f39c12; padding: 12px 24px; display: none;">
                            ⏸️ 暂停
                        </button>
                        <button id="resetPomodoroBtn" onclick="resetPomodoro()" style="background: #95a5a6; padding: 12px 24px;">
                            🔄 重置
                        </button>
                    </div>

                    <!-- 设置区域 -->
                    <div style="background: var(--bg-tertiary); padding: 15px; border-radius: 8px; margin: 15px 0;">
                        <h4>⚙️ 时钟设置</h4>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; text-align: left;">
                            <div>
                                <label>专注时间 (分钟):</label>
                                <input type="number" id="focusTime" min="1" max="60" value="25"
                                       style="width: 100%; padding: 8px; background: var(--bg-primary); color: var(--text-primary); border: 1px solid #555; border-radius: 4px;">
                            </div>
                            <div>
                                <label>休息时间 (分钟):</label>
                                <input type="number" id="breakTime" min="1" max="30" value="5"
                                       style="width: 100%; padding: 8px; background: var(--bg-primary); color: var(--text-primary); border: 1px solid #555; border-radius: 4px;">
                            </div>
                            <div>
                                <label>长休息时间 (分钟):</label>
                                <input type="number" id="longBreakTime" min="1" max="60" value="15"
                                       style="width: 100%; padding: 8px; background: var(--bg-primary); color: var(--text-primary); border: 1px solid #555; border-radius: 4px;">
                            </div>
                            <div>
                                <label>长休息间隔:</label>
                                <input type="number" id="longBreakInterval" min="1" max="10" value="4"
                                       style="width: 100%; padding: 8px; background: var(--bg-primary); color: var(--text-primary); border: 1px solid #555; border-radius: 4px;">
                            </div>
                        </div>
                    </div>

                    <!-- 统计信息 -->
                    <div style="background: var(--bg-tertiary); padding: 15px; border-radius: 8px;">
                        <h4>📊 今日统计</h4>
                        <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 10px; font-size: 0.9em;">
                            <div>今日番茄: <span id="todayPomodoros">0</span></div>
                            <div>总专注时间: <span id="totalFocusTime">0</span> 分钟</div>
                            <div>当前任务: <span id="currentTask">知识复习</span></div>
                            <div>状态: <span id="pomodoroStatus">未开始</span></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>

        <!-- ========== 在这里添加迷你时钟 ========== -->
        <div id="miniPomodoro" style="position: fixed; bottom: 20px; right: 20px; background: var(--bg-secondary); padding: 10px 15px; border-radius: 25px; box-shadow: 0 4px 12px rgba(0,0,0,0.3); border: 2px solid #444; z-index: 1000; cursor: pointer; display: none;">
            <div style="display: flex; align-items: center; gap: 10px;">
                <span id="miniTimer" style="font-weight: bold; color: var(--accent-primary);">25:00</span>
                <span id="miniPhase" style="font-size: 0.8em; color: var(--text-secondary);">专注</span>
                <button onclick="togglePomodoro()" style="background: none; border: none; color: var(--text-primary); cursor: pointer; font-size: 1.2em;">🍅</button>
            </div>
        </div>

        <script>
            // 全局变量
            let currentKnowledgeGraph = null;
            let statsChart = null;
            // 添加批量选择功能
            window.selectedItems = new Set(); // 确保全局可访问

            // 新增：全局聊天记录
            window.chatMessages = [];
            let currentChatContext = null; // 当前聊天上下文（选中的条目ID）

            // ========== 番茄时钟功能 ==========

            // 首先定义 pomodoroState，确保它在所有函数之前初始化
            const pomodoroState = {
                isRunning: false,
                isPaused: false,
                currentPhase: 'focus',
                timeLeft: 25 * 60,
                totalTime: 25 * 60,
                cyclesCompleted: 0,
                timerInterval: null,
                todayPomodoros: 0,
                totalFocusTime: 0
            };

            // 然后定义所有使用 pomodoroState 的函数
            window.togglePomodoro = function() {
                const modal = document.getElementById('pomodoroModal');
                if (modal.style.display === 'block' || modal.style.display === '') {
                    closePomodoro();
                } else {
                    showPomodoro();
                }
            };

            window.showPomodoro = function() {
                const modal = document.getElementById('pomodoroModal');
                modal.style.display = 'block';
                updatePomodoroDisplay();
            };

            window.closePomodoro = function() {
                const modal = document.getElementById('pomodoroModal');
                modal.style.display = 'none';
            };

            window.startPomodoro = function() {
                console.log('开始专注按钮被点击');

                if (pomodoroState.isRunning && !pomodoroState.isPaused) {
                    console.log('已经在运行');
                    return;
                }

                pomodoroState.isRunning = true;
                pomodoroState.isPaused = false;

                // 更新按钮状态
                const startBtn = document.getElementById('startPomodoroBtn');
                const pauseBtn = document.getElementById('pausePomodoroBtn');

                if (startBtn) startBtn.style.display = 'none';
                if (pauseBtn) pauseBtn.style.display = 'inline-block';

                // 显示迷你时钟
                const miniPomodoro = document.getElementById('miniPomodoro');
                if (miniPomodoro) miniPomodoro.style.display = 'block';

                // 清除之前的计时器
                if (pomodoroState.timerInterval) {
                    clearInterval(pomodoroState.timerInterval);
                }

                // 启动计时器
                pomodoroState.timerInterval = setInterval(updatePomodoroTimer, 1000);

                // 更新状态显示
                const statusElement = document.getElementById('pomodoroStatus');
                if (statusElement) statusElement.textContent = '进行中';

                console.log('番茄时钟已启动');
            };

            window.pausePomodoro = function() {
                if (!pomodoroState.isRunning) return;

                pomodoroState.isPaused = !pomodoroState.isPaused;

                if (pomodoroState.isPaused) {
                    clearInterval(pomodoroState.timerInterval);
                    document.getElementById('pausePomodoroBtn').innerHTML = '▶️ 继续';
                    document.getElementById('pomodoroStatus').textContent = '已暂停';
                } else {
                    pomodoroState.timerInterval = setInterval(updatePomodoroTimer, 1000);
                    document.getElementById('pausePomodoroBtn').innerHTML = '⏸️ 暂停';
                    document.getElementById('pomodoroStatus').textContent = '进行中';
                }
            };

            window.resetPomodoro = function() {
                clearInterval(pomodoroState.timerInterval);

                // 从设置中获取时间
                const focusTime = parseInt(document.getElementById('focusTime').value) || 25;
                const breakTime = parseInt(document.getElementById('breakTime').value) || 5;
                const longBreakTime = parseInt(document.getElementById('longBreakTime').value) || 15;

                pomodoroState.isRunning = false;
                pomodoroState.isPaused = false;
                pomodoroState.currentPhase = 'focus';
                pomodoroState.timeLeft = focusTime * 60;
                pomodoroState.totalTime = focusTime * 60;

                // 重置按钮状态
                document.getElementById('startPomodoroBtn').style.display = 'inline-block';
                document.getElementById('pausePomodoroBtn').style.display = 'none';
                document.getElementById('pausePomodoroBtn').innerHTML = '⏸️ 暂停';

                // 更新显示
                updatePomodoroDisplay();
                document.getElementById('pomodoroStatus').textContent = '未开始';

                // 重置标签页标题
                document.title = document.title.replace(/^\(\d+:\d+\) /, '');
            };

            window.updatePomodoroTimer = function() {
                console.log('计时器运行中，剩余时间:', pomodoroState.timeLeft);

                if (pomodoroState.timeLeft <= 0) {
                    console.log('时间到，完成阶段');
                    completePomodoroPhase();
                    return;
                }

                pomodoroState.timeLeft--;
                updatePomodoroDisplay();
                updateTabTitle();
            };

            window.completePomodoroPhase = function() {
                clearInterval(pomodoroState.timerInterval);

                // 播放提示音（如果有）
                playNotificationSound();

                // 发送浏览器通知
                sendPomodoroNotification();

                // 根据当前阶段决定下一步
                if (pomodoroState.currentPhase === 'focus') {
                    pomodoroState.cyclesCompleted++;
                    pomodoroState.todayPomodoros++;
                    pomodoroState.totalFocusTime += parseInt(document.getElementById('focusTime').value) || 25;

                    // 检查是否需要长休息
                    const longBreakInterval = parseInt(document.getElementById('longBreakInterval').value) || 4;
                    if (pomodoroState.cyclesCompleted % longBreakInterval === 0) {
                        // 长休息
                        pomodoroState.currentPhase = 'longBreak';
                        const longBreakTime = parseInt(document.getElementById('longBreakTime').value) || 15;
                        pomodoroState.timeLeft = longBreakTime * 60;
                        pomodoroState.totalTime = longBreakTime * 60;

                        showNotification('🎉 专注时间结束！开始长休息', 'success');
                    } else {
                        // 短休息
                        pomodoroState.currentPhase = 'break';
                        const breakTime = parseInt(document.getElementById('breakTime').value) || 5;
                        pomodoroState.timeLeft = breakTime * 60;
                        pomodoroState.totalTime = breakTime * 60;

                        showNotification('🎉 专注时间结束！开始休息', 'success');
                    }
                } else {
                    // 休息结束，开始新的专注
                    pomodoroState.currentPhase = 'focus';
                    const focusTime = parseInt(document.getElementById('focusTime').value) || 25;
                    pomodoroState.timeLeft = focusTime * 60;
                    pomodoroState.totalTime = focusTime * 60;

                    showNotification('💪 休息结束！开始新的专注时间', 'info');
                }

                // 自动开始下一阶段（可选）
                setTimeout(() => {
                    if (confirm(`准备开始${pomodoroState.currentPhase === 'focus' ? '专注' : '休息'}时间吗？`)) {
                        startPomodoro();
                    }
                }, 1000);

                updatePomodoroDisplay();
                savePomodoroStats();
            };

            window.updatePomodoroDisplay = function() {
                console.log('更新显示，当前阶段:', pomodoroState.currentPhase);

                const minutes = Math.floor(pomodoroState.timeLeft / 60);
                const seconds = pomodoroState.timeLeft % 60;
                const timeString = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;

                // 更新主时钟
                const timerElement = document.getElementById('pomodoroTimer');
                if (timerElement) {
                    timerElement.textContent = timeString;
                    console.log('更新时间显示:', timeString);
                }

                // 更新迷你时钟
                const miniTimer = document.getElementById('miniTimer');
                if (miniTimer) miniTimer.textContent = timeString;

                // 更新阶段显示
                const phaseNames = {
                    'focus': '专注时间',
                    'break': '休息时间',
                    'longBreak': '长休息'
                };
                document.getElementById('pomodoroPhase').textContent = phaseNames[pomodoroState.currentPhase] || '专注时间';
                document.getElementById('miniPhase').textContent = phaseNames[pomodoroState.currentPhase]?.substring(0, 2) || '专注';

                // 更新进度环
                const progressCircle = document.getElementById('progressCircle');
                if (progressCircle) {
                    const circumference = 565.48;
                    const progress = ((pomodoroState.totalTime - pomodoroState.timeLeft) / pomodoroState.totalTime) * circumference;
                    progressCircle.style.strokeDashoffset = circumference - progress;

                    // 更新颜色
                    const colors = {
                        'focus': '#e74c3c',
                        'break': '#27ae60',
                        'longBreak': '#3498db'
                    };
                    progressCircle.style.stroke = colors[pomodoroState.currentPhase] || '#e74c3c';
                    console.log('更新进度:', progress);
                }

                // 更新统计信息
                document.getElementById('pomodoroCycles').textContent = `已完成: ${pomodoroState.cyclesCompleted} 个番茄`;
                document.getElementById('todayPomodoros').textContent = pomodoroState.todayPomodoros;
                document.getElementById('totalFocusTime').textContent = pomodoroState.totalFocusTime;
            };

            window.updateTabTitle = function() {
                const minutes = Math.floor(pomodoroState.timeLeft / 60);
                const seconds = pomodoroState.timeLeft % 60;
                const timeString = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;

                const phaseSymbols = {
                    'focus': '🍅',
                    'break': '☕',
                    'longBreak': '🌴'
                };

                const originalTitle = document.title.replace(/^\([^)]*\) /, '');
                document.title = `(${timeString}) ${phaseSymbols[pomodoroState.currentPhase]} ${originalTitle}`;
            };

            window.sendPomodoroNotification = function() {
                if (Notification.permission === 'granted') {
                    const phaseMessages = {
                        'focus': '专注时间开始！',
                        'break': '休息时间开始，放松一下吧！',
                        'longBreak': '长休息时间开始，好好休息！'
                    };

                    new Notification('番茄时钟', {
                        body: phaseMessages[pomodoroState.currentPhase] || '时间到！',
                        icon: '🍅'
                    });
                }
            };

            window.playNotificationSound = function() {
                // 简单的提示音
                try {
                    const audioContext = new (window.AudioContext || window.webkitAudioContext)();
                    const oscillator = audioContext.createOscillator();
                    const gainNode = audioContext.createGain();

                    oscillator.connect(gainNode);
                    gainNode.connect(audioContext.destination);

                    oscillator.frequency.value = 800;
                    oscillator.type = 'sine';

                    gainNode.gain.setValueAtTime(0.3, audioContext.currentTime);
                    gainNode.gain.exponentialRampToValueAtTime(0.01, audioContext.currentTime + 1);

                    oscillator.start(audioContext.currentTime);
                    oscillator.stop(audioContext.currentTime + 1);
                } catch (e) {
                    console.log('音频播放失败，使用默认提示');
                }
            };

            window.savePomodoroStats = function() {
                const today = new Date().toDateString();
                const stats = {
                    date: today,
                    pomodoros: pomodoroState.todayPomodoros,
                    focusTime: pomodoroState.totalFocusTime
                };

                localStorage.setItem('pomodoroStats', JSON.stringify(stats));
            };

            window.loadPomodoroStats = function() {
                const saved = localStorage.getItem('pomodoroStats');
                if (saved) {
                    const stats = JSON.parse(saved);
                    const today = new Date().toDateString();

                    if (stats.date === today) {
                        pomodoroState.todayPomodoros = stats.pomodoros || 0;
                        pomodoroState.totalFocusTime = stats.focusTime || 0;
                    }
                }
            };

            // 页面加载时初始化
            document.addEventListener('DOMContentLoaded', function() {
                console.log('DOM加载完成，初始化番茄时钟...');

                // 确保元素存在
                const focusTimeInput = document.getElementById('focusTime');
                const breakTimeInput = document.getElementById('breakTime');

                if (focusTimeInput && breakTimeInput) {
                    loadPomodoroStats();
                    resetPomodoro();

                    // 监听设置变化
                    focusTimeInput.addEventListener('change', resetPomodoro);
                    breakTimeInput.addEventListener('change', resetPomodoro);
                    document.getElementById('longBreakTime')?.addEventListener('change', resetPomodoro);
                    document.getElementById('longBreakInterval')?.addEventListener('change', resetPomodoro);

                    console.log('番茄时钟初始化完成');
                } else {
                    console.error('番茄时钟DOM元素未找到');
                }
            });

            // 标签页切换
            function switchTab(tabName) {
                // 隐藏所有标签内容
                document.querySelectorAll('.tab-content').forEach(tab => {
                    tab.classList.remove('active');
                });

                // 移除所有按钮的active类
                document.querySelectorAll('.tab-button').forEach(btn => {
                    btn.classList.remove('active');
                });

                // 显示选中的标签内容
                const targetTab = document.getElementById(tabName + '-tab');
                if (targetTab) {
                    targetTab.classList.add('active');
                }

                // 激活对应的按钮
                const buttons = document.querySelectorAll('.tab-button');
                buttons.forEach(btn => {
                    if (btn.textContent.includes(tabName === 'add' ? '添加' :
                                                tabName === 'graph' ? '图谱' :
                                                tabName === 'review' ? '复习' : '')) {
                        btn.classList.add('active');
                    }
                });

                // 特殊处理：切换到图谱标签时加载图谱
                if (tabName === 'graph') {
                    setTimeout(loadKnowledgeGraph, 100);
                }
            }


            // KaTeX配置和渲染函数
            const katexOptions = {
                delimiters: [
                    {left: '$$', right: '$$', display: true},
                    {left: '$', right: '$', display: false},
                    {left: '\\(', right: '\\)', display: false},
                    {left: '\\[', right: '\\]', display: true}
                ],
                throwOnError: false,
                strict: false,
                trust: false
            };

            function renderMath(element) {
                if (element && typeof renderMathInElement === 'function') {
                    renderMathInElement(element, katexOptions);
                }
            }

            function renderAllMath() {
                renderMath(document.body);
            }

            // 搜索功能
            function searchItems() {
                const query = document.getElementById('searchInput').value;
                if (!query) {
                    showRecentItems();
                    return;
                }

                fetch('/api/search?q=' + encodeURIComponent(query))
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(data => displayResults(data, `搜索结果: "${query}"`))
                    .catch(error => {
                        console.error('搜索错误:', error);
                        displayResults([], `搜索失败: ${error.message}`);
                    });
            }

            // 显示全部知识条目
            function showAllItems() {
                fetch('/api/search?q=')
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(data => displayResults(data, '所有知识条目'))
                    .catch(error => {
                        console.error('Error:', error);
                        displayResults([], '加载失败');
                    });
            }


            // 知识图谱功能
            function loadKnowledgeGraph(category = '') {
                // 首先检查 vis 库是否可用
                if (typeof vis === 'undefined') {
                    console.error('Vis.js 未加载，无法渲染知识图谱');
                    const container = document.getElementById('mynetwork');
                    if (container) {
                        container.innerHTML = `
                            <div style="text-align: center; padding: 50px; color: #e74c3c;">
                                <h4>❌ 可视化库加载失败</h4>
                                <p>请刷新页面或检查网络连接</p>
                            </div>
                        `;
                    }
                    return;
                }

                let url = '/api/knowledge_graph';
                if (category) {
                    url += '?category=' + encodeURIComponent(category);
                }

                function addLayoutControls() {
                    const graphContainer = document.querySelector('.graph-container');
                    if (!graphContainer) return;

                    const controlsHtml = `
                        <div style="margin-bottom: 15px; display: flex; gap: 10px; flex-wrap: wrap; align-items: center;">
                            <span style="color: var(--text-secondary);">布局:</span>
                            <button onclick="switchLayout('force')" style="background: #3498db;">力导向布局</button>
                            <button onclick="switchLayout('hierarchical')" style="background: #9b59b6;">分层布局</button>
                            <button onclick="switchLayout('cluster')" style="background: #e74c3c;">聚类布局</button>
                            <button onclick="resetGraphLayout()" style="background: #95a5a6;">重置布局</button>
                        </div>
                    `;

                    const existingButtons = graphContainer.querySelector('div:first-child');
                    if (existingButtons) {
                        existingButtons.insertAdjacentHTML('afterend', controlsHtml);
                    }
                }

                // 切换布局函数
                function switchLayout(layoutType) {
                    const network = window.knowledgeGraphNetwork;
                    if (!network) return;

                    const options = {};

                    switch(layoutType) {
                        case 'force':
                            options.physics = {
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
                            };
                            options.layout = { hierarchical: { enabled: false } };
                            break;

                        case 'hierarchical':
                            options.physics = {
                                enabled: true,
                                solver: 'hierarchicalRepulsion',
                                hierarchicalRepulsion: {
                                    centralGravity: 0.0,
                                    springLength: 100,
                                    springConstant: 0.01,
                                    nodeDistance: 120,
                                    damping: 0.09
                                }
                            };
                            options.layout = {
                                hierarchical: {
                                    enabled: true,
                                    direction: 'LR',
                                    sortMethod: 'directed',
                                    levelSeparation: 150,
                                    nodeSpacing: 100
                                }
                            };
                            break;

                        case 'cluster':
                            // 聚类布局 - 基于分组
                            options.physics = {
                                enabled: true,
                                solver: 'repulsion',
                                repulsion: {
                                    centralGravity: 0.2,
                                    springLength: 200,
                                    springConstant: 0.05,
                                    nodeDistance: 150,
                                    damping: 0.09
                                }
                            };
                            options.layout = { hierarchical: { enabled: false } };
                            break;
                    }

                    network.setOptions(options);
                    network.stabilize();
                }

                function resetGraphLayout() {
                    const network = window.knowledgeGraphNetwork;
                    if (!network) return;

                    network.stabilize();
                    setTimeout(() => {
                        network.fit();
                    }, 1000);
                }

                console.log('加载知识图谱数据:', url);

                fetch(url)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(data => {
                        console.log('知识图谱数据:', data);
                        currentKnowledgeGraph = data;
                        renderKnowledgeGraph(data, category);
                    })
                    .catch(error => {
                        console.error('加载知识图谱失败:', error);
                        const graphInfo = document.getElementById('graphInfo');
                        if (graphInfo) {
                            graphInfo.innerHTML = '加载失败: ' + error.message;
                        }
                        const container = document.getElementById('mynetwork');
                        if (container) {
                            container.innerHTML = `<div style="text-align: center; padding: 50px; color: #e74c3c;">加载知识图谱失败: ${error.message}</div>`;
                        }
                    });
            // 在 renderKnowledgeGraph 函数末尾添加
            addLayoutControls();
            }

            function renderKnowledgeGraph(graphData, category = '') {
                const container = document.getElementById('mynetwork');
                if (!container) {
                    console.error('找不到知识图谱容器');
                    return;
                }

                // 检查 vis 库是否加载
                if (typeof vis === 'undefined') {
                    console.error('Vis.js 库未加载');
                    container.innerHTML = `
                        <div style="text-align: center; padding: 50px; color: #e74c3c;">
                            <h3>❌ Vis.js 可视化库加载失败</h3>
                            <p>知识图谱功能暂时不可用</p>
                            <p><small>请检查网络连接或稍后重试</small></p>
                            <button onclick="retryLoadGraph()" style="margin-top: 15px; padding: 10px 20px; background: #3498db; color: white; border: none; border-radius: 5px; cursor: pointer;">
                                🔄 重新加载
                            </button>
                        </div>
                    `;
                    return;
                }

                // 检查是否有数据
                if (!graphData || !graphData.nodes || graphData.nodes.length === 0) {
                    container.innerHTML = '<div style="text-align: center; padding: 50px; color: #888;">暂无知识图谱数据</div>';
                    const graphInfo = document.getElementById('graphInfo');
                    if (graphInfo) {
                        graphInfo.innerHTML = '没有可显示的数据';
                    }
                    return;
                }

                try {
                    // 原有的渲染代码保持不变...
                    console.log('开始渲染知识图谱，节点数量:', graphData.nodes.length);
                    // 过滤节点（如果指定了分类）
                    let nodesToShow = graphData.nodes;
                    if (category) {
                        nodesToShow = graphData.nodes.filter(node => node.category === category);
                        // 同时包含与这些节点关联的其他节点
                        const relatedNodeIds = new Set();
                        nodesToShow.forEach(node => relatedNodeIds.add(node.id));

                        // 添加关联的边和节点
                        graphData.edges.forEach(edge => {
                            if (relatedNodeIds.has(edge.source_id) || relatedNodeIds.has(edge.target_id)) {
                                relatedNodeIds.add(edge.source_id);
                                relatedNodeIds.add(edge.target_id);
                            }
                        });

                        nodesToShow = graphData.nodes.filter(node => relatedNodeIds.has(node.id));
                    }

                    // 检查是否有数据
                    if (!nodesToShow || nodesToShow.length === 0) {
                        container.innerHTML = '<div style="text-align: center; padding: 50px; color: #888;">暂无知识图谱数据</div>';
                        const graphInfo = document.getElementById('graphInfo');
                        if (graphInfo) {
                            graphInfo.innerHTML = '没有可显示的数据';
                        }
                        return;
                    }

                    const nodes = new vis.DataSet(nodesToShow.map(node => ({
                        id: node.id,
                        label: node.title && node.title.length > 20 ? node.title.substring(0, 20) + '...' : node.title || '未知',
                        group: node.category || '未分类',
                        title: `ID: ${node.id}\n标题: ${node.title || '未知'}\n分类: ${node.category || '未分类'}\n重要性: ${node.importance_level || 1}/5`,
                        value: node.importance_level || 1,
                        color: getNodeColor(node.importance_level || 1),
                        font: { color: '#ffffff' }
                    })));

                    // 过滤边（只显示与可见节点相关的边）
                    const visibleNodeIds = new Set(nodesToShow.map(node => node.id));
                    const edges = new vis.DataSet(graphData.edges
                        .filter(edge => visibleNodeIds.has(edge.source_id) && visibleNodeIds.has(edge.target_id))
                        .map(edge => ({
                            from: edge.source_id,
                            to: edge.target_id,
                            label: edge.relationship_type || '关联',
                            arrows: 'to',
                            color: { color: '#bb86fc' }
                        })));

                    // 创建网络
                    const data = { nodes: nodes, edges: edges };

                    const options = {
                        nodes: {
                            shape: 'dot',
                            size: 25,
                            font: {
                                size: 14,
                                face: 'Tahoma',
                                color: '#ffffff'
                            },
                            borderWidth: 2,
                            shadow: true
                        },
                        edges: {
                            width: 2,
                            color: { color: '#bb86fc' },
                            font: {
                                size: 12,
                                face: 'Tahoma',
                                color: '#ffffff',
                                strokeWidth: 3,
                                strokeColor: 'rgba(0,0,0,0.7)'
                            },
                            shadow: true,
                            smooth: {
                                type: 'continuous'
                            }
                        },
                        physics: {
                            enabled: true,
                            stabilization: {
                                iterations: 100,
                                fit: true
                            },
                            // 关键：使用力导向布局并启用分组排斥
                            solver: 'forceAtlas2Based',
                            forceAtlas2Based: {
                                gravitationalConstant: -50,    // 负值使节点相互排斥
                                centralGravity: 0.01,          // 中心引力
                                springLength: 100,             // 弹簧长度
                                springConstant: 0.08,          // 弹簧常数
                                damping: 0.4,                  // 阻尼
                                avoidOverlap: 1                // 避免重叠
                            },
                            // 分组排斥力配置
                            repulsion: {
                                centralGravity: 0.2,
                                springLength: 200,
                                springConstant: 0.05,
                                nodeDistance: 100,
                                damping: 0.09
                            },
                            // 分层布局（可选，用于更明显的分组）
                            hierarchical: {
                                enabled: false,  // 设为 true 可以尝试分层布局
                                direction: 'UD',
                                sortMethod: 'hubsize'
                            }
                        },
                        interaction: {
                            hover: true,
                            tooltipDelay: 200,
                            hideEdgesOnDrag: true,
                            navigationButtons: true,  // 添加导航按钮
                            keyboard: true
                        },
                        layout: {
                            improvedLayout: true,
                            randomSeed: 42  // 固定随机种子，使布局更稳定
                        },
                        groups: {
                            // 为不同分类定义不同的颜色和样式
                            '未分类': {
                                color: { background: '#666666', border: '#ffffff', highlight: { background: '#888888', border: '#ffffff' } },
                                font: { color: '#ffffff' }
                            },
                            'AI': {
                                color: { background: '#9b59b6', border: '#ffffff', highlight: { background: '#8e44ad', border: '#ffffff' } },
                                font: { color: '#ffffff' }
                            },
                            '数学': {
                                color: { background: '#3498db', border: '#ffffff', highlight: { background: '#2980b9', border: '#ffffff' } },
                                font: { color: '#ffffff' }
                            },
                            '编程': {
                                color: { background: '#e74c3c', border: '#ffffff', highlight: { background: '#c0392b', border: '#ffffff' } },
                                font: { color: '#ffffff' }
                            },
                            '读书笔记': {
                                color: { background: '#f39c12', border: '#ffffff', highlight: { background: '#d35400', border: '#ffffff' } },
                                font: { color: '#ffffff' }
                            },
                            '工作项目': {
                                color: { background: '#2ecc71', border: '#ffffff', highlight: { background: '#27ae60', border: '#ffffff' } },
                                font: { color: '#ffffff' }
                            },
                            '技术笔记': {
                                color: { background: '#1abc9c', border: '#ffffff', highlight: { background: '#16a085', border: '#ffffff' } },
                                font: { color: '#ffffff' }
                            }
                        }
                    };

                    // 创建网络实例
                    window.knowledgeGraphNetwork = new vis.Network(container, data, options);

                    // 添加点击事件
                    window.knowledgeGraphNetwork.on("click", function(params) {
                        if (params.nodes.length > 0) {
                            const nodeId = params.nodes[0];
                            showItemDetail(nodeId);
                        }
                    });

                    // 添加双击事件高亮关联节点
                    window.knowledgeGraphNetwork.on("doubleClick", function(params) {
                        if (params.nodes.length > 0) {
                            const nodeId = params.nodes[0];
                            highlightConnectedNodes(window.knowledgeGraphNetwork, nodeId);
                        }
                    });

                    // 更新图谱信息显示
                    const graphInfo = document.getElementById('graphInfo');
                    if (graphInfo) {
                        const categoryInfo = category ? ` | 分类: ${category}` : '';
                        graphInfo.innerHTML =
                            `节点: ${nodesToShow.length} | 关系: ${edges.length}${categoryInfo} | <span style="color: #bb86fc;">点击节点查看详情</span>`;
                    }

                } catch (error) {
                    console.error('渲染知识图谱失败:', error);
                    container.innerHTML = `<div style="text-align: center; padding: 50px; color: #e74c3c;">渲染知识图谱时出错: ${error.message}</div>`;
                }
            }


            // 添加分类筛选功能到图谱标签页
            function addCategoryFilterToGraph() {
                const graphContainer = document.querySelector('#graph-tab .graph-container');
                if (!graphContainer) return;

                // 在现有按钮后添加分类筛选
                const filterHtml = `
                    <div style="margin-bottom: 15px;">
                        <label>按分类筛选: </label>
                        <select id="graphCategoryFilter" onchange="filterGraphByCategory(this.value)">
                            <option value="">全部分类</option>
                            <option value="AI">AI</option>
                            <option value="数学">数学</option>
                            <option value="编程">编程</option>
                            <option value="读书笔记">读书笔记</option>
                            <option value="工作项目">工作项目</option>
                            <option value="技术笔记">技术笔记</option>
                            <option value="未分类">未分类</option>
                        </select>
                    </div>
                `;

                const existingButtons = graphContainer.querySelector('div:first-child');
                if (existingButtons) {
                    existingButtons.insertAdjacentHTML('afterend', filterHtml);
                }
            }

            function filterGraphByCategory(category) {
                loadKnowledgeGraph(category);
            }

            // 根据重要性级别设置节点颜色
            function getNodeColor(importanceLevel) {
                const colors = {
                    1: '#666666',  // 一般 - 灰色
                    2: '#3498db',  // 有用 - 蓝色
                    3: '#bb86fc',  // 重要 - 紫色
                    4: '#f39c12',  // 很重要 - 橙色
                    5: '#e74c3c'   // 极其重要 - 红色
                };
                return colors[importanceLevel] || colors[3];
            }


            // 高亮关联节点功能
            function highlightConnectedNodes(network, nodeId) {
                const connectedNodes = new Set();
                const connectedEdges = new Set();

                // 获取所有与当前节点关联的边
                const edges = network.body.data.edges.get();
                edges.forEach(edge => {
                    if (edge.from === nodeId || edge.to === nodeId) {
                        connectedEdges.add(edge.id);
                        connectedNodes.add(edge.from);
                        connectedNodes.add(edge.to);
                    }
                });

                // 设置高亮样式
                const nodes = network.body.data.nodes.get();
                nodes.forEach(node => {
                    if (connectedNodes.has(node.id)) {
                        node.color = {
                            background: node.id === nodeId ? '#03dac6' : '#9b59b6',
                            border: '#ffffff',
                            highlight: {
                                background: '#03dac6',
                                border: '#ffffff'
                            }
                        };
                    } else {
                        node.color = {
                            background: getNodeColor(node.value || 3),
                            border: '#ffffff',
                            highlight: {
                                background: '#03dac6',
                                border: '#ffffff'
                            }
                        };
                    }
                });

                // 更新网络
                network.body.data.nodes.update(nodes);
            }

            // 重置高亮
            function resetGraphHighlight() {
                const network = window.knowledgeGraphNetwork;
                if (!network) return;

                const nodes = network.body.data.nodes.get();
                nodes.forEach(node => {
                    node.color = {
                        background: getNodeColor(node.value || 3),
                        border: '#ffffff',
                        highlight: {
                            background: '#03dac6',
                            border: '#ffffff'
                        }
                    };
                });

                network.body.data.nodes.update(nodes);
            }



            // 聚焦重要节点功能
            function focusOnImportantNodes() {
                const network = window.knowledgeGraphNetwork;
                if (!network) return;

                const nodes = network.body.data.nodes.get();
                const importantNodes = nodes.filter(node => (node.value || 1) >= 4);

                if (importantNodes.length === 0) {
                    alert('没有找到重要性为4级或5级的节点');
                    return;
                }

                // 高亮重要节点
                nodes.forEach(node => {
                    if ((node.value || 1) >= 4) {
                        node.color = {
                            background: '#e74c3c',
                            border: '#ffffff',
                            highlight: {
                                background: '#03dac6',
                                border: '#ffffff'
                            }
                        };
                        node.size = 30; // 放大重要节点
                    } else {
                        node.color = {
                            background: '#666666',
                            border: '#ffffff',
                            highlight: {
                                background: '#03dac6',
                                border: '#ffffff'
                            }
                        };
                        node.size = 20;
                    }
                });

                network.body.data.nodes.update(nodes);

                // 聚焦到重要节点区域
                const nodeIds = importantNodes.map(node => node.id);
                network.selectNodes(nodeIds);
                network.focus(nodeIds[0], { scale: 0.8 });
            }

            // 图谱使用帮助
            function showGraphHelp() {
                alert(`知识图谱使用帮助：

            🖱️ 鼠标操作：
            • 左键点击节点：查看知识详情
            • 左键拖拽：移动视图
            • 鼠标滚轮：缩放图谱
            • 双击节点：高亮关联节点

            🎯 功能按钮：
            • 刷新图谱：重新加载数据
            • 重置视图：恢复默认显示
            • 导出数据：下载图谱数据
            • 聚焦重要节点：突出显示重要知识
            • 使用帮助：显示本提示

            💡 提示：
            • 节点颜色表示重要性级别
            • 节点大小表示关联程度
            • 点击关系线查看关联类型`);
            }

            // 添加键盘控制
            function addGraphKeyboardControls() {
                document.addEventListener('keydown', function(e) {
                    const network = window.knowledgeGraphNetwork;
                    if (!network) return;

                    // 只有在图谱标签页激活时才响应
                    const graphTab = document.getElementById('graph-tab');
                    if (!graphTab || !graphTab.classList.contains('active')) return;

                    switch(e.key) {
                        case '+':
                        case '=':
                            e.preventDefault();
                            network.moveTo({ scale: network.getScale() * 1.2 });
                            break;
                        case '-':
                            e.preventDefault();
                            network.moveTo({ scale: network.getScale() * 0.8 });
                            break;
                        case '0':
                            e.preventDefault();
                            network.fit();
                            break;
                        case 'r':
                            if (e.ctrlKey) {
                                e.preventDefault();
                                resetGraphHighlight();
                            }
                            break;
                    }
                });
            }

            // 在页面加载时添加键盘控制
            document.addEventListener('DOMContentLoaded', function() {
                addGraphKeyboardControls();
            });


            // AI分析功能
            function showAIRecommendations(itemId) {
                if (!itemId) return;

                fetch('/api/ai_recommendations/' + itemId)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(recommendations => {
                        const aiInsights = document.getElementById('aiInsights');
                        if (!aiInsights) return;

                        let html = '<h4>🤖 AI智能推荐</h4>';
                        if (recommendations && recommendations.length > 0) {
                            recommendations.forEach(rec => {
                                html += `
                                    <div class="recommendation-item" onclick="showItemDetail(${rec.id})">
                                        <strong>${rec.title || '未知标题'}</strong>
                                        <br><small>分类: ${rec.category || '未分类'} | 重要性: ${rec.importance_level || 3}/5</small>
                                    </div>
                                `;
                            });
                        } else {
                            html += '<p>暂无相关推荐</p>';
                        }
                        aiInsights.innerHTML = html;
                    })
                    .catch(error => {
                        console.error('获取AI推荐失败:', error);
                    });

                // 内容分析
                fetch('/api/content_analysis/' + itemId)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(analysis => {
                        const aiInsights = document.getElementById('aiInsights');
                        if (!aiInsights) return;

                        let analysisHtml = aiInsights.innerHTML;
                        analysisHtml += '<h4>📊 内容分析</h4><div class="analysis-panel">';
                        analysisHtml += `<div>字数: ${analysis.word_count || 0}</div>`;
                        analysisHtml += `<div>句子数: ${analysis.sentence_count || 0}</div>`;
                        analysisHtml += `<div>阅读时间: ${analysis.reading_time_minutes || 0} 分钟</div>`;
                        if (analysis.has_math) analysisHtml += '<div>包含数学公式</div>';
                        if (analysis.has_code_blocks) analysisHtml += '<div>包含代码块</div>';
                        analysisHtml += '</div>';
                        aiInsights.innerHTML = analysisHtml;
                    })
                    .catch(error => {
                        console.error('获取内容分析失败:', error);
                    });
            }


            // 复习模式
            function startReviewSession() {
                fetch('/api/review')
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(items => {
                        const reviewContent = document.getElementById('reviewContent');
                        if (!reviewContent) return;

                        if (!items || items.length === 0) {
                            reviewContent.innerHTML =
                                '<div class="success">🎉 恭喜！今天没有需要复习的内容！</div>';
                            return;
                        }

                        let html = `<h4>今日复习 (${items.length}个项目)</h4>`;
                        items.forEach((item, index) => {
                            html += `
                                <div class="item">
                                    <h4>${index + 1}. ${item.title || '未知标题'}</h4>
                                    <div class="content">${item.summary || ''}</div>
                                    <div style="margin-top: 10px;">
                                        <button onclick="rateReview(${item.id}, 5)" class="btn-success">完美</button>
                                        <button onclick="rateReview(${item.id}, 4)" class="btn-success">良好</button>
                                        <button onclick="rateReview(${item.id}, 3)" class="btn-warning">一般</button>
                                        <button onclick="rateReview(${item.id}, 2)" class="btn-danger">困难</button>
                                        <button onclick="rateReview(${item.id}, 1)" class="btn-danger">忘记</button>
                                    </div>
                                </div>
                            `;
                        });
                        reviewContent.innerHTML = html;
                        renderAllMath();
                    })
                    .catch(error => {
                        console.error('加载复习内容失败:', error);
                        const reviewContent = document.getElementById('reviewContent');
                        if (reviewContent) {
                            reviewContent.innerHTML = '<div class="error">加载复习内容失败</div>';
                        }
                    });
            }

            function rateReview(itemId, rating) {
                fetch('/api/review_session', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ item_id: itemId, rating: rating })
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        const button = document.querySelector(`button[onclick="rateReview(${itemId}, ${rating})"]`);
                        if (button) {
                            button.parentElement.innerHTML = '<span class="success">✓ 复习记录已保存</span>';
                        }
                    }
                })
                .catch(error => {
                    console.error('保存复习记录失败:', error);
                    alert('保存失败，请重试');
                });
            }

            // 基础功能函数
            function loadStats() {
                fetch('/api/stats')
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(data => {
                        const statsContent = document.getElementById('statsContent');
                        if (statsContent) {
                            statsContent.innerHTML = `
                                <strong>知识条目:</strong> ${data.total_items || 0} |
                                <strong>分类:</strong> ${data.categories_count || 0} |
                                <strong>标签:</strong> ${data.tags_count || 0} |
                                <strong>今日待复习:</strong> ${data.today_reviews || 0}
                            `;
                        }
                    })
                    .catch(error => {
                        console.error('加载统计失败:', error);
                        const statsContent = document.getElementById('statsContent');
                        if (statsContent) {
                            statsContent.innerHTML = '统计信息加载失败';
                        }
                    });
            }

            function showTodayReviews() {
                fetch('/api/review')
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(data => {
                        if (data.length === 0) {
                            displayResults([], '今日复习');
                            alert('🎉 今天没有需要复习的内容!');
                        } else {
                            displayResults(data, `今日复习 (${data.length}个项目)`);
                        }
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        displayResults([], '加载复习内容失败');
                    });
            }

            // 显示结果的函数
            function displayResults(items, title) {
                const resultsDiv = document.getElementById('results');
                if (!resultsDiv) return;

                if (!items || !Array.isArray(items)) {
                    resultsDiv.innerHTML = `<h3>${title}</h3><p>数据加载错误</p>`;
                    return;
                }

                if (items.length === 0) {
                    resultsDiv.innerHTML = `<h3>${title}</h3><p>🔍 未找到相关结果</p>`;
                    return;
                }

                let html = `
                    <h3>${title} (共${items.length}个)</h3>
                    <div style="background: #2d2d2d; padding: 10px; border-radius: 5px; margin-bottom: 15px;">
                        <strong>💡 使用说明：</strong> 点击知识条目可以选中/取消选中（用于AI分析），点击标题查看详情
                    </div>
                    <div id="selectionInfo"></div>
                `;

                items.forEach(item => {
                    const isSelected = selectedItems.has(item.id);
                    const tagsHtml = item.tag_names ?
                        item.tag_names.split(',').map(tag =>
                            `<span class="tag">${tag.trim()}</span>`
                        ).join('') : '无';

                    // 渲染内容预览为 Markdown
                    const rawContent = item.content || '';
                    let contentPreview = rawContent.substring(0, 200);

                    // 简单的 Markdown 清理用于预览
                    contentPreview = contentPreview
                        .replace(/#{1,6}\s?/g, '') // 移除标题标记
                        .replace(/\*\*(.*?)\*\*/g, '$1') // 移除粗体
                        .replace(/\*(.*?)\*/g, '$1') // 移除斜体
                        .replace(/`(.*?)`/g, '$1') // 移除代码标记
                        .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1'); // 移除链接标记

                    if (rawContent.length > 200) {
                        contentPreview += '...';
                    }


                    html += `
                        <div class="item ${isSelected ? 'item-selected' : ''}" onclick="toggleItemSelection(${item.id})">
                            <div style="display: flex; justify-content: space-between; align-items: start;">
                                <div style="flex: 1; cursor: pointer;" onclick="event.stopPropagation(); showItemDetail(${item.id})">
                                    <h4>${item.title || '无标题'} <small style="color: #bb86fc; font-size: 0.8em;">(ID: ${item.id})</small></h4>
                                    <div class="content">${markdownRenderingEnabled ?
                                        getPlainTextPreview(item.summary || (item.content ? item.content.substring(0, 200) + '...' : '无内容')) :
                                        getPlainTextPreview(item.summary || (item.content ? item.content.substring(0, 200) + '...' : '无内容'))
                                    }</div>
                                    <small>分类: ${item.category || '未分类'} | 标签: ${tagsHtml} | 理解程度: ${item.understanding_level || 3}/5 | 创建: ${item.created_date || '未知'}</small>
                                </div>
                                <div style="display: flex; flex-direction: column; gap: 5px;">
                                    <button onclick="event.stopPropagation(); editItem(${item.id})"
                                            style="background: #03dac6; padding: 8px 12px; font-size: 12px;">
                                        编辑
                                    </button>
                                    <button onclick="event.stopPropagation(); confirmDelete(${item.id})"
                                            style="background: #cf6679; padding: 8px 12px; font-size: 12px;">
                                        删除
                                    </button>
                                </div>
                            </div>
                        </div>
                    `;
                });

                resultsDiv.innerHTML = html;

                // 添加选中样式
                const style = document.createElement('style');
                style.textContent = `
                    .item-selected {
                        border: 2px solid #3498db !important;
                        background: rgba(52, 152, 219, 0.1) !important;
                    }
                `;
                document.head.appendChild(style);

                if (mathRenderingEnabled) {
                    setTimeout(renderAllMath, 50);
                }
            }

            // 模态框功能
            function showItemDetail(itemId) {
                if (!itemId) return;


                fetch('/api/item/' + itemId)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(item => {
                        const modal = document.getElementById('detailModal');
                        const modalContent = document.getElementById('modalContent');

                        if (!modal || !modalContent) return;

                        // 根据设置渲染内容
                        const rawContent = item.content || '无内容';
                        let contentHtml;

                        if (markdownRenderingEnabled) {
                            try {
                                if (typeof marked !== 'undefined') {
                                    contentHtml = marked.parse(rawContent);
                                } else {
                                    // 如果 marked 不可用，使用简单替换
                                    contentHtml = rawContent
                                        .replace(/^# (.*$)/gim, '<h1>$1</h1>')
                                        .replace(/^## (.*$)/gim, '<h2>$1</h2>')
                                        .replace(/^### (.*$)/gim, '<h3>$1</h3>')
                                        .replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>')
                                        .replace(/\*(.*?)\*/gim, '<em>$1</em>')
                                        .replace(/`(.*?)`/gim, '<code>$1</code>');
                                }
                            } catch (error) {
                                console.error('Markdown 渲染错误:', error);
                                contentHtml = `<pre>${rawContent}</pre>`;
                            }
                        } else {
                            // 不渲染 Markdown，显示纯文本
                            contentHtml = `<pre style="white-space: pre-wrap; font-family: inherit; background: transparent; border: none; padding: 0; margin: 0;">${escapeHtml(rawContent)}</pre>`;
                        }

                        modalContent.innerHTML = `
                            <div style="position: sticky; top: 0; background: var(--bg-secondary); padding: 15px 0; border-bottom: 1px solid #444; z-index: 100; margin-bottom: 20px;">
                                <div style="display: flex; align-items: center; gap: 15px; flex-wrap: wrap;">
                                    <div style="flex: 1; min-width: 300px;">
                                        <div style="display: flex; gap: 10px;">
                                            <input type="text" id="detailSearchInput" placeholder="在内容中搜索..."
                                                   style="flex: 1; padding: 10px; background: var(--bg-primary); border: 1px solid #555; border-radius: 5px; color: white;">
                                            <button onclick="searchInDetail()" style="background: #3498db; padding: 10px 20px; border: none; border-radius: 5px; color: white; cursor: pointer;">搜索</button>
                                            <button onclick="clearSearch()" style="background: #95a5a6; padding: 10px 15px; border: none; border-radius: 5px; color: white; cursor: pointer;">清除</button>
                                        </div>
                                    </div>
                                    <div style="display: flex; gap: 10px; align-items: center;">
                                        <button onclick="scrollToPrevMatch()" style="background: #9b59b6; padding: 8px 15px; border: none; border-radius: 5px; color: white; cursor: pointer;">上一个</button>
                                        <button onclick="scrollToNextMatch()" style="background: #9b59b6; padding: 8px 15px; border: none; border-radius: 5px; color: white; cursor: pointer;">下一个</button>
                                        <span id="searchResultCount" style="color: #bbb; font-size: 14px;"></span>
                                    </div>
                                </div>
                            </div>

                            <div style="max-width: 1600px; margin: 0 auto;">
                                <h1 style="font-size: 2.5em; margin-bottom: 20px; color: var(--text-primary);">${item.title || '无标题'} <small style="color: #bb86fc; font-size: 0.6em;">(ID: ${item.id})</small></h1>

                                <div style="display: grid; grid-template-columns: 5fr 1fr; gap: 30px; align-items: start;">
                                    <!-- 主要内容区域 -->
                                    <div>
                                        <div style="background: var(--bg-tertiary); padding: 30px; border-radius: 10px; margin-bottom: 30px;">
                                            <h3 style="color: var(--accent-primary); margin-top: 0;">内容</h3>
                                        <div id="detailContent" style="line-height: 1.8; font-size: 16px;">${contentHtml}</div>
                                        </div>
                                    </div>

                                    <!-- 侧边栏信息 -->
                                    <div>
                                        <div style="background: var(--bg-tertiary); padding: 20px; border-radius: 10px; margin-bottom: 20px;">
                                            <h4 style="color: var(--accent-primary); margin-top: 0;">基本信息</h4>
                                            <div style="display: grid; gap: 10px;">
                                                <div><strong>分类:</strong> ${item.category || '未分类'}</div>
                                                <div><strong>标签:</strong> ${item.tag_names || '无'}</div>
                                                <div><strong>创建时间:</strong> ${item.created_date || '未知'}</div>
                                                <div><strong>重要性:</strong> ${item.importance_level || 3}/5</div>
                                                <div><strong>理解程度:</strong> ${item.understanding_level || 3}/5</div>
                                            </div>
                                        </div>

                                        <div style="background: var(--bg-tertiary); padding: 20px; border-radius: 10px;">
                                            <h4 style="color: var(--accent-primary); margin-top: 0;">操作</h4>
                                            <div style="display: flex; flex-direction: column; gap: 10px;">
                                                <button onclick="editItem(${item.id})" style="background: #03dac6; padding: 12px; border: none; border-radius: 5px; color: var(--bg-primary); cursor: pointer; font-weight: bold;">编辑</button>
                                                <button onclick="confirmDelete(${item.id})" style="background: #cf6679; padding: 12px; border: none; border-radius: 5px; color: white; cursor: pointer; font-weight: bold;">删除</button>
                                                <button onclick="addRelationship(${item.id})" style="background: #9b59b6; padding: 12px; border: none; border-radius: 5px; color: white; cursor: pointer; font-weight: bold;">添加关联</button>
                                                <button onclick="closeDetailModal()" style="background: #6c757d; padding: 12px; border: none; border-radius: 5px; color: white; cursor: pointer; font-weight: bold;">关闭</button>
                                            </div>
                                        </div>
                                    </div>
                                </div>

                                <!-- 关联知识部分 -->
                                <div style="margin-top: 30px;">
                                    <h3 style="color: var(--accent-primary);">🔗 关联知识</h3>
                                    <div id="relatedItems" style="margin-bottom: 15px;">
                                        <div style="text-align: center; padding: 20px; color: #888;">
                                            <div style="border: 2px solid #f3f3f3; border-top: 2px solid #3498db; border-radius: 50%; width: 20px; height: 20px; animation: spin 1s linear infinite; margin: 0 auto 10px;"></div>
                                            加载关联知识中...
                                        </div>
                                    </div>
                                </div>
                            </div>

                            <style>
                                @keyframes spin {
                                    0% { transform: rotate(0deg); }
                                    100% { transform: rotate(360deg); }
                                }

                                .search-highlight {
                                    background-color: #FFD700;
                                    color: #000;
                                    padding: 2px 4px;
                                    border-radius: 3px;
                                    font-weight: bold;
                                }

                                .search-highlight.current {
                                    background-color: #FF6B6B;
                                    color: white;
                                    box-shadow: 0 0 5px #FF6B6B;
                                }
                            </style>
                        `;

                        modal.style.display = 'block';

                        // 关键：在模态框显示后渲染数学公式
                        setTimeout(() => {
                            const detailContent = document.getElementById('detailContent');
                            if (detailContent) {
                                renderMath(detailContent);
                            }
                        }, 100);

                        // 绑定搜索相关事件
                        setTimeout(() => {
                            bindDetailSearchEvents();
                        }, 50);

                        // 添加绑定函数
                        function bindDetailSearchEvents() {
                            const searchInput = document.getElementById('detailSearchInput');
                            if (!searchInput) return;

                            // 回车键搜索
                            searchInput.addEventListener('keypress', function(e) {
                                if (e.key === 'Enter') {
                                    e.preventDefault();
                                    searchInDetail();
                                }
                            });

                            // 其他有用的快捷键
                            searchInput.addEventListener('keydown', function(e) {
                                // Escape 清除搜索
                                if (e.key === 'Escape') {
                                    e.preventDefault();
                                    clearSearch();
                                }
                            });

                        }

                        // 更新现有的键盘事件处理，避免冲突
                        function initDetailModalKeyboard() {
                            document.addEventListener('keydown', function(e) {
                                const modal = document.getElementById('detailModal');
                                if (!modal || modal.style.display !== 'block') return;

                                const activeElement = document.activeElement;
                                const isSearchInput = activeElement && activeElement.id === 'detailSearchInput';

                                // 如果在搜索框中，不处理全局快捷键
                                if (isSearchInput) {
                                    // 只处理全局的 Escape 键（关闭模态框）
                                    if (e.key === 'Escape' && !e.target.value) {
                                        closeDetailModal();
                                    }
                                    return;
                                }

                                // 全局快捷键（不在搜索框中时）
                                // Ctrl+F 聚焦搜索框
                                if (e.ctrlKey && e.key === 'f') {
                                    e.preventDefault();
                                    const searchInput = document.getElementById('detailSearchInput');
                                    if (searchInput) {
                                        searchInput.focus();
                                        searchInput.select();
                                    }
                                }

                                // F3 查找下一个
                                if (e.key === 'F3') {
                                    e.preventDefault();
                                    if (searchMatches.length > 0) {
                                        if (e.shiftKey) {
                                            scrollToPrevMatch(); // Shift+F3 上一个
                                        } else {
                                            scrollToNextMatch(); // F3 下一个
                                        }
                                    } else {
                                        // 如果没有搜索结果，先执行搜索
                                        const searchInput = document.getElementById('detailSearchInput');
                                        if (searchInput && searchInput.value.trim()) {
                                            searchInDetail();
                                        }
                                    }
                                }
                            });
                        }

                        // 渲染数学公式
                        if (mathRenderingEnabled) {
                            renderMath(modalContent);
                        }

                        // 自动加载关联知识
                        loadRelatedItems(itemId);
                        showAIRecommendations(itemId);
                    })
                    .catch(error => {
                        console.error('获取详情失败:', error);
                        alert('获取知识详情失败，请稍后重试。');
                    });
            }

            // 新增：加载关联知识函数
            function loadRelatedItems(itemId) {
                const relatedContainer = document.getElementById('relatedItems');
                if (!relatedContainer) return;

                // 显示加载状态
                relatedContainer.innerHTML = `
                    <div style="text-align: center; padding: 20px; color: #888;">
                        <div style="border: 2px solid #f3f3f3; border-top: 2px solid #3498db; border-radius: 50%; width: 20px; height: 20px; animation: spin 1s linear infinite; margin: 0 auto 10px;"></div>
                        加载关联知识中...
                    </div>
                `;

                fetch('/api/related/' + itemId)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(relatedItems => {
                        if (relatedItems.length === 0) {
                            relatedContainer.innerHTML = `
                                <div style="text-align: center; padding: 20px; color: #888; background: var(--bg-tertiary); border-radius: 5px;">
                                    📝 暂无关联知识
                                    <br><small>点击"添加关联"按钮创建第一个关联</small>
                                </div>
                            `;
                            return;
                        }

                        let html = `
                            <div style="margin-bottom: 10px; font-size: 12px; color: #bb86fc;">
                                共找到 ${relatedItems.length} 个关联知识
                            </div>
                            <div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 10px; max-height: 400px; overflow-y: auto;">
                        `;

                        relatedItems.forEach(relatedItem => {
                            html += `
                                <div class="item" style="cursor: pointer; padding: 15px; margin: 0; position: relative;">
                                    <div onclick="showItemDetail(${relatedItem.id})">
                                        <h5 style="margin: 0 0 8px 0; color: var(--accent-primary);">
                                            ${relatedItem.title || '无标题'}
                                            <small style="color: #bb86fc;">(ID: ${relatedItem.id})</small>
                                        </h5>
                                        <small style="color: var(--text-secondary);">
                                            分类: ${relatedItem.category || '未分类'} |
                                            重要性: ${relatedItem.importance_level || 3}/5
                                            ${relatedItem.relationship_type ? ` | 关系: ${relatedItem.relationship_type}` : ''}
                                        </small>
                                        ${relatedItem.summary ? `<div style="margin-top: 8px; font-size: 12px; color: var(--text-secondary);">${relatedItem.summary.substring(0, 100)}...</div>` : ''}
                                    </div>
                                    <div style="margin-top: 10px; display: flex; gap: 5px; justify-content: flex-end;">
                                        <button onclick="event.stopPropagation(); removeRelationship(${itemId}, ${relatedItem.id})"
                                                style="background: #e74c3c; padding: 5px 10px; font-size: 11px; border: none; border-radius: 3px; color: white; cursor: pointer;">
                                            取消关联
                                        </button>
                                    </div>
                                </div>
                            `;
                        });
                        html += '</div>';
                        relatedContainer.innerHTML = html;
                    })
                    .catch(error => {
                        console.error('加载关联知识失败:', error);
                        relatedContainer.innerHTML = `
                            <div style="text-align: center; padding: 20px; color: #e74c3c; background: var(--bg-tertiary); border-radius: 5px;">
                                ❌ 加载关联知识失败
                                <br><small>${error.message}</small>
                            </div>
                        `;
                    });
            }

            function removeRelationship(sourceId, targetId) {
                if (!confirm('确定要取消这个关联吗？')) {
                    return;
                }

                fetch('/api/relationship', {
                    method: 'DELETE',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        source_id: sourceId,
                        target_id: targetId
                    })
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        // 显示成功消息
                        showNotification('关联已取消', 'success');

                        // 重新加载关联列表
                        loadRelatedItems(sourceId);

                        // 刷新知识图谱（如果正在显示）
                        if (window.knowledgeGraphNetwork) {
                            setTimeout(() => {
                                loadKnowledgeGraph();
                            }, 500);
                        }
                    } else {
                        throw new Error(data.error || '取消关联失败');
                    }
                })
                .catch(error => {
                    console.error('取消关联失败:', error);
                    showNotification('取消关联失败: ' + error.message, 'error');
                });
            }


            function showNotification(message, type = 'info') {
                // 移除现有的通知
                const existingNotification = document.getElementById('globalNotification');
                if (existingNotification) {
                    existingNotification.remove();
                }

                // 创建新通知
                const notification = document.createElement('div');
                notification.id = 'globalNotification';
                notification.style.cssText = `
                    position: fixed;
                    top: 20px;
                    right: 20px;
                    padding: 15px 20px;
                    border-radius: 5px;
                    color: white;
                    font-weight: bold;
                    z-index: 10000;
                    box-shadow: 0 4px 12px rgba(0,0,0,0.3);
                    transition: opacity 0.3s ease;
                    max-width: 300px;
                `;

                // 根据类型设置背景色
                const colors = {
                    success: '#27ae60',
                    error: '#e74c3c',
                    warning: '#f39c12',
                    info: '#3498db'
                };
                notification.style.background = colors[type] || colors.info;
                notification.textContent = message;

                document.body.appendChild(notification);

                // 3秒后自动消失
                setTimeout(() => {
                    notification.style.opacity = '0';
                    setTimeout(() => {
                        if (notification.parentNode) {
                            notification.parentNode.removeChild(notification);
                        }
                    }, 300);
                }, 3000);
            }


            function closeDetailModal() {
                const modal = document.getElementById('detailModal');
                if (modal) {
                    modal.style.display = 'none';
                    // 清除搜索状态
                    clearSearch();
                    searchMatches = [];
                    currentMatchIndex = -1;
                }
            }

            // 编辑功能
            function editItem(itemId) {
                fetch('/api/item/' + itemId)
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(item => {
                        showEditModal(item);
                    })
                    .catch(error => {
                        console.error('获取详情失败:', error);
                        alert('获取知识详情失败');
                    });
            }




            function saveItem(itemId) {
                const itemData = {
                    title: document.getElementById('editTitle').value,
                    content: document.getElementById('editContent').value,
                    tags: document.getElementById('editTags').value.split(',').map(tag => tag.trim()),
                    category: document.getElementById('editCategory').value,
                    importance_level: parseInt(document.getElementById('editImportance').value),
                    understanding_level: parseInt(document.getElementById('editUnderstanding').value)
                };

                fetch('/api/update/' + itemId, {
                    method: 'PUT',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(itemData)
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        closeEditModal();
                        refreshCurrentView();
                        showRecentItems();
                        showItemDetail(itemId, true); // 假设showItemDetail支持强制刷新参数
                        refreshDisplayAfterEdit();
                        loadStats();
                    } else {
                        alert('保存失败: ' + data.error);
                    }
                })
                .catch(error => {
                    alert('保存失败: ' + error);
                });
            }

            function closeEditModal() {
                const modal = document.getElementById('editModal');
                if (modal) {
                    modal.style.display = 'none';
                }
            }

            // 插入链接功能
            function insertLocalImage(context = 'add') {
                // 创建文件选择对话框，支持多选
                const fileInput = document.createElement('input');
                fileInput.type = 'file';
                fileInput.accept = 'images/*';
                fileInput.multiple = true; // 启用多选
                fileInput.style.display = 'none';

                fileInput.onchange = function(event) {
                    const files = event.target.files;
                    if (!files || files.length === 0) return;

                    // 提示用户输入 images 目录下的子文件夹路径（对所有图片通用）
                    const relativePathPrompt = `您选择了 ${files.length} 个图片文件。\n\n请输入这些图片在 "images" 目录下的存放路径（例如: project1/screenshots/ 或 产品图/2024年/）：`;
                    const subPath = prompt(relativePathPrompt, "");

                    // 如果用户取消输入，则退出函数
                    if (subPath === null) {
                        document.body.removeChild(fileInput);
                        return;
                    }

                    // 清理用户输入的路径：移除首尾的斜杠和空格
                    const cleanSubPath = subPath.replace(/^\/+|\/+$/g, '').trim();

                    const contentTextarea = document.getElementById(context === 'edit' ? 'editContent' : 'newContent');
                    if (!contentTextarea) {
                        document.body.removeChild(fileInput);
                        return;
                    }

                    let allImageTags = '';

                    // 遍历所有选中的图片文件
                    for (let i = 0; i < files.length; i++) {
                        const file = files[i];

                        // 构建完整的相对路径
                        // 格式：static/images/用户输入的子路径/文件名
                        const fullRelativePath = `static/images/${cleanSubPath ? cleanSubPath + '/' : ''}${file.name}`;
                        const fullUrl = `/${fullRelativePath}`;

                        // 为每个图片创建img标签
                        const imgTag = `<p><img src="${fullUrl}" alt="${file.name}" style="max-width: 100%; height: auto;"></p>\n`;
                        allImageTags += imgTag;
                    }

                    // 一次性插入所有图片标签
                    insertAtCursor(contentTextarea, allImageTags);

                    // 清理临时对象
                    document.body.removeChild(fileInput);
                };

                document.body.appendChild(fileInput);
                fileInput.click();
            }


            function insertFileLink(context = 'add') {
                // 创建文件选择对话框，支持多选
                const fileInput = document.createElement('input');
                fileInput.type = 'file';
                fileInput.multiple = true; // 启用多选
                fileInput.style.display = 'none';

                fileInput.onchange = function(event) {
                    const files = event.target.files;
                    if (!files || files.length === 0) return;

                    // 关键改进：提示用户输入 files 目录下的子文件夹路径（对所有文件通用）
                    const relativePathPrompt = `您选择了 ${files.length} 个文件。\n\n请输入这些文件在 "files" 目录下的存放路径（例如: project1/docs/ 或 财务报告/2024年/）：`;
                    const subPath = prompt(relativePathPrompt, "");

                    // 如果用户取消输入，则退出函数
                    if (subPath === null) {
                        document.body.removeChild(fileInput);
                        return;
                    }

                    // 清理用户输入的路径：移除首尾的斜杠和空格
                    const cleanSubPath = subPath.replace(/^\/+|\/+$/g, '').trim();

                    const contentTextarea = document.getElementById(context === 'edit' ? 'editContent' : 'newContent');
                    if (!contentTextarea) {
                        document.body.removeChild(fileInput);
                        return;
                    }

                    let allFileTags = '';

                    // 遍历所有选中的文件
                    for (let i = 0; i < files.length; i++) {
                        const file = files[i];

                        // 构建完整的相对路径
                        // 格式：static/files/用户输入的子路径/文件名
                        const fullRelativePath = `static/files/${cleanSubPath ? cleanSubPath + '/' : ''}${file.name}`;
                        const fullUrl = `/${fullRelativePath}`;

                        // 为每个文件创建链接
                        const fileTag = `<p><a href="${fullUrl}" target="_blank">📎 ${fullRelativePath}</a></p>\n`;
                        allFileTags += fileTag;
                    }

                    // 一次性插入所有文件链接
                    insertAtCursor(contentTextarea, allFileTags);

                    // 清理临时对象
                    document.body.removeChild(fileInput);
                };

                document.body.appendChild(fileInput);
                fileInput.click();
            }


            function insertAtCursor(textarea, text) {
                const start = textarea.selectionStart;
                const end = textarea.selectionEnd;
                textarea.value = textarea.value.substring(0, start) + text + textarea.value.substring(end);
                textarea.selectionStart = textarea.selectionEnd = start + text.length;
                textarea.focus();
            }

            // 文件导入功能
            function importFromFile() {
                const fileInput = document.getElementById('importFile');
                const file = fileInput.files[0];

                if (!file) {
                    document.getElementById('importResult').innerHTML = '<span class="error">请选择文件</span>';
                    return;
                }

                const formData = new FormData();
                formData.append('file', file);

                document.getElementById('importResult').innerHTML = '<span>导入中...</span>';

                fetch('/api/import', {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        document.getElementById('importResult').innerHTML =
                            `<span class="success">导入成功！共导入 ${data.imported_count} 条知识</span>`;
                        fileInput.value = '';
                        showRecentItems();
                        loadStats();
                    } else {
                        document.getElementById('importResult').innerHTML =
                            `<span class="error">导入失败: ${data.error}</span>`;
                    }
                })
                .catch(error => {
                    document.getElementById('importResult').innerHTML =
                        `<span class="error">导入失败: ${error}</span>`;
                });
            }

            // 删除功能
            function confirmDelete(itemId) {
                if (!confirm('确定要删除这个知识条目吗？此操作不可撤销！')) {
                    return;
                }

                fetch('/api/delete/' + itemId, {
                    method: 'DELETE'
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        showRecentItems();
                        refreshCurrentView();
                        loadStats();
                    } else {
                        alert('删除失败: ' + (data.error || '未知错误'));
                    }
                })
                .catch(error => {
                    alert('删除失败: ' + error.message);
                });
            }

            // 添加新知识功能
            function addNewItem() {
                const title = document.getElementById('newTitle').value.trim();
                const content = document.getElementById('newContent').value.trim();
                const tagsInput = document.getElementById('newTags').value;
                const tags = tagsInput ? tagsInput.split(',').map(tag => tag.trim()).filter(tag => tag) : [];
                const category = document.getElementById('newCategory').value.trim() || '未分类';
                const importance = parseInt(document.getElementById('newImportance').value) || 3;
                const understanding = parseInt(document.getElementById('newUnderstanding').value) || 3;

                const addResult = document.getElementById('addResult');
                if (!addResult) return;

                if (!title || !content) {
                    addResult.innerHTML = '<span class="error">标题和内容不能为空</span>';
                    return;
                }

                const data = {
                    title,
                    content,
                    tags,
                    category,
                    importance_level: importance,
                    understanding_level: understanding
                };

                fetch('/api/add', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify(data)
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        addResult.innerHTML = '<span class="success">添加成功!</span>';
                        // 重置表单
                        document.getElementById('newTitle').value = '';
                        document.getElementById('newContent').value = '';
                        document.getElementById('newTags').value = '';
                        refreshCurrentView();
                        loadStats();
                        showRecentItems();
                        setTimeout(() => {
                            addResult.innerHTML = '';
                        }, 3000);
                    } else {
                        addResult.innerHTML = `<span class="error">添加失败: ${data.error || '未知错误'}</span>`;
                    }
                })
                .catch(error => {
                    addResult.innerHTML = `<span class="error">添加失败: ${error.message || '网络错误'}</span>`;
                });
            }

            // 文件处理函数
            function handleDragOver(event) {
                event.preventDefault();
                event.currentTarget.classList.add('dragover');
            }

            function handleFileDrop(event) {
                event.preventDefault();
                event.currentTarget.classList.remove('dragover');
                const files = event.dataTransfer.files;
                handleFileUpload(files);
            }

            function handleFileUpload(files) {
                alert('文件上传功能正在开发中，当前版本支持插入文件链接');
            }

            // 示例功能
            function showMathExamples() {
                const examples = [
                    {
                        title: "勾股定理",
                        content: "在直角三角形中，斜边的平方等于两直角边的平方和：$$a^2 + b^2 = c^2$$",
                        category: "数学",
                        tags: "几何,定理"
                    },
                    {
                        title: "欧拉公式",
                        content: "数学中最优美的公式之一：$$e^{i\\pi} + 1 = 0$$",
                        category: "数学",
                        tags: "公式,复数"
                    }
                ];

                let html = '<h3>数学公式示例</h3>';
                examples.forEach((example, index) => {
                    html += `
                        <div class="item">
                            <h4>${example.title}</h4>
                            <div class="content">${example.content}</div>
                            <small>分类: ${example.category} | 标签: ${example.tags}</small>
                        </div>
                    `;
                });

                document.getElementById('results').innerHTML = html;
                renderAllMath();
            }

            function showShortcutHelp() {
                alert(`快捷键帮助：
            Ctrl+F - 搜索
            Ctrl+A - 显示全部
            Ctrl+R - 今日复习
            Ctrl+C - 显示分类
            Ctrl+O - 显示标签
            Ctrl+E - 批量编辑（选中条目时）
            Ctrl+S - 添加知识
            Ctrl+G - 知识图谱
            Ctrl+I - 文件导入
            Ctrl+Enter - 提交表单
            F1 - 显示此帮助
            ESC - 关闭弹窗`);
            }

            // 快捷键支持
            document.addEventListener('keydown', function(e) {
                // Ctrl 快捷键
                if (e.ctrlKey) {
                    e.preventDefault();
                    switch(e.key) {
                        case 'f': searchItems(); break;
                        case 'a': showAllItems(); break;
                        case 'r': showTodayReviews(); break;
                        case 's':
                            const titleInput = document.getElementById('newTitle');
                            if (titleInput) titleInput.focus();
                            break;
                        case 'g': switchTab('graph'); break;
                        case 'i':
                            const importInput = document.getElementById('importFile');
                            if (importInput) importInput.click();
                            break;
                        case 'Enter': addNewItem(); break;
                        case 'c': // Ctrl+C 显示分类
                            showCategories();
                            break;
                        case 't': // Ctrl+T 显示标签
                            showTags();
                            break;
                        case 'e': // Ctrl+E 批量编辑
                            if (window.selectedItems && window.selectedItems.size > 0) {
                                showBatchEditModal();
                            } else {
                                showNotification('请先选择要编辑的条目', 'warning');
                            }
                            break;
                    }
                }
                // 功能键
                else if (e.key === 'F1') {
                    e.preventDefault();
                    showShortcutHelp();
                }
                // Escape 键
                else if (e.key === 'Escape') {
                    closeDetailModal();
                    closeEditModal();
                }
            });

            // 回车键搜索
            const searchInput = document.getElementById('searchInput');
            if (searchInput) {
                searchInput.addEventListener('keypress', function(e) {
                    if (e.key === 'Enter') searchItems();
                });
            }

            // 导出图谱数据
            function exportGraphData() {
                if (currentKnowledgeGraph) {
                    const dataStr = JSON.stringify(currentKnowledgeGraph, null, 2);
                    const blob = new Blob([dataStr], {type: 'application/json'});
                    const url = URL.createObjectURL(blob);
                    const a = document.createElement('a');
                    a.href = url;
                    a.download = 'knowledge_graph.json';
                    a.click();
                    URL.revokeObjectURL(url);
                } else {
                    alert('请先加载知识图谱');
                }
            }

            // === 完全重写键盘事件处理 ===

            // 首先移除所有现有的键盘事件监听器
            function removeAllKeyboardListeners() {
                // 创建一个新的body元素来替换旧的，这样可以移除所有事件监听器
                const oldBody = document.body;
                const newBody = document.createElement('body');
                newBody.innerHTML = oldBody.innerHTML;
                oldBody.parentNode.replaceChild(newBody, oldBody);
                return newBody;
            }

            // 新的键盘事件处理系统
            function initKeyboardHandling() {
                // 全局键盘事件处理
                document.addEventListener('keydown', function(e) {
                    const activeElement = document.activeElement;
                    const isTextInput = activeElement && (
                        activeElement.tagName === 'INPUT' ||
                        activeElement.tagName === 'TEXTAREA'
                    );

                // 如果在文本输入框中
                if (isTextInput) {
                    // 特殊处理AI聊天输入框 - 完全放行所有字符
                    if (activeElement.id === 'chatInput') {
                        // 只处理Enter键发送，其他所有按键都不阻止
                        if (e.key === 'Enter') {
                            e.preventDefault();
                            sendChatMessage();
                        }
                        return; // 重要：直接返回，不阻止其他按键
                    }

                    // 其他输入框的处理逻辑保持不变
                    handleTextInputShortcuts(e, activeElement);
                    return;
                }

                // 非文本输入区域的全局快捷键
                handleGlobalShortcuts(e);
            });
            }

            // 处理文本输入区域的快捷键
            function handleTextInputShortcuts(e, activeElement) {
                // 搜索框的回车搜索
                if (e.key === 'Enter' && activeElement.id === 'searchInput') {
                    e.preventDefault();
                    searchItems();
                    return;
                }

                // 内容框的Ctrl+Enter提交
                if (e.ctrlKey && e.key === 'Enter' &&
                    (activeElement.id === 'newContent' || activeElement.id === 'editContent')) {
                    e.preventDefault();
                    addNewItem();
                    return;
                }

                // 对于其他所有快捷键（Ctrl+C, Ctrl+V等），完全不做任何处理
                // 让浏览器执行默认行为
            }

            // 处理全局快捷键
            function handleGlobalShortcuts(e) {
                if (e.ctrlKey) {
                    e.preventDefault(); // 只在全局功能键时阻止默认行为

                    switch(e.key.toLowerCase()) {
                        case 'f': searchItems(); break;
                        case 'a': showAllItems(); break;
                        case 'r': showTodayReviews(); break;
                        case 's':
                            const titleInput = document.getElementById('newTitle');
                            if (titleInput) titleInput.focus();
                            break;
                        case 'g': switchTab('graph'); break;
                        case 'i':
                            const importInput = document.getElementById('importFile');
                            if (importInput) importInput.click();
                            break;
                        case 'enter': addNewItem(); break;
                        case 'c': // Ctrl+C 显示分类
                            showCategories();
                            break;
                        case 'o': // Ctrl+O 显示标签
                            showTags();
                            break;
                        case 'e': // Ctrl+E 批量编辑
                            if (window.selectedItems && window.selectedItems.size > 0) {
                                showBatchEditModal();
                            } else {
                                showNotification('请先选择要编辑的条目', 'warning');
                            }
                            break;
                    }
                } else if (e.key === 'F1') {
                    e.preventDefault();
                    showShortcutHelp();
                } else if (e.key === 'Escape') {
                    closeDetailModal();
                    closeEditModal();
                }
            }

            // 确保输入框没有任何阻止事件的处理程序
            function setupCleanInputs() {
                // 获取所有输入框
                const inputs = document.querySelectorAll('input[type="text"], textarea');

                inputs.forEach(input => {
                    // 移除所有事件监听器（通过替换元素）
                    const newInput = input.cloneNode(true);
                    input.parentNode.replaceChild(newInput, input);

                    // 为特定输入框添加必要的事件处理
                    setupInputEventHandlers(newInput);
                });
            }

            // 为输入框设置必要的事件处理
            function setupInputEventHandlers(input) {
                if (input.id === 'searchInput') {
                    input.addEventListener('keydown', function(e) {
                        if (e.key === 'Enter') {
                            e.preventDefault();
                            searchItems();
                        }
                        // 不处理其他按键，让浏览器处理
                    });
                } else if (input.id === 'newContent' || input.id === 'editContent') {
                    input.addEventListener('keydown', function(e) {
                        if (e.ctrlKey && e.key === 'Enter') {
                            e.preventDefault();
                            addNewItem();
                        }
                        // 不处理其他按键，让浏览器处理
                    });
                }
                // 其他输入框不添加任何事件处理，让浏览器处理所有快捷键
            }

        // 页面初始化
        document.addEventListener('DOMContentLoaded', function() {
            console.log('页面加载完成，初始化知识库...');

            // 初始化数据库信息显示
            loadCurrentDatabaseInfo();

            updateMathButton();
            updateMarkdownButton();

            // 确保关键函数可用
            if (typeof showRecentItems === 'undefined') {
                window.showRecentItems = function() {
                    fetch('/api/recent')
                        .then(response => response.json())
                        .then(data => {
                            console.log('接收到数据:', data);
                            if (window.displayResults) {
                                window.displayResults(data, '最近知识条目');
                            }
                        })
                        .catch(error => {
                            console.error('加载失败:', error);
                            if (window.displayResults) {
                                window.displayResults([], '加载失败');
                            }
                        });
                };
            }

            loadStats();
            showRecentItems();
            loadCategories();
            addCategoryFilterToGraph();

            setTimeout(() => {
                if (typeof renderAllMath === 'function') {
                    renderAllMath();
                }
            }, 100);
        });

            // 快捷键测试函数
            function testShortcuts() {
                console.log('=== 快捷键系统状态 ===');
                console.log('✓ 标准快捷键 (Ctrl+C, Ctrl+V, Ctrl+X, Ctrl+A) 应该正常工作');
                console.log('✓ 功能快捷键 (Ctrl+F, Ctrl+A, Ctrl+R, Ctrl+S, Ctrl+G, Ctrl+I) 应该正常工作');
                console.log('✓ 文本输入框中的标准快捷键不受影响');
            }

            // 确保所有必要的函数都在全局作用域中
            // 如果这些函数不在全局作用域，需要将它们提升到全局
            window.searchItems = searchItems;
            window.showAllItems = showAllItems;
            window.showTodayReviews = showTodayReviews;
            window.switchTab = switchTab;
            window.addNewItem = addNewItem;
            window.showShortcutHelp = showShortcutHelp;
            window.closeDetailModal = closeDetailModal;
            window.closeEditModal = closeEditModal;

            // 如果这些函数是通过其他方式定义的，确保它们可用
            if (typeof searchItems === 'undefined') {
                window.searchItems = function() {
                    const query = document.getElementById('searchInput').value;
                    if (!query) {
                        showRecentItems();
                        return;
                    }
                    fetch('/api/search?q=' + encodeURIComponent(query))
                        .then(response => response.json())
                        .then(data => displayResults(data, `搜索结果: "${query}"`))
                        .catch(error => {
                            console.error('搜索错误:', error);
                            displayResults([], `搜索失败: ${error.message}`);
                        });
                };
            }

            // 类似地，确保其他函数也有定义
            if (typeof showAllItems === 'undefined') {
                window.showAllItems = function() {
                    fetch('/api/search?q=')
                        .then(response => response.json())
                        .then(data => displayResults(data, '所有知识条目'))
                        .catch(error => {
                            console.error('Error:', error);
                            displayResults([], '加载失败');
                        });
                };
            }


            // 修改模态框显示函数，确保新创建的输入框也能正确处理
            function showEditModal(item) {
                const modal = document.getElementById('editModal');
                const modalContent = document.getElementById('editModalContent');

                if (!modal || !modalContent) return;

                modalContent.innerHTML = `
                    <h2>编辑知识条目</h2>
                    <div style="background: var(--bg-tertiary); padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                        <strong>💡 提示：</strong> 内容支持 Markdown 格式：
                        <ul style="margin: 10px 0; padding-left: 20px; font-size: 14px;">
                            <li># 标题</li>
                            <li>**粗体** 和 *斜体*</li>
                            <li>- 列表项</li>
                            <li>[链接](http://example.com)</li>
                            <li>\`代码\` 和 \`\`\`代码块\`\`\`</li>
                            <li>> 引用块</li>
                        </ul>
                    </div>
                    <div class="form-grid">
                        <div>
                            <input type="text" id="editTitle" value="${item.title || ''}" placeholder="标题">
                            <textarea id="editContent" placeholder="内容" style="height: 200px;">${item.content || ''}</textarea>
                            <div style="margin-top: 10px;">
                                <button type="button" onclick="insertLocalImage('edit')" style="background: #6c757d;">插入图片链接</button>
                                <button type="button" onclick="insertFileLink('edit')" style="background: #6c757d;">插入文件链接</button>
                                <button type="button" onclick="uploadImages()" style="background: #3498db;">上传图片</button>
                                <button type="button" onclick="uploadFiles()" style="background: #3498db;">上传文件</button>
                                <button type="button" onclick="importTextToEditor('edit')" style="background: #9b59b6;">📄导入文件</button>
                            </div>
                            <!-- 添加隐藏的文件输入框 -->
                            <input type="file" id="imageUploadInput" accept="image/*" multiple style="display: none;" onchange="handleImageUpload(this.files, getCurrentContext())">
                            <input type="file" id="fileUploadInput" multiple style="display: none;" onchange="handleFileUpload(this.files, 'edit')">
                            <input type="file" id="textEditorImportInput" accept=".txt,.md,.tex,.rst,.vim,.csv,.py,.js,.java,.cpp,.c,.html,.css,.json,.yaml,.yml,.xml,.sty,.bib,.def" multiple style="display: none;" onchange="handleTextEditorImport(this.files, 'edit')">
                        </div>
                        <div>
                            <input type="text" id="editTags" value="${item.tag_names || ''}" placeholder="标签">
                            <input type="text" id="editCategory" value="${item.category || ''}" placeholder="分类">
                            <div style="margin: 15px 0;">
                                <label>重要程度:</label>
                                <select id="editImportance">
                                    ${[1,2,3,4,5].map(i =>
                                        `<option value="${i}" ${i == (item.importance_level || 3) ? 'selected' : ''}>${i}</option>`
                                    ).join('')}
                                </select>
                            </div>
                            <div style="margin: 15px 0;">
                                <label>理解程度:</label>
                                <select id="editUnderstanding">
                                    ${[1,2,3,4,5].map(i =>
                                        `<option value="${i}" ${i == (item.understanding_level || 3) ? 'selected' : ''}>${i}</option>`
                                    ).join('')}
                                </select>
                            </div>
                        </div>
                    </div>
                    <div style="text-align: right; margin-top: 20px;">
                        <button type="button" onclick="closeEditModal()" style="background: #666;">取消</button>
                        <button type="button" onclick="saveItem(${item.id || 0})" class="btn-success">保存更改</button>
                    </div>
                `;

                modal.style.display = 'block';
            }


            // 添加快捷键测试功能
            function testShortcuts() {
                console.log('=== 快捷键测试 ===');
                console.log('现在应该可以正常使用:');
                console.log('- Ctrl+C (复制)');
                console.log('- Ctrl+V (粘贴)');
                console.log('- Ctrl+X (剪切)');
                console.log('- Ctrl+A (全选)');
                console.log('- Ctrl+Z (撤销)');
                console.log('如果仍然不行，请检查浏览器控制台是否有错误信息');
            }

            // 在初始化完成后测试
            setTimeout(testShortcuts, 1000);


            // 添加显示最近条目的函数
            function showRecentItems() {
                fetch('/api/recent')
                    .then(response => {
                        if (!response.ok) {
                            throw new Error(`HTTP error! status: ${response.status}`);
                        }
                        return response.json();
                    })
                    .then(data => displayResults(data, '最近知识条目'))
                    .catch(error => {
                        console.error('加载最新条目失败:', error);
                        displayResults([], '加载失败');
                    });
            }

            // 加载分类选项
            function loadCategories() {
                const categories = ['未分类', 'AI', '数学', '编程', '读书笔记', '工作项目', '技术笔记'];
                const select = document.getElementById('categoryFilter');
                if (!select) return;

                categories.forEach(cat => {
                    const option = document.createElement('option');
                    option.value = cat;
                    option.textContent = cat;
                    select.appendChild(option);
                });
            }

            // === 数学公式渲染控制 ===
            let mathRenderingEnabled = true;

            // === Markdown 渲染控制 ===
            let markdownRenderingEnabled = true;

            function toggleMathRendering() {
                mathRenderingEnabled = !mathRenderingEnabled;
                updateMathButton();
                if (mathRenderingEnabled) renderAllMath();
            }

            function toggleMarkdownRendering() {
                markdownRenderingEnabled = !markdownRenderingEnabled;
                updateMarkdownButton();
                refreshDisplay(); // 刷新显示
            }

            function updateMathButton() {
                const btn = document.getElementById('mathToggleBtn');
                btn.innerHTML = mathRenderingEnabled ? '🔢 渲染公式' : '🔢 不渲染公式';
                btn.style.background = mathRenderingEnabled ? '#20c997' : '#6c757d';
            }

            function updateMarkdownButton() {
                const btn = document.getElementById('markdownToggleBtn');
                btn.innerHTML = markdownRenderingEnabled ? '📝 渲染Markdown' : '📝 不渲染Markdown';
                btn.style.background = markdownRenderingEnabled ? '#17a2b8' : '#6c757d';
            }

            function refreshDisplay() {
                // 重新显示当前结果来应用设置
                const searchInput = document.getElementById('searchInput');
                if (searchInput && searchInput.value) {
                    searchItems();
                } else {
                    showRecentItems();
                }
            }

            // 添加关联功能
            function addRelationship(sourceId) {
                const targetId = prompt('请输入要关联的知识条目ID:');
                if (!targetId) return;

                const relationshipType = prompt('请输入关联类型 (relates_to, depends_on, similar_to, part_of):', 'relates_to');
                if (!relationshipType) return;

                fetch('/api/relationship', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        source_id: parseInt(sourceId),
                        target_id: parseInt(targetId),
                        relationship_type: relationshipType
                    })
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        alert('关联创建成功！');
                        loadRelatedItems(sourceId); // 刷新关联列表
                        if (window.knowledgeGraphNetwork) {
                            loadKnowledgeGraph(); // 刷新知识图谱
                        }
                    } else {
                        alert('关联创建失败: ' + (data.error || '未知错误'));
                    }
                })
                .catch(error => {
                    alert('关联创建失败: ' + error.message);
                });
            }


            function toggleItemSelection(itemId) {
                console.log("切换选择:", itemId); // 调试信息

                if (window.selectedItems.has(itemId)) {
                    window.selectedItems.delete(itemId);
                } else {
                    window.selectedItems.add(itemId);
                }

                console.log("当前选中的条目:", Array.from(window.selectedItems)); // 调试信息
                updateSelectionUI();

                // 更新UI显示
                const itemElement = document.querySelector(`.item[onclick="toggleItemSelection(${itemId})"]`);
                if (itemElement) {
                    if (window.selectedItems.has(itemId)) {
                        itemElement.classList.add('item-selected');
                    } else {
                        itemElement.classList.remove('item-selected');
                    }
                }
            }

            function updateSelectionUI() {
                const selectionInfo = document.getElementById('selectionInfo');
                if (!selectionInfo) return;

                const selectedCount = window.selectedItems.size;

                if (selectedCount > 0) {
                    selectionInfo.innerHTML = `
                        <div style="background: #3498db; padding: 15px; border-radius: 8px; margin: 15px 0; border-left: 5px solid #2980b9;">
                            <div style="display: flex; justify-content: space-between; align-items: center;">
                                <div>
                                    <strong style="font-size: 16px;">✅ 已选择 ${selectedCount} 个知识条目</strong>
                                    <div style="font-size: 12px; margin-top: 5px;">
                                        选中的条目ID: ${Array.from(window.selectedItems).join(', ')}
                                    </div>
                                </div>
                                <div style="display: flex; gap: 10px;">
                                    <button onclick="analyzeWithAI()" style="background: #9b59b6; padding: 8px 16px;">AI分析</button>
                                    <button onclick="showBatchEditModal()" style="background: #2ecc71; padding: 8px 16px;">📝 批量编辑</button>
                                    <button onclick="batchDelete()" style="background: #e74c3c; padding: 8px 16px;">批量删除</button>
                                    <button onclick="batchCreateRelationships()" style="background: #9b59b6; padding: 8px 16px;">创建关联</button>
                                    <button onclick="exportSelectedItems()" style="background: #27ae60; padding: 8px 16px;">📥 导出条目</button>
                                    <button onclick="clearSelection()" style="background: #95a5a6; padding: 8px 16px;">清除选择</button>
                                </div>
                            </div>
                        </div>
                    `;
                } else {
                    selectionInfo.innerHTML = `
                        <div style="background: #f39c12; padding: 10px; border-radius: 5px; margin: 10px 0; text-align: center;">
                            💡 提示：点击知识条目可以选中（用于AI分析和批量操作）
                        </div>
                    `;
                }
            }

            // 显示批量编辑模态框
            function showBatchEditModal() {
                const selectedCount = window.selectedItems.size;
                if (selectedCount === 0) {
                    showNotification('请先选择要编辑的条目', 'warning');
                    return;
                }

                const modalHtml = `
                    <div id="batchEditModal" class="modal" style="display: block;">
                        <div class="modal-content" style="max-width: 600px; max-height: 80vh; margin: 50px auto;">
                            <span class="close" onclick="closeBatchEditModal()">&times;</span>
                            <h3>📝 批量编辑 ${selectedCount} 个条目</h3>

                            <div style="margin: 20px 0;">
                                <div style="background: var(--bg-tertiary); padding: 15px; border-radius: 8px; margin-bottom: 20px;">
                                    <h4>🏷️ 标签操作</h4>

                                    <div style="margin-bottom: 15px;">
                                        <label>操作类型:</label>
                                        <select id="tagOperation" onchange="updateTagOperation()" style="width: 100%; padding: 8px; margin: 5px 0;">
                                            <option value="add_tags">添加标签</option>
                                            <option value="remove_tags">移除标签</option>
                                            <option value="set_tags">设置标签（覆盖）</option>
                                        </select>
                                    </div>

                                    <div>
                                        <label>标签（用逗号分隔）:</label>
                                        <input type="text" id="batchTags" placeholder="例如: 重要,待复习,项目A"
                                               style="width: 100%; padding: 8px; margin: 5px 0;">
                                        <small style="color: #bbb;">多个标签用逗号分隔</small>
                                    </div>
                                </div>

                                <div style="background: var(--bg-tertiary); padding: 15px; border-radius: 8px;">
                                    <h4>📂 分类操作</h4>
                                    <div>
                                        <label>设置分类:</label>
                                        <input type="text" id="batchCategory" list="categorySuggestions"
                                               placeholder="输入分类名称" style="width: 100%; padding: 8px; margin: 5px 0;">
                                        <datalist id="categorySuggestions">
                                            <option value="未分类">
                                            <option value="AI">
                                            <option value="数学">
                                            <option value="编程">
                                            <option value="读书笔记">
                                            <option value="工作项目">
                                            <option value="技术笔记">
                                        </datalist>
                                    </div>
                                </div>
                            </div>

                            <div style="display: flex; justify-content: space-between; margin-top: 20px;">
                                <button onclick="closeBatchEditModal()" style="background: #95a5a6; padding: 10px 20px;">取消</button>
                                <button onclick="executeBatchEdit()" style="background: #2ecc71; padding: 10px 20px;">执行批量编辑</button>
                            </div>

                            <div id="batchEditResult" style="margin-top: 15px;"></div>
                        </div>
                    </div>
                `;

                // 移除已存在的模态框
                const existingModal = document.getElementById('batchEditModal');
                if (existingModal) {
                    existingModal.remove();
                }

                document.body.insertAdjacentHTML('beforeend', modalHtml);
            }

            // 关闭批量编辑模态框
            function closeBatchEditModal() {
                const modal = document.getElementById('batchEditModal');
                if (modal) {
                    modal.remove();
                }
            }

            // 更新标签操作提示
            function updateTagOperation() {
                const operation = document.getElementById('tagOperation').value;
                const tagsInput = document.getElementById('batchTags');
                const examples = {
                    'add_tags': '例如: 重要,待复习,项目A',
                    'remove_tags': '例如: 临时,旧版本,待删除',
                    'set_tags': '例如: 机器学习,Python,算法'
                };
                tagsInput.placeholder = examples[operation] || '例如: 标签1,标签2,标签3';
            }

            // 执行批量编辑
            function executeBatchEdit() {
                const selectedItems = Array.from(window.selectedItems);
                const tagOperation = document.getElementById('tagOperation').value;
                const tagsInput = document.getElementById('batchTags').value.trim();
                const categoryInput = document.getElementById('batchCategory').value.trim();

                const resultDiv = document.getElementById('batchEditResult');

                // 验证输入
                if (!tagsInput && !categoryInput) {
                    resultDiv.innerHTML = '<span class="error">请至少填写标签或分类</span>';
                    return;
                }

                // 准备数据
                const data = {
                    item_ids: selectedItems,
                    operation: tagOperation,
                    tags: tagsInput ? tagsInput.split(',').map(tag => tag.trim()).filter(tag => tag) : [],
                    category: categoryInput
                };

                // 显示加载状态
                resultDiv.innerHTML = '<span style="color: #3498db;">🔄 执行中...</span>';

                // 发送请求
                fetch('/api/batch_edit', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                    },
                    body: JSON.stringify(data)
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    if (data.success) {
                        resultDiv.innerHTML = `
                            <span class="success">
                                ✅ 批量编辑完成！<br>
                                成功: ${data.success_count} 个条目<br>
                                失败: ${data.failed_count} 个条目
                            </span>
                        `;

                        // 3秒后关闭模态框并刷新显示
                        setTimeout(() => {
                            closeBatchEditModal();
                            clearSelection();
                            refreshCurrentView();
                            loadStats();
                            showNotification(`批量编辑完成，成功更新 ${data.success_count} 个条目`, 'success');
                        }, 2000);

                    } else {
                        resultDiv.innerHTML = `<span class="error">❌ 批量编辑失败: ${data.error}</span>`;
                    }
                })
                .catch(error => {
                    console.error('批量编辑失败:', error);
                    resultDiv.innerHTML = `<span class="error">❌ 批量编辑失败: ${error.message}</span>`;
                });
            }


            function clearSelection() {
                selectedItems.clear();
                updateSelectionUI();
                // 移除所有项目的选中状态
                document.querySelectorAll('.item-selected').forEach(el => {
                    el.classList.remove('item-selected');
                });
            }

            function batchDelete() {
                if (selectedItems.size === 0) return;
                if (!confirm(`确定要删除选中的 ${selectedItems.size} 个项目吗？`)) return;

                const promises = Array.from(selectedItems).map(itemId =>
                    fetch('/api/delete/' + itemId, { method: 'DELETE' })
                );

                Promise.all(promises)
                    .then(() => {
                        alert('批量删除完成！');
                        clearSelection();
                        showRecentItems();
                        loadStats();
                    })
                    .catch(error => {
                        alert('批量删除失败: ' + error.message);
                    });
            }

            function batchCreateRelationships() {
                if (selectedItems.size < 2) {
                    alert('请至少选择2个项目来创建关联');
                    return;
                }

                const itemIds = Array.from(selectedItems);
                const relationshipType = prompt('请输入关联类型:', 'relates_to');
                if (!relationshipType) return;

                // 创建所有可能的关联对
                const promises = [];
                for (let i = 0; i < itemIds.length; i++) {
                    for (let j = i + 1; j < itemIds.length; j++) {
                        promises.push(
                            fetch('/api/relationship', {
                                method: 'POST',
                                headers: { 'Content-Type': 'application/json' },
                                body: JSON.stringify({
                                    source_id: itemIds[i],
                                    target_id: itemIds[j],
                                    relationship_type: relationshipType
                                })
                            })
                        );
                    }
                }

                Promise.all(promises)
                    .then(() => {
                        clearSelection();
                        if (window.knowledgeGraphNetwork) {
                            loadKnowledgeGraph();
                        }
                    })
                    .catch(error => {
                        alert('创建关联失败: ' + error.message);
                    });
            }

            // 修改现有的渲染函数
            const originalRenderAllMath = renderAllMath;
            window.renderAllMath = function() {
                if (mathRenderingEnabled) originalRenderAllMath();
            };

            const originalRenderMath = renderMath;
            window.renderMath = function(element) {
                if (mathRenderingEnabled) originalRenderMath(element);
            };


            // 图片上传功能
            function uploadImages() {
                document.getElementById('imageUploadInput').click();
            }

            // 文件上传功能
            function uploadFiles() {
                document.getElementById('fileUploadInput').click();
            }

            // 处理图片上传
            function handleImageUpload(files, context = 'add') {
                if (!files || files.length === 0) return;

                uploadFilesToServer(files, 'images', function(fileUrls, fileDetails) {
                    const contentTextarea = document.getElementById(context === 'edit' ? 'editContent' : 'newContent');
                    if (!contentTextarea) return;

                    let imageTags = '';
                    fileUrls.forEach((url, index) => {
                        // 使用原始文件名（现在包含中文）
                        const fileName = fileDetails && fileDetails[index] ?
                            fileDetails[index].original_name :
                            decodeURIComponent(url.split('/').pop());

                        imageTags += `<p><img src="${url}" alt="${fileName}" style="max-width: 100%; height: auto;"></p>\n`;
                    });

                    insertAtCursor(contentTextarea, imageTags);
                });
            }

            // 处理文件上传
            function handleFileUpload(files, context = 'add') {
                if (!files || files.length === 0) return;

                uploadFilesToServer(files, 'files', function(fileUrls, fileDetails) {
                    const contentTextarea = document.getElementById(context === 'edit' ? 'editContent' : 'newContent');
                    if (!contentTextarea) return;

                    let fileLinks = '';
                    fileUrls.forEach((url, index) => {
                        // 使用原始文件名（现在包含中文）
                        const fileName = fileDetails && fileDetails[index] ?
                            fileDetails[index].original_name :
                            decodeURIComponent(url.split('/').pop());

                        fileLinks += `<p><a href="${url}" target="_blank">📎 ${fileName}</a></p>\n`;
                    });

                    insertAtCursor(contentTextarea, fileLinks);
                });
            }

            // 通用的文件上传函数
            function uploadFilesToServer(files, fileType, callback) {
                const formData = new FormData();

                // 添加所有文件到FormData
                for (let i = 0; i < files.length; i++) {
                    formData.append('files', files[i]);
                }

                // 添加文件类型信息
                formData.append('file_type', fileType);

                // 显示上传进度
                showUploadProgress(files.length);

                fetch('/api/upload', {
                    method: 'POST',
                    body: formData
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    hideUploadProgress();
                    if (data.success) {
                        callback(data.file_urls || []);
                            showNotification(`成功上传 ${data.file_urls.length} 个文件`, 'success');
                    } else {
                        throw new Error(data.error || '上传失败');
                    }
                })
                .catch(error => {
                    hideUploadProgress();
                    console.error('上传失败:', error);
                    showNotification('上传失败: ' + error.message, 'error');
                });
            }

            // 显示上传进度
            function showUploadProgress(fileCount) {
                // 移除现有的进度条
                const existingProgress = document.getElementById('uploadProgress');
                if (existingProgress) {
                    existingProgress.remove();
                }

                // 创建进度条
                const progressDiv = document.createElement('div');
                progressDiv.id = 'uploadProgress';
                progressDiv.style.cssText = `
                    position: fixed;
                    top: 50%;
                    left: 50%;
                    transform: translate(-50%, -50%);
                    background: var(--bg-secondary);
                    padding: 20px;
                    border-radius: 10px;
                    box-shadow: 0 4px 20px rgba(0,0,0,0.5);
                    z-index: 10000;
                    text-align: center;
                    border: 2px solid var(--accent-primary);
                `;

                progressDiv.innerHTML = `
                    <div style="margin-bottom: 10px;">
                        <div style="border: 2px solid #f3f3f3; border-top: 2px solid #3498db; border-radius: 50%; width: 30px; height: 30px; animation: spin 1s linear infinite; margin: 0 auto;"></div>
                    </div>
                    <div>正在上传 ${fileCount} 个文件...</div>
                    <style>
                        @keyframes spin {
                            0% { transform: rotate(0deg); }
                            100% { transform: rotate(360deg); }
                        }
                    </style>
                `;

                document.body.appendChild(progressDiv);
            }

            // 隐藏上传进度
            function hideUploadProgress() {
                const progressDiv = document.getElementById('uploadProgress');
                if (progressDiv) {
                    progressDiv.remove();
                }
            }

            // 修改现有的 insertAtCursor 函数，确保它在全局可用
            window.insertAtCursor = function(textarea, text) {
                const start = textarea.selectionStart;
                const end = textarea.selectionEnd;
                textarea.value = textarea.value.substring(0, start) + text + textarea.value.substring(end);
                textarea.selectionStart = textarea.selectionEnd = start + text.length;
                textarea.focus();
            };

            // AI功能函数
            function analyzeWithAI() {
                // 确保使用全局的selectedItems
                const selectedItems = Array.from(window.selectedItems || []);

                console.log("选中的条目:", selectedItems); // 调试信息

                if (selectedItems.length === 0) {
                    alert('请先选择要分析的知识条目（点击知识条目可以选中）');
                    return;
                }

                const itemId = selectedItems[0]; // 取第一个选中的条目
                console.log("分析条目ID:", itemId); // 调试信息

                showAILoading('正在分析内容...');

                fetch('/api/ai/analyze/' + itemId)
                    .then(response => response.json())
                    .then(data => {
                        hideAILoading();
                        if (data.error) {
                            showAIError(data.error);
                        } else {
                            displayAIAnalysis(data);
                        }
                    })
                    .catch(error => {
                        hideAILoading();
                        showAIError('分析失败: ' + error.message);
                    });
            }

            function generateQuestions() {
                const selectedItems = Array.from(window.selectedItems || []);
                console.log("选中的条目:", selectedItems); // 调试信息

                if (selectedItems.length === 0) {
                    alert('请先选择要生成问题的知识条目（点击知识条目可以选中）');
                    return;
                }

                const itemId = selectedItems[0];
                showAILoading('正在生成测试问题...');

                fetch('/api/ai/generate_questions/' + itemId)
                    .then(response => response.json())
                    .then(data => {
                        hideAILoading();
                        if (data.error) {
                            showAIError(data.error);
                        } else {
                            displayAIQuestions(data.questions);
                        }
                    })
                    .catch(error => {
                        hideAILoading();
                        showAIError('生成问题失败: ' + error.message);
                    });
            }

            function improveWriting() {
                const contentTextarea = document.getElementById('newContent') || document.getElementById('editContent');
                if (!contentTextarea || !contentTextarea.value.trim()) {
                    alert('请在编辑框中输入要改进的内容');
                    return;
                }

                showAILoading('正在改进写作...');

                fetch('/api/ai/improve_writing', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ content: contentTextarea.value })
                })
                .then(response => response.json())
                .then(data => {
                    hideAILoading();
                    if (data.error) {
                        showAIError(data.error);
                    } else {
                        contentTextarea.value = data.improved_content;
                        showAISuccess('写作改进完成！');
                    }
                })
                .catch(error => {
                    hideAILoading();
                    showAIError('改进失败: ' + error.message);
                });
            }

            // AI对话功能
            function showAIChat() {
                const selectedItems = Array.from(window.selectedItems || []);
                const currentItemId = selectedItems.length > 0 ? selectedItems[0] : null;

                // 如果切换了聊天上下文，清空历史记录（可选）
                // 如果希望保留所有对话，可以移除这个判断
                if (currentChatContext !== currentItemId) {
                    // window.chatMessages = []; // 取消注释这行会在切换条目时清空对话
                    currentChatContext = currentItemId;
                }

                const selectedInfo = currentItemId ?
                    `（基于条目ID: ${currentItemId}）` :
                    '（全局知识）';

                let chatMessagesHtml = '';

                // 如果有历史消息，显示历史消息
                if (window.chatMessages && window.chatMessages.length > 0) {
                    window.chatMessages.forEach(msg => {
                        if (msg.role === 'user') {
                            chatMessagesHtml += `
                                <div class="user-message" style="text-align: right; margin: 10px 0;">
                                    <strong>您:</strong> ${msg.content}
                                </div>
                            `;
                        } else if (msg.role === 'assistant') {
                            chatMessagesHtml += `
                                <div class="ai-message">
                                    <div style="display: flex; align-items: flex-start;">
                                        <div style="font-weight: bold; margin-right: 8px;">AI助手:</div>
                                        <div style="flex: 1;">
                                            ${msg.thinking ? `
                                                <div class="thinking-process" style="margin-bottom: 12px;">
                                                    <div style="border: 1px solid #e74c3c; border-radius: 5px; padding: 10px; background: rgba(231, 76, 60, 0.05);">
                                                        <div style="color: #e74c3c; font-weight: bold; margin-bottom: 5px;">思考过程:</div>
                                                        <div style="color: #7f8c8d; font-style: italic; white-space: pre-wrap;">${msg.thinking}</div>
                                                    </div>
                                                </div>
                                            ` : ''}
                                            <div class="final-answer" style="white-space: pre-wrap;">${msg.answer}</div>
                                        </div>
                                    </div>
                                </div>
                            `;
                        }
                    });
                } else {
                    // 没有历史消息时显示欢迎信息
                    chatMessagesHtml = `
                        <div class="ai-message">
                            <strong>AI助手:</strong> 您好！我是您的知识库AI助手。${currentItemId ? '我将基于您选中的知识条目回答问题。' : '您可以问我关于知识库的任何问题。'}
                        </div>
                    `;

                    // 可选：将欢迎信息也保存到聊天记录中
                    window.chatMessages.push({
                        role: 'assistant',
                        content: `您好！我是您的知识库AI助手。${currentItemId ? '我将基于您选中的知识条目回答问题。' : '您可以问我关于知识库的任何问题。'}`,
                        timestamp: new Date().toISOString()
                    });
                }

                const chatHtml = `
                    <div style="background: var(--bg-tertiary); padding: 20px; border-radius: 10px; margin-top: 15px;">
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 15px;">
                            <h4 style="margin: 0;">💬 AI对话助手 ${selectedInfo}</h4>
                            <div style="display: flex; gap: 10px;">
                                <button onclick="clearChatHistory()" style="background: #e74c3c; padding: 5px 10px; font-size: 12px; border: none; border-radius: 3px; color: white; cursor: pointer;">清空对话</button>
                                <button onclick="exportChatHistory()" style="background: #3498db; padding: 5px 10px; font-size: 12px; border: none; border-radius: 3px; color: white; cursor: pointer;">导出对话</button>
                            </div>
                        </div>
                        <div id="chatMessages" style="height: 400px; overflow-y: auto; background: var(--bg-primary); padding: 15px; border-radius: 5px; margin-bottom: 15px;">
                            ${chatMessagesHtml}
                        </div>
                        <div style="display: flex; gap: 10px;">
                            <input type="text" id="chatInput" placeholder="输入您的问题... (按Enter发送)" style="flex: 1; padding: 10px;">
                            <button onclick="sendChatMessage()" style="background: #9b59b6;">发送</button>
                        </div>
                        <div style="margin-top: 10px; font-size: 12px; color: #888;">
                            提示：对话记录会在页面刷新后消失，如需永久保存请使用导出功能
                        </div>
                    </div>
                `;

                document.getElementById('aiInsights').innerHTML = chatHtml;

                // 绑定Enter键发送
                const chatInput = document.getElementById('chatInput');
                if (chatInput) {
                    chatInput.focus();
                    chatInput.addEventListener('keypress', function(e) {
                        if (e.key === 'Enter') {
                            sendChatMessage();
                        }
                    });
                }

                // 滚动到底部
                scrollChatToBottom();
            }

            function sendChatMessage() {
                const chatInput = document.getElementById('chatInput');
                const chatMessages = document.getElementById('chatMessages');
                const message = chatInput.value.trim();

                if (!message) return;

                // 保存用户消息到聊天记录
                const userMessage = {
                    role: 'user',
                    content: message,
                    timestamp: new Date().toISOString()
                };
                window.chatMessages.push(userMessage);

                // 添加用户消息到界面
                chatMessages.innerHTML += `
                    <div class="user-message" style="text-align: right; margin: 10px 0;">
                        <strong>您:</strong> ${message}
                    </div>
                `;

                // 清空输入框
                chatInput.value = '';

                // 显示AI思考中
                const thinkingId = 'thinking-' + Date.now();
                chatMessages.innerHTML += `
                    <div class="ai-message" id="${thinkingId}">
                        <div style="display: flex; align-items: flex-start;">
                            <div style="font-weight: bold; margin-right: 8px;">AI助手:</div>
                            <div style="flex: 1;">
                                <div class="ai-thinking" style="color: #7f8c8d; font-style: italic;">
                                    <div style="border: 1px solid #3498db; border-radius: 5px; padding: 10px; background: rgba(52, 152, 219, 0.05);">
                                        <div style="display: flex; align-items: center; margin-bottom: 8px;">
                                            <div style="border: 2px solid #f3f3f3; border-top: 2px solid #3498db; border-radius: 50%; width: 16px; height: 16px; animation: spin 1s linear infinite; margin-right: 8px;"></div>
                                            <strong>思考中...</strong>
                                        </div>
                                        <div id="${thinkingId}-content" style="min-height: 20px;"></div>
                                    </div>
                                </div>
                            </div>
                        </div>
                    </div>
                `;

                scrollChatToBottom();

                // 获取当前选中的条目ID作为上下文
                const selectedItems = Array.from(window.selectedItems || new Set());
                const itemId = selectedItems.length > 0 ? selectedItems[0] : null;

                fetch('/api/ai/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        question: message,
                        item_id: itemId,
                        chat_history: window.chatMessages.slice(0, -1) // 发送历史记录（不包括当前消息）
                    })
                })
                .then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error! status: ${response.status}`);
                    }
                    return response.json();
                })
                .then(data => {
                    // 移除思考中的消息
                    const thinkingMsg = document.getElementById(thinkingId);
                    if (thinkingMsg) thinkingMsg.remove();

                    if (data.error) {
                        // 保存错误消息
                        const errorMessage = {
                            role: 'assistant',
                            content: `抱歉，出现错误: ${data.error}`,
                            timestamp: new Date().toISOString()
                        };
                        window.chatMessages.push(errorMessage);

                        chatMessages.innerHTML += `
                            <div class="ai-message error">
                                <strong>AI助手:</strong> 抱歉，出现错误: ${data.error}
                            </div>
                        `;
                    } else {
                        // 保存AI回复到聊天记录
                        const aiMessage = {
                            role: 'assistant',
                            content: data.answer || data.response || '',
                            thinking: data.thinking || '',
                            answer: data.answer || '',
                            timestamp: new Date().toISOString()
                        };
                        window.chatMessages.push(aiMessage);

                        // 显示思考过程和答案
                        let aiMessageHtml = `
                            <div class="ai-message">
                                <div style="display: flex; align-items: flex-start;">
                                    <div style="font-weight: bold; margin-right: 8px;">AI助手:</div>
                                    <div style="flex: 1;">
                        `;

                        // 如果有思考过程，显示思考过程
                        if (data.thinking && data.thinking.trim()) {
                            aiMessageHtml += `
                                <div class="thinking-process" style="margin-bottom: 12px;">
                                    <div style="border: 1px solid #e74c3c; border-radius: 5px; padding: 10px; background: rgba(231, 76, 60, 0.05);">
                                        <div style="color: #e74c3c; font-weight: bold; margin-bottom: 5px;">思考过程:</div>
                                        <div style="color: #7f8c8d; font-style: italic; white-space: pre-wrap;">${data.thinking}</div>
                                    </div>
                                </div>
                            `;
                        }

                        // 显示最终答案
                        aiMessageHtml += `
                                <div class="final-answer" style="white-space: pre-wrap;">${data.answer}</div>
                            </div>
                        </div>
                    </div>
                        `;

                        chatMessages.innerHTML += aiMessageHtml;
                    }
                    scrollChatToBottom();
                })
                .catch(error => {
                    console.error("AI对话错误:", error);

                    const thinkingMsg = document.getElementById(thinkingId);
                    if (thinkingMsg) thinkingMsg.remove();

                    // 保存错误消息
                    const errorMessage = {
                        role: 'assistant',
                        content: `网络错误: ${error.message}`,
                        timestamp: new Date().toISOString()
                    };
                    window.chatMessages.push(errorMessage);

                    chatMessages.innerHTML += `
                        <div class="ai-message error">
                            <strong>AI助手:</strong> 网络错误: ${error.message}
                        </div>
                    `;
                    scrollChatToBottom();
                });
            }


            // AI工具函数
            function showAILoading(message) {
                document.getElementById('aiInsights').innerHTML = `
                    <div style="text-align: center; padding: 20px;">
                        <div style="border: 2px solid #f3f3f3; border-top: 2px solid #3498db; border-radius: 50%; width: 30px; height: 30px; animation: spin 1s linear infinite; margin: 0 auto 10px;"></div>
                        ${message}
                    </div>
                `;
            }

            function hideAILoading() {
                // 加载状态会在新内容显示时自动替换
            }

            function showAIError(message) {
                document.getElementById('aiInsights').innerHTML = `
                    <div class="error-message" style="color: #e74c3c; padding: 15px; background: rgba(231, 76, 60, 0.1); border-radius: 5px;">
                        ❌ ${message}
                    </div>
                `;
            }

            function showAISuccess(message) {
                document.getElementById('aiInsights').innerHTML = `
                    <div class="success-message" style="color: #27ae60; padding: 15px; background: rgba(39, 174, 96, 0.1); border-radius: 5px;">
                        ✅ ${message}
                    </div>
                `;
            }

            function displayAIAnalysis(analysis) {
                let html = '<h4>🔍 AI分析结果</h4>';

                if (analysis.analysis) {
                    html += `<div style="background: var(--bg-tertiary); padding: 15px; border-radius: 5px; margin-bottom: 15px; white-space: pre-wrap;">${analysis.analysis}</div>`;
                }

                if (analysis.summary) {
                    html += `<div><strong>摘要:</strong> ${analysis.summary}</div>`;
                }

                if (analysis.related_topics && analysis.related_topics.length > 0) {
                    html += `<div style="margin-top: 15px;"><strong>相关主题:</strong><ul>`;
                    analysis.related_topics.forEach(topic => {
                        html += `<li>${topic}</li>`;
                    });
                    html += `</ul></div>`;
                }

                document.getElementById('aiInsights').innerHTML = html;
            }

            function displayAIQuestions(questions) {
                let html = '<h4>❓ 生成的测试问题</h4>';

                if (questions && questions.length > 0) {
                    html += '<ol style="padding-left: 20px;">';
                    questions.forEach((question, index) => {
                        html += `<li style="margin-bottom: 10px;">${question}</li>`;
                    });
                    html += '</ol>';
                } else {
                    html += '<p>未能生成问题</p>';
                }

                document.getElementById('aiInsights').innerHTML = html;
            }

            function showAISettings() {
                fetch('/api/ai/status')
                    .then(response => response.json())
                    .then(status => {
                        const settingsHtml = `
                            <h4>⚙️ AI设置</h4>
                            <div style="background: var(--bg-tertiary); padding: 15px; border-radius: 5px;">
                                <p><strong>服务状态:</strong> ${status.enabled ? '✅ 已启用' : '❌ 未配置'}</p>
                                <p><strong>模型:</strong> ${status.model || '未知'}</p>
                                ${!status.enabled ? `
                                    <div style="margin-top: 15px; padding: 10px; background: rgba(231, 76, 60, 0.1); border-radius: 5px;">
                                        <strong>配置说明:</strong>
                                        <p>要启用AI功能，请设置环境变量 DEEPSEEK_API_KEY</p>
                                        <code>export DEEPSEEK_API_KEY=your_api_key_here</code>
                                    </div>
                                ` : ''}
                            </div>
                        `;
                        document.getElementById('aiInsights').innerHTML = settingsHtml;
                    })
                    .catch(error => {
                        showAIError('获取AI状态失败: ' + error.message);
                    });
            }

    // 页面加载时检查AI状态
    document.addEventListener('DOMContentLoaded', function() {
        // 延迟检查AI状态
        setTimeout(() => {
            fetch('/api/ai/status')
                .then(response => response.json())
                .then(status => {
                    if (!status.enabled) {
                        console.warn('AI服务未配置，相关功能将不可用');
                    }
                })
                .catch(error => {
                    console.error('检查AI状态失败:', error);
                });
        }, 1000);
    });

    // 文本文件导入功能
    function importFromTextFiles() {
        const fileInput = document.getElementById('textFileImport');
        const files = fileInput.files;

        if (!files || files.length === 0) {
            document.getElementById('textImportResult').innerHTML = '<span class="error">请选择文件</span>';
            return;
        }

        const useFilenameAsTitle = document.getElementById('useFilenameAsTitle').checked;
        const autoDetectTags = document.getElementById('autoDetectTags').checked;

        showUploadProgress(files.length, '正在导入文本文件...');

        const formData = new FormData();

        // 添加所有文件
        Array.from(files).forEach(file => {
            formData.append('files', file);
        });

        // 添加选项
        formData.append('use_filename_as_title', useFilenameAsTitle);
        formData.append('auto_detect_tags', autoDetectTags);

        fetch('/api/import_text_files', {
            method: 'POST',
            body: formData
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            hideUploadProgress();

            const resultElement = document.getElementById('textImportResult');

            if (data.success) {
                let resultHtml = '';

                if (data.imported_count > 0) {
                    resultHtml += `<span class="success">成功导入 ${data.imported_count} 个文件</span>`;

                    // 显示导入的项目（可选）
                    if (data.imported_items && data.imported_items.length > 0) {
                        resultHtml += `<div style="margin-top: 10px; font-size: 12px;">
                            <strong>导入的项目:</strong><br>
                            ${data.imported_items.map(item =>
                                `• ${item.title} (ID: ${item.id})`
                            ).join('<br>')}
                        </div>`;
                    }

                    // 刷新显示
                    showRecentItems();
                    loadStats();
                }

                if (data.failed_count > 0) {
                    resultHtml += `<span class="error">，${data.failed_count} 个文件导入失败</span>`;

                    // 显示失败的文件（可选）
                    if (data.failed_files && data.failed_files.length > 0) {
                        resultHtml += `<div style="margin-top: 10px; font-size: 12px; color: #e74c3c;">
                            <strong>失败的文件:</strong><br>
                            ${data.failed_files.map(file =>
                                `• ${file.filename}: ${file.error}`
                            ).join('<br>')}
                        </div>`;
                    }
                }

                resultElement.innerHTML = resultHtml;
            } else {
                resultElement.innerHTML = `<span class="error">导入失败: ${data.error}</span>`;
            }

            // 3秒后清空结果和文件选择
            setTimeout(() => {
                fileInput.value = '';
                resultElement.innerHTML = '';
            }, 8000);
        })
        .catch(error => {
            hideUploadProgress();
            document.getElementById('textImportResult').innerHTML =
                `<span class="error">导入失败: ${error.message}</span>`;
        });
    }

    // 移除之前的前端处理函数，因为现在由后端处理
    // 保留辅助函数如 extractTagsFromContent, detectCategoryFromContent 等用于其他用途

    function processTextFile(file, useFilenameAsTitle, autoDetectTags) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();

            reader.onload = function(e) {
                try {
                    const content = e.target.result;

                    // 从文件名提取标题（去掉扩展名）
                    let title = file.name;
                    const lastDotIndex = title.lastIndexOf('.');
                    if (lastDotIndex > 0) {
                        title = title.substring(0, lastDotIndex);
                    }

                    // 自动检测标签（从文件名和内容中提取关键词）
                    let tags = [];
                    if (autoDetectTags) {
                        tags = extractTagsFromContent(title, content);
                    }

                    // 确定分类
                    const category = detectCategoryFromContent(title, content);

                    // 创建知识条目
                    createKnowledgeItemFromFile(title, content, tags, category, file.name)
                        .then(result => {
                            resolve(result);
                        })
                        .catch(error => {
                            reject(error);
                        });

                } catch (error) {
                    reject(error);
                }
            };

            reader.onerror = function(error) {
                reject(new Error(`读取文件失败: ${error}`));
            };

            // 根据文件类型选择读取方式
            if (file.name.toLowerCase().endsWith('.pdf')) {
                // PDF文件需要特殊处理
                readPDFFile(file).then(content => {
                    processPDFContent(content, file, useFilenameAsTitle, autoDetectTags)
                        .then(resolve)
                        .catch(reject);
                }).catch(reject);
            } else {
                // 文本文件直接读取
                reader.readAsText(file, 'UTF-8');
            }
        });
    }

    // 提取标签函数
    function extractTagsFromContent(title, content) {
        const tags = new Set();

        // 从文件名中提取可能的标签
        const titleWords = title.split(/[\s\-_]+/).filter(word => word.length > 1);
        titleWords.forEach(word => {
            if (word.length > 2 && !isCommonWord(word)) {
                tags.add(word.toLowerCase());
            }
        });

        // 从内容中提取关键词（简单实现）
        const contentWords = content.split(/\s+/);
        const wordFrequency = {};

        contentWords.forEach(word => {
            const cleanWord = word.replace(/[^\w\u4e00-\u9fa5]/g, '').toLowerCase();
            if (cleanWord.length > 2 && !isCommonWord(cleanWord)) {
                wordFrequency[cleanWord] = (wordFrequency[cleanWord] || 0) + 1;
            }
        });

        // 取频率最高的几个词作为标签
        const topWords = Object.entries(wordFrequency)
            .sort((a, b) => b[1] - a[1])
            .slice(0, 5)
            .map(entry => entry[0]);

        topWords.forEach(tag => tags.add(tag));

        return Array.from(tags).slice(0, 8); // 最多返回8个标签
    }

    // 常见词过滤
    function isCommonWord(word) {
        const commonWords = new Set([
            'the', 'and', 'for', 'are', 'but', 'not', 'you', 'all', 'can', 'your', 'has', 'had', 'was', 'one', 'our', 'out', 'get',
            '这个', '那个', '可以', '应该', '因为', '所以', '但是', '然后', '一些', '一种', '进行', '需要', '使用', '通过', '如果'
        ]);
        return commonWords.has(word.toLowerCase()) || word.length < 2;
    }

    // 根据内容检测分类
    function detectCategoryFromContent(title, content) {
        const techKeywords = ['编程', '代码', '算法', 'python', 'java', 'javascript', 'html', 'css', '函数', '变量', '类', '对象'];
        const mathKeywords = ['数学', '公式', '定理', '证明', '计算', '几何', '代数', '微积分', '概率', '统计'];
        const aiKeywords = ['人工智能', '机器学习', '深度学习', '神经网络', 'AI', '模型', '训练', '推理'];

        const allText = (title + ' ' + content).toLowerCase();

        if (aiKeywords.some(keyword => allText.includes(keyword))) {
            return 'AI';
        } else if (techKeywords.some(keyword => allText.includes(keyword))) {
            return '编程';
        } else if (mathKeywords.some(keyword => allText.includes(keyword))) {
            return '数学';
        }

        return '未分类';
    }

    // 创建知识条目
    function createKnowledgeItemFromFile(title, content, tags, category, filename) {
        const data = {
            title: title,
            content: content,
            tags: tags,
            category: category,
            importance_level: 3,
            understanding_level: 3,
            source_file: filename
        };

        return fetch('/api/add', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        })
        .then(response => {
            if (!response.ok) {
                throw new Error(`HTTP error! status: ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            return { success: true, item_id: data.item_id };
        })
        .catch(error => {
            console.error('创建知识条目失败:', error);
            return { success: false, error: error.message };
        });
    }

    // PDF文件读取（基础版本）
    function readPDFFile(file) {
        return new Promise((resolve, reject) => {
            // 简单提示，实际PDF解析需要后端支持
            const reader = new FileReader();
            reader.onload = function(e) {
                // 这里只是返回文件名提示，实际应该在后端解析PDF
                resolve(`[PDF文件: ${file.name}]\n\n注意：PDF内容解析需要在后端实现，当前仅记录文件信息。`);
            };
            reader.onerror = reject;
            reader.readAsDataURL(file); // 实际应该发送到后端解析
        });
    }

    // 更新上传进度显示
    function updateUploadProgress(current, total) {
        const progressDiv = document.getElementById('uploadProgress');
        if (progressDiv) {
            const progressText = progressDiv.querySelector('div:last-child');
            if (progressText) {
                progressText.textContent = `正在导入文件... (${current}/${total})`;
            }
        }
    }

    // 搜索相关变量
    let searchMatches = [];
    let currentMatchIndex = -1;

    function searchInDetail() {
        const searchInput = document.getElementById('detailSearchInput');
        const contentDiv = document.getElementById('detailContent');
        const resultCount = document.getElementById('searchResultCount');

        if (!searchInput || !contentDiv) return;

        const searchTerm = searchInput.value.trim();

        if (!searchTerm) {
            clearSearch();
            // 恢复原始显示
            refreshDetailContent();
            return;
        }

        // 清除之前的高亮
        clearSearchHighlights();

        // 简单方案：只在当前可见文本中搜索，不重新渲染整个内容
        const visibleText = contentDiv.textContent || contentDiv.innerText;

        const regex = new RegExp(escapeRegExp(searchTerm), 'gi');
        let match;
        searchMatches = [];

        while ((match = regex.exec(visibleText)) !== null) {
            searchMatches.push({
                start: match.index,
                end: match.index + match[0].length
            });
        }

        if (resultCount) {
            resultCount.textContent = `找到 ${searchMatches.length} 个结果`;
        }

        if (searchMatches.length > 0) {
            // 只在当前内容中高亮，不重新渲染
            highlightCurrentContent(searchTerm);
            currentMatchIndex = 0;
            scrollToMatch(currentMatchIndex);
        } else {
            if (resultCount) {
                resultCount.textContent = '未找到匹配内容';
            }
            currentMatchIndex = -1;
        }
    }

    // 只在当前内容中高亮，不重新渲染
    function highlightCurrentContent(searchTerm) {
        const contentDiv = document.getElementById('detailContent');
        if (!contentDiv) return;

        const html = contentDiv.innerHTML;
        const regex = new RegExp(escapeRegExp(searchTerm), 'gi');
        const highlightedHtml = html.replace(regex,
            match => `<span class="search-highlight">${match}</span>`
        );

        contentDiv.innerHTML = highlightedHtml;
    }

    function escapeRegExp(string) {
        return string.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    }

    function highlightMatches(contentDiv, originalContent, searchTerm) {
        const regex = new RegExp(escapeRegExp(searchTerm), 'gi');
        const highlightedContent = originalContent.replace(regex,
            match => `<span class="search-highlight">${match}</span>`
        );

        contentDiv.innerHTML = highlightedContent;

        // 重新渲染数学公式（如果启用）
        if (mathRenderingEnabled) {
            renderMath(contentDiv);
        }
    }

    function clearSearchHighlights() {
        const contentDiv = document.getElementById('detailContent');
        if (!contentDiv) return;

        const highlights = contentDiv.querySelectorAll('.search-highlight');
        highlights.forEach(highlight => {
            const parent = highlight.parentNode;
            parent.replaceChild(document.createTextNode(highlight.textContent), highlight);
            parent.normalize();
        });
    }

    function clearSearch() {
        const searchInput = document.getElementById('detailSearchInput');
        const resultCount = document.getElementById('searchResultCount');

        if (searchInput) searchInput.value = '';
        if (resultCount) resultCount.textContent = '';

        clearSearchHighlights();
        searchMatches = [];
        currentMatchIndex = -1;
    }

    function scrollToMatch(index) {
        if (searchMatches.length === 0 || index < 0 || index >= searchMatches.length) return;

        const contentDiv = document.getElementById('detailContent');
        const highlights = contentDiv.querySelectorAll('.search-highlight');

        // 移除当前高亮样式
        highlights.forEach(highlight => highlight.classList.remove('current'));

        // 添加当前高亮样式并滚动到该位置
        if (highlights[index]) {
            highlights[index].classList.add('current');
            highlights[index].scrollIntoView({
                behavior: 'smooth',
                block: 'center'
            });
        }

        currentMatchIndex = index;

        // 更新结果计数显示当前匹配位置
        const resultCount = document.getElementById('searchResultCount');
        if (resultCount && searchMatches.length > 0) {
            resultCount.textContent = `${currentMatchIndex + 1} / ${searchMatches.length}`;
        }
    }

    function scrollToNextMatch() {
        if (searchMatches.length === 0) return;

        currentMatchIndex = (currentMatchIndex + 1) % searchMatches.length;
        scrollToMatch(currentMatchIndex);
    }

    function scrollToPrevMatch() {
        if (searchMatches.length === 0) return;

        currentMatchIndex = (currentMatchIndex - 1 + searchMatches.length) % searchMatches.length;
        scrollToMatch(currentMatchIndex);
    }

    // 添加键盘快捷键支持
    function initDetailModalKeyboard() {
        document.addEventListener('keydown', function(e) {
            const modal = document.getElementById('detailModal');
            if (!modal || modal.style.display !== 'block') return;

            // Ctrl+F 聚焦搜索框
            if (e.ctrlKey && e.key === 'f') {
                e.preventDefault();
                const searchInput = document.getElementById('detailSearchInput');
                if (searchInput) {
                    searchInput.focus();
                    searchInput.select();
                }
            }

            // F3 或 Enter 查找下一个
            if (e.key === 'F3' || (e.key === 'Enter' && e.target.id === 'detailSearchInput')) {
                e.preventDefault();
                if (searchMatches.length > 0) {
                    scrollToNextMatch();
                } else {
                    searchInDetail();
                }
            }

            // Shift+F3 查找上一个
            if (e.key === 'F3' && e.shiftKey) {
                e.preventDefault();
                scrollToPrevMatch();
            }

            // Escape 清除搜索
            if (e.key === 'Escape' && e.target.id === 'detailSearchInput') {
                clearSearch();
            }
        });
    }

    // 在页面加载时初始化键盘事件
    document.addEventListener('DOMContentLoaded', function() {
        initDetailModalKeyboard();
    });


    // 滚动聊天到底部
    function scrollChatToBottom() {
        const chatMessages = document.getElementById('chatMessages');
        if (chatMessages) {
            chatMessages.scrollTop = chatMessages.scrollHeight;
        }
    }

    // 清空聊天记录
    function clearChatHistory() {
        if (confirm('确定要清空当前对话记录吗？')) {
            window.chatMessages = [];
            currentChatContext = null;
            showAIChat(); // 重新显示聊天界面
        }
    }

    // 导出聊天记录
    function exportChatHistory() {
        if (!window.chatMessages || window.chatMessages.length === 0) {
            alert('没有可导出的对话记录');
            return;
        }

        const chatData = {
            export_date: new Date().toISOString(),
            context: currentChatContext ? `基于条目ID: ${currentChatContext}` : '全局对话',
            messages: window.chatMessages
        };

        const dataStr = JSON.stringify(chatData, null, 2);
        const blob = new Blob([dataStr], { type: 'application/json' });
        const url = URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.href = url;
        a.download = `chat_history_${new Date().getTime()}.json`;
        a.click();
        URL.revokeObjectURL(url);

        alert('对话记录已导出');
    }

    // 导入聊天记录（可选功能）
    function importChatHistory(file) {
        // 这里可以实现导入功能
        console.log('导入聊天记录功能待实现');
    }


    // Marked.js 配置
    marked.setOptions({
        breaks: true,        // 换行符转换为 <br>
        gfm: true,           // 启用 GitHub Flavored Markdown
        tables: true,        // 启用表格支持
        sanitize: false,     // 不清理 HTML（允许在 Markdown 中使用 HTML）
        smartLists: true,    // 使用智能列表
        smartypants: true,   // 使用智能标点
        highlight: function(code, lang) {
            // 代码高亮函数（可以后续添加 highlight.js）
            return '<pre><code class="lang-' + lang + '">' + code + '</code></pre>';
        }
    });


    // Markdown 渲染函数
    function renderMarkdown(content) {
        if (!content || typeof content !== 'string') {
            return '<div class="markdown-content">无内容</div>';
        }

        // 检查 marked 是否可用
        if (typeof marked === 'undefined') {
            console.warn('marked.js 未加载，使用简单 Markdown 解析');
            return simpleMarkdownRender(content);
        }

        try {
            // 配置 marked
            marked.setOptions({
                breaks: true,
                gfm: true,
                tables: true,
                sanitize: false
            });

            const html = marked.parse(content);
            return `<div class="markdown-content">${html}</div>`;
        } catch (error) {
            console.error('Markdown 渲染错误:', error);
            return `<div class="markdown-content"><pre>${content}</pre></div>`;
        }
    }

    // 简单的 Markdown 解析（备用方案）
    function simpleMarkdownRender(content) {
        let html = content;

        // 标题
        html = html.replace(/^# (.*$)/gim, '<h1>$1</h1>');
        html = html.replace(/^## (.*$)/gim, '<h2>$1</h2>');
        html = html.replace(/^### (.*$)/gim, '<h3>$1</h3>');
        html = html.replace(/^#### (.*$)/gim, '<h4>$1</h4>');

        // 粗体和斜体
        html = html.replace(/\*\*(.*?)\*\*/gim, '<strong>$1</strong>');
        html = html.replace(/\*(.*?)\*/gim, '<em>$1</em>');
        html = html.replace(/_(.*?)_/gim, '<em>$1</em>');

        // 代码
        html = html.replace(/`(.*?)`/gim, '<code>$1</code>');

        // 代码块
        html = html.replace(/```(\w+)?\n([\s\S]*?)```/gim, '<pre><code class="language-$1">$2</code></pre>');

        // 引用
        html = html.replace(/^> (.*$)/gim, '<blockquote>$1</blockquote>');

        // 水平线
        html = html.replace(/^\-\-\-$/gim, '<hr>');

        // 链接
        html = html.replace(/\[([^\]]+)\]\(([^)]+)\)/gim, '<a href="$2" target="_blank">$1</a>');

        // 图片
        html = html.replace(/!\[([^\]]*)\]\(([^)]+)\)/gim, '<img src="$2" alt="$1">');

        // 无序列表
        html = html.replace(/^\s*[\-\*\+] (.*$)/gim, '<ul><li>$1</li></ul>');
        html = html.replace(/<\/ul>\s*<ul>/gim, '');

        // 有序列表
        html = html.replace(/^\s*\d+\. (.*$)/gim, '<ol><li>$1</li></ol>');
        html = html.replace(/<\/ol>\s*<ol>/gim, '');

        // 换行
        html = html.replace(/\n/g, '<br>');

        return `<div class="markdown-content">${html}</div>`;
    }


    // 结合 LaTeX 和 Markdown 的渲染函数
    function renderContentWithMarkdownAndLatex(content) {
        if (!content) return '';

        try {
            // 先渲染 Markdown
            let html = marked.parse(content);

            // 然后处理 LaTeX 公式（如果需要）
            // 这里可以添加 LaTeX 预处理逻辑

            // 添加 Markdown 内容类
            html = `<div class="markdown-content">${html}</div>`;

            return html;
        } catch (error) {
            console.error('内容渲染错误:', error);
            return `<div class="markdown-content"><pre>${content}</pre></div>`;
        }
    }

    const contentDiv = document.getElementById('detailContent');
    contentDiv.innerHTML = renderMarkdown(item.content || '无内容');

    // HTML 转义函数
    function escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    // 纯文本预览函数（如果还没有的话）
    function getPlainTextPreview(content) {
        if (!content) return '无内容';

        // 移除所有 Markdown 标记
        let text = content
            .replace(/^#{1,6}\s+/gm, '') // 移除标题
            .replace(/\*\*(.*?)\*\*/g, '$1') // 移除粗体
            .replace(/\*(.*?)\*/g, '$1') // 移除斜体
            .replace(/`(.*?)`/g, '$1') // 移除代码
            .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1') // 移除链接
            .replace(/!\[([^\]]*)\]\([^)]+\)/g, '') // 移除图片
            .replace(/```[\s\S]*?```/g, '[代码块]') // 替换代码块
            .replace(/^>\s+/gm, '') // 移除引用
            .replace(/\n/g, ' '); // 替换换行为空格

        // 限制长度
        if (text.length > 200) {
            text = text.substring(0, 200) + '...';
        }

        return text;
    }

    // 获取当前编辑上下文（添加页面或编辑页面）
    function getCurrentContext() {
        const addContent = document.getElementById('newContent');
        const editContent = document.getElementById('editContent');

        if (editContent && editContent.offsetParent !== null) {
            return 'edit'; // 编辑模式
        } else if (addContent) {
            return 'add'; // 添加模式
        }
        return 'add'; // 默认
    }


    // 导入文本文件到编辑框
    function importTextToEditor(context = 'add') {
        document.getElementById('textEditorImportInput').click();
    }

    // 处理文本文件导入到编辑框
    function handleTextEditorImport(files, context = 'add') {
        if (!files || files.length === 0) return;

        const contentTextarea = document.getElementById(context === 'edit' ? 'editContent' : 'newContent');
        if (!contentTextarea) {
            console.error('找不到文本编辑框');
            showNotification('找不到文本编辑框', 'error');
            return;
        }

        showUploadProgress(files.length, '正在读取文本文件...');

        let processedCount = 0;
        const totalFiles = files.length;

        // 复用现有的 processTextFile 函数逻辑，但修改为直接插入内容
        Array.from(files).forEach((file, index) => {
            // 复用现有的文件读取逻辑
            readTextFileContent(file)
                .then(({ content, encoding }) => {
                    if (content) {
                        // 格式化内容以便插入（复用现有逻辑）
                        const formattedContent = formatContentForEditor(content, file.name, file);

                        // 插入到文本编辑框的光标位置
                        insertAtCursor(contentTextarea, formattedContent);

                        processedCount++;
                        updateImportProgress(processedCount, totalFiles);

                        if (processedCount === totalFiles) {
                            hideUploadProgress();
                            showNotification(`成功导入 ${totalFiles} 个文件到编辑框`, 'success');
                        }
                    } else {
                        throw new Error('无法读取文件内容');
                    }
                })
                .catch(error => {
                    console.error(`处理文件 ${file.name} 失败:`, error);
                    processedCount++;
                    updateImportProgress(processedCount, totalFiles);

                    if (processedCount === totalFiles) {
                        hideUploadProgress();
                        showNotification(`导入完成，${processedCount}/${totalFiles} 个文件成功`,
                                       processedCount === totalFiles ? 'success' : 'warning');
                    }
                });
        });
    }

    // 复用现有的 readTextFileContent 函数
    function readTextFileContent(file) {
        return new Promise((resolve, reject) => {
            const reader = new FileReader();

            reader.onload = function(e) {
                resolve({
                    content: e.target.result,
                    encoding: 'UTF-8'
                });
            };

            reader.onerror = function(error) {
                reject(new Error(`读取文件失败: ${error}`));
            };

            reader.readAsText(file, 'UTF-8');
        });
    }

    // 格式化内容以便插入编辑框（基于现有逻辑修改）
    function formatContentForEditor(content, filename, file) {
        // 获取文件扩展名
        const fileExt = filename.split('.').pop().toLowerCase();

        let formattedContent = '\n\n'; // 先添加空行分隔

        // 根据文件类型进行不同的格式化（复用现有的检测逻辑）
        const codeFiles = ['py', 'js', 'java', 'cpp', 'c', 'html', 'css', 'json', 'yaml', 'yml', 'xml'];
        const markdownFiles = ['md'];
        const latexFiles = ['tex'];

        formattedContent += content + '\n';

        return formattedContent;
    }

    // 复用现有的 getCodeLanguage 函数
    function getCodeLanguage(fileExt) {
        const languageMap = {
            'py': 'python',
            'js': 'javascript',
            'java': 'java',
            'cpp': 'cpp',
            'c': 'c',
            'html': 'html',
            'css': 'css',
            'json': 'json',
            'yaml': 'yaml',
            'yml': 'yaml',
            'xml': 'xml',
            'tex': 'latex'
        };

        return languageMap[fileExt] || 'text';
    }

    // 更新导入进度
    function updateImportProgress(current, total) {
        const progressDiv = document.getElementById('uploadProgress');
        if (progressDiv) {
            const progressText = progressDiv.querySelector('div:last-child');
            if (progressText) {
                progressText.textContent = `正在导入文件... (${current}/${total})`;
            }
        }
    }

    // 导出选中的知识条目 - 简化版本
    async function exportSelectedItems() {
        const selectedItems = Array.from(window.selectedItems || []);

        if (selectedItems.length === 0) {
            alert('请先选择要导出的知识条目');
            return;
        }

        // 询问文件后缀
        const fileExtension = prompt('请输入文件后缀（例如: .md, .txt, .py, .tex, .json）:', '.md');
        if (!fileExtension) return; // 用户取消

        // 确保后缀以点开头
        const extension = fileExtension.startsWith('.') ? fileExtension : '.' + fileExtension;

        try {
            showUploadProgress(selectedItems.length, '正在导出知识条目...');

            let successCount = 0;

            // 逐个导出选中的条目
            for (let i = 0; i < selectedItems.length; i++) {
                const itemId = selectedItems[i];
                try {
                    await exportSingleItem(itemId, extension);
                    successCount++;
                    updateExportProgress(i + 1, selectedItems.length, successCount);
                } catch (error) {
                    console.error(`导出条目 ${itemId} 失败:`, error);
                    updateExportProgress(i + 1, selectedItems.length, successCount);
                }
            }

            hideUploadProgress();
            showNotification(`成功导出 ${successCount} 个条目`, 'success');

        } catch (error) {
            hideUploadProgress();
            console.error('导出过程出错:', error);
            showNotification('导出失败: ' + error.message, 'error');
        }
    }

    // 导出单个知识条目
    async function exportSingleItem(itemId, extension) {
        // 获取条目详情
        const item = await fetchItemDetails(itemId);
        if (!item) {
            throw new Error(`无法获取条目 ${itemId} 的详情`);
        }

        // 生成文件内容
        const fileContent = generateFileContent(item, extension);

        // 生成文件名
        const fileName = generateFileName(item.title || `知识条目_${itemId}`, extension);

        // 下载文件
        downloadFile(fileContent, fileName, getMimeType(extension));
    }

    // 获取条目详情
    function fetchItemDetails(itemId) {
        return fetch('/api/item/' + itemId)
            .then(response => {
                if (!response.ok) {
                    throw new Error(`HTTP error! status: ${response.status}`);
                }
                return response.json();
            });
    }

    // 生成文件内容
    function generateFileContent(item, extension) {
        const timestamp = new Date().toLocaleString('zh-CN');

        // 对于JSON格式，导出结构化数据
        if (extension === '.json') {
            const exportData = {
                title: item.title || '无标题',
                content: item.content || '无内容',
                category: item.category || '未分类',
                tags: item.tag_names ? item.tag_names.split(',').map(tag => tag.trim()) : [],
                importance_level: item.importance_level || 3,
                understanding_level: item.understanding_level || 3,
                created_date: item.created_date || '未知',
                exported_at: timestamp,
                id: item.id
            };
            return JSON.stringify(exportData, null, 2);
        }

        // 对于其他文本格式，导出纯文本内容
        let content = '';

        // 添加主要内容
        content += item.content || '无内容';

        return content;
    }

    // 生成文件名
    function generateFileName(title, extension) {
        // 简单的文件名清理
        let fileName = title
            .replace(/[<>:"/\\|?*]/g, '_') // 替换非法字符
            .replace(/\s+/g, '_') // 替换空格为下划线
            .trim();

        // 如果文件名为空，使用默认名称
        if (!fileName) {
            fileName = '知识条目';
        }

        return fileName + extension;
    }

    // 获取MIME类型
    function getMimeType(extension) {
        const mimeMap = {
            '.md': 'text/markdown',
            '.txt': 'text/plain',
            '.py': 'text/x-python',
            '.js': 'text/javascript',
            '.java': 'text/x-java',
            '.cpp': 'text/x-c++',
            '.c': 'text/x-c',
            '.html': 'text/html',
            '.css': 'text/css',
            '.tex': 'text/x-tex',
            '.json': 'application/json'
        };

        return mimeMap[extension] || 'text/plain';
    }

    // 下载文件
    function downloadFile(content, fileName, mimeType) {
        const blob = new Blob([content], { type: mimeType });
        const url = URL.createObjectURL(blob);

        const a = document.createElement('a');
        a.href = url;
        a.download = fileName;
        a.style.display = 'none';

        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);

        URL.revokeObjectURL(url);
    }

    // 更新导出进度
    function updateExportProgress(current, total, success) {
        const progressDiv = document.getElementById('uploadProgress');
        if (progressDiv) {
            const progressText = progressDiv.querySelector('div:last-child');
            if (progressText) {
                progressText.textContent = `正在导出条目... (${current}/${total}) - 成功: ${success}`;
            }
        }
    }


    // 数据库管理功能
    function showDatabaseManager() {
        const dbManagerHtml = `
            <div style="background: var(--bg-tertiary); padding: 20px; border-radius: 10px; margin-top: 15px;">
                <h4 style="margin-top: 0; color: var(--accent-primary);">📁 数据库管理</h4>

                <div style="margin-bottom: 15px;">
                    <label style="color: var(--text-primary); font-weight: bold;">当前数据库:</label>
                    <span id="currentDbName" style="color: var(--accent-secondary); margin-left: 10px;">加载中...</span>
                </div>

                <div style="display: grid; grid-template-columns: 1fr 1fr; gap: 15px; margin-bottom: 20px;">
                    <div style="background: var(--bg-secondary); padding: 15px; border-radius: 8px;">
                        <h5 style="margin-top: 0; color: var(--text-primary);">切换数据库</h5>
                        <div style="margin-bottom: 10px;">
                            <input type="text" id="newDbName" placeholder="输入数据库名称 (如: my_knowledge.db)"
                                   style="width: 100%; padding: 8px; background: var(--bg-primary); color: var(--text-primary); border: 1px solid #555; border-radius: 4px;">
                        </div>
                        <button onclick="switchDatabase()" style="background: #3498db; width: 100%;">切换到该数据库</button>
                    </div>

                    <div style="background: var(--bg-secondary); padding: 15px; border-radius: 8px;">
                        <h5 style="margin-top: 0; color: var(--text-primary);">常用数据库</h5>
                        <div style="display: flex; flex-direction: column; gap: 8px;">
                            <button onclick="quickSwitchDb('knowledge.db')" style="background: #95a5a6; text-align: left;">knowledge.db (默认)</button>
                            <button onclick="quickSwitchDb('work_knowledge.db')" style="background: #95a5a6; text-align: left;">work_knowledge.db (工作)</button>
                            <button onclick="quickSwitchDb('study_knowledge.db')" style="background: #95a5a6; text-align: left;">study_knowledge.db (学习)</button>
                        </div>
                    </div>
                </div>

                <div style="background: var(--bg-secondary); padding: 15px; border-radius: 8px; margin-top: 10px;">
                    <h5 style="margin-top: 0; color: var(--text-primary);">数据库信息</h5>
                    <div id="dbInfo" style="font-size: 14px; color: var(--text-secondary);">
                        加载数据库信息中...
                    </div>
                </div>

                <div style="margin-top: 15px; text-align: center;">
                    <button onclick="refreshDatabaseInfo()" style="background: #95a5a6; margin-right: 10px;">刷新信息</button>
                    <button onclick="closeDatabaseManager()" style="background: #e74c3c;">关闭</button>
                </div>
            </div>
        `;

        document.getElementById('aiInsights').innerHTML = dbManagerHtml;
        loadCurrentDatabaseInfo();
    }

    function loadCurrentDatabaseInfo() {
        // 获取当前数据库信息
        fetch('/api/current_database')
            .then(response => response.json())
            .then(data => {
                document.getElementById('currentDbDisplay').textContent = data.current_database;
                document.getElementById('currentDbName').textContent = data.current_database;

                // 加载数据库统计信息
                loadDatabaseStats(data.current_database);
            })
            .catch(error => {
                console.error('获取数据库信息失败:', error);
                document.getElementById('currentDbName').textContent = '获取失败';
                document.getElementById('dbInfo').innerHTML = '无法加载数据库信息';
            });
    }

    function loadDatabaseStats(dbName) {
        // 这里可以添加获取数据库统计信息的逻辑
        // 由于需要访问不同数据库，这里只显示基本信息
        const dbInfo = document.getElementById('dbInfo');
        dbInfo.innerHTML = `
            <div>数据库文件: ${dbName}</div>
            <div>位置: 当前工作目录</div>
            <div>切换说明: 新数据库会在首次使用时自动创建</div>
            <div style="margin-top: 10px; color: #f39c12;">
                💡 提示: 切换数据库后页面会自动刷新以加载新数据
            </div>
        `;
    }

    function switchDatabase() {
        const newDbName = document.getElementById('newDbName').value.trim();

        if (!newDbName) {
            alert('请输入数据库名称');
            return;
        }

        if (!newDbName.endsWith('.db')) {
            alert('数据库名称应以 .db 结尾');
            return;
        }

        if (!confirm(`确定要切换到数据库 "${newDbName}" 吗？\n\n如果该数据库不存在，系统会自动创建。`)) {
            return;
        }

        // 显示切换中状态
        const dbInfo = document.getElementById('dbInfo');
        dbInfo.innerHTML = '<div style="color: #3498db;">🔄 切换数据库中...</div>';

        // 发送切换请求
        fetch('/api/switch_database', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                database: newDbName
            })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                dbInfo.innerHTML = `<div style="color: #27ae60;">✅ 成功切换到 ${newDbName}</div>`;

                // 延迟刷新页面以加载新数据库数据
                setTimeout(() => {
                    location.reload();
                }, 1000);
            } else {
                dbInfo.innerHTML = `<div style="color: #e74c3c;">❌ 切换失败: ${data.error}</div>`;
            }
        })
        .catch(error => {
            console.error('切换数据库失败:', error);
            dbInfo.innerHTML = `<div style="color: #e74c3c;">❌ 切换失败: ${error.message}</div>`;
        });
    }

    function quickSwitchDb(dbName) {
        document.getElementById('newDbName').value = dbName;
        switchDatabase();
    }

    function refreshDatabaseInfo() {
        loadCurrentDatabaseInfo();
    }

    function closeDatabaseManager() {
        // 清空AI分析面板内容
        document.getElementById('aiInsights').innerHTML = '选择AI功能开始使用...';
    }


    // 显示所有分类
    function showCategories() {
        fetch('/api/categories')
            .then(response => response.json())
            .then(categories => {
                let html = '<h3>📂 所有分类</h3>';

                if (categories.length === 0) {
                    html += '<p>暂无分类</p>';
                } else {
                    html += '<div style="display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 10px; margin-top: 15px;">';

                    categories.forEach(cat => {
                        html += `
                            <div class="category-item" onclick="showCategoryItems('${cat.name}')"
                                 style="background: var(--bg-tertiary); padding: 15px; border-radius: 8px; cursor: pointer; border: 1px solid #444; transition: all 0.3s ease;">
                                <div style="font-weight: bold; color: var(--accent-primary);">${cat.name}</div>
                                <div style="font-size: 12px; color: var(--text-secondary);">${cat.count} 个条目</div>
                            </div>
                        `;
                    });

                    html += '</div>';
                }

                document.getElementById('results').innerHTML = html;
            })
            .catch(error => {
                console.error('加载分类失败:', error);
                document.getElementById('results').innerHTML = '<div class="error">加载分类失败</div>';
            });
    }

    // 显示所有标签
    function showTags() {
        fetch('/api/tags')
            .then(response => response.json())
            .then(tags => {
                let html = '<h3>🏷️ 所有标签</h3>';

                if (tags.length === 0) {
                    html += '<p>暂无标签</p>';
                } else {
                    html += '<div style="display: flex; flex-wrap: wrap; gap: 8px; margin-top: 15px;">';

                    tags.forEach(tag => {
                        const tagColor = tag.color || '#bb86fc';
                        html += `
                            <div class="tag-item" onclick="showTagItems('${tag.name}')"
                                 style="background: ${tagColor}; color: white; padding: 8px 15px; border-radius: 20px; cursor: pointer; font-size: 14px; font-weight: bold; transition: all 0.3s ease;">
                                ${tag.name} <span style="background: rgba(255,255,255,0.3); padding: 2px 6px; border-radius: 10px; font-size: 12px;">${tag.count}</span>
                            </div>
                        `;
                    });

                    html += '</div>';
                }

                document.getElementById('results').innerHTML = html;
            })
            .catch(error => {
                console.error('加载标签失败:', error);
                document.getElementById('results').innerHTML = '<div class="error">加载标签失败</div>';
            });
    }

    // 显示分类下的条目
    function showCategoryItems(categoryName) {
        fetch('/api/category/' + encodeURIComponent(categoryName))
            .then(response => response.json())
            .then(items => {
                displayResults(items, `分类: ${categoryName}`);

                // 添加返回按钮
                const resultsDiv = document.getElementById('results');
                const backButton = `<div style="margin-bottom: 15px;">
                    <button onclick="showCategories()" style="background: #6c757d;">← 返回分类列表</button>
                </div>`;
                resultsDiv.innerHTML = backButton + resultsDiv.innerHTML;
            })
            .catch(error => {
                console.error('加载分类条目失败:', error);
                document.getElementById('results').innerHTML = '<div class="error">加载分类条目失败</div>';
            });
    }

    // 显示标签下的条目
    function showTagItems(tagName) {
        fetch('/api/tag/' + encodeURIComponent(tagName))
            .then(response => response.json())
            .then(items => {
                displayResults(items, `标签: ${tagName}`);

                // 添加返回按钮
                const resultsDiv = document.getElementById('results');
                const backButton = `<div style="margin-bottom: 15px;">
                    <button onclick="showTags()" style="background: #6c757d;">← 返回标签列表</button>
                </div>`;
                resultsDiv.innerHTML = backButton + resultsDiv.innerHTML;
            })
            .catch(error => {
                console.error('加载标签条目失败:', error);
                document.getElementById('results').innerHTML = '<div class="error">加载标签条目失败</div>';
            });
    }

    // 刷新当前视图的函数
    function refreshCurrentView() {
        const resultsDiv = document.getElementById('results');
        if (!resultsDiv) return;

        // 获取当前显示的标题来判断当前视图类型
        const currentTitle = resultsDiv.querySelector('h3');
        if (!currentTitle) {
            // 如果没有标题，默认显示最近条目
            showRecentItems();
            return;
        }

        const titleText = currentTitle.textContent;

        // 根据当前显示的标题判断视图类型并刷新
        if (titleText.includes('搜索结果')) {
            // 刷新搜索结果
            const searchInput = document.getElementById('searchInput');
            if (searchInput && searchInput.value) {
                searchItems();
            } else {
                showRecentItems();
            }
        }
        else if (titleText.includes('分类:')) {
            // 刷新分类视图
            const categoryName = titleText.replace('分类:', '').trim();
            showCategoryItems(categoryName);
        }
        else if (titleText.includes('标签:')) {
            // 刷新标签视图
            const tagName = titleText.replace('标签:', '').trim();
            showTagItems(tagName);
        }
        else if (titleText.includes('所有分类')) {
            // 刷新分类列表
            showCategories();
        }
        else if (titleText.includes('所有标签')) {
            // 刷新标签列表
            showTags();
        }
        else if (titleText.includes('今日复习')) {
            // 刷新复习视图
            showTodayReviews();
        }
        else {
            // 默认刷新最近条目
            showRecentItems();
        }
    }


    function refreshDisplayAfterEdit() {
        const resultsDiv = document.getElementById('results');
        if (resultsDiv) {
            // 先显示加载中
            resultsDiv.innerHTML = '<div style="text-align: center; padding: 20px;">🔄 刷新中...</div>';

            // 短暂延迟后重新加载
            setTimeout(() => {
                const searchInput = document.getElementById('searchInput');
                if (searchInput && searchInput.value.trim()) {
                    // 如果有搜索内容，重新搜索
                    searchItems();
                } else {
                    // 否则显示最新条目
                    showRecentItems();
                }
            }, 500);
        }
    }
        </script>
    </body>
    </html>
    """
    return html


# 新增API端点
@app.route('/api/advanced_search')
def api_advanced_search():
    """高级搜索API"""
    try:
        query = request.args.get('q', '')
        category = request.args.get('category', '')
        tags = request.args.getlist('tag')
        importance_min = int(request.args.get('importance_min', 1))
        importance_max = int(request.args.get('importance_max', 5))
        understanding_min = int(request.args.get('understanding_min', 1))
        understanding_max = int(request.args.get('understanding_max', 5))

        manager = KnowledgeManager(_current_db)
        results = manager.advanced_search(
            query=query,
            category=category,
            tags=tags,
            importance_min=importance_min,
            importance_max=importance_max,
            understanding_min=understanding_min,
            understanding_max=understanding_max,
            limit=100
        )

        # 预处理LaTeX公式
        for item in results:
            if 'content' in item:
                item['content'] = preprocess_latex(item['content'])
            if 'summary' in item:
                item['summary'] = preprocess_latex(item['summary'])

        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ai_recommendations/<int:item_id>')
def api_ai_recommendations(item_id):
    """AI推荐API"""
    try:
        manager = KnowledgeManager(_current_db)
        recommendations = manager.get_ai_recommendations(item_id, limit=5)
        return jsonify(recommendations)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/content_analysis/<int:item_id>')
def api_content_analysis(item_id):
    """内容分析API"""
    try:
        manager = KnowledgeManager(_current_db)
        analysis = manager.get_content_analysis(item_id)
        return jsonify(analysis)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/review_session', methods=['POST'])
def api_review_session():
    """复习会话API"""
    try:
        data = request.json
        manager = KnowledgeManager(_current_db)
        success = manager.add_review_session(
            data['item_id'],
            data['rating'],
            notes="通过Web界面复习"
        )
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

# 保留原有API端点
@app.route('/api/search')
def api_search():
    """搜索API - 支持多关键词（逗号分隔）"""
    try:
        query = request.args.get('q', '')
        manager = KnowledgeManager(_current_db)

        if not query:
            results = manager.get_recent_items(limit=50)
        else:
            keywords = [kw.strip() for kw in query.split(',') if kw.strip()]

            if not keywords:
                results = []
            elif len(keywords) == 1:
                results = manager.search_knowledge(keywords[0], limit=50)
            else:
                # 多关键词搜索 - 使用 AND 逻辑
                results = manager.search_multiple_keywords_and(keywords, limit=50)

        # 预处理LaTeX公式
        for item in results:
            if 'content' in item:
                item['content'] = preprocess_latex(item['content'])
            if 'summary' in item:
                item['summary'] = preprocess_latex(item['summary'])

        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/item/<int:item_id>')
def api_get_item(item_id):
    """获取条目详情API"""
    try:
        manager = KnowledgeManager(_current_db)
        item = manager.get_item_by_id(item_id)
        if item:
            if 'content' in item:
                item['content'] = preprocess_latex(item['content'])
            if 'summary' in item:
                item['summary'] = preprocess_latex(item['summary'])
            return jsonify(item)
        else:
            return jsonify({'error': 'Item not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/review')
def api_get_reviews():
    """获取复习项目API"""
    try:
        manager = KnowledgeManager(_current_db)
        items = manager.get_today_reviews()

        for item in items:
            if 'content' in item:
                item['content'] = preprocess_latex(item['content'])
            if 'summary' in item:
                item['summary'] = preprocess_latex(item['summary'])

        return jsonify(items)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/stats')
def api_get_stats():
    """获取统计信息API"""
    try:
        manager = KnowledgeManager(_current_db)
        stats = manager.get_statistics()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/add', methods=['POST'])
def api_add_item():
    """添加条目API"""
    try:
        data = request.json
        manager = KnowledgeManager(_current_db)
        item_id = manager.add_knowledge_item(
            title=data['title'],
            content=data['content'],
            tags=data.get('tags', []),
            category=data.get('category', '未分类'),
            importance_level=data.get('importance_level', 3),
            understanding_level=data.get('understanding_level', 3)
        )
        return jsonify({'success': True, 'item_id': item_id})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 400

@app.route('/api/delete/<int:item_id>', methods=['DELETE'])
def api_delete_item(item_id):
    """删除条目API"""
    try:
        manager = KnowledgeManager(_current_db)
        success = manager.delete_knowledge_item(item_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '删除失败'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/recent')
def api_get_recent():
    """获取最近的知识条目API"""
    try:
        manager = KnowledgeManager(_current_db)
        results = manager.get_recent_items(limit=5)
        for item in results:
            if 'content' in item:
                item['content'] = preprocess_latex(item['content'])
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/update/<int:item_id>', methods=['PUT'])
def api_update_item(item_id):
    """更新条目API"""
    try:
        data = request.json
        manager = KnowledgeManager(_current_db)

        # 确保数据格式正确
        update_data = {
            'title': data.get('title', ''),
            'content': data.get('content', ''),
            'category': data.get('category', '未分类'),
            'importance_level': int(data.get('importance_level', 3)),
            'understanding_level': int(data.get('understanding_level', 3)),
            'tags': data.get('tags', [])
        }

        success = manager.update_knowledge_item(item_id, update_data)

        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '更新失败'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/import', methods=['POST'])
def api_import_file():
    """文件导入API"""
    try:
        if 'file' not in request.files:
            return jsonify({'success': False, 'error': '没有选择文件'})

        file = request.files['file']
        if file.filename == '':
            return jsonify({'success': False, 'error': '没有选择文件'})

        # 保存临时文件
        import tempfile
        import os
        with tempfile.NamedTemporaryFile(delete=False, suffix=os.path.splitext(file.filename)[1]) as tmp_file:
            file.save(tmp_file.name)
            manager = KnowledgeManager(_current_db)
            result = manager.import_from_file(tmp_file.name)

        # 删除临时文件
        os.unlink(tmp_file.name)

        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/related/<int:item_id>')
def api_get_related_items(item_id):
    """获取关联知识API"""
    try:
        manager = KnowledgeManager(_current_db)
        related_items = manager.get_related_items(item_id)
        return jsonify(related_items)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/relationship', methods=['POST'])
def api_create_relationship():
    """创建知识关联API"""
    try:
        data = request.json
        manager = KnowledgeManager(_current_db)
        success = manager.create_relationship(
            source_id=data['source_id'],
            target_id=data['target_id'],
            relationship_type=data.get('relationship_type', 'relates_to'),
            strength=data.get('strength', 1)
        )
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/knowledge_graph')
def api_knowledge_graph():
    """知识图谱数据API，支持分类筛选"""
    try:
        category = request.args.get('category', '')
        manager = KnowledgeManager(_current_db)
        graph_data = manager.get_knowledge_graph_data()

        # 调试信息
        print(f"知识图谱数据 - 节点数: {len(graph_data.get('nodes', []))}, 边数: {len(graph_data.get('edges', []))}")

        # 如果指定了分类，过滤数据
        if category:
            # 过滤节点
            filtered_nodes = [node for node in graph_data['nodes'] if node.get('category') == category]
            filtered_node_ids = {node['id'] for node in filtered_nodes}

            # 过滤边（只保留与过滤节点相关的边）
            filtered_edges = [
                edge for edge in graph_data['edges']
                if edge['source_id'] in filtered_node_ids and edge['target_id'] in filtered_node_ids
            ]

            # 更新分类统计
            filtered_categories = [cat for cat in graph_data.get('categories', []) if cat.get('category') == category]

            graph_data = {
                'nodes': filtered_nodes,
                'edges': filtered_edges,
                'categories': filtered_categories,
                'stats': {
                    'total_nodes': len(filtered_nodes),
                    'total_edges': len(filtered_edges),
                    'total_categories': len(filtered_categories)
                }
            }

        return jsonify(graph_data)
    except Exception as e:
        print(f"知识图谱API错误: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/export')
def api_export_knowledge():
    """导出知识库API"""
    try:
        manager = KnowledgeManager(_current_db)
        conn = manager._get_connection()
        cursor = conn.cursor()

        # 获取所有知识条目及其标签
        cursor.execute("""
            SELECT ki.*, GROUP_CONCAT(t.name) as tags
            FROM knowledge_items ki
            LEFT JOIN knowledge_tags kt ON ki.id = kt.knowledge_id
            LEFT JOIN tags t ON kt.tag_id = t.id
            GROUP BY ki.id
        """)

        items = [dict(row) for row in cursor.fetchall()]
        conn.close()

        # 创建导出数据
        export_data = {
            'version': '1.0',
            'export_date': datetime.now().isoformat(),
            'total_items': len(items),
            'items': items
        }

        return jsonify(export_data)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/relationship', methods=['DELETE'])
def api_delete_relationship():
    """删除知识关联API"""
    try:
        data = request.json
        manager = KnowledgeManager(_current_db)
        success = manager.delete_relationship(
            source_id=data['source_id'],
            target_id=data['target_id']
        )
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/upload', methods=['POST'])
def api_upload_files():
    """文件上传API - 支持中文文件名"""
    try:
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': '没有选择文件'})

        files = request.files.getlist('files')
        file_type = request.form.get('file_type', 'files')

        if not files or files[0].filename == '':
            return jsonify({'success': False, 'error': '没有选择文件'})

        # 确定上传目录
        if file_type == 'images':
            upload_folder = 'static/images'
            allowed_extensions = ALLOWED_IMAGE_EXTENSIONS
        else:
            upload_folder = 'static/files'
            allowed_extensions = ALLOWED_FILE_EXTENSIONS

        # 创建上传目录
        os.makedirs(upload_folder, exist_ok=True)

        file_urls = []
        uploaded_count = 0

        for file in files:
            if file and allowed_file(file.filename, file_type):
                # 使用支持中文的文件名处理函数
                original_filename = secure_filename_with_chinese(file.filename)

                # 检查文件是否已存在，如果存在则添加序号
                file_path = os.path.join(upload_folder, original_filename)
                counter = 1
                name, ext = os.path.splitext(original_filename)

                while os.path.exists(file_path):
                    # 文件已存在，在文件名后添加序号
                    new_filename = f"{name}_{counter}{ext}"
                    file_path = os.path.join(upload_folder, new_filename)
                    counter += 1
                    # 防止无限循环，设置最大尝试次数
                    if counter > 100:
                        raise Exception("文件名冲突过多，请重试")

                # 如果因为重命名使用了新文件名，更新original_filename
                if counter > 1:
                    original_filename = f"{name}_{counter-1}{ext}"

                # 保存文件
                file.save(file_path)

                # 生成访问URL - 需要对中文文件名进行URL编码
                encoded_filename = urllib.parse.quote(original_filename)
                file_url = f"/{upload_folder}/{encoded_filename}"
                file_urls.append({
                    'url': file_url,
                    'original_name': original_filename,
                    'encoded_name': encoded_filename
                })
                uploaded_count += 1

                print(f"文件上传成功: {file.filename} -> {original_filename}")
            else:
                print(f"文件类型不允许: {file.filename}")

        if uploaded_count > 0:
            return jsonify({
                'success': True,
                'file_urls': [item['url'] for item in file_urls],
                'file_details': file_urls,
                'uploaded_count': uploaded_count
            })
        else:
            return jsonify({
                'success': False,
                'error': '没有文件被上传，请检查文件类型'
            })

    except Exception as e:
        print(f"文件上传错误: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/static/<path:filename>')
def serve_uploaded_files(filename):
    """提供上传文件的静态访问，支持中文文件名"""
    try:
        # 解码URL中的中文文件名
        decoded_filename = urllib.parse.unquote(filename)
        return send_from_directory('static/', decoded_filename)
    except Exception as e:
        print(f"服务文件失败: {filename}, 错误: {e}")
        return "文件未找到", 404

# AI相关的API端点
@app.route('/api/ai/analyze/<int:item_id>')
def api_ai_analyze(item_id):
    """AI分析知识条目"""
    try:
        data = request.get_json(silent=True) or {}
        provider = data.get('provider')
        model = data.get('model')

        manager = KnowledgeManager(_current_db)
        item = manager.get_item_by_id(item_id)
        if not item:
            return jsonify({'error': '条目不存在'}), 404

        tags = item.get('tag_names', '').split(',') if item.get('tag_names') else []
        analysis = ai_service.analyze_knowledge_item(
            title=item.get('title', ''),
            content=item.get('content', ''),
            tags=tags,
            category=item.get('category', '未分类'),
            provider=provider, model=model
        )

        return jsonify(analysis)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/generate_questions/<int:item_id>')
def api_ai_generate_questions(item_id):
    """生成测试问题"""
    try:
        data = request.get_json(silent=True) or {}
        provider = data.get('provider')
        model = data.get('model')

        manager = KnowledgeManager(_current_db)
        item = manager.get_item_by_id(item_id)
        if not item:
            return jsonify({'error': '条目不存在'}), 404

        questions = ai_service.generate_questions(item.get('content', ''), provider=provider, model=model)
        return jsonify({'questions': questions})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/improve_writing', methods=['POST'])
def api_ai_improve_writing():
    """改进写作"""
    try:
        data = request.json
        content = data.get('content', '')
        provider = data.get('provider')
        model = data.get('model')
        improved = ai_service.improve_writing(content, provider=provider, model=model)
        return jsonify({'improved_content': improved})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/ai/chat', methods=['POST'])
def api_ai_chat():
    """AI对话"""
    try:
        data = request.json
        question = data.get('question', '')
        item_id = data.get('item_id')
        chat_history = data.get('chat_history', [])  # 新增：聊天历史
        provider = data.get('provider')
        model = data.get('model')

        context_items = []
        if item_id:
            # 基于特定条目的对话
            manager = KnowledgeManager(_current_db)
            item = manager.get_item_by_id(item_id)
            if item:
                context_items.append(item)

            # 获取相关条目作为上下文
            related_items = manager.get_related_items(item_id)
            context_items.extend(related_items)
        else:
            # 全局对话，获取最近条目作为上下文
            manager = KnowledgeManager(_current_db)
            recent_items = manager.get_recent_items(limit=5)
            context_items.extend(recent_items)

        result = ai_service.chat_with_knowledge(question, context_items, provider=provider, model=model)

        # 确保返回的是字典格式
        if isinstance(result, dict):
            return jsonify(result)
        else:
            # 如果是字符串，包装成字典
            return jsonify({
                "thinking": "",
                "answer": str(result) if result else "抱歉，暂时无法回答这个问题。"
            })

    except Exception as e:
        print(f"AI对话错误: {str(e)}")
        return jsonify({
            "thinking": "",
            "answer": f"AI服务错误: {str(e)}"
        }), 500

# @app.route('/api/ai/status')
# def api_ai_status():
#     """获取AI服务状态"""
#     return jsonify({
#         'enabled': ai_service.enabled,
#         'model': 'DeepSeek'
#     })

# 删除或注释掉 DeepSeek API Key 的设置
# os.environ['DEEPSEEK_API_KEY'] = 'your_deepseek_api_key_here'

# 确保 Ollama 服务运行状态检查
@app.route('/api/ai/status')
def api_ai_status():
    """获取AI服务状态"""
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


@app.route('/api/ai/providers')
def api_ai_providers():
    return jsonify({
        'success': True,
        'data': ai_service.list_providers(),
    })


@app.route('/api/import_text_files', methods=['POST'])
def api_import_text_files():
    """导入文本文件为知识条目"""
    try:
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': '没有选择文件'})

        files = request.files.getlist('files')
        use_filename_as_title = request.form.get('use_filename_as_title', 'true') == 'true'
        auto_detect_tags = request.form.get('auto_detect_tags', 'true') == 'true'

        if not files or files[0].filename == '':
            return jsonify({'success': False, 'error': '没有选择文件'})

        imported_items = []
        failed_files = []

        for file in files:
            try:
                # 检查文件类型
                if not allowed_text_file(file.filename):
                    failed_files.append({
                        'filename': file.filename,
                        'error': '文件类型不支持'
                    })
                    continue

                # 读取文件内容 - 关键修改：直接读取原始内容，不进行任何处理
                content = file.read().decode('utf-8', errors='replace')

                if content is None:
                    failed_files.append({
                        'filename': file.filename,
                        'error': '无法读取文件内容'
                    })
                    continue

                # 生成标题
                if use_filename_as_title:
                    title = generate_title_from_filename(file.filename)
                else:
                    # 从内容第一行提取标题
                    title = extract_title_from_content(content, file.filename)

                # 自动处理标签和分类
                tags = []
                category = '未分类'

                if auto_detect_tags:
                    tags = extract_tags_from_content(title, content)
                    category = detect_category_from_content(title, content)

                # 关键修改：直接使用原始内容，不进行任何转义或处理
                manager = KnowledgeManager(_current_db)
                item_id = manager.add_knowledge_item(
                    title=title,
                    content=content,  # 直接使用原始内容
                    tags=tags,
                    category=category,
                    importance_level=3,
                    understanding_level=3,
                    source_file=file.filename
                )

                imported_items.append({
                    'id': item_id,
                    'title': title,
                    'filename': file.filename
                })

            except Exception as e:
                print(f"处理文件 {file.filename} 失败: {str(e)}")
                failed_files.append({
                    'filename': file.filename,
                    'error': str(e)
                })

        return jsonify({
            'success': True,
            'imported_count': len(imported_items),
            'failed_count': len(failed_files),
            'imported_items': imported_items,
            'failed_files': failed_files
        })

    except Exception as e:
        print(f"导入文本文件失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/current_database')
def api_current_database():
    """获取当前使用的数据库"""
    return jsonify({'current_database': _current_db})

@app.route('/api/switch_database', methods=['POST'])
def api_switch_database():
    """切换当前数据库API，如果数据库不存在则自动创建"""
    try:
        data = request.json
        new_database = data.get('database', '').strip()

        if not new_database:
            return jsonify({'success': False, 'error': '数据库名称不能为空'})

        if not new_database.endswith('.db'):
            return jsonify({'success': False, 'error': '数据库名称必须以 .db 结尾'})

        # 检查数据库文件是否存在
        if not os.path.exists(new_database):
            print(f"数据库 {new_database} 不存在，开始创建新数据库...")

            # 使用 setup.py 中的 KnowledgeDatabase 类创建新数据库
            from setup import KnowledgeDatabase
            db_initializer = KnowledgeDatabase(new_database)

            try:
                # 初始化数据库（这会创建所有表结构和默认数据）
                db_initializer.initialize_database()
                print(f"✅ 成功创建新数据库: {new_database}")
            except Exception as init_error:
                print(f"❌ 创建数据库失败: {init_error}")
                return jsonify({
                    'success': False,
                    'error': f'创建数据库失败: {str(init_error)}'
                }), 500
        else:
            print(f"✅ 使用现有数据库: {new_database}")

        # 更新全局数据库变量
        global _current_db
        _current_db = new_database

        # 更新环境变量（可选）
        os.environ['CURRENT_DATABASE'] = new_database

        print(f"已切换到数据库: {_current_db}")

        return jsonify({
            'success': True,
            'message': f'已切换到数据库: {new_database}',
            'new_database': new_database,
            'is_new': not os.path.exists(new_database)  # 指示是否是新建的数据库
        })

    except Exception as e:
        print(f"切换数据库错误: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
@app.route('/api/categories')
def api_get_categories():
    """获取所有分类"""
    try:
        manager = KnowledgeManager(_current_db)
        categories = manager.get_all_categories()
        return jsonify(categories)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tags')
def api_get_tags():
    """获取所有标签"""
    try:
        manager = KnowledgeManager(_current_db)
        tags = manager.get_all_tags()
        return jsonify(tags)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/category/<category_name>')
def api_get_category_items(category_name):
    """获取指定分类下的所有知识条目"""
    try:
        manager = KnowledgeManager(_current_db)
        items = manager.get_items_by_category(category_name)

        for item in items:
            if 'content' in item:
                item['content'] = preprocess_latex(item['content'])
            if 'summary' in item:
                item['summary'] = preprocess_latex(item['summary'])

        return jsonify(items)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/tag/<tag_name>')
def api_get_tag_items(tag_name):
    """获取指定标签下的所有知识条目"""
    try:
        manager = KnowledgeManager(_current_db)
        items = manager.get_items_by_tag(tag_name)

        for item in items:
            if 'content' in item:
                item['content'] = preprocess_latex(item['content'])
            if 'summary' in item:
                item['summary'] = preprocess_latex(item['summary'])

        return jsonify(items)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/batch_edit', methods=['POST'])
def api_batch_edit():
    """批量编辑API"""
    try:
        data = request.json
        item_ids = data.get('item_ids', [])
        operation = data.get('operation', '')  # add_tags, remove_tags, set_tags, set_category
        tags = data.get('tags', [])
        category = data.get('category', '')

        if not item_ids:
            return jsonify({'success': False, 'error': '没有选择任何条目'})

        manager = KnowledgeManager(_current_db)
        success_count = 0

        for item_id in item_ids:
            try:
                if operation == 'add_tags':
                    # 添加标签（不覆盖现有标签）
                    success = manager.add_tags_to_item(item_id, tags)
                elif operation == 'remove_tags':
                    # 移除指定标签
                    success = manager.remove_tags_from_item(item_id, tags)
                elif operation == 'set_tags':
                    # 设置标签（覆盖现有标签）
                    success = manager.set_item_tags(item_id, tags)
                elif operation == 'set_category':
                    # 设置分类
                    success = manager.set_item_category(item_id, category)
                else:
                    success = False

                if success:
                    success_count += 1

            except Exception as e:
                print(f"编辑条目 {item_id} 失败: {e}")
                continue

        return jsonify({
            'success': True,
            'processed_count': len(item_ids),
            'success_count': success_count,
            'failed_count': len(item_ids) - success_count
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500

def allowed_text_file(filename):
    """检查文件是否为允许的文本类型"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in ALLOWED_TEXT_EXTENSIONS

def read_text_file_content(file):
    """读取文本文件内容 - 简化版本，直接返回原始内容"""
    try:
        # 重置文件指针并直接读取内容
        file.seek(0)
        content = file.read().decode('utf-8', errors='replace')
        return content, 'utf-8'
    except Exception as e:
        print(f"读取文件内容失败: {str(e)}")
        # 尝试其他编码
        try:
            file.seek(0)
            content = file.read().decode('latin-1', errors='replace')
            return content, 'latin-1'
        except:
            return None, None

    except Exception as e:
        print(f"读取文件内容失败: {str(e)}")
        # 尝试使用utf-8作为后备编码
        try:
            file.seek(0)  # 重置文件指针
            content = file.read().decode('utf-8', errors='replace')
            return content, 'utf-8'
        except:
            return None, None
def generate_title_from_filename(filename):
    """从文件名生成标题"""
    # 移除扩展名
    name = os.path.splitext(filename)[0]
    # 替换分隔符为空格
    name = name.replace('_', ' ').replace('-', ' ')
    # 首字母大写
    return ' '.join(word.capitalize() for word in name.split())

def extract_title_from_content(content, filename):
    """从内容中提取标题"""
    # 取第一行作为标题，但限制长度
    first_line = content.split('\n')[0].strip()
    if first_line and len(first_line) < 100:
        return first_line
    else:
        return generate_title_from_filename(filename)

def extract_tags_from_content(title, content):
    """从内容中提取标签（简单实现）"""
    # 这里可以实现更复杂的标签提取逻辑
    # 目前返回空列表，由前端处理
    return []

def detect_category_from_content(title, content):
    """从内容中检测分类"""
    # 这里可以实现更复杂的分类检测逻辑
    # 目前返回默认分类
    return '未分类'

if __name__ == '__main__':
    print("🌐 启动完整修复版Web界面...")
    print("访问 http://localhost:5000 使用系统")
    print("按 Ctrl+C 停止服务器")

    import os
    os.environ['FLASK_ENV'] = 'production'

    app.run(debug=False, host='127.0.0.1', port=5000, use_reloader=False)
