"""
媒体内容API
用于处理媒体内容的上传和获取
"""

import os
import uuid
from flask import Blueprint, request, jsonify, current_app, send_from_directory
from flask_login import login_required
from werkzeug.utils import secure_filename
import logging

# 创建蓝图
media_bp = Blueprint('media', __name__)

# 获取日志记录器
logger = logging.getLogger(__name__)

# 允许的文件类型
ALLOWED_EXTENSIONS = {
    'image': {'png', 'jpg', 'jpeg', 'gif', 'webp'},
    'video': {'mp4', 'webm', 'ogg', 'mov'},
    'gif': {'gif'}
}

def allowed_file(filename, file_type=None):
    """检查文件是否允许上传"""
    if '.' not in filename:
        return False
    
    ext = filename.rsplit('.', 1)[1].lower()
    
    if file_type:
        return ext in ALLOWED_EXTENSIONS.get(file_type, set())
    
    # 检查所有允许的扩展名
    for extensions in ALLOWED_EXTENSIONS.values():
        if ext in extensions:
            return True
    
    return False

def get_file_type(filename):
    """获取文件类型"""
    if '.' not in filename:
        return None
    
    ext = filename.rsplit('.', 1)[1].lower()
    
    if ext in ALLOWED_EXTENSIONS['image']:
        return 'image'
    elif ext in ALLOWED_EXTENSIONS['video']:
        return 'video'
    elif ext in ALLOWED_EXTENSIONS['gif']:
        return 'gif'
    
    return None

@media_bp.route('/api/media/upload', methods=['POST'])
@login_required
def upload_media():
    """上传媒体文件"""
    try:
        # 检查是否有文件
        if 'file' not in request.files:
            return jsonify({
                'success': False,
                'message': '没有文件'
            }), 400
        
        file = request.files['file']
        
        # 检查文件名
        if file.filename == '':
            return jsonify({
                'success': False,
                'message': '没有选择文件'
            }), 400
        
        # 检查文件类型
        file_type = request.form.get('type')
        if not file_type:
            file_type = get_file_type(file.filename)
        
        if not allowed_file(file.filename, file_type):
            return jsonify({
                'success': False,
                'message': '不支持的文件类型'
            }), 400
        
        # 创建安全的文件名
        filename = secure_filename(file.filename)
        # 添加UUID前缀，避免文件名冲突
        unique_filename = f"{uuid.uuid4().hex}_{filename}"
        
        # 确保媒体目录存在
        media_dir = os.path.join(current_app.static_folder, 'media', file_type)
        os.makedirs(media_dir, exist_ok=True)
        
        # 保存文件
        file_path = os.path.join(media_dir, unique_filename)
        file.save(file_path)
        
        # 生成URL
        media_url = f"/static/media/{file_type}/{unique_filename}"
        
        logger.info(f"媒体文件上传成功: {media_url}")
        return jsonify({
            'success': True,
            'message': '上传成功',
            'url': media_url,
            'type': file_type
        })
    except Exception as e:
        logger.error(f"媒体文件上传失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"上传失败: {str(e)}"
        }), 500

@media_bp.route('/api/media/<path:filename>')
def get_media(filename):
    """获取媒体文件"""
    try:
        # 从URL中提取文件类型
        parts = filename.split('/')
        if len(parts) < 2:
            return jsonify({
                'success': False,
                'message': '无效的文件路径'
            }), 400
        
        file_type = parts[0]
        file_name = parts[-1]
        
        # 检查文件类型
        if file_type not in ALLOWED_EXTENSIONS:
            return jsonify({
                'success': False,
                'message': '不支持的文件类型'
            }), 400
        
        # 返回文件
        media_dir = os.path.join(current_app.static_folder, 'media', file_type)
        return send_from_directory(media_dir, file_name)
    except Exception as e:
        logger.error(f"获取媒体文件失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"获取失败: {str(e)}"
        }), 500
