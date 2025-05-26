#!/usr/bin/env python3
"""
推送队列处理器
定期处理推送队列中的消息
"""

import os
import time
import logging
import schedule

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(os.path.join('logs', 'push_queue.log'))
    ]
)

logger = logging.getLogger('push_queue')

def process_queue():
    """处理推送队列"""
    logger.info(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始处理推送队列...")

    try:
        # 导入Flask应用
        from web_app import app

        # 创建应用上下文
        with app.app_context():
            # 导入推送队列服务
            from services.push_queue_service import process_notification_queue, retry_failed_notifications

            # 先重试失败的通知
            retry_count = retry_failed_notifications(max_age_hours=24, limit=5)
            if retry_count > 0:
                logger.info(f"已将 {retry_count} 条失败的通知重新加入队列")

            # 处理队列
            processed, success = process_notification_queue(limit=10)

            if processed > 0:
                logger.info(f"队列处理完成，共处理 {processed} 条通知，成功 {success} 条")
            else:
                logger.info("队列为空，无需处理")
    except Exception as e:
        logger.error(f"处理推送队列时出错: {str(e)}")

def clean_old_notifications():
    """清理旧的推送通知记录"""
    logger.info(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始清理旧的推送通知记录...")

    try:
        # 导入Flask应用
        from web_app import app

        # 创建应用上下文
        with app.app_context():
            # 导入推送队列服务
            from services.push_queue_service import clean_old_notifications

            # 清理30天前的记录
            deleted = clean_old_notifications(days=30)

            logger.info(f"清理完成，共删除 {deleted} 条旧记录")
    except Exception as e:
        logger.error(f"清理旧的推送通知记录时出错: {str(e)}")

def print_status():
    """打印当前状态"""
    logger.info(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 推送队列处理器正在运行...")

    try:
        # 导入Flask应用
        from web_app import app

        # 创建应用上下文
        with app.app_context():
            # 导入PushNotification模型
            from models.push_notification import PushNotification

            # 获取统计信息
            pending_count = PushNotification.query.filter(
                (PushNotification.status == 'pending') | (PushNotification.status == 'retrying')
            ).count()

            failed_count = PushNotification.query.filter_by(status='failed').count()
            success_count = PushNotification.query.filter_by(status='success').count()

            logger.info(f"当前状态: 待处理={pending_count}, 失败={failed_count}, 成功={success_count}")
    except Exception as e:
        logger.error(f"获取状态信息时出错: {str(e)}")

if __name__ == "__main__":
    logger.info(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 推送队列处理器启动")

    # 获取处理间隔（秒）
    process_interval = int(os.getenv("PUSH_QUEUE_INTERVAL_SECONDS", "30"))

    # 设置定时任务
    schedule.every(process_interval).seconds.do(process_queue)

    # 每天凌晨3点清理旧记录
    schedule.every().day.at("03:00").do(clean_old_notifications)

    # 每小时打印状态
    schedule.every().hour.do(print_status)

    # 立即执行一次
    process_queue()
    print_status()

    logger.info(f"定时任务已启动，每 {process_interval} 秒处理一次队列")

    # 循环执行定时任务
    while True:
        schedule.run_pending()
        time.sleep(1)
