from flask import Blueprint, request, jsonify, current_app, g
from knowledge_manager import KnowledgeManager
import urllib.request
import urllib.error
import re
import os
import json

from ai.file_extractor import FileExtractor

ai_bp = Blueprint('ai', __name__)

_ai_service = None


def get_manager():
    if 'manager' not in g:
        g.manager = KnowledgeManager(current_app.config['DB_PATH'])
    return g.manager


def get_ai_service():
    global _ai_service
    if _ai_service is None:
        from ai import AIService, load_config
        _ai_service = AIService(load_config('config/ai.yaml'))
    return _ai_service


def fetch_url_content(url: str) -> str:
    """抓取 URL 的文本内容（简单实现，正则提取正文）"""
    from urllib.parse import urlparse
    parsed = urlparse(url)
    if parsed.scheme not in ('http', 'https'):
        raise ValueError(f'不支持的URL协议: {parsed.scheme}')

    # Block private/reserved IPs for SSRF protection
    import socket
    hostname = parsed.hostname
    if hostname:
        try:
            ip = socket.gethostbyname(hostname)
        except socket.gaierror:
            raise ValueError(f'无法解析域名: {hostname}')
        if ip.startswith(('127.', '10.', '192.168.', '172.16.', '172.17.',
                          '172.18.', '172.19.', '172.20.', '172.21.', '172.22.',
                          '172.23.', '172.24.', '172.25.', '172.26.', '172.27.',
                          '172.28.', '172.29.', '172.30.', '172.31.',
                          '169.254.', '0.', '100.64.')):
            raise ValueError('不允许访问内网地址')

    req = urllib.request.Request(url, headers={
        'User-Agent': 'Mozilla/5.0 (compatible; KnowledgeManager/1.0)'
    })
    # Build opener without redirect handling for SSRF protection
    opener = urllib.request.build_opener(urllib.request.HTTPHandler,
                                          urllib.request.HTTPSHandler)
    try:
        with opener.open(req, timeout=15) as resp:
            # Read with size limit (512KB max)
            chunks = []
            total = 0
            while total < 512 * 1024:
                chunk = resp.read(8192)
                if not chunk:
                    break
                chunks.append(chunk)
                total += len(chunk)
            raw = b''.join(chunks)
            # Detect charset from Content-Type header
            content_type = resp.headers.get('Content-Type', '')
            charset = 'utf-8'
            if 'charset=' in content_type:
                charset = content_type.split('charset=')[-1].split(';')[0].strip()
            html = raw.decode(charset, errors='replace')
    except Exception as e:
        raise ValueError(f'无法获取URL内容: {str(e)}')

    # 去除 script/style 标签内容
    html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
    html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
    # 去除 HTML 标签
    text = re.sub(r'<[^>]+>', ' ', html)
    # 合并空白
    text = re.sub(r'\s+', ' ', text).strip()
    # 返回前 4000 字
    return text[:4000]


def read_uploaded_file(filename: str) -> str:
    """读取已上传文件内容"""
    static_dir = os.path.join(current_app.root_path, 'static', 'files')
    filepath = os.path.join(static_dir, os.path.basename(filename))
    if not os.path.exists(filepath):
        raise ValueError('文件不存在')
    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        return f.read()[:4000]


def list_uploaded_files() -> list[dict]:
    """列出 web/static/files/ 下所有文件"""
    static_files_dir = os.path.join(current_app.root_path, 'static', 'files')
    if not os.path.isdir(static_files_dir):
        return []
    files = []
    for name in os.listdir(static_files_dir):
        filepath = os.path.join(static_files_dir, name)
        if os.path.isfile(filepath):
            stat = os.stat(filepath)
            files.append({
                'name': name,
                'size': stat.st_size,
                'modified': stat.st_mtime,
            })
    files.sort(key=lambda f: f['modified'], reverse=True)
    return files


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
            if len(file_data) > 10 * 1024 * 1024:
                return jsonify({'error': '图片文件过大，最大10MB'}), 400
            mime_type = {
                '.png': 'image/png', '.jpg': 'image/jpeg', '.jpeg': 'image/jpeg',
                '.gif': 'image/gif', '.bmp': 'image/bmp', '.webp': 'image/webp',
            }.get(ext, 'image/png')
            b64 = base64.b64encode(file_data).decode('ascii')
            data_url = f'data:{mime_type};base64,{b64}'

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
            file_data = file.read()
            if len(file_data) > 10 * 1024 * 1024:
                return jsonify({'error': '文件过大，最大10MB'}), 400

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
                'text': text[:8000],
            })

        else:
            return jsonify({'error': f'不支持的文件类型: {ext}'}), 400

    except Exception as e:
        return jsonify({'error': f'上传处理失败: {str(e)}'}), 500


