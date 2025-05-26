"""
Apprise适配器队列版本
使用队列系统发送推送通知
"""

import os
import logging
import traceback
# 使用注释形式的类型注解，避免类型参数问题
# from typing import Optional, List, Dict, Any, Union

# 配置日志
try:
    from utils.logger import get_logger
    logger = get_logger('apprise_adapter_queue')
except ImportError:
    # 如果无法导入自定义日志器，使用标准日志
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('apprise_adapter_queue')

# 导入推送队列服务
try:
    from services.push_queue_service import queue_notification, process_notification_queue
except ImportError:
    logger.error("无法导入推送队列服务，将使用兼容模式")
    queue_notification = None
    process_notification_queue = None

# 导入原始的Apprise适配器，用于兼容模式
try:
    from modules.bots.apprise_adapter import send_notification as direct_send_notification
    # 尝试导入 send_to_specific_url，如果不存在则导入 send_to_url
    try:
        from modules.bots.apprise_adapter import send_to_specific_url as direct_send_to_specific_url
    except ImportError:
        logger.info("尝试导入 send_to_url 作为替代")
        from modules.bots.apprise_adapter import send_to_url as direct_send_to_specific_url
except ImportError:
    logger.error("无法导入原始的Apprise适配器，推送功能可能无法正常工作")
    direct_send_notification = None
    direct_send_to_specific_url = None

def send_notification(
    message,
    title=None,
    attach=None,
    tag=None,
    account_id=None,
    post_id=None,
    metadata=None,
    use_queue=True
):
    """
    发送通知

    Args:
        message: 通知内容
        title: 通知标题
        attach: 附件路径或URL
        tag: 标签，用于筛选通知目标
        account_id: 关联的账号ID
        post_id: 关联的帖子ID
        metadata: 额外元数据
        use_queue: 是否使用队列，如果为False则直接发送

    Returns:
        bool: 是否成功发送或加入队列
    """
    # 记录调用信息
    logger.info(f"发送通知请求: 标题={title}, 消息长度={len(message) if message else 0}, 使用队列={use_queue}")

    # 如果消息为空，记录警告并返回
    if not message:
        logger.warning("通知消息为空，无法发送")
        return False

    # 处理附件
    if metadata is None:
        metadata = {}
    if attach:
        if isinstance(attach, list):
            metadata['attachments'] = attach
        else:
            metadata['attachments'] = [attach]

    try:
        if use_queue and queue_notification:
            # 导入Flask应用程序
            try:
                from web_app import app

                # 使用Flask应用程序上下文
                with app.app_context():
                    # 使用队列系统
                    notification = queue_notification(
                        message=message,
                        title=title,
                        tag=tag,
                        account_id=account_id,
                        post_id=post_id,
                        metadata=metadata
                    )

                    logger.info(f"通知已加入队列，ID: {notification.id}")

                    # 立即处理队列中的一条消息
                    try:
                        processed, success = process_notification_queue(limit=1)
                        logger.info(f"立即处理队列结果: 处理={processed}, 成功={success}")
                    except Exception as e:
                        logger.error(f"立即处理队列时出错: {str(e)}")
            except ImportError as e:
                logger.error(f"导入Flask应用程序时出错: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"使用Flask应用程序上下文时出错: {str(e)}")
                raise

            return True
        else:
            # 使用直接发送模式
            logger.info("使用直接发送模式")

            if direct_send_notification:
                return direct_send_notification(
                    message=message,
                    title=title,
                    attach=attach,
                    tag=tag
                )
            else:
                logger.error("直接发送功能不可用")
                return False
    except Exception as e:
        error_details = {
            'exception': str(e),
            'traceback': traceback.format_exc()
        }
        logger.error(f"发送通知时出错: {str(e)}")
        logger.debug(f"错误详情: {error_details}")
        return False

def send_to_specific_url(
    url,
    custom_message,
    custom_title=None,
    attach=None,
    use_queue=True
):
    """
    发送通知到特定URL

    Args:
        url: 推送URL
        custom_message: 通知内容
        custom_title: 通知标题
        attach: 附件路径或URL
        use_queue: 是否使用队列，如果为False则直接发送

    Returns:
        bool: 是否成功发送或加入队列
    """
    # 记录调用信息（脱敏URL）
    masked_url = mask_url(url)
    logger.info(f"发送通知到特定URL: {masked_url}, 标题={custom_title}, 消息长度={len(custom_message) if custom_message else 0}, 使用队列={use_queue}")

    # 如果消息为空，记录警告并返回
    if not custom_message:
        logger.warning("通知消息为空，无法发送")
        return False

    # 处理附件
    metadata = {}
    if attach:
        if isinstance(attach, list):
            metadata['attachments'] = attach
        else:
            metadata['attachments'] = [attach]

    try:
        if use_queue and queue_notification:
            # 导入Flask应用程序
            try:
                from web_app import app

                # 使用Flask应用程序上下文
                with app.app_context():
                    # 使用队列系统
                    notification = queue_notification(
                        message=custom_message,
                        title=custom_title,
                        targets=url,
                        metadata=metadata
                    )

                    logger.info(f"通知已加入队列，ID: {notification.id}")

                    # 立即处理队列中的一条消息
                    try:
                        processed, success = process_notification_queue(limit=1)
                        logger.info(f"立即处理队列结果: 处理={processed}, 成功={success}")
                    except Exception as e:
                        logger.error(f"立即处理队列时出错: {str(e)}")
            except ImportError as e:
                logger.error(f"导入Flask应用程序时出错: {str(e)}")
                raise
            except Exception as e:
                logger.error(f"使用Flask应用程序上下文时出错: {str(e)}")
                raise

            return True
        else:
            # 使用直接发送模式
            logger.info("使用直接发送模式")

            if direct_send_to_specific_url:
                return direct_send_to_specific_url(
                    url=url,
                    custom_message=custom_message,
                    custom_title=custom_title
                )
            else:
                logger.error("直接发送功能不可用")
                return False
    except Exception as e:
        error_details = {
            'exception': str(e),
            'traceback': traceback.format_exc()
        }
        logger.error(f"发送通知到特定URL时出错: {str(e)}")
        logger.debug(f"错误详情: {error_details}")
        return False

# 导入URL工具
try:
    from utils.url_utils import mask_sensitive_url as mask_url
except ImportError:
    # 如果无法导入，使用内部实现
    def mask_url(url):
        """
        隐藏URL中的敏感信息

        Args:
            url: 原始URL

        Returns:
            str: 脱敏后的URL
        """
        if not url:
            return ''

        # 对于Telegram URL，隐藏token
        if url.startswith('tgram://'):
            parts = url.replace('tgram://', '').split('/')
            if len(parts) >= 2:
                return f"tgram://****/{parts[1]}"

        # 对于Bark URL，隐藏token
        elif url.startswith('bark://') or url.startswith('barks://'):
            protocol = 'bark://' if url.startswith('bark://') else 'barks://'
            parts = url.replace('bark://', '').replace('barks://', '').split('/')
            if len(parts) >= 2:
                return f"{protocol}{parts[0]}/****"

        # 对于其他URL，只显示服务类型
        parts = url.split('://')
        if len(parts) >= 2:
            return f"{parts[0]}://****"

        return "****"
