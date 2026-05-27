import json
import os
import csv
import io
import zipfile
import re

from flask import Blueprint, request, jsonify, current_app, g, send_file
from knowledge_manager import KnowledgeManager
from datetime import datetime

knowledge_bp = Blueprint('knowledge', __name__)


def get_manager():
    if 'manager' not in g:
        g.manager = KnowledgeManager(current_app.config['DB_PATH'])
    return g.manager


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


@knowledge_bp.route('/api/advanced_search')
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

        manager = get_manager()
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


@knowledge_bp.route('/api/content_analysis/<int:item_id>')
def api_content_analysis(item_id):
    """内容分析API"""
    try:
        manager = get_manager()
        analysis = manager.get_content_analysis(item_id)
        return jsonify(analysis)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@knowledge_bp.route('/api/search')
def api_search():
    """搜索API - 支持多关键词（逗号分隔）"""
    try:
        query = request.args.get('q', '')
        manager = get_manager()

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


@knowledge_bp.route('/api/item/<int:item_id>')
def api_get_item(item_id):
    """获取条目详情API"""
    try:
        manager = get_manager()
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


@knowledge_bp.route('/api/add', methods=['POST'])
def api_add_item():
    """添加条目API"""
    try:
        data = request.json
        manager = get_manager()
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


@knowledge_bp.route('/api/delete/<int:item_id>', methods=['DELETE'])
def api_delete_item(item_id):
    """删除条目API"""
    try:
        manager = get_manager()
        success = manager.delete_knowledge_item(item_id)
        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': '删除失败'})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@knowledge_bp.route('/api/recent')
def api_get_recent():
    """获取最近的知识条目API"""
    try:
        manager = get_manager()
        results = manager.get_recent_items(limit=5)
        for item in results:
            if 'content' in item:
                item['content'] = preprocess_latex(item['content'])
        return jsonify(results)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@knowledge_bp.route('/api/update/<int:item_id>', methods=['PUT'])
def api_update_item(item_id):
    """更新条目API"""
    try:
        data = request.json
        manager = get_manager()

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


@knowledge_bp.route('/api/import', methods=['POST'])
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
            manager = get_manager()
            result = manager.import_from_file(tmp_file.name)

        # 删除临时文件
        os.unlink(tmp_file.name)

        return jsonify(result)
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@knowledge_bp.route('/api/related/<int:item_id>')
def api_get_related_items(item_id):
    """获取关联知识API"""
    try:
        manager = get_manager()
        related_items = manager.get_related_items(item_id)
        return jsonify(related_items)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@knowledge_bp.route('/api/relationship', methods=['POST'])
def api_create_relationship():
    """创建知识关联API"""
    try:
        data = request.json
        manager = get_manager()
        success = manager.create_relationship(
            source_id=data['source_id'],
            target_id=data['target_id'],
            relationship_type=data.get('relationship_type', 'relates_to'),
            strength=data.get('strength', 1)
        )
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@knowledge_bp.route('/api/knowledge_graph')
def api_knowledge_graph():
    """知识图谱数据API，支持分类筛选"""
    try:
        category = request.args.get('category', '')
        manager = get_manager()
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


def _sanitize_filename(name: str, default: str = 'untitled') -> str:
    """Remove characters unsafe for filenames"""
    safe = re.sub(r'[<>:"/\\|?*]', '_', name)
    safe = safe.strip().rstrip('.') or default
    return safe[:80]


def _get_items(manager, category: str = ''):
    """Fetch items, optionally filtered by category"""
    with manager.connection() as conn:
        cursor = conn.cursor()
        if category:
            cursor.execute("""
                SELECT ki.*, GROUP_CONCAT(t.name) as tags
                FROM knowledge_items ki
                LEFT JOIN knowledge_tags kt ON ki.id = kt.knowledge_id
                LEFT JOIN tags t ON kt.tag_id = t.id
                WHERE ki.category = ? AND ki.is_archived = 0
                GROUP BY ki.id
                ORDER BY ki.category, ki.created_date DESC
            """, (category,))
        else:
            cursor.execute("""
                SELECT ki.*, GROUP_CONCAT(t.name) as tags
                FROM knowledge_items ki
                LEFT JOIN knowledge_tags kt ON ki.id = kt.knowledge_id
                LEFT JOIN tags t ON kt.tag_id = t.id
                WHERE ki.is_archived = 0
                GROUP BY ki.id
                ORDER BY ki.category, ki.created_date DESC
            """)
        return [dict(row) for row in cursor.fetchall()]


def _format_markdown(item: dict) -> str:
    """Format a single item as Markdown"""
    lines = []
    lines.append(f"# {item.get('title', 'Untitled')}")
    lines.append('')
    meta = []
    if item.get('category'):
        meta.append(f"**分类:** {item['category']}")
    meta.append(f"**重要性:** {item.get('importance_level', 3)}/5")
    meta.append(f"**理解程度:** {item.get('understanding_level', 3)}/5")
    if item.get('tags'):
        tags = item['tags']
        meta.append(f"**标签:** {tags.replace(',', ', ')}")
    meta.append(f"**创建日期:** {item.get('created_date', '')}")
    meta.append(f"**更新日期:** {item.get('updated_date', '')}")
    lines.append(' | '.join(meta))
    lines.append('')
    if item.get('summary'):
        lines.append(f"> {item['summary']}")
        lines.append('')
    lines.append('---')
    lines.append('')
    content = item.get('content', '') or ''
    lines.append(content)
    lines.append('')
    return '\n'.join(lines)