@ai_bp.route('/api/ai_recommendations/<int:item_id>')
def api_ai_recommendations(item_id):
    """AI推荐API"""
    try:
        manager = get_manager()
        recommendations = manager.get_ai_recommendations(item_id, limit=5)
        return jsonify(recommendations)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ai_bp.route('/api/ai/analyze/<int:item_id>', methods=['GET', 'POST'])
def api_ai_analyze(item_id):
    """AI分析知识条目"""
    try:
        data = request.get_json(silent=True) or {}
        provider = data.get('provider')
        model = data.get('model')

        manager = get_manager()
        item = manager.get_item_by_id(item_id)
        if not item:
            return jsonify({'error': '条目不存在'}), 404

        tags = item.get('tag_names', '').split(',') if item.get('tag_names') else []
        ai_service = get_ai_service()
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


@ai_bp.route('/api/ai/generate_questions/<int:item_id>', methods=['GET', 'POST'])
def api_ai_generate_questions(item_id):
    """生成测试问题"""
    try:
        data = request.get_json(silent=True) or {}
        provider = data.get('provider')
        model = data.get('model')

        manager = get_manager()
        item = manager.get_item_by_id(item_id)
        if not item:
            return jsonify({'error': '条目不存在'}), 404

        ai_service = get_ai_service()
        questions = ai_service.generate_questions(item.get('content', ''), provider=provider, model=model)
        return jsonify({'questions': questions})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ai_bp.route('/api/ai/improve_writing', methods=['POST'])
def api_ai_improve_writing():
    """改进写作"""
    try:
        data = request.json
        content = data.get('content', '')
        provider = data.get('provider')
        model = data.get('model')
        ai_service = get_ai_service()
        improved = ai_service.improve_writing(content, provider=provider, model=model)
        return jsonify({'improved_content': improved})
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@ai_bp.route('/api/ai/chat', methods=['POST'])
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
            manager = get_manager()
            item = manager.get_item_by_id(item_id)
            if item:
                context_items.append(item)

            # 获取相关条目作为上下文
            related_items = manager.get_related_items(item_id)
            context_items.extend(related_items)
        else:
            # 全局对话，获取最近条目作为上下文
            manager = get_manager()
            recent_items = manager.get_recent_items(limit=5)
            context_items.extend(recent_items)

        ai_service = get_ai_service()
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


@ai_bp.route('/api/ai/status')
def api_ai_status():
    """获取AI服务状态"""
    ai_service = get_ai_service()
    capabilities = [
        'analyze', 'generate_questions', 'improve_writing', 'chat',
        'extract', 'discover_relationships', 'discover_gaps',
        'generate_learning_path', 'optimize_review_plan',
    ]
    return jsonify({
        'success': True,
        'data': {
            'providers': ai_service.list_providers(),
            'defaults': {c: ai_service.get_default(c) for c in capabilities},
        }
    })


@ai_bp.route('/api/ai/providers')
def api_ai_providers():
    ai_service = get_ai_service()
    return jsonify({
        'success': True,
        'data': ai_service.list_providers(),
    })


