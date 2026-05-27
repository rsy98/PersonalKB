#!/usr/bin/env python3
# run.py - 一键启动脚本（支持命令行参数）

import os
import sys
import glob
import argparse

# 预定义的数据库选项
DATABASE_OPTIONS = {
    '1': 'knowledge.db',
    '2': 'art.db',
    '3': 'AI.db',
    '4': 'math.db',
    '5': 'life.db',
    '6': 'physics.db'
}

def parse_arguments():
    """解析命令行参数"""
    parser = argparse.ArgumentParser(description='知识管理系统启动器')
    parser.add_argument('--db', type=str, help='直接指定数据库文件')
    parser.add_argument('--auto', action='store_true', help='自动模式，使用默认数据库')
    return parser.parse_args()

def auto_select_database():
    """自动选择数据库（默认选择1号数据库）"""
    default_db = DATABASE_OPTIONS['1']  # knowledge.db

    if os.path.exists(default_db):
        print(f"✅ 自动选择默认数据库: {default_db}")
        return default_db
    else:
        # 如果默认数据库不存在，创建它
        print(f"📦 默认数据库不存在，正在创建: {default_db}")
        return default_db

def initialize_database(db_filename):
    """初始化数据库"""
    if not os.path.exists(db_filename):
        print(f"📦 初始化数据库 {db_filename}...")
        try:
            from setup import KnowledgeDatabase
            db = KnowledgeDatabase(db_filename)
            db.initialize_database()

            from sample_data import create_sample_data
            create_sample_data(db_filename)
            print(f"✅ 数据库 {db_filename} 和示例数据创建完成")
        except Exception as e:
            print(f"❌ 数据库初始化失败: {e}")
            return False
    else:
        print(f"✅ 数据库 {db_filename} 已存在")

    return True

def set_current_database(db_filename):
    """设置当前数据库到web_interface模块"""
    try:
        # 通过环境变量传递
        os.environ['CURRENT_DATABASE'] = db_filename

        # 直接修改web_interface的全局变量
        import web_interface
        web_interface._current_db = db_filename
        print(f"🔗 已设置当前数据库: {db_filename}")

    except Exception as e:
        print(f"⚠️  设置数据库时出现警告: {e}")

def start_web_interface(selected_db):
    """启动Web界面"""
    print(f"\n🚀 启动Web界面...")
    print(f"🌐 访问地址: http://localhost:5000")
    print(f"📊 当前数据库: {selected_db}")
    print("⏹️  按 Ctrl+C 停止服务器")
    print("-" * 50)

    # 自动打开浏览器
    import webbrowser
    webbrowser.open('http://localhost:5000')
    print("✅ 已自动打开浏览器")

    try:
        import web_interface
        from web_interface import app

        app.run(debug=False, host='127.0.0.1', port=5000, use_reloader=False)

    except KeyboardInterrupt:
        print("\n👋 服务已停止，再见！")
    except Exception as e:
        print(f"❌ Web界面启动失败: {e}")
        import traceback
        traceback.print_exc()

def main():
    args = parse_arguments()

    # 处理命令行参数
    if args.db:
        # 直接指定数据库
        selected_db = args.db
        print(f"🎯 使用指定数据库: {selected_db}")
    elif args.auto:
        # 自动模式
        selected_db = auto_select_database()
    else:
        # 交互模式（原有的选择界面）
        from interactive_mode import run_interactive_mode
        selected_db = run_interactive_mode()

    # 初始化数据库
    if not initialize_database(selected_db):
        sys.exit(1)

    # 设置当前数据库
    set_current_database(selected_db)

    # 启动Web界面
    start_web_interface(selected_db)

if __name__ == "__main__":
    main()
