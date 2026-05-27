from flask import Blueprint, request, jsonify, current_app, g
from knowledge_manager import KnowledgeManager
import os
import re
import urllib.parse

upload_bp = Blueprint('upload', __name__)


def get_manager():
    if 'manager' not in g:
        g.manager = KnowledgeManager(current_app.config['DB_PATH'])
    return g.manager


def _get_upload_config():
    return current_app.config['APP_CONFIG']['upload']


def allowed_file(filename, file_type):
    """检查文件类型是否允许"""
    if '.' not in filename:
        return False

    ext = filename.rsplit('.', 1)[1].lower()
    if file_type == 'images':
        return ext in set(_get_upload_config()['image_extensions'])
    elif file_type == 'files':
        return ext in set(_get_upload_config()['file_extensions'])
    return False


def secure_filename_with_chinese(filename):
    """
    安全地处理文件名，同时保留中文字符。
    移除了操作系统路径分隔符等危险字符，但保留了中文、字母、数字、下划线、连字符和点。
    """
    if not filename:
        return "file"

    # 定义一个更安全的模式，主要移除路径分隔符和其他可能引起问题的字符
    # 允许：中文字符 (一-龥)、字母、数字、下划线、连字符、点
    dangerous_chars = r'[\/\\:*?"<>|\x00]'  # 移除这些危险字符
    safe_name = re.sub(dangerous_chars, '_', filename)

    # 确保文件名不以点或空格开头（在某些系统上可能有问题）
    safe_name = safe_name.lstrip('. ')

    return safe_name if safe_name else "file"


@upload_bp.route('/api/upload', methods=['POST'])
def api_upload_files():
    """文件上传API - 支持中文文件名"""
    try:
        if 'files' not in request.files:
            return jsonify({'success': False, 'error': '没有选择文件'})

        files = request.files.getlist('files')
        file_type = request.form.get('file_type', 'files')

        if not files or files[0].filename == '':
            return jsonify({'success': False, 'error': '没有选择文件'})

        # 确定上传目录（使用 Flask 的 static_folder 确保文件可访问）
        static_dir = current_app.static_folder
        if file_type == 'images':
            upload_folder = os.path.join(static_dir, 'images')
            allowed_extensions = set(_get_upload_config()['image_extensions'])
        else:
            upload_folder = os.path.join(static_dir, 'files')
            allowed_extensions = set(_get_upload_config()['file_extensions'])

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

                # 生成访问URL
                url_dir = 'static/images' if file_type == 'images' else 'static/files'
                encoded_filename = urllib.parse.quote(original_filename)
                file_url = f"/{url_dir}/{encoded_filename}"
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


def allowed_text_file(filename):
    """检查文件是否为允许的文本类型"""
    if '.' not in filename:
        return False
    ext = filename.rsplit('.', 1)[1].lower()
    return ext in set(_get_upload_config()['text_extensions'])


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


@upload_bp.route('/api/import_text_files', methods=['POST'])
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
                manager = get_manager()
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