@ai_bp.route('/api/ai/extract/url', methods=['POST'])
def api_ai_extract_url():
    """从 URL 提取知识条目"""
    try:
        data = request.get_json(silent=True) or {}
        url = data.get('url', '').strip()
        if not url:
            return jsonify({'error': 'URL不能为空'}), 400

        source_text = fetch_url_content(url)
        ai_service = get_ai_service()
        result = ai_service.extract_knowledge_item(
            source_text,
            provider=data.get('provider'),
            model=data.get('model'),
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 400
    except Exception as e:
        return jsonify({'error': f'AI提取失败: {str(e)}'}), 500


@ai_bp.route('/api/ai/files', methods=['GET'])
def api_ai_list_files():
    """列出可提取的文件"""
    try:
        return jsonify({'success': True, 'files': list_uploaded_files()})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@ai_bp.route('/api/ai/extract/text', methods=['POST'])
def api_ai_extract_text():
    """从文本提取知识条目"""
    try:
        data = request.get_json(silent=True) or {}
        text = data.get('text', '').strip()
        if not text:
            return jsonify({'error': '文本内容为空'}), 400

        ai_service = get_ai_service()
        result = ai_service.extract_knowledge_item(
            text,
            provider=data.get('provider'),
            model=data.get('model'),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'AI提取失败: {str(e)}'}), 500


@ai_bp.route('/api/ai/extract/file/<path:filename>', methods=['POST'])
def api_ai_extract_file(filename):
    """从已上传文件提取知识条目"""
    try:
        source_text = read_uploaded_file(filename)
        data = request.get_json(silent=True) or {}
        ai_service = get_ai_service()
        result = ai_service.extract_knowledge_item(
            source_text,
            provider=data.get('provider'),
            model=data.get('model'),
        )
        return jsonify(result)
    except ValueError as e:
        return jsonify({'error': str(e)}), 404
    except Exception as e:
        return jsonify({'error': f'AI提取失败: {str(e)}'}), 500


@ai_bp.route('/api/ai/discover/relationships', methods=['POST'])
def api_ai_discover_relationships():
    """AI 发现知识条目间的隐藏关联"""
    try:
        data = request.get_json(silent=True) or {}
        scope = data.get('scope', 'all')
        category = data.get('category', '')
        limit = min(data.get('limit', 30), 50)

        manager = get_manager()
        if scope == 'category' and category:
            all_items = manager.get_items_by_category(category)
        else:
            all_items = manager.search_knowledge('', limit=limit)

        items = all_items[:limit]
        if len(items) < 2:
            return jsonify({'error': '需要至少2个条目才能发现关联'}), 400

        ai_service = get_ai_service()
        result = ai_service.discover_relationships(
            items,
            provider=data.get('provider'),
            model=data.get('model'),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'AI分析失败: {str(e)}'}), 500


@ai_bp.route('/api/ai/discover/gaps', methods=['POST'])
def api_ai_discover_gaps():
    """AI 发现知识缺口"""
    try:
        data = request.get_json(silent=True) or {}
        category = data.get('category', '').strip()
        if not category:
            return jsonify({'error': '请指定分类'}), 400

        manager = get_manager()
        items = manager.get_items_by_category(category)
        if len(items) < 2:
            return jsonify({'error': '该分类条目太少，无法分析缺口'}), 400

        ai_service = get_ai_service()
        result = ai_service.discover_gaps(
            category, items,
            provider=data.get('provider'),
            model=data.get('model'),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'AI分析失败: {str(e)}'}), 500


@ai_bp.route('/api/ai/learning/path', methods=['POST'])
def api_ai_generate_learning_path():
    """AI 生成学习路径"""
    try:
        data = request.get_json(silent=True) or {}
        goal = data.get('goal', '').strip()
        if not goal:
            return jsonify({'error': '请输入学习目标'}), 400

        scope = data.get('scope', 'all')
        category = data.get('category', '')
        manager = get_manager()

        if scope == 'category' and category:
            items = manager.get_items_by_category(category)
        else:
            items = manager.search_knowledge(goal, limit=20)
            if len(items) < 20:
                all_items = manager.search_knowledge('', limit=30)
                existing_ids = {i['id'] for i in items}
                for i in all_items:
                    if i['id'] not in existing_ids:
                        items.append(i)
                        if len(items) >= 30:
                            break

        ai_service = get_ai_service()
        result = ai_service.generate_learning_path(
            goal, items[:30],
            provider=data.get('provider'),
            model=data.get('model'),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'AI分析失败: {str(e)}'}), 500


