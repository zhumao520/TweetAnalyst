"""
任务API模块
处理所有任务相关的API请求，包括手动触发抓取任务
"""

import logging
import time
import threading
import os
from flask import Blueprint, request, jsonify, session, current_app
import main
from models import db, SocialAccount

# 创建日志记录器
logger = logging.getLogger('api.tasks')

# 创建Blueprint
tasks_api = Blueprint('tasks_api', __name__, url_prefix='/tasks')

# 全局变量，用于跟踪任务状态
task_status = {
    "is_running": False,
    "start_time": None,
    "end_time": None,
    "status": "idle",  # idle, running, completed, failed
    "message": "",
    "total_posts": 0,
    "relevant_posts": 0,
    "accounts_processed": 0,
    "total_accounts": 0
}

def run_task_in_thread(account_id=None):
    """
    在线程中运行抓取任务

    Args:
        account_id: 可选，指定要抓取的账号ID
    """
    global task_status

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
                    "enableAutoReply": account.enable_auto_reply
                }

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

            # 直接调用main函数
            main.main()

            # 由于main函数内部会处理所有账号，这里无法获取具体数量
            # 可以从日志中解析，但这里简化处理
            task_status["message"] = "所有账号抓取完成"

        # 更新任务状态
        task_status["status"] = "completed"
        task_status["message"] = "任务已完成"
        logger.info("手动抓取任务完成")
    except Exception as e:
        logger.error(f"执行抓取任务时出错: {str(e)}", exc_info=True)
        task_status["status"] = "failed"
        task_status["message"] = f"任务执行失败: {str(e)}"
    finally:
        task_status["is_running"] = False
        task_status["end_time"] = time.time()

@tasks_api.route('/run', methods=['POST'])
def run_task():
    """手动触发抓取任务"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    # 检查任务是否正在运行
    if task_status["is_running"]:
        return jsonify({
            "success": False,
            "message": "任务已在运行中",
            "status": task_status
        })

    # 获取请求参数
    try:
        # 支持JSON和表单数据
        if request.is_json:
            data = request.get_json() or {}
        else:
            data = request.form.to_dict() or {}

        # 如果没有在请求体中找到，尝试从URL参数获取
        account_id = data.get('account_id') or request.args.get('account_id')

        # 验证account_id格式（如果提供）
        if account_id and not isinstance(account_id, str):
            account_id = str(account_id)

        logger.info(f"准备启动任务，账号ID: {account_id if account_id else '所有账号'}")

        # 启动线程执行任务
        thread = threading.Thread(target=run_task_in_thread, args=(account_id,))
        thread.daemon = True
        thread.start()

        return jsonify({
            "success": True,
            "message": f"任务已启动，{'处理账号: ' + account_id if account_id else '处理所有账号'}",
            "status": task_status
        })
    except Exception as e:
        logger.error(f"启动任务时出错: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"启动任务失败: {str(e)}"}), 500

@tasks_api.route('/status', methods=['GET'])
def get_task_status():
    """获取任务状态"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    return jsonify({
        "success": True,
        "status": task_status
    })
