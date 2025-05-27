"""
任务API模块
处理所有任务相关的API请求，包括手动触发抓取任务
"""

import logging
import time
import threading
import os
from flask import Blueprint, request, jsonify, session, current_app, copy_current_request_context
# 避免循环导入，不在模块级别导入main
# import main
from models import db, SocialAccount
from api.utils import api_response, handle_api_exception, login_required, validate_json_request

# 创建日志记录器
logger = logging.getLogger('api.tasks')

# 创建Blueprint
tasks_api = Blueprint('tasks_api', __name__, url_prefix='/tasks')

# 全局变量，用于跟踪任务状态
# 账号抓取任务状态
account_task_status = {
    "is_running": False,
    "start_time": None,
    "end_time": None,
    "status": "idle",  # idle, running, completed, failed
    "message": "",
    "total_posts": 0,
    "relevant_posts": 0,
    "accounts_processed": 0,
    "total_accounts": 0,
    "task_type": "account"
}

# 时间线抓取任务状态
timeline_task_status = {
    "is_running": False,
    "start_time": None,
    "end_time": None,
    "status": "idle",  # idle, running, completed, failed
    "message": "",
    "total_posts": 0,
    "relevant_posts": 0,
    "accounts_processed": 0,
    "total_accounts": 0,
    "task_type": "timeline"
}

# 兼容性：保持原有的task_status变量，指向账号任务状态
task_status = account_task_status

def run_task_in_thread(account_id=None):
    """
    在线程中运行抓取任务

    Args:
        account_id: 可选，指定要抓取的账号ID
    """
    global task_status

    # 获取当前应用实例
    app = current_app._get_current_object()

    try:
        # 更新任务状态
        task_status["is_running"] = True
        task_status["start_time"] = time.time()
        task_status["status"] = "running"
        task_status["message"] = "任务正在执行中..."
        task_status["total_posts"] = 0
        task_status["relevant_posts"] = 0

        # 获取自动回复设置
        enable_auto_reply = os.getenv("ENABLE_AUTO_REPLY", "false").lower() == "true"
        auto_reply_prompt = os.getenv("AUTO_REPLY_PROMPT", "")

        # 如果指定了账号ID，只处理该账号
        if account_id:
            # 创建应用上下文
            with app.app_context():
                try:
                    # 从数据库获取账号信息
                    account = SocialAccount.query.filter_by(account_id=account_id).first()
                    if not account:
                        logger.error(f"未找到账号: {account_id}")
                        task_status["status"] = "failed"
                        task_status["message"] = f"未找到账号: {account_id}"
                        return

                    logger.info(f"开始手动抓取账号: {account_id}")
                    task_status["message"] = f"正在抓取账号: {account_id}"
                    task_status["total_accounts"] = 1

                    # 转换为main.py中使用的格式
                    # 确保tag是字符串
                    tag = account.tag
                    if tag is not None:
                        tag = str(tag)

                    account_config = {
                        "type": account.type,
                        "socialNetworkId": account.account_id,
                        "prompt": account.prompt_template,  # 修正：使用正确的字段名
                        "tag": tag,
                        "enableAutoReply": account.enable_auto_reply,
                        "bypass_ai": account.bypass_ai
                    }

                    # 延迟导入main模块，避免循环导入
                    import main
                    # 调用处理函数
                    total, relevant = main.process_account_posts(
                        account_config,
                        enable_auto_reply,
                        auto_reply_prompt,
                        True  # 保存到数据库
                    )

                    task_status["total_posts"] = total
                    task_status["relevant_posts"] = relevant
                    task_status["accounts_processed"] = 1

                    logger.info(f"账号 {account_id} 抓取完成，处理了 {total} 条帖子，其中 {relevant} 条相关内容")
                except Exception as e:
                    logger.error(f"处理账号 {account_id} 时出错: {str(e)}", exc_info=True)
                    task_status["status"] = "failed"
                    task_status["message"] = f"处理账号时出错: {str(e)}"
                    return
        else:
            # 处理所有账号
            logger.info("开始手动抓取所有账号")
            task_status["message"] = "正在抓取所有账号..."

            # 创建应用上下文
            with app.app_context():
                try:
                    # 延迟导入main模块，避免循环导入
                    import main

                    # 获取所有账号数量
                    accounts = SocialAccount.query.all()
                    task_status["total_accounts"] = len(accounts)

                    # 记录处理前的分析结果数量
                    from models.analysis_result import AnalysisResult
                    before_total = AnalysisResult.query.count()
                    before_relevant = AnalysisResult.query.filter_by(is_relevant=True).count()

                    # 直接调用main函数
                    main.main()

                    # 计算处理后的分析结果数量，得出新增数量
                    after_total = AnalysisResult.query.count()
                    after_relevant = AnalysisResult.query.filter_by(is_relevant=True).count()

                    # 更新任务状态
                    task_status["total_posts"] = after_total - before_total
                    task_status["relevant_posts"] = after_relevant - before_relevant
                    task_status["accounts_processed"] = task_status["total_accounts"]
                    task_status["message"] = f"所有账号抓取完成，处理了 {task_status['total_posts']} 条内容，发现 {task_status['relevant_posts']} 条相关内容"
                except Exception as e:
                    logger.error(f"处理所有账号时出错: {str(e)}", exc_info=True)
                    task_status["status"] = "failed"
                    task_status["message"] = f"处理所有账号时出错: {str(e)}"
                    return

        # 更新任务状态
        task_status["status"] = "completed"
        task_status["message"] = "任务已完成"
        logger.info("手动抓取任务完成")

        # 更新最后运行时间
        try:
            from utils.redisClient import redis_client
            redis_client.set("last_run_time", time.time())
            logger.info("已更新最后运行时间")
        except Exception as e:
            logger.error(f"更新最后运行时间时出错: {str(e)}")
    except Exception as e:
        logger.error(f"执行抓取任务时出错: {str(e)}", exc_info=True)
        task_status["status"] = "failed"
        task_status["message"] = f"任务执行失败: {str(e)}"
    finally:
        task_status["is_running"] = False
        task_status["end_time"] = time.time()

