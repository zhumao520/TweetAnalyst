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

def extract_timestamp(log_line):
    """
    从日志行中提取时间戳
    支持多种常见的日志时间格式
    如果无法提取，返回当前时间作为默认值
    """
    # 尝试匹配常见的时间格式
    # 格式1: 2023-05-15 14:30:45
    pattern1 = r'(\d{4}-\d{2}-\d{2}\s+\d{2}:\d{2}:\d{2})'
    # 格式2: 15/May/2023 14:30:45
    pattern2 = r'(\d{2}/[A-Za-z]{3}/\d{4}\s+\d{2}:\d{2}:\d{2})'
    # 格式3: May 15 14:30:45
    pattern3 = r'([A-Za-z]{3}\s+\d{1,2}\s+\d{2}:\d{2}:\d{2})'

    # 尝试匹配格式1
    match = re.search(pattern1, log_line)
    if match:
        try:
            return datetime.strptime(match.group(1), '%Y-%m-%d %H:%M:%S')
        except:
            pass

    # 尝试匹配格式2
    match = re.search(pattern2, log_line)
    if match:
        try:
            return datetime.strptime(match.group(1), '%d/%b/%Y %H:%M:%S')
        except:
            pass

    # 尝试匹配格式3
    match = re.search(pattern3, log_line)
    if match:
        try:
            # 添加当前年份，因为这种格式通常不包含年份
            current_year = datetime.now().year
            timestamp_str = f"{match.group(1)} {current_year}"
            return datetime.strptime(timestamp_str, '%b %d %H:%M:%S %Y')
        except:
            pass

    # 如果无法提取时间戳，使用当前时间
    return datetime.now()

# 创建Blueprint
logs_api = Blueprint('logs_api', __name__, url_prefix='/logs')

