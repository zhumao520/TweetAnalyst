import os
import apprise
from utils.yaml import load_config_with_env

# 创建全局Apprise对象
apobj = apprise.Apprise()

def load_apprise_urls():
    """
    从配置文件加载Apprise URLs
    """
    # 清空现有URLs
    apobj.clear()

    # 从环境变量加载URLs
    urls = os.getenv('APPRISE_URLS', '')
    if urls:
        for url in urls.split(','):
            url = url.strip()
            if url:
                apobj.add(url)

    # 从配置文件加载URLs
    try:
        config_path = os.path.join('config', 'apprise.yml')
        if os.path.exists(config_path):
            config = apprise.AppriseConfig()
            config.add(config_path)
            apobj.add(config)
    except Exception as e:
        print(f"加载Apprise配置文件时出错: {e}")

def send_notification(message, title=None, attach=None, tag=None):
    """
    发送通知

    Args:
        message (str): 通知内容
        title (str, optional): 通知标题
        attach (str or list, optional): 附件路径或URL
        tag (str, optional): 标签，用于筛选通知目标

    Returns:
        bool: 是否成功发送
    """
    # 如果Apprise对象为空，尝试加载配置
    if not apobj:
        load_apprise_urls()

    # 如果仍然为空，则打印消息并返回
    if not apobj:
        print(f"未配置Apprise URLs，无法发送通知。消息内容: {message}")
        return False

    try:
        # 处理tag参数，确保它是字符串或None
        tag_str = None
        if tag is not None:
            if isinstance(tag, list):
                tag_str = ','.join(tag)
            else:
                tag_str = str(tag)

        # 处理attach参数，确保它是字符串、列表或None
        attach_param = None
        if attach is not None:
            if isinstance(attach, list):
                # 如果是列表，确保所有元素都是字符串
                attach_param = [str(item) for item in attach]
            else:
                attach_param = str(attach)

        # 发送通知
        return apobj.notify(
            body=message,
            title=title,
            attach=attach_param,
            tag=tag_str
        )
    except Exception as e:
        print(f"发送通知时出错: {e}")
        return False

# 初始化时加载配置
load_apprise_urls()

if __name__ == "__main__":
    # 测试
    send_notification("这是一条测试消息", "测试标题")
