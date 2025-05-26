"""
URL处理工具
提供URL脱敏、验证和处理功能
"""

import re
import logging
from typing import List, Optional, Tuple

# 获取日志记录器
logger = logging.getLogger(__name__)

def mask_sensitive_url(url: str) -> str:
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

    # 对于Discord URL，隐藏webhook token
    elif url.startswith('discord://'):
        parts = url.replace('discord://', '').split('/')
        if len(parts) >= 2:
            return f"discord://****/{parts[1][:4]}****"

    # 对于其他URL，只显示服务类型
    parts = url.split('://')
    if len(parts) >= 2:
        return f"{parts[0]}://****"

    return "****"

def validate_url(url: str) -> Tuple[bool, Optional[str]]:
    """
    验证URL格式是否正确

    Args:
        url: 要验证的URL

    Returns:
        Tuple[bool, Optional[str]]: (是否有效, 错误信息)
    """
    if not url:
        return False, "URL不能为空"

    # 检查URL是否包含协议
    if '://' not in url:
        return False, "URL必须包含协议（如tgram://、bark://等）"

    # 检查是否是支持的协议
    protocol = url.split('://')[0].lower()
    supported_protocols = ['tgram', 'bark', 'barks', 'discord', 'slack', 'wxteams', 'mailto', 'pushover']

    if protocol not in supported_protocols:
        return False, f"不支持的协议: {protocol}，支持的协议有: {', '.join(supported_protocols)}"

    # 特定协议的格式验证
    if protocol == 'tgram':
        # Telegram格式: tgram://token/chat_id
        pattern = r'^tgram://[^/]+/[^/]+$'
        if not re.match(pattern, url):
            return False, "Telegram URL格式不正确，应为: tgram://token/chat_id"

    elif protocol in ['bark', 'barks']:
        # Bark格式: bark://server/key
        pattern = r'^bark[s]?://[^/]+/[^/]+$'
        if not re.match(pattern, url):
            return False, "Bark URL格式不正确，应为: bark://server/key 或 barks://server/key"

    return True, None

def parse_urls(urls_text: str) -> List[str]:
    """
    解析多个URL

    Args:
        urls_text: 包含多个URL的文本，可以是逗号分隔或换行符分隔

    Returns:
        List[str]: URL列表
    """
    if not urls_text:
        return []

    # 支持两种分隔方式：逗号和换行符
    if '\n' in urls_text:
        url_list = urls_text.splitlines()
    else:
        # 如果没有换行符，按逗号分割
        url_list = urls_text.split(',')

    # 清理URL
    cleaned_urls = []
    for url in url_list:
        url = url.strip()
        if url:
            # 检查URL是否包含未替换的变量（以$开头的字符串）
            if '$' in url:
                logger.warning(f"URL包含未替换的变量，已跳过: {url[:10]}...")
                continue

            # 去掉URL末尾的斜杠，避免解析问题
            if url.endswith('/') and not url.endswith('//'):
                url = url[:-1]

            cleaned_urls.append(url)

    return cleaned_urls

def normalize_bark_url(url: str) -> str:
    """
    规范化Bark URL

    Args:
        url: 原始Bark URL

    Returns:
        str: 规范化后的URL
    """
    if not url:
        return url

    # 将barks://转换为bark://
    if url.startswith('barks://'):
        url = url.replace('barks://', 'bark://')

    # 不再自动替换Bark服务器域名，因为设备令牌可能只在特定服务器上有效
    # if 'bark.021800.xyz' in url:
    #     url = url.replace('bark.021800.xyz', 'api.day.app')

    # 去掉URL末尾的斜杠，避免解析问题
    if url.endswith('/') and not url.endswith('//'):
        url = url[:-1]

    return url
