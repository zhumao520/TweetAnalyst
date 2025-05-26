"""
推送队列服务
管理推送消息队列，处理推送请求
"""

import logging
import time
import traceback
from datetime import datetime, timedelta, timezone
# 使用注释形式的类型注解，避免类型参数问题
# from typing import Dict, Any, List, Optional, Tuple

from models.push_notification import PushNotification
from web_app import db
from modules.bots.apprise_adapter import send_notification, send_to_specific_url

# 获取日志记录器
logger = logging.getLogger(__name__)

def queue_notification(
    message,
    title=None,
    tag=None,
    targets=None,
    account_id=None,
    post_id=None,
    metadata=None,
    max_attempts=3,
    scheduled_for=None
):
    """
    将推送通知加入队列

    Args:
        message: 通知内容
        title: 通知标题
        tag: 标签，用于筛选通知目标
        targets: 推送目标，逗号分隔的URL列表
        account_id: 关联的账号ID
        post_id: 关联的帖子ID
        metadata: 额外元数据
        max_attempts: 最大尝试次数
        scheduled_for: 计划发送时间

    Returns:
        PushNotification: 创建的推送通知记录
    """
    try:
        # 创建推送通知记录
        notification = PushNotification(
            title=title,
            message=message,
            tag=tag,
            targets=targets,
            status='pending',
            attempt_count=0,
            max_attempts=max_attempts,
            account_id=account_id,
            post_id=post_id,
            meta_data=metadata,
            scheduled_for=scheduled_for
        )

        # 保存到数据库
        db.session.add(notification)
        db.session.commit()

        logger.info(f"推送通知已加入队列，ID: {notification.id}")
        return notification
    except Exception as e:
        logger.error(f"将推送通知加入队列时出错: {str(e)}")
        db.session.rollback()
        raise

def process_notification_queue(limit=10):
    """
    处理推送通知队列

    Args:
        limit: 每次处理的最大通知数

    Returns:
        Tuple[int, int]: (处理的通知数, 成功的通知数)
    """
    processed_count = 0
    success_count = 0

    try:
        # 获取待处理的通知
        notifications = PushNotification.get_pending(limit=limit)

        if not notifications:
            logger.debug("没有待处理的推送通知")
            return 0, 0

        logger.info(f"开始处理 {len(notifications)} 条推送通知")

        for notification in notifications:
            processed_count += 1

            # 检查是否到达计划发送时间
            if notification.scheduled_for and notification.scheduled_for > datetime.now(timezone.utc):
                logger.debug(f"通知 {notification.id} 尚未到达计划发送时间，跳过")
                continue

            # 增加尝试次数
            notification.increment_attempt()

            try:
                # 发送通知
                if notification.targets:
                    # 发送到特定目标
                    targets = [url.strip() for url in notification.targets.split(',') if url.strip()]

                    # 记录发送目标（脱敏）
                    masked_targets = [mask_url(url) for url in targets]
                    logger.info(f"发送通知 {notification.id} 到特定目标: {masked_targets}")

                    # 逐个发送到每个目标
                    success = True
                    errors = []

                    for url in targets:
                        try:
                            result = send_to_specific_url(
                                url=url,
                                custom_message=notification.message,
                                custom_title=notification.title
                            )
                            if not result:
                                success = False
                                errors.append(f"发送到 {mask_url(url)} 失败")
                        except Exception as e:
                            success = False
                            errors.append(f"发送到 {mask_url(url)} 出错: {str(e)}")

                    if success:
                        notification.mark_as_success()
                        success_count += 1
                        logger.info(f"通知 {notification.id} 发送成功")
                    else:
                        error_message = "; ".join(errors)
                        notification.error_message = error_message
                        logger.warning(f"通知 {notification.id} 发送失败: {error_message}")
                else:
                    # 使用默认配置发送
                    logger.info(f"使用默认配置发送通知 {notification.id}")

                    result = send_notification(
                        message=notification.message,
                        title=notification.title,
                        tag=notification.tag
                    )

                    if result:
                        notification.mark_as_success()
                        success_count += 1
                        logger.info(f"通知 {notification.id} 发送成功")
                    else:
                        notification.error_message = "发送失败，未返回具体错误"
                        logger.warning(f"通知 {notification.id} 发送失败")
            except Exception as e:
                error_details = {
                    'exception': str(e),
                    'traceback': traceback.format_exc()
                }
                notification.mark_as_failed(
                    error_message=str(e),
                    error_details=error_details
                )
                logger.error(f"处理通知 {notification.id} 时出错: {str(e)}")

        return processed_count, success_count
    except Exception as e:
        logger.error(f"处理推送通知队列时出错: {str(e)}")
        return processed_count, success_count

def retry_failed_notifications(max_age_hours=24, limit=10):
    """
    重试失败的推送通知

    Args:
        max_age_hours: 最大年龄（小时），超过此时间的失败通知不会重试
        limit: 每次重试的最大通知数

    Returns:
        int: 重试的通知数
    """
    retry_count = 0

    try:
        # 计算截止时间
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)

        # 查询需要重试的通知
        notifications = PushNotification.query.filter_by(status='failed').filter(
            PushNotification.created_at >= cutoff_time,
            PushNotification.attempt_count < PushNotification.max_attempts
        ).limit(limit).all()

        if not notifications:
            logger.debug("没有需要重试的失败通知")
            return 0

        logger.info(f"开始重试 {len(notifications)} 条失败的推送通知")

        for notification in notifications:
            # 将状态改为重试中
            notification.status = 'retrying'
            db.session.commit()

            retry_count += 1

        return retry_count
    except Exception as e:
        logger.error(f"重试失败的推送通知时出错: {str(e)}")
        return retry_count

def clean_old_notifications(days=30):
    """
    清理旧的推送通知记录

    Args:
        days: 保留天数，超过此天数的记录将被删除

    Returns:
        int: 删除的记录数
    """
    try:
        # 计算截止时间
        cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)

        # 删除旧记录
        result = PushNotification.query.filter(PushNotification.created_at < cutoff_time).delete()
        db.session.commit()

        logger.info(f"已清理 {result} 条超过 {days} 天的推送通知记录")
        return result
    except Exception as e:
        logger.error(f"清理旧的推送通知记录时出错: {str(e)}")
        db.session.rollback()
        return 0

# 导入URL工具
try:
    from utils.url_utils import mask_sensitive_url as mask_url
except ImportError:
    # 如果无法导入，使用内部实现
    def mask_url(url: str) -> str:
        """
        对URL进行脱敏处理

        Args:
            url: 原始URL

        Returns:
            str: 脱敏后的URL
        """
        if not url:
            return ''

        # 简单的脱敏处理，保留URL类型但隐藏具体凭证
        parts = url.split('://')
        if len(parts) < 2:
            return url

        protocol = parts[0]
        return f"{protocol}://***"
