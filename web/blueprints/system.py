from flask import Blueprint, request, jsonify, current_app, g
from knowledge_manager import KnowledgeManager
import os

system_bp = Blueprint('system', __name__)


def get_manager():
    if 'manager' not in g:
        g.manager = KnowledgeManager(current_app.config['DB_PATH'])
    return g.manager


@system_bp.route('/api/stats')
def api_get_stats():
    """获取统计信息API"""
    try:
        manager = get_manager()
        stats = manager.get_statistics()
        return jsonify(stats)
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@system_bp.route('/api/current_database')
def api_current_database():
    """获取当前使用的数据库"""
    return jsonify({'current_database': current_app.config['DB_PATH']})


@system_bp.route('/api/switch_database', methods=['POST'])
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

        # 更新配置中的数据库路径
        current_app.config['DB_PATH'] = new_database
        g.pop('manager', None)

        print(f"已切换到数据库: {new_database}")

        return jsonify({
            'success': True,
            'message': f'已切换到数据库: {new_database}',
            'new_database': new_database,
            'is_new': not os.path.exists(new_database)  # 指示是否是新建的数据库
        })

    except Exception as e:
        print(f"切换数据库错误: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500
