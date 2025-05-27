#!/usr/bin/env python3
"""
定时任务脚本
负责执行定时抓取任务
"""
import time
import schedule
import os
import subprocess
import threading
from dotenv import load_dotenv
import sys
import logging
from datetime import datetime
from services.config_service import get_config
from modules.socialmedia.smart_fetch import fetch_twitter_posts_smart

# 添加当前目录到路径，确保能导入web_app模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入日志设置函数
from utils.logger import setup_third_party_logging

# 设置第三方库的日志级别，减少不必要的日志输出
setup_third_party_logging()

# 导入配置和数据库初始化函数
try:
    from web_app import init_db
    from services.config_service import init_config

    # 初始化数据库
    init_db()

    # 使用统一的配置初始化函数
    # 创建应用上下文
    from web_app import app
    with app.app_context() as ctx:
        if init_config(app_context=ctx):
            print("配置初始化成功")
        else:
            print("配置初始化失败，将使用环境变量中的配置")
except ImportError:
    print("警告: 无法导入必要模块，将使用环境变量中的配置")

load_dotenv()

# 全局变量跟踪正在运行的任务
running_tasks = {}
task_lock = threading.Lock()

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('scheduler')

def get_scheduler_config():
    """从数据库获取定时任务配置"""
    try:
        # 获取配置
        interval = int(get_config('SCHEDULER_INTERVAL_MINUTES', '30'))
        auto_fetch = get_config('AUTO_FETCH_ENABLED', 'false').lower() == 'true'
        timeline_interval = int(get_config('TIMELINE_INTERVAL_MINUTES', '60'))
        timeline_fetch = get_config('TIMELINE_FETCH_ENABLED', 'false').lower() == 'true'

        logger.info(f"定时任务配置: 间隔={interval}分钟, 自动抓取={auto_fetch}")
        logger.info(f"时间线任务配置: 间隔={timeline_interval}分钟, 自动抓取={timeline_fetch}")

        return {
            'interval': interval,
            'auto_fetch': auto_fetch,
            'timeline_interval': timeline_interval,
            'timeline_fetch': timeline_fetch
        }
    except Exception as e:
        logger.error(f"获取定时任务配置失败: {str(e)}")
        return {
            'interval': 30,
            'auto_fetch': False,
            'timeline_interval': 60,
            'timeline_fetch': False
        }

def run_scheduled_task():
    """执行定时任务"""
    try:
        logger.info("开始执行定时任务")
        # 获取当前配置
        config = get_scheduler_config()
        logger.info(f"当前定时任务配置: 间隔={config['interval']}分钟, 自动抓取={config['auto_fetch']}")

        # 检查是否启用自动抓取
        if not config['auto_fetch']:
            logger.info("自动抓取未启用，跳过执行")
            return

        # 执行任务
        with app.app_context():
            # 从数据库获取所有需要抓取的账号
            from models.social_account import SocialAccount
            accounts = SocialAccount.query.filter_by(type='twitter').all()

            # 获取抓取数量配置
            fetch_limit = int(get_config('SCHEDULER_FETCH_LIMIT', '10'))

            for account in accounts:
                logger.info(f"开始抓取账号 {account.account_id} 的推文（限制: {fetch_limit} 条）")
                from modules.socialmedia.async_utils import safe_asyncio_run
                posts = safe_asyncio_run(fetch_twitter_posts_smart(account.account_id, fetch_limit, "account"))
                if posts:
                    logger.info(f"成功抓取到 {len(posts)} 条推文")

                    # 处理抓取到的推文（AI分析和保存到数据库）
                    from main import process_posts_for_account
                    processed_count, relevant_count = process_posts_for_account(
                        posts,
                        account,
                        save_to_db=True
                    )

                    logger.info(f"账号 {account.account_id}: 处理了 {processed_count} 条推文，其中 {relevant_count} 条相关内容")
                else:
                    logger.warning(f"账号 {account.account_id}: 未抓取到推文")

        logger.info("定时任务执行完成")
    except Exception as e:
        logger.error(f"执行定时任务时出错: {str(e)}")

def run_timeline_scheduled_task():
    """执行时间线定时任务"""
    try:
        logger.info("开始执行时间线定时任务")
        # 获取当前配置
        config = get_scheduler_config()
        logger.info(f"当前时间线任务配置: 间隔={config['timeline_interval']}分钟, 自动抓取={config['timeline_fetch']}")

        # 检查是否启用时间线抓取
        if not config['timeline_fetch']:
            logger.info("时间线抓取未启用，跳过执行")
            return

        # 执行任务
        with app.app_context():
            # 导入main模块中的处理函数
            from main import process_timeline_posts

            # 获取自动回复设置
            enable_auto_reply = os.getenv("ENABLE_AUTO_REPLY", "false").lower() == "true"
            auto_reply_prompt = os.getenv("AUTO_REPLY_PROMPT", "")

            # 调用处理函数，确保保存到数据库
            total, relevant = process_timeline_posts(enable_auto_reply, auto_reply_prompt, save_to_db=True)

            if total > 0:
                logger.info(f"成功处理 {total} 条时间线推文，其中 {relevant} 条相关内容")
            else:
                logger.warning("未处理到任何时间线推文")

        logger.info("时间线定时任务执行完成")
    except Exception as e:
        logger.error(f"执行时间线定时任务时出错: {str(e)}")

def main():
    """主函数"""
    try:
        logger.info("启动定时任务服务")

        # 获取当前配置
        config = get_scheduler_config()
        logger.info(f"定时任务配置: 间隔={config['interval']}分钟, 自动抓取={config['auto_fetch']}")
        logger.info(f"时间线任务配置: 间隔={config['timeline_interval']}分钟, 自动抓取={config['timeline_fetch']}")

        # 设置定时任务
        schedule.every(config['interval']).minutes.do(run_scheduled_task)
        schedule.every(config['timeline_interval']).minutes.do(run_timeline_scheduled_task)

        logger.info("已设置定时任务")

        # 立即执行一次任务
        logger.info("立即执行一次定时任务")
        with app.app_context():
            # 执行账号抓取任务
            if config['auto_fetch']:
                run_scheduled_task()

            # 执行时间线抓取任务
            if config['timeline_fetch']:
                run_timeline_scheduled_task()

        # 运行定时任务
        while True:
            schedule.run_pending()
            time.sleep(1)
    except Exception as e:
        logger.error(f"定时任务服务出错: {str(e)}")

if __name__ == '__main__':
    main()
