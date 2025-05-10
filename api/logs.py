"""
日志API模块
处理所有日志相关的API请求
"""

import os
import logging
import re
import glob
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
        # 添加更详细的错误信息
        logger.warning("尝试未登录访问日志API")
        return jsonify({
            "success": False,
            "message": "未登录",
            "debug_info": {
                "session_keys": list(session.keys()),
                "has_user_id": 'user_id' in session,
                "request_path": request.path,
                "request_args": dict(request.args)
            }
        }), 401

    try:
        # 获取请求参数
        lines = request.args.get('lines', default=50, type=int)
        level = request.args.get('level', default='info').lower()
        file_name = request.args.get('file', default='')

        # 验证并限制行数
        if lines < 1:
            lines = 50
        elif lines > 1000:
            lines = 1000

        # 使用固定的日志目录
        log_dir = os.path.join(os.getcwd(), 'logs')
        logger.info(f"使用固定的日志目录: {log_dir}")

        # 确保日志目录存在
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
                logger.warning(f"日志目录不存在，已创建: {log_dir}")
            except Exception as e:
                logger.error(f"创建日志目录时出错: {str(e)}")
                # 尝试使用临时目录
                import tempfile
                log_dir = tempfile.gettempdir()
                logger.warning(f"使用临时目录作为日志目录: {log_dir}")

        # 获取可用的日志文件列表
        available_log_files = []
        try:
            available_log_files = glob.glob(os.path.join(log_dir, '*.log'))
            logger.info(f"找到 {len(available_log_files)} 个日志文件")
        except Exception as e:
            logger.error(f"查找日志文件时出错: {str(e)}")
            # 即使出错也继续执行，返回空列表

        # 获取日志文件路径
        if file_name:
            # 使用指定的日志文件
            log_file = os.path.join(log_dir, file_name)
            logger.info(f"使用指定的日志文件: {log_file}")
        else:
            # 获取主日志文件路径
            log_file = os.path.join(log_dir, 'app.log')
            logger.info(f"使用默认日志文件: {log_file}")

        # 如果日志文件不存在，尝试查找其他日志文件
        if not os.path.exists(log_file):
            logger.warning(f"指定的日志文件不存在: {log_file}")

            # 尝试创建一个空的日志文件
            try:
                with open(log_file, 'w') as f:
                    f.write(f"日志文件创建于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
                logger.info(f"已创建新的日志文件: {log_file}")

                # 返回创建的日志文件内容
                return jsonify({
                    "success": True,
                    "data": {
                        "log_file": log_file,
                        "log_entries": [f"日志文件创建于 {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"],
                        "total_entries": 1,
                        "level": level,
                        "available_log_files": [os.path.basename(f) for f in available_log_files]
                    }
                })
            except Exception as e:
                logger.error(f"创建日志文件时出错: {str(e)}")

            # 如果创建失败，返回一个默认的响应
            return jsonify({
                "success": True,
                "data": {
                    "log_file": log_file,
                    "log_entries": ["系统尚未生成日志文件，请先执行一些操作或检查日志目录权限"],
                    "total_entries": 1,
                    "level": level,
                    "available_log_files": [os.path.basename(f) for f in available_log_files]
                }
            })

        # 读取日志文件
        log_entries = []
        level_filter = get_level_filter(level)

        try:
            # 检查文件是否存在且可读
            if not os.path.exists(log_file):
                logger.warning(f"日志文件不存在: {log_file}")
                return jsonify({
                    "success": True,
                    "data": {
                        "log_file": log_file,
                        "log_entries": ["日志文件不存在或为空"],
                        "total_entries": 1,
                        "level": level,
                        "available_log_files": [os.path.basename(f) for f in available_log_files]
                    }
                })

            # 检查文件大小
            file_size = os.path.getsize(log_file)
            if file_size == 0:
                logger.warning(f"日志文件为空: {log_file}")
                return jsonify({
                    "success": True,
                    "data": {
                        "log_file": log_file,
                        "log_entries": ["日志文件为空"],
                        "total_entries": 1,
                        "level": level,
                        "available_log_files": [os.path.basename(f) for f in available_log_files]
                    }
                })

            # 读取文件内容
            # 尝试不同的编码方式读取文件
            try:
                # 首先尝试UTF-8
                with open(log_file, 'r', encoding='utf-8') as f:
                    all_lines = f.readlines()
            except UnicodeDecodeError:
                # 如果UTF-8失败，尝试GBK（中文环境常用）
                try:
                    with open(log_file, 'r', encoding='gbk') as f:
                        all_lines = f.readlines()
                except UnicodeDecodeError:
                    # 最后使用errors='replace'作为后备方案
                    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                        all_lines = f.readlines()

            filtered_lines = []

            # 从后向前过滤日志级别
            for line in reversed(all_lines):
                try:
                    if level_filter(line):
                        filtered_lines.append(line.strip())
                        if len(filtered_lines) >= lines:
                            break
                except Exception as e:
                    logger.error(f"过滤日志行时出错: {str(e)}, 行内容: {line[:50]}...")
                    continue

            # 再次反转，使日志按时间顺序排列
            log_entries = list(reversed(filtered_lines))

            # 如果没有日志条目，添加一个提示
            if not log_entries:
                log_entries = ["没有找到符合条件的日志记录"]
        except Exception as e:
            logger.error(f"读取日志文件时出错: {str(e)}")
            return jsonify({
                "success": False,
                "message": f"读取日志文件时出错: {str(e)}",
                "data": {
                    "log_file": log_file,
                    "available_log_files": [os.path.basename(f) for f in available_log_files]
                }
            }), 500

        return jsonify({
            "success": True,
            "data": {
                "log_file": log_file,
                "log_entries": log_entries,
                "total_entries": len(log_entries),
                "level": level,
                "available_log_files": [os.path.basename(f) for f in available_log_files]
            }
        })
    except Exception as e:
        logger.error(f"获取系统日志时出错: {str(e)}")
        return jsonify({"success": False, "message": f"获取系统日志时出错: {str(e)}"}), 500

@logs_api.route('/download', methods=['GET'])
def download_logs():
    """下载日志文件"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        lines = request.args.get('lines', default=1000, type=int)
        level = request.args.get('level', default='info').lower()
        file_name = request.args.get('file', default='')

        # 验证并限制行数
        if lines < 1:
            lines = 1000
        elif lines > 10000:  # 下载允许更多行
            lines = 10000

        # 使用固定的日志目录
        log_dir = os.path.join(os.getcwd(), 'logs')
        logger.info(f"使用固定的日志目录: {log_dir}")

        # 确保日志目录存在
        if not os.path.exists(log_dir):
            try:
                os.makedirs(log_dir, exist_ok=True)
                logger.warning(f"日志目录不存在，已创建: {log_dir}")
            except Exception as e:
                logger.error(f"创建日志目录时出错: {str(e)}")
                # 尝试使用临时目录
                import tempfile
                log_dir = tempfile.gettempdir()
                logger.warning(f"使用临时目录作为日志目录: {log_dir}")

        # 获取日志文件路径
        if file_name:
            # 使用指定的日志文件
            log_file = os.path.join(log_dir, file_name)
            logger.info(f"下载指定的日志文件: {log_file}")
        else:
            # 获取主日志文件路径
            log_file = os.path.join(log_dir, 'app.log')
            logger.info(f"下载默认日志文件: {log_file}")

        # 如果日志文件不存在，返回错误
        if not os.path.exists(log_file):
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
            # 尝试不同的编码方式读取文件
            try:
                # 首先尝试UTF-8
                with open(log_file, 'r', encoding='utf-8') as f:
                    all_lines = f.readlines()
            except UnicodeDecodeError:
                # 如果UTF-8失败，尝试GBK（中文环境常用）
                try:
                    with open(log_file, 'r', encoding='gbk') as f:
                        all_lines = f.readlines()
                except UnicodeDecodeError:
                    # 最后使用errors='replace'作为后备方案
                    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                        all_lines = f.readlines()

            filtered_lines = []

            # 从后向前过滤日志级别
            for line in reversed(all_lines):
                try:
                    if level_filter(line):
                        filtered_lines.append(line.strip())
                        if len(filtered_lines) >= lines:
                            break
                except Exception as e:
                    logger.error(f"过滤日志行时出错: {str(e)}, 行内容: {line[:50]}...")
                    continue

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

        # 创建响应
        from flask import Response
        response = Response(
            "\n".join(log_entries),
            mimetype="text/plain",
            headers={"Content-disposition": f"attachment; filename={os.path.basename(log_file)}"}
        )

        return response
    except Exception as e:
        logger.error(f"下载日志文件时出错: {str(e)}")
        return jsonify({"success": False, "message": f"下载日志文件时出错: {str(e)}"}), 500

def get_level_filter(level):
    """获取日志级别过滤器"""
    if level == 'debug':
        # 包含所有级别
        return lambda line: True
    elif level == 'info':
        # 包含INFO, WARNING, ERROR, CRITICAL
        # 更宽松的匹配，只要不包含DEBUG就显示
        return lambda line: 'DEBUG' not in line.upper()
    elif level == 'warning':
        # 包含WARNING, ERROR, CRITICAL
        # 更宽松的匹配，只要包含WARNING、ERROR或CRITICAL就显示
        return lambda line: any(lvl in line.upper() for lvl in ['WARNING', 'ERROR', 'CRITICAL'])
    elif level == 'error':
        # 包含ERROR, CRITICAL
        # 更宽松的匹配，只要包含ERROR或CRITICAL就显示
        return lambda line: any(lvl in line.upper() for lvl in ['ERROR', 'CRITICAL'])
    else:
        # 默认包含所有级别
        return lambda line: True

@logs_api.route('/test', methods=['GET'])
def test_logs_api():
    """测试日志API，不需要登录验证"""

    # 生成一些测试日志
    logger.debug("这是一条调试日志，用于测试日志系统")
    logger.info("这是一条信息日志，用于测试日志系统")
    logger.warning("这是一条警告日志，用于测试日志系统")
    logger.error("这是一条错误日志，用于测试日志系统")

    # 生成更多的测试日志，包含中文
    logger.debug("调试信息: 系统正在初始化")
    logger.info("信息: 用户已登录系统")
    logger.warning("警告: 磁盘空间不足")
    logger.error("错误: 无法连接到数据库")
    # 使用固定的日志目录
    log_dir = os.path.join(os.getcwd(), 'logs')
    logger.info(f"使用固定的日志目录: {log_dir}")

    # 确保日志目录存在
    if not os.path.exists(log_dir):
        try:
            os.makedirs(log_dir, exist_ok=True)
            # 设置权限为755，确保所有用户都可以读取
            os.chmod(log_dir, 0o755)
            logger.warning(f"日志目录不存在，已创建: {log_dir}，并设置权限为755")
        except Exception as e:
            logger.error(f"创建日志目录时出错: {str(e)}")
            # 尝试使用临时目录
            import tempfile
            log_dir = tempfile.gettempdir()
            logger.warning(f"使用临时目录作为日志目录: {log_dir}")

    # 创建测试日志文件
    test_log_file = os.path.join(log_dir, 'test_api.log')
    try:
        with open(test_log_file, 'w', encoding='utf-8') as f:
            # 标准格式的日志
            now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            f.write(f"{now} - test_api - INFO - 测试日志文件创建于 {now}\n")
            f.write(f"{now} - test_api - DEBUG - 这是一条调试日志\n")
            f.write(f"{now} - test_api - WARNING - 这是一条警告日志\n")
            f.write(f"{now} - test_api - ERROR - 这是一条错误日志\n")

            # 带有中文的日志
            f.write(f"{now} - test_api - INFO - 信息: 用户已登录系统\n")
            f.write(f"{now} - test_api - WARNING - 警告: 磁盘空间不足\n")
            f.write(f"{now} - test_api - ERROR - 错误: 无法连接到数据库\n")

            # 简化格式的日志
            f.write(f"[INFO] 这是一条简化格式的信息日志\n")
            f.write(f"[DEBUG] 这是一条简化格式的调试日志\n")
            f.write(f"[WARNING] 这是一条简化格式的警告日志\n")
            f.write(f"[ERROR] 这是一条简化格式的错误日志\n")

        # 设置测试日志文件的权限为644，确保所有用户都可以读取
        try:
            os.chmod(test_log_file, 0o644)
            logger.info(f"已设置测试日志文件权限为644: {test_log_file}")
        except Exception as e:
            logger.error(f"设置测试日志文件权限时出错: {str(e)}")

        logger.info(f"已创建测试日志文件: {test_log_file}")
    except Exception as e:
        logger.error(f"创建测试日志文件时出错: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"创建测试日志文件时出错: {str(e)}",
            "debug_info": {
                "log_dir": log_dir,
                "test_log_file": test_log_file,
                "error": str(e)
            }
        }), 500

    # 获取可用的日志文件列表
    available_log_files = []
    try:
        available_log_files = [os.path.basename(f) for f in glob.glob(os.path.join(log_dir, '*.log'))]
        logger.info(f"找到 {len(available_log_files)} 个日志文件")
    except Exception as e:
        logger.error(f"查找日志文件时出错: {str(e)}")

    # 返回测试结果
    return jsonify({
        "success": True,
        "message": "日志API测试成功",
        "data": {
            "log_dir": log_dir,
            "test_log_file": test_log_file,
            "available_log_files": available_log_files,
            "session_info": {
                "has_user_id": 'user_id' in session,
                "session_keys": list(session.keys())
            },
            "request_info": {
                "path": request.path,
                "args": dict(request.args),
                "method": request.method
            }
        }
    })

@logs_api.route('/raw', methods=['GET'])
def get_raw_logs():
    """获取原始日志内容，不进行过滤"""
    # 获取请求参数
    file_name = request.args.get('file', default='app.log')
    lines = request.args.get('lines', default=50, type=int)

    # 使用固定的日志目录
    log_dir = os.path.join(os.getcwd(), 'logs')
    logger.info(f"使用固定的日志目录: {log_dir}")

    # 获取日志文件路径
    log_file = os.path.join(log_dir, file_name)

    # 读取日志文件
    try:
        if not os.path.exists(log_file):
            return jsonify({
                "success": False,
                "message": f"日志文件不存在: {log_file}"
            }), 404

        # 尝试不同的编码方式读取文件
        try:
            # 首先尝试UTF-8
            with open(log_file, 'r', encoding='utf-8') as f:
                all_lines = f.readlines()
        except UnicodeDecodeError:
            # 如果UTF-8失败，尝试GBK（中文环境常用）
            try:
                with open(log_file, 'r', encoding='gbk') as f:
                    all_lines = f.readlines()
            except UnicodeDecodeError:
                # 最后使用errors='replace'作为后备方案
                with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                    all_lines = f.readlines()

        # 只返回最后的lines行
        log_entries = [line.strip() for line in all_lines[-lines:]]

        return jsonify({
            "success": True,
            "data": {
                "log_file": log_file,
                "log_entries": log_entries,
                "total_entries": len(log_entries)
            }
        })
    except Exception as e:
        return jsonify({
            "success": False,
            "message": f"读取日志文件时出错: {str(e)}"
        }), 500