@logs_api.route('/system', methods=['GET'])
def get_system_logs():
    """获取系统日志"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        # 添加更详细的错误信息
        logger.warning("尝试未登录访问日志API")

        # 设置响应头，禁止缓存
        response = jsonify({
            "success": False,
            "message": "未登录",
            "debug_info": {
                "session_keys": list(session.keys()),
                "has_user_id": 'user_id' in session,
                "request_path": request.path,
                "request_args": dict(request.args)
            }
        })
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response, 401

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

        # 定义主要日志文件列表
        main_log_files = ['main.log', 'web_app.log', 'test_utils.log', 'twitter.log', 'llm.log', 'apprise_adapter.log']

        # 获取日志文件路径
        if file_name:
            # 使用指定的日志文件
            log_files = [os.path.join(log_dir, file_name)]
            logger.info(f"使用指定的日志文件: {log_files[0]}")
        else:
            # 使用所有主要日志文件
            log_files = [os.path.join(log_dir, f) for f in main_log_files]
            logger.info(f"使用所有主要日志文件: {', '.join(main_log_files)}")

        # 读取日志文件
        log_entries = []
        level_filter = get_level_filter(level)

        # 用于存储所有日志行及其时间戳
        all_log_lines_with_timestamps = []

        try:
            # 遍历所有日志文件
            for log_file in log_files:
                # 如果日志文件不存在，跳过
                if not os.path.exists(log_file):
                    logger.warning(f"日志文件不存在，跳过: {log_file}")
                    continue

                # 检查文件大小
                file_size = os.path.getsize(log_file)
                if file_size == 0:
                    logger.warning(f"日志文件为空，跳过: {log_file}")
                    continue

                try:
                    # 读取文件内容
                    # 尝试不同的编码方式读取文件
                    try:
                        # 首先尝试UTF-8
                        with open(log_file, 'r', encoding='utf-8') as f:
                            file_lines = f.readlines()
                    except UnicodeDecodeError:
                        # 如果UTF-8失败，尝试GBK（中文环境常用）
                        try:
                            with open(log_file, 'r', encoding='gbk') as f:
                                file_lines = f.readlines()
                        except UnicodeDecodeError:
                            # 最后使用errors='replace'作为后备方案
                            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                                file_lines = f.readlines()

                    # 过滤日志级别并提取时间戳
                    for line in file_lines:
                        try:
                            if level_filter(line):
                                # 尝试提取时间戳
                                timestamp = extract_timestamp(line)
                                # 添加文件名前缀以区分不同日志文件
                                file_basename = os.path.basename(log_file)
                                prefixed_line = f"[{file_basename}] {line.strip()}"
                                all_log_lines_with_timestamps.append((timestamp, prefixed_line))
                        except Exception as e:
                            logger.error(f"处理日志行时出错: {str(e)}, 行内容: {line[:50]}...")
                            continue
                except Exception as e:
                    logger.error(f"读取日志文件时出错: {str(e)}, 文件: {log_file}")
                    continue

            # 如果是单个文件，不添加文件名前缀
            if file_name:
                # 清除之前添加的前缀
                all_log_lines_with_timestamps = [(ts, line.replace(f"[{file_name}] ", ""))
                                                for ts, line in all_log_lines_with_timestamps]

            # 按时间戳排序
            all_log_lines_with_timestamps.sort(key=lambda x: x[0], reverse=True)

            # 取最近的指定行数
            sorted_log_lines = [line for _, line in all_log_lines_with_timestamps[:lines]]

            # 反转，使日志按时间顺序排列（从旧到新）
            log_entries = list(reversed(sorted_log_lines))

            # 如果没有日志条目，添加一个提示
            if not log_entries:
                if file_name:
                    log_entries = [f"没有找到符合条件的日志记录: {file_name}"]
                else:
                    log_entries = ["没有找到符合条件的日志记录"]

        except Exception as e:
            logger.error(f"读取日志文件时出错: {str(e)}")
            return jsonify({
                "success": False,
                "message": f"读取日志文件时出错: {str(e)}",
                "data": {
                    "log_files": [os.path.basename(f) for f in log_files],
                    "available_log_files": [os.path.basename(f) for f in available_log_files]
                }
            }), 500

        # 创建响应并添加禁止缓存的头信息
        response = jsonify({
            "success": True,
            "data": {
                "log_files": [os.path.basename(f) for f in log_files],
                "log_entries": log_entries,
                "total_entries": len(log_entries),
                "level": level,
                "available_log_files": [os.path.basename(f) for f in available_log_files],
                "is_combined": not bool(file_name)  # 标记是否是合并的日志
            }
        })
        response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
        response.headers['Pragma'] = 'no-cache'
        response.headers['Expires'] = '0'
        return response
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

        # 定义主要日志文件列表
        main_log_files = ['main.log', 'web_app.log', 'test_utils.log', 'twitter.log', 'llm.log', 'apprise_adapter.log']

        # 获取日志文件路径
        if file_name:
            # 使用指定的日志文件
            log_files = [os.path.join(log_dir, file_name)]
            logger.info(f"下载指定的日志文件: {log_files[0]}")
            download_filename = file_name
        else:
            # 使用所有主要日志文件
            log_files = [os.path.join(log_dir, f) for f in main_log_files]
            logger.info(f"下载所有主要日志文件: {', '.join(main_log_files)}")
            download_filename = 'all_logs.txt'

        # 读取日志文件
        log_entries = []
        level_filter = get_level_filter(level)

        # 用于存储所有日志行及其时间戳
        all_log_lines_with_timestamps = []

        try:
            # 遍历所有日志文件
            for log_file in log_files:
                # 如果日志文件不存在，跳过
                if not os.path.exists(log_file):
                    logger.warning(f"日志文件不存在，跳过: {log_file}")
                    continue

                # 检查文件大小
                file_size = os.path.getsize(log_file)
                if file_size == 0:
                    logger.warning(f"日志文件为空，跳过: {log_file}")
                    continue

                try:
                    # 读取文件内容
                    # 尝试不同的编码方式读取文件
                    try:
                        # 首先尝试UTF-8
                        with open(log_file, 'r', encoding='utf-8') as f:
                            file_lines = f.readlines()
                    except UnicodeDecodeError:
                        # 如果UTF-8失败，尝试GBK（中文环境常用）
                        try:
                            with open(log_file, 'r', encoding='gbk') as f:
                                file_lines = f.readlines()
                        except UnicodeDecodeError:
                            # 最后使用errors='replace'作为后备方案
                            with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                                file_lines = f.readlines()

                    # 过滤日志级别并提取时间戳
                    for line in file_lines:
                        try:
                            if level_filter(line):
                                # 尝试提取时间戳
                                timestamp = extract_timestamp(line)
                                # 添加文件名前缀以区分不同日志文件
                                file_basename = os.path.basename(log_file)
                                prefixed_line = f"[{file_basename}] {line.strip()}"
                                all_log_lines_with_timestamps.append((timestamp, prefixed_line))
                        except Exception as e:
                            logger.error(f"处理日志行时出错: {str(e)}, 行内容: {line[:50]}...")
                            continue
                except Exception as e:
                    logger.error(f"读取日志文件时出错: {str(e)}, 文件: {log_file}")
                    continue

            # 如果是单个文件，不添加文件名前缀
            if file_name:
                # 清除之前添加的前缀
                all_log_lines_with_timestamps = [(ts, line.replace(f"[{file_name}] ", ""))
                                                for ts, line in all_log_lines_with_timestamps]

            # 按时间戳排序
            all_log_lines_with_timestamps.sort(key=lambda x: x[0], reverse=True)

            # 取最近的指定行数
            sorted_log_lines = [line for _, line in all_log_lines_with_timestamps[:lines]]

            # 反转，使日志按时间顺序排列（从旧到新）
            log_entries = list(reversed(sorted_log_lines))

            # 如果没有日志条目，添加一个提示
            if not log_entries:
                if file_name:
                    log_entries = [f"没有找到符合条件的日志记录: {file_name}"]
                else:
                    log_entries = ["没有找到符合条件的日志记录"]
        except Exception as e:
            logger.error(f"读取日志文件时出错: {str(e)}")
            return jsonify({
                "success": False,
                "message": f"读取日志文件时出错: {str(e)}",
                "data": {
                    "log_files": [os.path.basename(f) for f in log_files]
                }
            }), 500

        # 创建响应
        from flask import Response
        response = Response(
            "\n".join(log_entries),
            mimetype="text/plain",
            headers={"Content-disposition": f"attachment; filename={download_filename}"}
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

@logs_api.route('/clean', methods=['POST'])
def clean_logs():
    """清理日志文件"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 导入必要的模块
        import glob
        import time
        import re
        from utils.logger import clean_old_logs

        # 获取请求参数
        data = request.get_json() or {}
        mode = data.get('mode', 'auto')  # 清理模式：auto(自动)、all(所有)、old(旧的)

        # 使用固定的日志目录
        log_dir = os.path.join(os.getcwd(), 'logs')

        # 获取日志文件列表
        log_files = glob.glob(os.path.join(log_dir, '*.log*'))
        total_files = len(log_files)

        # 获取核心日志文件列表
        from utils.logger import CORE_LOG_FILES

        # 当前时间
        current_time = time.time()
        # 30天的秒数
        thirty_days_in_seconds = 30 * 24 * 60 * 60
        # 7天的秒数
        seven_days_in_seconds = 7 * 24 * 60 * 60

        # 已删除的文件列表
        deleted_files = []

        # 遍历所有日志文件
        for log_file in log_files:
            file_name = os.path.basename(log_file)

            # 检查是否是核心日志文件
            is_core_log = False
            for core_log in CORE_LOG_FILES:
                if file_name == core_log or re.match(f"{core_log}\\.\\d+$", file_name):
                    is_core_log = True
                    break

            # 根据模式决定是否删除
            should_delete = False

            if mode == 'all':
                # 全部清理模式：删除所有非核心日志文件和所有轮转文件
                should_delete = not is_core_log or re.search(r'\.\d+$', file_name)
            elif mode == 'old':
                # 旧文件清理模式：删除所有超过30天的文件
                file_mod_time = os.path.getmtime(log_file)
                should_delete = current_time - file_mod_time > thirty_days_in_seconds
            else:  # auto模式
                # 自动清理模式：删除超过30天的核心日志轮转文件，删除超过7天的非核心日志文件
                file_mod_time = os.path.getmtime(log_file)
                if is_core_log:
                    # 核心日志文件：只删除超过30天的轮转文件
                    should_delete = re.search(r'\.\d+$', file_name) and current_time - file_mod_time > thirty_days_in_seconds
                else:
                    # 非核心日志文件：删除超过7天的文件
                    should_delete = current_time - file_mod_time > seven_days_in_seconds

            # 执行删除
            if should_delete:
                try:
                    os.remove(log_file)
                    deleted_files.append(file_name)
                    logger.info(f"已删除日志文件: {file_name}")
                except Exception as e:
                    logger.error(f"删除日志文件时出错: {file_name}, 错误: {str(e)}")

        # 获取剩余的日志文件
        remaining_files = glob.glob(os.path.join(log_dir, '*.log*'))

        return jsonify({
            "success": True,
            "message": f"日志清理完成，已删除 {len(deleted_files)} 个文件",
            "data": {
                "total_files_before": total_files,
                "total_files_after": len(remaining_files),
                "deleted_files": deleted_files,
                "mode": mode
            }
        })
    except Exception as e:
        logger.error(f"清理日志文件时出错: {str(e)}")
        return jsonify({"success": False, "message": f"清理日志文件时出错: {str(e)}"}), 500