@tasks_api.route('/run', methods=['POST'])
@login_required
@handle_api_exception
def run_task():
    """手动触发抓取任务"""
    # 检查任务是否正在运行
    if task_status["is_running"]:
        return api_response(
            success=False,
            message="任务已在运行中",
            status=task_status
        )

    # 获取请求参数
    # 支持JSON和表单数据
    if request.is_json:
        data = request.get_json() or {}
    else:
        data = request.form.to_dict() or {}

    # 如果没有在请求体中找到，尝试从URL参数获取
    account_id = data.get('account_id') or request.args.get('account_id')

    # 获取是否重置处理记录的参数
    reset_cursor = data.get('reset_cursor', False) or request.args.get('reset_cursor') == 'true'

    # 验证account_id格式（如果提供）
    if account_id and not isinstance(account_id, str):
        account_id = str(account_id)

    logger.info(f"准备启动任务，账号ID: {account_id if account_id else '所有账号'}, 重置处理记录: {reset_cursor}")

    # 如果需要重置处理记录
    if reset_cursor:
        try:
            from utils.redisClient import redis_client

            # 如果指定了账号ID，只重置该账号的记录
            if account_id:
                key = f"twitter:{account_id}:last_post_id"
                redis_client.delete(key)
                logger.info(f"已重置账号 {account_id} 的处理记录")
            else:
                # 获取所有Twitter相关的键
                keys = redis_client.keys("twitter:*:last_post_id")
                for key in keys:
                    redis_client.delete(key)
                logger.info(f"已重置所有账号的处理记录，共 {len(keys)} 个")
        except Exception as e:
            logger.error(f"重置处理记录时出错: {str(e)}")

    # 使用copy_current_request_context装饰器包装线程函数
    @copy_current_request_context
    def wrapped_task_thread(account_id=None):
        run_task_in_thread(account_id)

    # 启动线程执行任务
    thread = threading.Thread(target=wrapped_task_thread, args=(account_id,))
    thread.daemon = True
    thread.start()

    return api_response(
        success=True,
        message=f"任务已启动，{'处理账号: ' + account_id if account_id else '处理所有账号'}{', 已重置处理记录' if reset_cursor else ''}",
        status=task_status
    )


