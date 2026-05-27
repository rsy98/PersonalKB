#!/usr/bin/env python3
# cli_interface.py - 命令行交互界面

import sys
import os
from knowledge_manager import KnowledgeManager
from ai import AIService, load_config

class KnowledgeCLI:
    def __init__(self):
        import os
        db_path = os.environ.get('CURRENT_DATABASE', 'knowledge.db')
        self.manager = KnowledgeManager(db_path)
        self.running = True
        try:
            ai_config = load_config('config/ai.yaml')
            self.ai_service = AIService(ai_config)
        except Exception:
            self.ai_service = None

    def print_menu(self):
        """显示主菜单"""
        print("""
🐙 个人知识管理系统命令行界面
================================
1. 添加知识条目
2. 搜索知识
3. 今日复习
4. 查看统计
5. 查看条目详情
6. 创建关联
7. 退出系统
================================
        """)

    def run(self):
        """运行命令行界面"""
        print("🐙 个人知识管理系统命令行界面")
        print("输入 help 查看命令帮助")

        while self.running:
            self.print_menu()
# 快捷命令映射
            shortcut_commands = {
                'qa': 'quickadd',
                'imp': 'import',
                'del': 'delete',
                's': 'search',
                'r': 'review',
                'stat': 'stats',
                'v': 'show',
                'help': 'shortcuts'
            }

            if choice in shortcut_commands:
                # 执行快捷命令
                method_name = 'do_' + shortcut_commands[choice]
                method = getattr(self, method_name)
                method('')
            choice = input("请选择操作 (1-7): ").strip()

            if choice == '1':
                self.add_item()
            elif choice == '2':
                self.search_items()
            elif choice == '3':
                self.review_items()
            elif choice == '4':
                self.show_stats()
            elif choice == '5':
                self.show_item()
            elif choice == '6':
                self.create_relation()
            elif choice == '7' or choice.lower() == 'quit':
                self.exit_system()
            elif choice.lower() == 'help':
                self.show_help()
            else:
                print("❌ 无效选择，请输入 1-7 或 help")

            input("\n按回车键继续...")

    def show_help(self):
        """显示帮助信息"""
        print("""
命令帮助:
- 输入 1-7 选择对应功能
- 输入 help 显示此帮助
- 输入 quit 或选择 7 退出系统

快捷命令示例:
- 添加: add "标题" "内容" [标签] [分类]
- 搜索: search 关键词
- 复习: review
- 统计: stats
        """)

    def add_item(self):
        """添加知识条目"""
        print("\n📝 添加知识条目")
        print("=" * 30)

        title = input("标题: ").strip()
        if not title:
            print("❌ 标题不能为空")
            return

        print("内容 (输入空行结束):")
        content_lines = []
        while True:
            line = input()
            if line.strip() == "":
                break
            content_lines.append(line)

        content = "\n".join(content_lines)
        if not content:
            print("❌ 内容不能为空")
            return

        tags_input = input("标签 (逗号分隔，可选): ").strip()
        tags = [tag.strip() for tag in tags_input.split(',')] if tags_input else []

        category = input("分类 (可选，默认'未分类'): ").strip() or "未分类"

        try:
            importance = int(input("重要程度 (1-5，默认3): ").strip() or "3")
            understanding = int(input("理解程度 (1-5，默认3): ").strip() or "3")
        except ValueError:
            print("❌ 请输入有效数字，使用默认值")
            importance = 3
            understanding = 3

        item_id = self.manager.add_knowledge_item(
            title=title,
            content=content,
            tags=tags,
            category=category,
            importance_level=importance,
            understanding_level=understanding
        )

        print(f"✅ 知识条目已添加! ID: {item_id}")

    def search_items(self):
        """搜索知识"""
        query = input("\n🔍 搜索关键词: ").strip()
        if not query:
            print("❌ 请输入搜索关键词")
            return

        results = self.manager.search_knowledge(query)

        if not results:
            print("🔍 未找到相关结果")
            return

        print(f"\n📚 找到 {len(results)} 个相关结果:\n")
        for i, item in enumerate(results, 1):
            print(f"{i}. [{item['id']}] {item['title']}")
            print(f"   摘要: {item['summary']}")
            print(f"   分类: {item['category']} | 标签: {item['tag_names']}")
            print(f"   创建: {item['created_date']}\n")

    def review_items(self):
        """今日复习"""
        items = self.manager.get_today_reviews()

        if not items:
            print("🎉 今天没有需要复习的内容!")
            return

        print(f"\n📖 今日复习 ({len(items)} 个项目):\n")

        for i, item in enumerate(items, 1):
            print(f"{i}. {item['title']}")
            print(f"   理解程度: {item['understanding_level']}/5")
            print(f"   摘要: {item['summary']}\n")

            # 模拟复习过程
            while True:
                try:
                    rating_input = input("回忆难度评分 (0-5, 5=最容易): ").strip()
                    if not rating_input:
                        print("⏭️  跳过此项")
                        break

                    rating = int(rating_input)
                    if 0 <= rating <= 5:
                        notes = input("复习笔记 (可选): ").strip()
                        self.manager.add_review_session(item['id'], rating, notes)
                        print("✅ 复习记录已保存!\n")
                        break
                    else:
                        print("❌ 请输入 0-5 之间的数字")
                except ValueError:
                    print("❌ 请输入有效数字")

    def show_stats(self):
        """查看统计"""
        stats = self.manager.get_statistics()

        print("\n📊 知识库统计信息:")
        print(f"   知识条目总数: {stats['total_items']}")
        print(f"   归档条目: {stats['archived_items']}")
        print(f"   分类数量: {stats['categories_count']}")
        print(f"   标签数量: {stats['tags_count']}")
        print(f"   关联关系: {stats['relationships_count']}")
        print(f"   今日新增: {stats['today_new']}")
        print(f"   今日待复习: {stats['today_reviews']}")

        print("\n理解程度分布:")
        for level, count in stats['understanding_distribution'].items():
            print(f"   等级{level}: {count} 个条目")

    def show_item(self):
        """查看条目详情"""
        item_id_input = input("\n📄 请输入条目ID: ").strip()
        if not item_id_input.isdigit():
            print("❌ 请输入有效的条目ID")
            return

        item = self.manager.get_item_by_id(int(item_id_input))
        if not item:
            print("❌ 未找到该条目")
            return

        print(f"\n📄 条目详情 (ID: {item['id']}):")
        print(f"标题: {item['title']}")
        print(f"分类: {item['category']}")
        print(f"类型: {item['item_type']}")
        print(f"标签: {item['tag_names']}")
        print(f"重要程度: {item['importance_level']}/5")
        print(f"理解程度: {item['understanding_level']}/5")
        print(f"创建时间: {item['created_date']}")
        print(f"下次复习: {item['next_review_date']}")
        print(f"\n内容:\n{item['content']}\n")

        # 显示关联条目
        related = self.manager.get_related_items(item['id'])
        if related:
            print("🔗 关联条目:")
            for rel_item in related:
                print(f"  - {rel_item['title']} (ID: {rel_item['id']})")

    def create_relation(self):
        """创建关联"""
        print("\n🔗 创建知识关联")
        print("=" * 30)

        try:
            source_id = int(input("源条目ID: ").strip())
            target_id = int(input("目标条目ID: ").strip())
            rel_type = input("关联类型 (默认'relates_to'): ").strip() or "relates_to"
            strength = int(input("关联强度 (1-5，默认1): ").strip() or "1")

            if self.manager.create_relationship(source_id, target_id, rel_type, strength):
                print("✅ 关联创建成功!")
            else:
                print("❌ 关联创建失败，可能已存在或ID无效")
        except ValueError:
            print("❌ 请输入有效的数字ID")

    def exit_system(self):
        """退出系统"""
        self.manager.close()
        print("👋 再见!")
        self.running = False
    def quick_add(self, args):
        """快速添加命令: quickadd "标题" "内容" [标签] [分类]"""
        # 解析参数并快速添加
        pass
    def do_quickadd(self, arg):
        """快速添加命令: quickadd "标题" "内容" [标签] [分类]"""
        args = arg.split('"')
        if len(args) < 3:
            print("❌ 用法: quickadd \"标题\" \"内容\" [标签] [分类]")
            return

        title = args[1].strip()
        content = args[3].strip()

        tags = []
        category = "未分类"

        if len(args) > 4 and args[4].strip():
            tags_str = args[4].strip()
            if tags_str:
                tags = [tag.strip() for tag in tags_str.split(',')]

        if len(args) > 5 and args[5].strip():
            category = args[5].strip()

        item_id = self.manager.add_knowledge_item(
            title=title,
            content=content,
            tags=tags,
            category=category
        )

        print(f"✅ 知识条目已快速添加! ID: {item_id}")

    def do_import(self, arg):
        """文件导入命令: import 文件路径"""
        if not arg:
            print("❌ 用法: import 文件路径")
            return

        result = self.manager.import_from_file(arg)
        if result['success']:
            print(f"✅ 文件导入成功! 共导入 {result['imported_count']} 条知识")
        else:
            print(f"❌ 导入失败: {result['error']}")

    def do_delete(self, arg):
        """删除命令: delete 条目ID"""
        if not arg.isdigit():
            print("❌ 请输入有效的条目ID")
            return

        item_id = int(arg)
        # 确认删除
        confirm = input(f"⚠️  确定要删除条目 {item_id} 吗？(y/N): ")
        if confirm.lower() == 'y':
            success = self.manager.delete_knowledge_item(item_id)
            if success:
                print("✅ 条目删除成功!")
            else:
                print("❌ 删除失败，条目可能不存在")
        else:
            print("🗑️  删除操作已取消")

    def do_shortcuts(self, arg):
        """显示快捷键帮助: shortcuts"""
        print("""
    ⌨️  快捷键命令:
    - quickadd "标题" "内容" [标签] [分类]  # 快速添加
    - import 文件路径                      # 导入文件
    - delete 条目ID                        # 删除条目
    - search 关键词                        # 搜索知识
    - review                              # 今日复习
    - stats                               # 查看统计
    - show 条目ID                         # 查看详情
        """)

if __name__ == "__main__":
    # 检查数据库是否存在，如果不存在则初始化
    import os
    if not os.path.exists('knowledge.db'):
        print("⚠️  数据库不存在，正在初始化...")
        from setup import KnowledgeDatabase
        db = KnowledgeDatabase()
        db.initialize_database()

        # 创建示例数据
        from sample_data import create_sample_data
        create_sample_data()

    cli = KnowledgeCLI()
    cli.run()
