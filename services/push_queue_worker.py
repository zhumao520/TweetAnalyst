"""
推送队列后台工作线程
在主应用中启动一个后台线程来处理推送队列
"""

import os
import time
import threading
import logging
import datetime
from typing import Optional

# 配置日志
try:
    from utils.logger import get_logger
    logger = get_logger('push_queue_worker')
except ImportError:
    # 如果无法导入自定义日志器，使用标准日志
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('push_queue_worker')

# 全局变量，用于存储工作线程
_worker_thread = None  # type: Optional[threading.Thread]
_worker_running: bool = False
_last_run_time = None  # type: Optional[datetime.datetime]
_processed_count: int = 0
_success_count: int = 0
_error_count: int = 0

def push_queue_worker():
    """推送队列处理线程"""
    global _worker_running, _last_run_time, _processed_count, _success_count, _error_count

    logger.info("推送队列处理线程已启动")
    _worker_running = True

    # 获取处理间隔（秒）
    try:
        interval_seconds = int(os.getenv("PUSH_QUEUE_INTERVAL_SECONDS", "30"))
    except Exception as e:
        logger.error(f"获取环境变量出错: {str(e)}，使用默认值30秒")
        interval_seconds = 30

    while _worker_running:
        try:
            # 记录开始时间
            start_time = time.time()
            _last_run_time = datetime.datetime.now()

            # 导入推送队列服务
            try:
                # 使用绝对导入，避免循环导入问题
                import sys

                # 获取项目根目录
                root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
                if root_dir not in sys.path:
                    sys.path.append(root_dir)

                from services.push_queue_service import process_notification_queue, retry_failed_notifications
                from web_app import app

                # 使用Flask应用程序上下文
                with app.app_context():
                    # 先重试失败的通知
                    retry_count = retry_failed_notifications(max_age_hours=24, limit=5)
                    if retry_count > 0:
                        logger.info(f"已将 {retry_count} 条失败的通知重新加入队列")

                    # 处理队列
                    processed, success = process_notification_queue(limit=10)

                # 更新统计信息
                _processed_count += processed
                _success_count += success
                if processed > success:
                    _error_count += (processed - success)

                if processed > 0:
                    logger.info(f"队列处理完成，共处理 {processed} 条通知，成功 {success} 条")
            except ImportError as e:
                logger.error(f"无法导入推送队列服务，请确保服务已正确安装: {str(e)}")
            except Exception as e:
                logger.error(f"处理推送队列时出错: {str(e)}")
                _error_count += 1

            # 计算需要等待的时间
            elapsed = time.time() - start_time
            wait_time = max(0, interval_seconds - elapsed)

            # 等待指定时间
            if wait_time > 0:
                # 使用小的时间间隔检查_worker_running，以便能够及时响应停止请求
                check_interval = 1.0  # 1秒
                for _ in range(int(wait_time / check_interval)):
                    if not _worker_running:
                        break
                    time.sleep(check_interval)

                # 处理剩余的等待时间
                remaining = wait_time % check_interval
                if remaining > 0 and _worker_running:
                    time.sleep(remaining)

        except Exception as e:
            logger.error(f"推送队列处理线程出错: {str(e)}")
            # 出错后等待一段时间再继续
            time.sleep(5)

    logger.info("推送队列处理线程已停止")

def start_push_queue_worker():
    """启动推送队列处理线程"""
    global _worker_thread, _worker_running

    # 检查是否启用推送队列
    try:
        push_queue_enabled = os.getenv("PUSH_QUEUE_ENABLED", "true").lower() == "true"
    except Exception as e:
        logger.error(f"获取环境变量出错: {str(e)}，使用默认值true")
        push_queue_enabled = True
    if not push_queue_enabled:
        logger.info("推送队列功能已禁用，不启动处理线程")
        return False

    # 检查线程是否已经在运行
    if _worker_thread is not None and _worker_thread.is_alive():
        logger.info("推送队列处理线程已在运行")
        return True

    # 创建并启动线程
    _worker_running = True
    _worker_thread = threading.Thread(target=push_queue_worker, daemon=True)
    _worker_thread.start()

    logger.info("推送队列处理线程已启动")
    return True

def stop_push_queue_worker():
    """停止推送队列处理线程"""
    global _worker_running

    if _worker_thread is not None and _worker_thread.is_alive():
        logger.info("正在停止推送队列处理线程...")
        _worker_running = False

        # 等待线程结束，最多等待5秒
        _worker_thread.join(timeout=5.0)

        if _worker_thread.is_alive():
            logger.warning("推送队列处理线程未能在5秒内停止")
            return False
        else:
            logger.info("推送队列处理线程已停止")
            return True
    else:
        logger.info("推送队列处理线程未在运行")
        return True

def try_get_interval_seconds():
    """尝试获取处理间隔（秒）"""
    try:
        return int(os.getenv("PUSH_QUEUE_INTERVAL_SECONDS", "30"))
    except Exception as e:
        logger.error(f"获取环境变量出错: {str(e)}，使用默认值30秒")
        return 30

def get_worker_status():
    """获取工作线程状态"""
    return {
        "running": _worker_running and _worker_thread is not None and _worker_thread.is_alive(),
        "last_run_time": _last_run_time.isoformat() if _last_run_time else None,
        "processed_count": _processed_count,
        "success_count": _success_count,
        "error_count": _error_count,
        "interval_seconds": try_get_interval_seconds()
    }