def _format_anki_card(item: dict) -> dict:
    """Format a single item as an Anki card row"""
    title = item.get('title', 'Untitled')
    summary = item.get('summary', '') or ''
    content = item.get('content', '') or ''
    tags = (item.get('tags', '') or '').replace(',', ' ')

    front_parts = []
    front_parts.append(f"<h3>{title}</h3>")
    if summary:
        front_parts.append(f"<p><i>{summary}</i></p>")
    front = ''.join(front_parts)

    back = content.replace('\n', '<br>')
    return {
        'Front': front,
        'Back': back,
        'Tags': tags,
    }


@knowledge_bp.route('/api/export')
def api_export_knowledge():
    """导出知识库 — ?format=json|markdown|anki&category=xxx

    - json:      单个 .json 文件下载
    - markdown:  .zip 包内含每个条目一个 .md 文件
    - anki:      .csv 文件可直接导入 Anki
    """
    try:
        fmt = request.args.get('format', 'json').lower()
        category = request.args.get('category', '').strip()
        manager = get_manager()
        items = _get_items(manager, category)

        if not items:
            return jsonify({'error': '没有可导出的条目'}), 404

        if fmt == 'json':
            export_data = {
                'version': '1.0',
                'export_date': datetime.now().isoformat(),
                'total_items': len(items),
                'items': items,
            }
            buf = io.BytesIO()
            buf.write(json.dumps(export_data, ensure_ascii=False, indent=2).encode('utf-8'))
            buf.seek(0)
            return send_file(
                buf, mimetype='application/json', as_attachment=True,
                download_name=f'knowledge_export_{datetime.now().strftime("%Y%m%d")}.json',
            )

        elif fmt == 'markdown':
            buf = io.BytesIO()
            with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as zf:
                title_counts = {}
                for item in items:
                    md_text = _format_markdown(item)
                    title = _sanitize_filename(item.get('title', 'untitled'))
                    # Handle duplicate titles
                    if title in title_counts:
                        title_counts[title] += 1
                        title = f"{title}_{title_counts[title]}"
                    else:
                        title_counts[title] = 0
                    zf.writestr(f"{title}.md", md_text.encode('utf-8'))
            buf.seek(0)
            return send_file(
                buf, mimetype='application/zip', as_attachment=True,
                download_name=f'knowledge_markdown_{datetime.now().strftime("%Y%m%d")}.zip',
            )

        elif fmt == 'anki':
            buf = io.StringIO()
            writer = csv.DictWriter(buf, fieldnames=['Front', 'Back', 'Tags'])
            writer.writeheader()
            for item in items:
                writer.writerow(_format_anki_card(item))
            buf.seek(0)
            bytes_buf = io.BytesIO(buf.getvalue().encode('utf-8-sig'))
            return send_file(
                bytes_buf, mimetype='text/csv', as_attachment=True,
                download_name=f'knowledge_anki_{datetime.now().strftime("%Y%m%d")}.csv',
            )

        else:
            return jsonify({'error': f'不支持的格式: {fmt}。支持: json, markdown, anki'}), 400

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@knowledge_bp.route('/api/relationship', methods=['DELETE'])
def api_delete_relationship():
    """删除知识关联API"""
    try:
        data = request.json
        manager = get_manager()
        success = manager.delete_relationship(
            source_id=data['source_id'],
            target_id=data['target_id']
        )
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@knowledge_bp.route('/api/batch_edit', methods=['POST'])
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

        manager = get_manager()
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


@knowledge_bp.route('/api/import/json', methods=['POST'])
def api_import_json():
    """从上传的 JSON 数据批量导入知识条目"""
    try:
        data = request.get_json(silent=True) or {}
        items = data.get('items', [])

        if not isinstance(items, list) or len(items) == 0:
            return jsonify({'success': False, 'error': 'JSON 数据为空或格式错误'}), 400

        manager = get_manager()
        imported = 0
        skipped = 0

        for item in items:
            if not isinstance(item, dict) or 'title' not in item or 'content' not in item:
                skipped += 1
                continue
            try:
                manager.add_knowledge_item(
                    title=item['title'],
                    content=item['content'],
                    tags=item.get('tags', []),
                    category=item.get('category', '未分类'),
                    importance_level=item.get('importance_level', 3),
                    understanding_level=item.get('understanding_level', 3),
                )
                imported += 1
            except Exception:
                skipped += 1

        return jsonify({
            'success': True,
            'total': len(items),
            'imported': imported,
            'skipped': skipped,
        })

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@knowledge_bp.route('/api/search_items', methods=['GET'])
def api_search_items():
    """搜索知识条目（用于关联选择器等场景），返回 id + title"""
    try:
        q = request.args.get('q', '').strip()
        manager = get_manager()
        if not q:
            items = manager.search_knowledge('', limit=50)
        else:
            items = manager.search_knowledge(q, limit=20)
        results = [{'id': i['id'], 'title': i['title'], 'category': i.get('category', '')}
                    for i in items]
        return jsonify({'success': True, 'items': results})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500
