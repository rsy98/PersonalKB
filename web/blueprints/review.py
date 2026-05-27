from flask import Blueprint, request, jsonify, current_app, g
from knowledge_manager import KnowledgeManager

review_bp = Blueprint('review', __name__)


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


@review_bp.route('/api/review_session', methods=['POST'])
def api_review_session():
    """复习会话API"""
    try:
        data = request.json
        manager = get_manager()
        success = manager.add_review_session(
            data['item_id'],
            data['rating'],
            notes="通过Web界面复习"
        )
        return jsonify({'success': success})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})


@review_bp.route('/api/review')
def api_get_reviews():
    """获取复习项目API。?all=1 返回全部条目用于复习"""
    try:
        manager = get_manager()
        all_mode = request.args.get('all', '0') == '1'
        if all_mode:
            items = manager.get_all_items_for_review()
        else:
            items = manager.get_today_reviews()

        for item in items:
            if 'content' in item:
                item['content'] = preprocess_latex(item['content'])
            if 'summary' in item:
                item['summary'] = preprocess_latex(item['summary'])

        return jsonify(items)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@review_bp.route('/api/categories')
def api_get_categories():
    """获取所有分类"""
    try:
        manager = get_manager()
        categories = manager.get_all_categories()
        return jsonify(categories)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@review_bp.route('/api/tags')
def api_get_tags():
    """获取所有标签"""
    try:
        manager = get_manager()
        tags = manager.get_all_tags()
        return jsonify(tags)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@review_bp.route('/api/category/<category_name>')
def api_get_category_items(category_name):
    """获取指定分类下的所有知识条目"""
    try:
        manager = get_manager()
        items = manager.get_items_by_category(category_name)

        for item in items:
            if 'content' in item:
                item['content'] = preprocess_latex(item['content'])
            if 'summary' in item:
                item['summary'] = preprocess_latex(item['summary'])

        return jsonify(items)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@review_bp.route('/api/tag/<tag_name>')
def api_get_tag_items(tag_name):
    """获取指定标签下的所有知识条目"""
    try:
        manager = get_manager()
        items = manager.get_items_by_tag(tag_name)

        for item in items:
            if 'content' in item:
                item['content'] = preprocess_latex(item['content'])
            if 'summary' in item:
                item['summary'] = preprocess_latex(item['summary'])

        return jsonify(items)
    except Exception as e:
        return jsonify({'error': str(e)}), 500
