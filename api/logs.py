"""
日志API模块
处理所有日志相关的API请求
"""

import os
import logging
import re
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, session, current_app

# 创建日志记录器
logger = logging.getLogger('api.logs')

# 创建Blueprint
logs_api = Blueprint('logs_api', __name__, url_prefix='/logs')

@logs_api.route('/system', methods=['GET'])
def get_system_logs():
    """获取系统日志"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401
    
    try:
        # 获取请求参数
        lines = request.args.get('lines', default=50, type=int)
        level = request.args.get('level', default='info').lower()
        
        # 验证并限制行数
        if lines < 1:
            lines = 50
        elif lines > 1000:
            lines = 1000
            
        # 获取日志目录
        log_dir = os.getenv('LOG_DIR', 'logs')
        if not os.path.isabs(log_dir):
            log_dir = os.path.join(os.getcwd(), log_dir)
            
        # 获取主日志文件路径
        log_file = os.path.join(log_dir, 'app.log')
        
        # 如果日志文件不存在，尝试查找其他日志文件
        if not os.path.exists(log_file):
            log_files = []
            if os.path.exists(log_dir):
                log_files = [f for f in os.listdir(log_dir) if f.endswith('.log')]
            
            if log_files:
                # 使用最新的日志文件
                log_file = os.path.join(log_dir, log_files[0])
            else:
                return jsonify({
                    "success": False,
                    "message": "未找到日志文件",
                    "data": {
                        "log_dir": log_dir,
                        "log_file": log_file
                    }
                }), 404
        
        # 读取日志文件
        log_entries = []
        level_filter = get_level_filter(level)
        
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                # 从文件末尾读取指定行数
                all_lines = f.readlines()
                filtered_lines = []
                
                # 从后向前过滤日志级别
                for line in reversed(all_lines):
                    if level_filter(line):
                        filtered_lines.append(line.strip())
                        if len(filtered_lines) >= lines:
                            break
                
                # 再次反转，使日志按时间顺序排列
                log_entries = list(reversed(filtered_lines))
        except Exception as e:
            logger.error(f"读取日志文件时出错: {str(e)}")
            return jsonify({
                "success": False,
                "message": f"读取日志文件时出错: {str(e)}",
                "data": {
                    "log_file": log_file
                }
            }), 500
        
        return jsonify({
            "success": True,
            "data": {
                "log_file": log_file,
                "log_entries": log_entries,
                "total_entries": len(log_entries),
                "level": level
            }
        })
    except Exception as e:
        logger.error(f"获取系统日志时出错: {str(e)}")
        return jsonify({"success": False, "message": f"获取系统日志时出错: {str(e)}"}), 500

def get_level_filter(level):
    """获取日志级别过滤器"""
    if level == 'debug':
        # 包含所有级别
        return lambda line: True
    elif level == 'info':
        # 包含INFO, WARNING, ERROR, CRITICAL
        return lambda line: not re.search(r'\[DEBUG\]', line, re.IGNORECASE)
    elif level == 'warning':
        # 包含WARNING, ERROR, CRITICAL
        return lambda line: re.search(r'\[(WARNING|ERROR|CRITICAL)\]', line, re.IGNORECASE)
    elif level == 'error':
        # 包含ERROR, CRITICAL
        return lambda line: re.search(r'\[(ERROR|CRITICAL)\]', line, re.IGNORECASE)
    else:
        # 默认包含所有级别
        return lambda line: True
