#!/usr/bin/env python3
# setup.py - 数据库初始化脚本（增强版）

import sqlite3
import os
from datetime import datetime

class KnowledgeDatabase:
    def __init__(self, db_path='knowledge.db'):
        self.db_path = db_path
        self.conn = None

    def initialize_database(self):
        """初始化数据库表结构"""
        if os.path.exists(self.db_path):
            # 备份现有数据库而不是直接删除
            backup_path = f"{self.db_path}.backup.{datetime.now().strftime('%Y%m%d_%H%M%S')}"
            os.rename(self.db_path, backup_path)
            print(f"📦 已备份现有数据库: {backup_path}")

        self.conn = sqlite3.connect(self.db_path)
        self.conn.row_factory = sqlite3.Row

        # 启用外键支持
        self.conn.execute("PRAGMA foreign_keys = ON")

        self._create_tables()
        self._insert_default_data()

        print("✅ 数据库初始化完成!")
        return self.conn

    def _create_tables(self):
        """创建数据表（增强版）"""
        tables = [
            # 知识条目主表（增加content_hash字段）
            """
            CREATE TABLE knowledge_items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                title VARCHAR(500) NOT NULL,
                content TEXT NOT NULL,
                summary TEXT,
                item_type VARCHAR(50) DEFAULT 'note',
                category VARCHAR(100),
                source_type VARCHAR(50),
                source_details TEXT,
                author VARCHAR(200),
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                access_count INTEGER DEFAULT 0,
                importance_level INTEGER DEFAULT 1 CHECK(importance_level BETWEEN 1 AND 5),
                understanding_level INTEGER DEFAULT 3 CHECK(understanding_level BETWEEN 1 AND 5),
                is_archived BOOLEAN DEFAULT 0,
                next_review_date DATE,
                content_hash VARCHAR(32) UNIQUE  -- 新增：内容哈希用于去重
            )
            """,

            # 标签表
            """
            CREATE TABLE tags (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name VARCHAR(50) UNIQUE NOT NULL,
                color VARCHAR(7),
                usage_count INTEGER DEFAULT 0
            )
            """,

            # 知识标签关联表
            """
            CREATE TABLE knowledge_tags (
                knowledge_id INTEGER,
                tag_id INTEGER,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (knowledge_id, tag_id),
                FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
                FOREIGN KEY (tag_id) REFERENCES tags(id) ON DELETE CASCADE
            )
            """,

            # 知识关联表
            """
            CREATE TABLE knowledge_relationships (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                source_id INTEGER NOT NULL,
                target_id INTEGER NOT NULL,
                relationship_type VARCHAR(50) NOT NULL,
                strength INTEGER DEFAULT 1 CHECK(strength BETWEEN 1 AND 5),
                description TEXT,
                created_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (source_id) REFERENCES knowledge_items(id) ON DELETE CASCADE,
                FOREIGN KEY (target_id) REFERENCES knowledge_items(id) ON DELETE CASCADE
            )
            """,

            # 复习记录表
            """
            CREATE TABLE review_sessions (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                knowledge_id INTEGER NOT NULL,
                review_date DATETIME DEFAULT CURRENT_TIMESTAMP,
                ease_factor REAL DEFAULT 2.5,
                interval_days INTEGER DEFAULT 1,
                performance_rating INTEGER CHECK(performance_rating BETWEEN 0 AND 5),
                next_review_date DATE,
                notes TEXT,
                FOREIGN KEY (knowledge_id) REFERENCES knowledge_items(id) ON DELETE CASCADE
            )
            """
        ]

        for table_sql in tables:
            try:
                self.conn.execute(table_sql)
            except sqlite3.Error as e:
                print(f"❌ 创建表时出错: {e}")
                raise

        # 创建索引以提高查询性能
        indexes = [
            "CREATE INDEX idx_knowledge_items_category ON knowledge_items(category)",
            "CREATE INDEX idx_knowledge_items_importance ON knowledge_items(importance_level)",
            "CREATE INDEX idx_knowledge_items_understanding ON knowledge_items(understanding_level)",
            "CREATE INDEX idx_knowledge_items_created_date ON knowledge_items(created_date)",
            "CREATE INDEX idx_knowledge_items_content_hash ON knowledge_items(content_hash)",
            "CREATE INDEX idx_knowledge_relationships_source ON knowledge_relationships(source_id)",
            "CREATE INDEX idx_knowledge_relationships_target ON knowledge_relationships(target_id)",
            "CREATE INDEX idx_review_sessions_knowledge ON review_sessions(knowledge_id)",
            "CREATE INDEX idx_review_sessions_date ON review_sessions(review_date)"
        ]

        for index_sql in indexes:
            try:
                self.conn.execute(index_sql)
            except sqlite3.Error as e:
                print(f"⚠️  创建索引时出错: {e}")

    def _insert_default_data(self):
        """插入默认数据"""
        # 插入默认标签
        default_tags = [
            ('Python', '#3572A5'),
            ('数据库', '#ff9999'),
            ('算法', '#00cc00'),
            ('重要', '#ff0000'),
            ('待复习', '#ff9900'),
            ('技术笔记', '#3498db'),
            ('读书笔记', '#e74c3c'),
            ('工作项目', '#f39c12'),
            ('AI', '#9b59b6'),  # 新增AI相关标签
            ('机器学习', '#e67e22'),
            ('深度学习', '#f1c40f'),
            ('数学', '#1abc9c')
        ]

        for name, color in default_tags:
            self.conn.execute(
                "INSERT OR IGNORE INTO tags (name, color) VALUES (?, ?)",
                (name, color)
            )

        # 插入示例知识条目（用于演示新功能）
        example_items = [
            {
                'title': '机器学习基础概念',
                'content': '机器学习是人工智能的一个分支，主要研究如何让计算机通过数据自动学习。常见的机器学习算法包括线性回归、决策树、支持向量机等。',
                'category': 'AI',
                'tags': ['AI', '机器学习', '算法'],
                'importance_level': 4,
                'understanding_level': 3
            },
            {
                'title': '神经网络原理',
                'content': '神经网络模仿人脑的神经元结构，由输入层、隐藏层和输出层组成。通过反向传播算法调整权重，实现复杂的模式识别功能。',
                'category': 'AI',
                'tags': ['AI', '深度学习', '神经网络'],
                'importance_level': 5,
                'understanding_level': 2
            }
        ]

        # 注意：这里只是示例，实际添加需要通过KnowledgeManager类
        print("📝 默认标签和数据已插入")

        self.conn.commit()

    def upgrade_database(self):
        """升级现有数据库（保留数据）"""
        if not os.path.exists(self.db_path):
            print("❌ 数据库文件不存在，无法升级")
            return False

        try:
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row

            # 检查是否需要添加content_hash字段
            cursor = self.conn.cursor()
            cursor.execute("PRAGMA table_info(knowledge_items)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'content_hash' not in columns:
                print("🔄 升级数据库表结构...")
                cursor.execute("ALTER TABLE knowledge_items ADD COLUMN content_hash VARCHAR(32)")
                print("✅ 数据库升级完成")
            else:
                print("✅ 数据库已是最新版本")

            self.conn.commit()
            return True

        except Exception as e:
            print(f"❌ 数据库升级失败: {e}")
            return False
        finally:
            if self.conn:
                self.conn.close()

if __name__ == "__main__":
    db = KnowledgeDatabase()

    # 检查是否要升级现有数据库
    if os.path.exists('knowledge.db'):
        choice = input("检测到现有数据库，是否升级而不是重新创建？(y/N): ")
        if choice.lower() == 'y':
            db.upgrade_database()
        else:
            db.initialize_database()
    else:
        db.initialize_database()
