# interactive_mode.py - 交互式数据库选择模式

import os
import sys
import glob

# 预定义的数据库选项
DATABASE_OPTIONS = {
    '1': 'knowledge.db',
    '2': 'art.db',
    '3': 'AI.db',
    '4': 'math.db',
    '5': 'life.db',
    '6': 'physics.db'
}

def show_database_menu():
    """显示数据库选择菜单"""
    available_dbs = list_database_files()

    print("\n📁 请选择要使用的数据库:")
    print("=" * 50)

    # 显示预定义数据库选项
    for key in sorted(DATABASE_OPTIONS.keys()):
        db_info = available_dbs[key]
        status = "✅ 已存在" if db_info['exists'] else "❌ 未创建"
        size_info = f"({db_info['size']} bytes)" if db_info['exists'] else "(待创建)"

        print(f"{key}. {db_info['file']} {status} {size_info}")

    # 其他选项
    print("\n7. 创建新的数据库")
    print("8. 列出所有数据库文件")
    print("9. 退出")
    print("-" * 50)

def list_database_files():
    """列出预定义的数据库文件及其状态"""
    available_dbs = {}

    for key, db_file in DATABASE_OPTIONS.items():
        if os.path.exists(db_file):
            size = os.path.getsize(db_file)
            available_dbs[key] = {
                'file': db_file,
                'size': size,
                'exists': True
            }
        else:
            available_dbs[key] = {
                'file': db_file,
                'size': 0,
                'exists': False
            }

    return available_dbs

def create_new_database():
    """创建新的数据库文件"""
    while True:
        db_name = input("请输入新数据库文件名（不含扩展名，将自动添加.db）: ").strip()
        if not db_name:
            print("❌ 数据库名不能为空")
            continue

        db_filename = f"{db_name}.db"
        if os.path.exists(db_filename):
            print(f"❌ 数据库文件 {db_filename} 已存在")
            continue

        return db_filename

def list_all_database_files():
    """列出所有数据库文件"""
    all_db_files = glob.glob("*.db")

    if not all_db_files:
        print("📭 当前目录下没有数据库文件")
        return None

    print("\n📂 所有数据库文件:")
    print("-" * 40)

    for i, db_file in enumerate(all_db_files, 1):
        size = os.path.getsize(db_file)
        print(f"   {db_file} ({size} bytes)")

    input("\n按回车键返回主菜单...")
    return None

def run_interactive_mode():
    """运行交互式选择模式"""
    show_welcome_banner()

    while True:
        show_database_menu()

        try:
            choice = input("请选择 [1-9]: ").strip()

            if choice == '9':
                print("👋 再见！")
                sys.exit(0)
            elif choice == '7':
                selected_db = create_new_database()
            elif choice == '8':
                list_all_database_files()
                continue
            elif choice in DATABASE_OPTIONS:
                selected_db = DATABASE_OPTIONS[choice]
                db_info = list_database_files()[choice]

                if not db_info['exists']:
                    create_new = input(f"数据库 {selected_db} 不存在，是否创建？(y/n): ").strip().lower()
                    if create_new != 'y':
                        print("❌ 已取消选择")
                        continue
            else:
                print("❌ 请输入 1-9 之间的有效数字")
                continue

            print(f"✅ 已选择数据库: {selected_db}")
            return selected_db

        except ValueError:
            print("❌ 请输入有效的数字")
        except KeyboardInterrupt:
            print("\n👋 再见！")
            sys.exit(0)

def show_welcome_banner():
    """显示欢迎横幅"""
    print("🚀 个人知识管理系统启动器")
    print("=" * 60)
    print("📚 预定义数据库:")
    print("   1. knowledge.db - 默认知识库")
    print("   2. art.db      - 艺术相关")
    print("   3. AI.db       - 人工智能")
    print("   4. math.db     - 数学知识")
    print("   5. life.db     - 生活记录")
    print("   6. physics.db  - 物理科学")
    print("=" * 60)
