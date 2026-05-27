#!/usr/bin/env python3
# knowledge_manager.py - 核心功能实现（修复版）

import sqlite3
import json
import re
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
import hashlib

class KnowledgeManager:
    def __init__(self, db_path='knowledge.db'):
        self.db_path = db_path

    def _get_connection(self):
        """为每个线程创建新的数据库连接"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        # 启用外键支持
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def add_knowledge_item(self, title: str, content: str, **kwargs) -> int:
        """添加知识条目"""
        summary = kwargs.get('summary', self._generate_summary(content))
        item_type = kwargs.get('item_type', 'note')
        category = kwargs.get('category', '未分类')
        tags = kwargs.get('tags', [])

        sql = """
        INSERT INTO knowledge_items
        (title, content, summary, item_type, category, source_type, source_details,
         importance_level, understanding_level, next_review_date, content_hash)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

        conn = self._get_connection()
        cursor = conn.cursor()

        # 生成内容哈希用于去重
        content_hash = hashlib.md5(content.encode('utf-8')).hexdigest()

        cursor.execute(sql, (
            title, content, summary, item_type, category,
            kwargs.get('source_type'), kwargs.get('source_details'),
            kwargs.get('importance_level', 1),
            kwargs.get('understanding_level', 3),
            kwargs.get('next_review_date', self._calculate_next_review_date(3)),
            content_hash
        ))

        item_id = cursor.lastrowid

        # 添加标签
        for tag_name in tags:
            self._add_tag_to_item(conn, item_id, tag_name)

        conn.commit()
        conn.close()
        return item_id

    def _generate_summary(self, content: str, max_length: int = 150) -> str:
        """智能生成摘要"""
        # 清理HTML标签和多余空格
        clean_content = re.sub(r'<[^>]+>', '', content)
        clean_content = re.sub(r'\s+', ' ', clean_content).strip()

        if len(clean_content) <= max_length:
            return clean_content

        # 尝试在句子边界截断
        sentences = re.split(r'[.!?。！？]', clean_content)
        summary = ""
        for sentence in sentences:
            if len(summary + sentence) < max_length - 3:
                summary += sentence + ". "
            else:
                break

        return summary.strip() + "..." if summary else clean_content[:max_length] + "..."

    def _add_tag_to_item(self, conn, knowledge_id: int, tag_name: str):
        """为知识条目添加标签"""
        cursor = conn.cursor()
        # 确保标签存在
        cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
        cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
        tag_id = cursor.fetchone()[0]

        # 关联标签
        cursor.execute(
            "INSERT OR IGNORE INTO knowledge_tags (knowledge_id, tag_id) VALUES (?, ?)",
            (knowledge_id, tag_id)
        )

        # 更新标签使用计数
        cursor.execute(
            "UPDATE tags SET usage_count = usage_count + 1 WHERE id = ?",
            (tag_id,)
        )

    def advanced_search(self, query: str = "", category: str = "", tags: List[str] = None,
                       importance_min: int = 0, importance_max: int = 5,
                       understanding_min: int = 0, understanding_max: int = 5,
                       date_from: str = "", date_to: str = "", limit: int = 50) -> List[Dict]:
        """高级搜索功能"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 构建动态SQL查询
        sql_parts = []
        params = []

        sql_base = """
        SELECT ki.*, GROUP_CONCAT(t.name) as tag_names
        FROM knowledge_items ki
        LEFT JOIN knowledge_tags kt ON ki.id = kt.knowledge_id
        LEFT JOIN tags t ON kt.tag_id = t.id
        """

        # 关键词搜索
        if query:
            sql_parts.append("(ki.title LIKE ? OR ki.content LIKE ? OR ki.summary LIKE ?)")
            search_term = f"%{query}%"
            params.extend([search_term, search_term, search_term])

        # 分类筛选
        if category:
            sql_parts.append("ki.category = ?")
            params.append(category)

        # 标签筛选 - 修复f-string问题
        if tags:
            placeholders = ','.join('?' * len(tags))
            # 使用简单的字符串拼接避免f-string嵌套问题
            tag_query = "ki.id IN (SELECT knowledge_id FROM knowledge_tags kt JOIN tags t ON kt.tag_id = t.id WHERE t.name IN (" + placeholders + ") GROUP BY knowledge_id HAVING COUNT(DISTINCT t.name) = ?)"
            sql_parts.append(tag_query)
            params.extend(tags)
            params.append(len(tags))

        # 重要性筛选
        if importance_min > 0 or importance_max < 5:
            sql_parts.append("ki.importance_level BETWEEN ? AND ?")
            params.extend([importance_min, importance_max])

        # 理解程度筛选
        if understanding_min > 0 or understanding_max < 5:
            sql_parts.append("ki.understanding_level BETWEEN ? AND ?")
            params.extend([understanding_min, understanding_max])

        # 日期范围筛选
        if date_from:
            sql_parts.append("ki.created_date >= ?")
            params.append(date_from)
        if date_to:
            sql_parts.append("ki.created_date <= ?")
            params.append(date_to)

        # 组合查询条件
        if sql_parts:
            sql_base += " WHERE " + " AND ".join(sql_parts)

        sql_base += " GROUP BY ki.id ORDER BY ki.importance_level DESC, ki.created_date DESC LIMIT ?"
        params.append(limit)

        cursor.execute(sql_base, params)
        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_knowledge_graph_data(self) -> Dict[str, Any]:
        """获取知识图谱数据"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 获取所有节点（知识条目）
        cursor.execute("""
            SELECT id, title, category, importance_level, understanding_level
            FROM knowledge_items
            WHERE is_archived = 0
        """)
        nodes = [dict(row) for row in cursor.fetchall()]

        # 获取所有边（关联关系）
        cursor.execute("""
            SELECT kr.id, kr.source_id, kr.target_id, kr.relationship_type, kr.strength,
                   ki1.title as source_title, ki2.title as target_title
            FROM knowledge_relationships kr
            JOIN knowledge_items ki1 ON kr.source_id = ki1.id
            JOIN knowledge_items ki2 ON kr.target_id = ki2.id
        """)
        edges = [dict(row) for row in cursor.fetchall()]

        # 获取分类统计
        cursor.execute("""
            SELECT category, COUNT(*) as count
            FROM knowledge_items
            WHERE is_archived = 0
            GROUP BY category
        """)
        categories = [dict(row) for row in cursor.fetchall()]

        conn.close()

        return {
            'nodes': nodes,
            'edges': edges,
            'categories': categories,
            'stats': {
                'total_nodes': len(nodes),
                'total_edges': len(edges),
                'total_categories': len(categories)
            }
        }

    def get_ai_recommendations(self, item_id: int, limit: int = 5) -> List[Dict]:
        """基于内容相似度的AI推荐"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 获取当前条目的信息
        cursor.execute("SELECT title, content, category FROM knowledge_items WHERE id = ?", (item_id,))
        current_item = cursor.fetchone()
        if not current_item:
            return []

        # 简单的基于标题和内容的相似度计算
        current_title = current_item['title'].lower()
        current_content = current_item['content'].lower()
        current_category = current_item['category']

        # 查找相关条目
        cursor.execute("""
            SELECT ki.*, GROUP_CONCAT(t.name) as tag_names,
                   (CASE WHEN ki.category = ? THEN 2 ELSE 1 END) as category_score,
                   (LENGTH(ki.title) - ABS(LENGTH(ki.title) - LENGTH(?))) as title_similarity
            FROM knowledge_items ki
            LEFT JOIN knowledge_tags kt ON ki.id = kt.knowledge_id
            LEFT JOIN tags t ON kt.tag_id = t.id
            WHERE ki.id != ? AND ki.is_archived = 0
            GROUP BY ki.id
            ORDER BY category_score DESC, title_similarity DESC
            LIMIT ?
        """, (current_category, current_title, item_id, limit))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_content_analysis(self, item_id: int) -> Dict[str, Any]:
        """内容分析功能"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("SELECT content FROM knowledge_items WHERE id = ?", (item_id,))
        result = cursor.fetchone()
        if not result:
            return {}

        content = result['content']

        # 基础文本分析
        words = re.findall(r'\b\w+\b', content)
        sentences = re.split(r'[.!?。！？]', content)
        sentences = [s.strip() for s in sentences if s.strip()]

        analysis = {
            'word_count': len(words),
            'sentence_count': len(sentences),
            'avg_sentence_length': len(words) / len(sentences) if sentences else 0,
            'reading_time_minutes': max(1, len(words) // 200),
            'has_code_blocks': '```' in content or '<code>' in content,
            'has_images': '![' in content or '<img' in content,
            'has_links': 'http' in content,
            'has_math': '$' in content or '\\[' in content
        }

        conn.close()
        return analysis

    # def search_knowledge(self, query: str, limit: int = 50) -> List[Dict]:
    #     """增强搜索功能：搜索标题、内容、分类、标签"""
    #     conn = self._get_connection()
    #     cursor = conn.cursor()

    #     sql = """
    #     SELECT DISTINCT ki.*, GROUP_CONCAT(t.name) as tag_names
    #     FROM knowledge_items ki
    #     LEFT JOIN knowledge_tags kt ON ki.id = kt.knowledge_id
    #     LEFT JOIN tags t ON kt.tag_id = t.id
    #     WHERE ki.title LIKE ?
    #        OR ki.content LIKE ?
    #        OR ki.summary LIKE ?
    #        OR ki.category LIKE ?
    #        OR t.name LIKE ?
    #     GROUP BY ki.id
    #     ORDER BY ki.importance_level DESC, ki.created_date DESC
    #     LIMIT ?
    #     """
    def search_knowledge(self, query: str, limit: int = 50) -> List[Dict]:
        """增强搜索功能：支持多关键词搜索，用逗号或空格分隔"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 处理空查询：返回所有条目
        if not query or query.strip() == "":
            cursor.execute("""
                SELECT DISTINCT ki.*, GROUP_CONCAT(t.name) as tag_names
                FROM knowledge_items ki
                LEFT JOIN knowledge_tags kt ON ki.id = kt.knowledge_id
                LEFT JOIN tags t ON kt.tag_id = t.id
                GROUP BY ki.id
                ORDER BY ki.importance_level DESC, ki.created_date DESC
                LIMIT ?
            """, (limit,))

            results = cursor.fetchall()
            items = [dict(row) for row in results]
            conn.close()
            return items

        # 处理多关键词：支持逗号和空格分隔
        keywords = []
        if ',' in query:
            # 用逗号分隔
            keywords = [kw.strip() for kw in query.split(',') if kw.strip()]
        else:
            # 用空格分隔
            keywords = [kw.strip() for kw in query.split() if kw.strip()]

        # 如果没有有效关键词，返回空结果（这里应该不会发生，因为前面已经处理了空查询）
        if not keywords:
            return []

        # 构建LIKE查询条件
        like_conditions = []
        params = []

        for keyword in keywords:
            like_pattern = f'%{keyword}%'
            # 每个关键词在多个字段中搜索
            like_conditions.append("""
                (ki.title LIKE ? OR ki.content LIKE ? OR ki.summary LIKE ?
                 OR ki.category LIKE ? OR t.name LIKE ?)
            """)
            params.extend([like_pattern] * 5)  # 5个字段都需要参数

        # 用AND连接所有关键词条件
        where_clause = " AND ".join(like_conditions)

        sql = f"""
        SELECT DISTINCT ki.*, GROUP_CONCAT(t.name) as tag_names
        FROM knowledge_items ki
        LEFT JOIN knowledge_tags kt ON ki.id = kt.knowledge_id
        LEFT JOIN tags t ON kt.tag_id = t.id
        WHERE {where_clause}
        GROUP BY ki.id
        ORDER BY ki.importance_level DESC, ki.created_date DESC
        LIMIT ?
        """

        params.append(limit)  # 添加limit参数

        cursor.execute(sql, params)
        results = cursor.fetchall()

        # 转换为字典列表
        items = [dict(row) for row in results]

        conn.close()
        return items
    def get_item_by_id(self, item_id: int) -> Dict:
        """根据ID获取知识条目详情"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ki.*, GROUP_CONCAT(t.name) as tag_names
            FROM knowledge_items ki
            LEFT JOIN knowledge_tags kt ON ki.id = kt.knowledge_id
            LEFT JOIN tags t ON kt.tag_id = t.id
            WHERE ki.id = ?
            GROUP BY ki.id
        """, (item_id,))

        row = cursor.fetchone()
        conn.close()
        return dict(row) if row else None

    def add_review_session(self, knowledge_id: int, performance_rating: int, notes: str = "") -> bool:
        """添加复习记录"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 获取之前的复习记录
        cursor.execute("""
            SELECT ease_factor, interval_days
            FROM review_sessions
            WHERE knowledge_id = ?
            ORDER BY review_date DESC
            LIMIT 1
        """, (knowledge_id,))

        last_review = cursor.fetchone()

        if last_review:
            ease_factor = last_review['ease_factor']
            last_interval = last_review['interval_days']
        else:
            ease_factor = 2.5
            last_interval = 0

        # 计算新的间隔（简化版SM-2算法）
        new_interval, new_ease = self._calculate_next_interval(
            performance_rating, last_interval, ease_factor
        )

        next_review_date = datetime.now() + timedelta(days=new_interval)

        # 插入复习记录
        cursor.execute("""
            INSERT INTO review_sessions
            (knowledge_id, performance_rating, ease_factor, interval_days, next_review_date, notes)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (knowledge_id, performance_rating, new_ease, new_interval,
              next_review_date.date(), notes))

        # 更新知识条目的下次复习时间
        cursor.execute("""
            UPDATE knowledge_items
            SET next_review_date = ?, understanding_level = ?
            WHERE id = ?
        """, (next_review_date.date(), performance_rating, knowledge_id))

        conn.commit()
        conn.close()
        return True

    def _calculate_next_interval(self, performance: int, last_interval: int, ease_factor: float):
        """计算下次复习间隔"""
        if performance >= 3:
            if last_interval == 0:
                new_interval = 1
            elif last_interval == 1:
                new_interval = 3
            else:
                new_interval = int(last_interval * ease_factor)

            new_ease = max(1.3, ease_factor + 0.1 - (5 - performance) * 0.08)
        else:
            new_interval = 1
            new_ease = max(1.3, ease_factor - 0.2)

        return new_interval, new_ease

    def _calculate_next_review_date(self, understanding_level: int) -> str:
        """根据理解程度计算下次复习日期"""
        base_intervals = {1: 1, 2: 2, 3: 4, 4: 7, 5: 14}
        days = base_intervals.get(understanding_level, 7)
        return (datetime.now() + timedelta(days=days)).strftime('%Y-%m-%d')

    def get_today_reviews(self) -> List[Dict]:
        """获取今天需要复习的项目"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ki.id, ki.title, ki.summary, ki.understanding_level,
                   rs.ease_factor, rs.interval_days
            FROM knowledge_items ki
            LEFT JOIN review_sessions rs ON ki.id = rs.knowledge_id
            WHERE ki.next_review_date <= date('now')
            AND ki.is_archived = 0
            ORDER BY ki.importance_level DESC, ki.next_review_date ASC
        """)

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def create_relationship(self, source_id: int, target_id: int,
                          relationship_type: str = "relates_to", strength: int = 1) -> bool:
        """创建知识关联"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO knowledge_relationships
                (source_id, target_id, relationship_type, strength)
                VALUES (?, ?, ?, ?)
            """, (source_id, target_id, relationship_type, strength))

            conn.commit()
            conn.close()
            return True
        except sqlite3.IntegrityError:
            if 'conn' in locals():
                conn.close()
            return False

    def get_related_items(self, item_id: int, depth: int = 1) -> List[Dict]:
        """获取相关知识点"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT DISTINCT
                CASE WHEN source_id = ? THEN target_id ELSE source_id END as related_id,
                relationship_type
            FROM knowledge_relationships
            WHERE source_id = ? OR target_id = ?
        """, (item_id, item_id, item_id))

        related_ids = [row['related_id'] for row in cursor.fetchall()]

        if not related_ids:
            conn.close()
            return []

        placeholders = ','.join('?' * len(related_ids))
        cursor.execute(f"""
            SELECT ki.*, GROUP_CONCAT(t.name) as tag_names
            FROM knowledge_items ki
            LEFT JOIN knowledge_tags kt ON ki.id = kt.knowledge_id
            LEFT JOIN tags t ON kt.tag_id = t.id
            WHERE ki.id IN ({placeholders})
            GROUP BY ki.id
        """, related_ids)

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def get_statistics(self) -> Dict[str, Any]:
        """获取知识库统计信息"""
        conn = self._get_connection()
        cursor = conn.cursor()

        stats = {}

        cursor.execute("SELECT COUNT(*) as total FROM knowledge_items")
        stats['total_items'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) as total FROM knowledge_items WHERE is_archived = 1")
        stats['archived_items'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(DISTINCT category) as count FROM knowledge_items")
        stats['categories_count'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) as count FROM tags")
        stats['tags_count'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) as count FROM knowledge_relationships")
        stats['relationships_count'] = cursor.fetchone()[0]

        cursor.execute("""
            SELECT understanding_level, COUNT(*) as count
            FROM knowledge_items
            WHERE is_archived = 0
            GROUP BY understanding_level
            ORDER BY understanding_level
        """)
        stats['understanding_distribution'] = dict(cursor.fetchall())

        cursor.execute("SELECT COUNT(*) as count FROM knowledge_items WHERE date(created_date) = date('now')")
        stats['today_new'] = cursor.fetchone()[0]

        cursor.execute("SELECT COUNT(*) as count FROM knowledge_items WHERE next_review_date <= date('now') AND is_archived = 0")
        stats['today_reviews'] = cursor.fetchone()[0]

        conn.close()
        return stats

    def close(self):
        pass

    def import_from_file(self, file_path: str) -> dict:
        """从JSON或YAML文件导入知识库"""
        import os
        import yaml
        import json

        if not os.path.exists(file_path):
            return {'success': False, 'error': '文件不存在'}

        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                if file_path.endswith('.yaml') or file_path.endswith('.yml'):
                    data = yaml.safe_load(f)
                else:
                    data = json.load(f)

            imported_count = 0
            if isinstance(data, list):
                for item_data in data:
                    try:
                        self.add_knowledge_item(**item_data)
                        imported_count += 1
                    except Exception as e:
                        print(f"导入失败: {e}")

            return {'success': True, 'imported_count': imported_count}

        except Exception as e:
            return {'success': False, 'error': str(e)}

    def delete_knowledge_item(self, item_id: int) -> bool:
        """删除知识条目"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("DELETE FROM knowledge_items WHERE id = ?", (item_id,))
            conn.commit()
            return cursor.rowcount > 0
        except Exception as e:
            conn.rollback()
            return False
        finally:
            conn.close()

    def update_knowledge_item(self, item_id: int, data: dict) -> bool:
        """更新知识条目"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute("""
                UPDATE knowledge_items
                SET title = ?, content = ?, category = ?,
                    importance_level = ?, understanding_level = ?,
                    updated_date = datetime('now')
                WHERE id = ?
            """, (
                data['title'], data['content'], data['category'],
                data['importance_level'], data['understanding_level'],
                item_id
            ))

            cursor.execute("DELETE FROM knowledge_tags WHERE knowledge_id = ?", (item_id,))
            for tag_name in data.get('tags', []):
                self._add_tag_to_item(conn, item_id, tag_name)

            conn.commit()
            return True
        except Exception as e:
            conn.rollback()
            print(f"更新失败: {e}")
            return False
        finally:
            conn.close()

    def get_recent_items(self, limit=5):
        """获取最近添加的N条知识条目"""
        conn = self._get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            SELECT ki.*, GROUP_CONCAT(t.name) as tag_names
            FROM knowledge_items ki
            LEFT JOIN knowledge_tags kt ON ki.id = kt.knowledge_id
            LEFT JOIN tags t ON kt.tag_id = t.id
            GROUP BY ki.id
            ORDER BY ki.created_date DESC
            LIMIT ?
        """, (limit,))

        results = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return results

    def delete_relationship(self, source_id, target_id):
        """删除两个知识条目之间的关联"""
        try:
            conn = self._get_connection()
            cursor = conn.cursor()

            # 删除关联（双向都删除）
            cursor.execute("""
                DELETE FROM knowledge_relationships
                WHERE (source_id = ? AND target_id = ?)
                   OR (source_id = ? AND target_id = ?)
            """, (source_id, target_id, target_id, source_id))

            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"删除关联失败: {e}")
            return False

    def get_all_categories(self):
        """获取所有分类"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT category, COUNT(*) as item_count
            FROM knowledge_items
            WHERE category IS NOT NULL AND category != ''
            GROUP BY category
            ORDER BY item_count DESC
        """)
        categories = [{'name': row['category'], 'count': row['item_count']} for row in cursor.fetchall()]
        conn.close()
        return categories

    def get_all_tags(self):
        """获取所有标签"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT t.name, t.color, COUNT(kt.knowledge_id) as usage_count
            FROM tags t
            LEFT JOIN knowledge_tags kt ON t.id = kt.tag_id
            GROUP BY t.id, t.name
            ORDER BY usage_count DESC
        """)
        tags = [{'name': row['name'], 'color': row['color'], 'count': row['usage_count']} for row in cursor.fetchall()]
        conn.close()
        return tags

    def get_items_by_category(self, category_name):
        """获取指定分类下的所有知识条目"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ki.*, GROUP_CONCAT(t.name) as tag_names
            FROM knowledge_items ki
            LEFT JOIN knowledge_tags kt ON ki.id = kt.knowledge_id
            LEFT JOIN tags t ON kt.tag_id = t.id
            WHERE ki.category = ?
            GROUP BY ki.id
            ORDER BY ki.created_date DESC
        """, (category_name,))
        items = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return items

    def get_items_by_tag(self, tag_name):
        """获取指定标签下的所有知识条目"""
        conn = self._get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT ki.*, GROUP_CONCAT(t.name) as tag_names
            FROM knowledge_items ki
            JOIN knowledge_tags kt ON ki.id = kt.knowledge_id
            JOIN tags t ON kt.tag_id = t.id
            WHERE t.name = ?
            GROUP BY ki.id
            ORDER BY ki.created_date DESC
        """, (tag_name,))
        items = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return items
    def search_multiple_keywords(self, keywords, limit=50):
        """搜索多个关键词（OR逻辑）"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 构建查询条件：每个关键词匹配标题、内容或标签
        conditions = []
        params = []

        for keyword in keywords:
            like_pattern = f'%{keyword}%'
            conditions.append("""
                (ki.title LIKE ? OR ki.content LIKE ? OR ki.summary LIKE ?
                 OR EXISTS (
                     SELECT 1 FROM knowledge_tags kt
                     JOIN tags t ON kt.tag_id = t.id
                     WHERE kt.knowledge_id = ki.id AND t.name LIKE ?
                 ))
            """)
            params.extend([like_pattern, like_pattern, like_pattern, like_pattern])

        where_clause = " OR ".join(conditions)

        # 执行查询
        cursor.execute(f"""
            SELECT DISTINCT ki.*, GROUP_CONCAT(t.name) as tag_names
            FROM knowledge_items ki
            LEFT JOIN knowledge_tags kt ON ki.id = kt.knowledge_id
            LEFT JOIN tags t ON kt.tag_id = t.id
            WHERE {where_clause}
            GROUP BY ki.id
            ORDER BY ki.created_date DESC
            LIMIT ?
        """, params + [limit])

        items = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return items

    def search_multiple_keywords_and(self, keywords, limit=50):
        """搜索多个关键词（AND逻辑）- 必须包含所有关键词"""
        conn = self._get_connection()
        cursor = conn.cursor()

        # 构建查询条件：必须匹配所有关键词
        conditions = []
        params = []

        for keyword in keywords:
            like_pattern = f'%{keyword}%'
            conditions.append("""
                (ki.title LIKE ? OR ki.content LIKE ? OR ki.summary LIKE ?
                 OR EXISTS (
                     SELECT 1 FROM knowledge_tags kt
                     JOIN tags t ON kt.tag_id = t.id
                     WHERE kt.knowledge_id = ki.id AND t.name LIKE ?
                 ))
            """)
            params.extend([like_pattern, like_pattern, like_pattern, like_pattern])

        where_clause = " AND ".join(conditions)

        # 执行查询
        cursor.execute(f"""
            SELECT DISTINCT ki.*, GROUP_CONCAT(t.name) as tag_names
            FROM knowledge_items ki
            LEFT JOIN knowledge_tags kt ON ki.id = kt.knowledge_id
            LEFT JOIN tags t ON kt.tag_id = t.id
            WHERE {where_clause}
            GROUP BY ki.id
            ORDER BY ki.created_date DESC
            LIMIT ?
        """, params + [limit])

        items = [dict(row) for row in cursor.fetchall()]
        conn.close()
        return items

    def add_tags_to_item(self, item_id, tags):
        """为条目添加标签（不覆盖现有标签）"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # 获取现有标签
            cursor.execute("""
                SELECT t.name FROM tags t
                JOIN knowledge_tags kt ON t.id = kt.tag_id
                WHERE kt.knowledge_id = ?
            """, (item_id,))
            existing_tags = [row['name'] for row in cursor.fetchall()]

            # 过滤掉已存在的标签
            new_tags = [tag for tag in tags if tag not in existing_tags]

            # 添加新标签
            for tag_name in new_tags:
                # 获取或创建标签
                cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
                cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
                tag_id = cursor.fetchone()['id']

                # 关联标签
                cursor.execute(
                    "INSERT OR IGNORE INTO knowledge_tags (knowledge_id, tag_id) VALUES (?, ?)",
                    (item_id, tag_id)
                )

            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            print(f"添加标签失败: {e}")
            return False
        finally:
            conn.close()

    def remove_tags_from_item(self, item_id, tags):
        """从条目中移除指定标签"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            for tag_name in tags:
                cursor.execute("""
                    DELETE FROM knowledge_tags
                    WHERE knowledge_id = ? AND tag_id IN (
                        SELECT id FROM tags WHERE name = ?
                    )
                """, (item_id, tag_name))

            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            print(f"移除标签失败: {e}")
            return False
        finally:
            conn.close()

    def set_item_tags(self, item_id, tags):
        """设置条目标签（覆盖现有标签）"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            # 删除现有标签关联
            cursor.execute("DELETE FROM knowledge_tags WHERE knowledge_id = ?", (item_id,))

            # 添加新标签
            for tag_name in tags:
                # 获取或创建标签
                cursor.execute("INSERT OR IGNORE INTO tags (name) VALUES (?)", (tag_name,))
                cursor.execute("SELECT id FROM tags WHERE name = ?", (tag_name,))
                tag_id = cursor.fetchone()['id']

                # 关联标签
                cursor.execute(
                    "INSERT OR IGNORE INTO knowledge_tags (knowledge_id, tag_id) VALUES (?, ?)",
                    (item_id, tag_id)
                )

            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            print(f"设置标签失败: {e}")
            return False
        finally:
            conn.close()

    def set_item_category(self, item_id, category):
        """设置条目分类"""
        conn = self._get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(
                "UPDATE knowledge_items SET category = ?, updated_date = CURRENT_TIMESTAMP WHERE id = ?",
                (category, item_id)
            )
            conn.commit()
            return True

        except Exception as e:
            conn.rollback()
            print(f"设置分类失败: {e}")
            return False
        finally:
            conn.close()

# 便捷函数
def create_sample_knowledge_base():
    """创建示例知识库"""
    from sample_data import sample_data

    manager = KnowledgeManager()

    for item in sample_data:
        manager.add_knowledge_item(**item)

    print("✅ 示例知识库创建完成!")
    return manager

if __name__ == "__main__":
    manager = KnowledgeManager()
    stats = manager.get_statistics()
    print("知识库统计:", stats)