def run_timeline_task_in_thread():
    """在线程中运行时间线抓取任务"""
    global timeline_task_status

    # 获取当前应用实例
    app = current_app._get_current_object()

    try:
        # 更新任务状态
        timeline_task_status["is_running"] = True
        timeline_task_status["start_time"] = time.time()
        timeline_task_status["status"] = "running"
        timeline_task_status["message"] = "时间线抓取任务正在执行中..."
        timeline_task_status["total_posts"] = 0
        timeline_task_status["relevant_posts"] = 0

        # 获取自动回复设置
        enable_auto_reply = os.getenv("ENABLE_AUTO_REPLY", "false").lower() == "true"
        auto_reply_prompt = os.getenv("AUTO_REPLY_PROMPT", "")

        # 创建应用上下文
        with app.app_context():
            try:
                # 延迟导入main模块，避免循环导入
                import main

                # 记录处理前的分析结果数量
                from models.analysis_result import AnalysisResult
                before_total = AnalysisResult.query.count()
                before_relevant = AnalysisResult.query.filter_by(is_relevant=True).count()

                # 调用时间线处理函数，确保保存到数据库
                main.process_timeline_posts(enable_auto_reply, auto_reply_prompt, save_to_db=True)

                # 计算处理后的分析结果数量，得出新增数量
                after_total = AnalysisResult.query.count()
                after_relevant = AnalysisResult.query.filter_by(is_relevant=True).count()

                # 更新任务状态
                timeline_task_status["total_posts"] = after_total - before_total
                timeline_task_status["relevant_posts"] = after_relevant - before_relevant
                timeline_task_status["message"] = f"时间线抓取完成，处理了 {timeline_task_status['total_posts']} 条内容，发现 {timeline_task_status['relevant_posts']} 条相关内容"
            except Exception as e:
                logger.error(f"处理时间线时出错: {str(e)}", exc_info=True)
                timeline_task_status["status"] = "failed"
                timeline_task_status["message"] = f"处理时间线时出错: {str(e)}"
                return

        # 更新任务状态
        timeline_task_status["status"] = "completed"
        timeline_task_status["message"] = "时间线抓取任务已完成"
        logger.info("时间线抓取任务完成")

        # 更新最后运行时间
        try:
            from utils.redisClient import redis_client
            redis_client.set("last_run_time", time.time())
            logger.info("已更新最后运行时间")
        except Exception as e:
            logger.error(f"更新最后运行时间时出错: {str(e)}")
    except Exception as e:
        logger.error(f"执行时间线抓取任务时出错: {str(e)}", exc_info=True)
        timeline_task_status["status"] = "failed"
        timeline_task_status["message"] = f"任务执行失败: {str(e)}"
    finally:
        timeline_task_status["is_running"] = False
        timeline_task_status["end_time"] = time.time()


@tasks_api.route('/run_timeline', methods=['POST'])
@login_required
@handle_api_exception
def run_timeline_task():
    """手动触发时间线抓取任务"""
    # 检查时间线任务是否正在运行
    if timeline_task_status["is_running"]:
        return api_response(
            success=False,
            message="任务已在运行中",
            status=timeline_task_status
        )

    # 获取请求参数
    # 支持JSON和表单数据
    if request.is_json:
        data = request.get_json() or {}
    else:
        data = request.form.to_dict() or {}

    logger.info("准备启动时间线抓取任务")

    # 使用copy_current_request_context装饰器包装线程函数
    @copy_current_request_context
    def wrapped_timeline_thread():
        run_timeline_task_in_thread()

    # 启动线程执行任务
    thread = threading.Thread(target=wrapped_timeline_thread)
    thread.daemon = True
    thread.start()

    return api_response(
        success=True,
        message="时间线抓取任务已启动，请稍后查看结果",
        status=timeline_task_status
    )

@tasks_api.route('/status', methods=['GET'])
@login_required
@handle_api_exception
def get_task_status():
    """获取任务状态 - 返回当前运行的任务状态"""
    # 检查哪个任务正在运行
    if timeline_task_status["is_running"]:
        return api_response(
            success=True,
            status=timeline_task_status
        )
    elif account_task_status["is_running"]:
        return api_response(
            success=True,
            status=account_task_status
        )
    else:
        # 如果没有任务运行，返回最后完成的任务状态
        # 比较两个任务的结束时间，返回最近的一个
        if (timeline_task_status.get("end_time", 0) > account_task_status.get("end_time", 0)):
            return api_response(
                success=True,
                status=timeline_task_status
            )
        else:
            return api_response(
                success=True,
                status=account_task_status
            )

@tasks_api.route('/status/account', methods=['GET'])
@login_required
@handle_api_exception
def get_account_task_status():
    """获取账号抓取任务状态"""
    return api_response(
        success=True,
        status=account_task_status
    )

@tasks_api.route('/status/timeline', methods=['GET'])
@login_required
@handle_api_exception
def get_timeline_task_status():
    """获取时间线抓取任务状态"""
    return api_response(
        success=True,
        status=timeline_task_status
    )

@tasks_api.route('/last_run', methods=['GET'])
@login_required
@handle_api_exception
def get_last_run_time():
    """获取上次运行时间"""
    # 从Redis中获取上次运行时间
    try:
        from utils.redisClient import redis_client
        last_run = redis_client.get("last_run_time")
        if last_run:
            last_run = float(last_run)
        else:
            last_run = None
    except Exception as e:
        logger.error(f"获取上次运行时间时出错: {str(e)}")
        last_run = None

    return api_response(
        success=True,
        last_run=last_run
    )