@logs_api.route('/stats', methods=['GET'])
def get_logs_stats():
    """获取日志统计信息"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 导入必要的模块
        import glob
        import time
        import re
        from datetime import datetime

        # 使用固定的日志目录
        log_dir = os.path.join(os.getcwd(), 'logs')

        # 获取日志文件列表
        log_files = glob.glob(os.path.join(log_dir, '*.log*'))

        # 获取核心日志文件列表
        from utils.logger import CORE_LOG_FILES

        # 统计信息
        stats = {
            "total_files": len(log_files),
            "total_size_bytes": 0,
            "core_files": 0,
            "core_size_bytes": 0,
            "rotation_files": 0,
            "rotation_size_bytes": 0,
            "other_files": 0,
            "other_size_bytes": 0,
            "files_by_age": {
                "last_day": 0,
                "last_week": 0,
                "last_month": 0,
                "older": 0
            },
            "size_by_age": {
                "last_day": 0,
                "last_week": 0,
                "last_month": 0,
                "older": 0
            },
            "files_details": []
        }

        # 当前时间
        current_time = time.time()
        # 时间段（秒）
        one_day = 24 * 60 * 60
        one_week = 7 * one_day
        one_month = 30 * one_day

        # 遍历所有日志文件
        for log_file in log_files:
            file_name = os.path.basename(log_file)
            file_size = os.path.getsize(log_file)
            file_mod_time = os.path.getmtime(log_file)
            file_age = current_time - file_mod_time

            # 更新总大小
            stats["total_size_bytes"] += file_size

            # 检查是否是核心日志文件
            is_core_log = False
            for core_log in CORE_LOG_FILES:
                if file_name == core_log:
                    is_core_log = True
                    break

            # 检查是否是轮转文件
            is_rotation = re.search(r'\.\d+$', file_name) is not None

            # 更新分类统计
            if is_core_log:
                stats["core_files"] += 1
                stats["core_size_bytes"] += file_size
            elif is_rotation:
                stats["rotation_files"] += 1
                stats["rotation_size_bytes"] += file_size
            else:
                stats["other_files"] += 1
                stats["other_size_bytes"] += file_size

            # 更新按年龄统计
            if file_age <= one_day:
                stats["files_by_age"]["last_day"] += 1
                stats["size_by_age"]["last_day"] += file_size
            elif file_age <= one_week:
                stats["files_by_age"]["last_week"] += 1
                stats["size_by_age"]["last_week"] += file_size
            elif file_age <= one_month:
                stats["files_by_age"]["last_month"] += 1
                stats["size_by_age"]["last_month"] += file_size
            else:
                stats["files_by_age"]["older"] += 1
                stats["size_by_age"]["older"] += file_size

            # 添加文件详情
            stats["files_details"].append({
                "name": file_name,
                "size_bytes": file_size,
                "size_human": format_size(file_size),
                "modified": datetime.fromtimestamp(file_mod_time).strftime('%Y-%m-%d %H:%M:%S'),
                "age_seconds": int(file_age),
                "age_human": format_age(file_age),
                "is_core": is_core_log,
                "is_rotation": is_rotation
            })

        # 格式化总大小
        stats["total_size_human"] = format_size(stats["total_size_bytes"])
        stats["core_size_human"] = format_size(stats["core_size_bytes"])
        stats["rotation_size_human"] = format_size(stats["rotation_size_bytes"])
        stats["other_size_human"] = format_size(stats["other_size_bytes"])

        # 格式化按年龄统计的大小
        for key in stats["size_by_age"]:
            stats["size_by_age"][f"{key}_human"] = format_size(stats["size_by_age"][key])

        return jsonify({
            "success": True,
            "data": stats
        })
    except Exception as e:
        logger.error(f"获取日志统计信息时出错: {str(e)}")
        return jsonify({"success": False, "message": f"获取日志统计信息时出错: {str(e)}"}), 500

# 格式化文件大小
def format_size(size_bytes):
    """将字节数格式化为人类可读的形式"""
    if size_bytes < 1024:
        return f"{size_bytes} B"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.2f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.2f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.2f} GB"

# 格式化时间间隔
def format_age(age_seconds):
    """将秒数格式化为人类可读的时间间隔"""
    if age_seconds < 60:
        return f"{int(age_seconds)}秒"
    elif age_seconds < 60 * 60:
        return f"{int(age_seconds / 60)}分钟"
    elif age_seconds < 60 * 60 * 24:
        return f"{int(age_seconds / (60 * 60))}小时"
    elif age_seconds < 60 * 60 * 24 * 30:
        return f"{int(age_seconds / (60 * 60 * 24))}天"
    elif age_seconds < 60 * 60 * 24 * 365:
        return f"{int(age_seconds / (60 * 60 * 24 * 30))}个月"
    else:
        return f"{int(age_seconds / (60 * 60 * 24 * 365))}年"

@logs_api.route('/raw', methods=['GET'])
def get_raw_logs():
    """获取原始日志内容，不进行过滤"""
    # 设置响应头，禁止缓存
    response = current_app.make_response('')
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'

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
            response = jsonify({
                "success": False,
                "message": f"日志文件不存在: {log_file}"
            })
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response, 404

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