@ai_bp.route('/api/ai/learning/review-plan', methods=['POST'])
def api_ai_optimize_review_plan():
    """AI 优化复习计划"""
    try:
        data = request.get_json(silent=True) or {}
        days = min(data.get('days', 7), 14)

        manager = get_manager()
        review_items = manager.get_today_reviews()

        if not review_items:
            return jsonify({
                'daily_plan': [],
                'max_daily': 0,
                'strategy_notes': '当前没有待复习条目',
            })

        ai_service = get_ai_service()
        result = ai_service.optimize_review_plan(
            review_items, days=days,
            provider=data.get('provider'),
            model=data.get('model'),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'AI分析失败: {str(e)}'}), 500


@ai_bp.route('/api/ai/suggest/related/<int:item_id>', methods=['GET', 'POST'])
def api_ai_suggest_related(item_id):
    """AI 为指定条目推荐可能关联的其他条目"""
    try:
        data = request.get_json(silent=True) or {}
        manager = get_manager()
        item = manager.get_item_by_id(item_id)
        if not item:
            return jsonify({'error': '条目不存在'}), 404

        all_items = manager.search_knowledge('', limit=50)
        other_items = [i for i in all_items if i['id'] != item_id]
        if len(other_items) < 2:
            return jsonify({'suggestions': [], 'message': '知识库条目太少，无法建议关联'})

        ai_service = get_ai_service()
        result = ai_service.suggest_related_items(
            item, other_items[:30],
            provider=data.get('provider'),
            model=data.get('model'),
        )
        return jsonify(result)
    except Exception as e:
        return jsonify({'error': f'AI分析失败: {str(e)}'}), 500


# ═══════════════════════════════════════════════════════════
# Embedding & Semantic Search & RAG
# ═══════════════════════════════════════════════════════════

@ai_bp.route('/api/ai/embeddings/generate', methods=['POST'])
def api_ai_generate_embeddings():
    """为知识库所有条目生成嵌入向量"""
    try:
        manager = get_manager()
        all_items = manager.search_knowledge('', limit=200)

        if not all_items:
            return jsonify({'error': '知识库中没有条目'}), 400

        ai_service = get_ai_service()
        total = len(all_items)
        generated = 0
        for item in all_items:
            try:
                text = f"{item.get('title', '')}\n{item.get('content', '')[:2000]}"
                vector = ai_service.embed_text(text)
                manager.save_embedding(item['id'], vector, 'bge-m3')
                generated += 1
            except Exception as e:
                current_app.logger.warning(f'Embedding failed for item {item["id"]}: {e}')

        return jsonify({
            'success': True,
            'total': total,
            'generated': generated,
            'message': f'已为 {generated}/{total} 个条目生成嵌入向量',
        })
    except Exception as e:
        return jsonify({'error': f'生成嵌入失败: {str(e)}'}), 500


@ai_bp.route('/api/ai/semantic_search', methods=['GET'])
def api_ai_semantic_search():
    """语义搜索"""
    try:
        q = request.args.get('q', '').strip()
        if not q:
            return jsonify({'success': True, 'items': []})

        top_k = min(int(request.args.get('limit', 10)), 30)
        manager = get_manager()

        if not manager.has_embeddings():
            return jsonify({
                'success': True,
                'items': [],
                'warning': '尚未生成嵌入向量，请在知识管理页面点击"生成索引"按钮',
            })

        items_with_vec = manager.get_all_embeddings()
        ai_service = get_ai_service()
        results = ai_service.semantic_search(q, items_with_vec, top_k=top_k)

        clean_results = []
        for r in results:
            clean_results.append({
                'id': r['id'],
                'title': r.get('title', ''),
                'category': r.get('category', ''),
                'summary': (r.get('summary', '') or '')[:200],
                'content': (r.get('content', '') or '')[:300],
                'score': r['score'],
            })

        return jsonify({'success': True, 'items': clean_results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


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

        manager = get_manager()

        if not manager.has_embeddings():
            return jsonify({
                'answer': '知识库尚未建立索引，请先在知识管理页面点击"生成索引"按钮。',
                'thinking': '',
                'sources': [],
            })

        items_with_vec = manager.get_all_embeddings()
        ai_service = get_ai_service()
        result = ai_service.rag_chat(
            question, items_with_vec,
            chat_history=chat_history,
            provider=provider, model=model,
            top_k=top_k,
        )

        return jsonify(result)
    except Exception as e:
        return jsonify({
            'answer': f'RAG对话出错: {str(e)}',
            'thinking': '',
            'sources': [],
        }), 500
