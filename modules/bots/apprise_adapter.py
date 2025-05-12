import os
import apprise
import logging
import requests
import json
import re

# 配置日志
try:
    from utils.logger import get_logger
    logger = get_logger('apprise_adapter')
except ImportError:
    # 如果无法导入自定义日志器，使用标准日志
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('apprise_adapter')

# 创建全局Apprise对象
apobj = None

def load_apprise_urls():
    """
    从配置文件加载Apprise URLs
    """
    global apobj

    # 创建新的Apprise对象
    apobj = apprise.Apprise()

    # 设置代理
    setup_proxy()

    # 从环境变量加载URLs
    urls = os.getenv('APPRISE_URLS', '')
    if not urls:
        # 尝试从/data/.env文件读取
        try:
            env_file = '/data/.env'
            if os.path.exists(env_file):
                with open(env_file, 'r') as f:
                    for line in f:
                        if line.startswith('APPRISE_URLS='):
                            urls = line.strip().split('=', 1)[1].strip()
                            # 如果有引号，去掉引号
                            if urls.startswith('"') and urls.endswith('"'):
                                urls = urls[1:-1]
                            elif urls.startswith("'") and urls.endswith("'"):
                                urls = urls[1:-1]

                            # 设置环境变量，这样其他地方也能使用
                            os.environ['APPRISE_URLS'] = urls
                            logger.info(f"从.env文件加载APPRISE_URLS")
                            break
        except Exception as e:
            logger.error(f"读取.env文件时出错: {e}")

    if urls:
        logger.info(f"从环境变量加载Apprise URLs")
        for url in urls.split(','):
            url = url.strip()
            if url:
                try:
                    # 检查URL是否包含未替换的变量（以$开头的字符串）
                    if '$' in url:
                        logger.warning(f"URL包含未替换的变量，已跳过: {url[:10]}...")
                        continue

                    added = apobj.add(url)
                    if added:
                        # 隐藏敏感信息
                        masked_url = mask_sensitive_url(url)
                        logger.info(f"成功添加URL: {masked_url}")
                    else:
                        logger.warning(f"无法添加URL，格式可能不正确")
                except Exception as e:
                    logger.error(f"添加URL时出错: {str(e)}")
    else:
        logger.warning("未找到APPRISE_URLS环境变量")

    # 从配置文件加载URLs
    try:
        config_path = os.path.join('config', 'apprise.yml')
        if os.path.exists(config_path):
            logger.info(f"从配置文件加载Apprise URLs: {config_path}")

            # 直接读取文件内容
            with open(config_path, 'r') as f:
                for line in f:
                    line = line.strip()
                    # 跳过空行和注释
                    if not line or line.startswith('#'):
                        continue

                    # 添加URL
                    try:
                        # 检查URL是否包含未替换的变量（以$开头的字符串）
                        if '$' in line:
                            logger.warning(f"URL包含未替换的变量，已跳过: {line[:10]}...")
                            continue

                        added = apobj.add(line)
                        if added:
                            # 隐藏敏感信息
                            masked_url = mask_sensitive_url(line)
                            logger.info(f"从配置文件成功添加URL: {masked_url}")
                        else:
                            logger.warning(f"无法从配置文件添加URL: {line[:10]}...")
                    except Exception as url_error:
                        logger.error(f"添加URL时出错: {url_error}")
    except Exception as e:
        logger.error(f"加载Apprise配置文件时出错: {e}")

    # 检查是否成功加载了任何URL
    if not apobj or not hasattr(apobj, 'servers'):
        logger.warning("未加载任何有效的Apprise URL")
        return False

    # 检查servers是方法还是属性
    servers_attr = getattr(apobj, 'servers', None)
    if servers_attr is None:
        logger.warning("无法获取servers属性")
        return False

    # 如果servers是列表而不是方法
    if not callable(servers_attr):
        # 检查列表是否为空
        if not servers_attr:
            logger.warning("未加载任何有效的Apprise URL (servers列表为空)")
            return False
    else:
        # 如果servers是方法，调用它并检查结果
        if not servers_attr():
            logger.warning("未加载任何有效的Apprise URL (servers()方法返回空)")
            return False

    return True

def setup_proxy():
    """
    设置代理环境变量
    """
    # 获取代理设置
    http_proxy = os.getenv('HTTP_PROXY', '')
    https_proxy = os.getenv('HTTPS_PROXY', '')

    # 如果没有设置代理，尝试从/data/.env文件读取
    if not http_proxy:
        try:
            env_file = '/data/.env'
            if os.path.exists(env_file):
                with open(env_file, 'r') as f:
                    for line in f:
                        if line.startswith('HTTP_PROXY='):
                            http_proxy = line.strip().split('=', 1)[1].strip()
                            # 如果有引号，去掉引号
                            if http_proxy.startswith('"') and http_proxy.endswith('"'):
                                http_proxy = http_proxy[1:-1]
                            elif http_proxy.startswith("'") and http_proxy.endswith("'"):
                                http_proxy = http_proxy[1:-1]

                            # 设置环境变量
                            os.environ['HTTP_PROXY'] = http_proxy
                            os.environ['http_proxy'] = http_proxy

                            if not https_proxy:
                                os.environ['HTTPS_PROXY'] = http_proxy
                                os.environ['https_proxy'] = http_proxy

                            logger.info(f"从.env文件设置HTTP_PROXY: {http_proxy}")
                            break
        except Exception as e:
            logger.error(f"读取代理设置时出错: {e}")

    # 确保同时设置大小写版本的代理环境变量
    if http_proxy:
        os.environ['HTTP_PROXY'] = http_proxy
        os.environ['http_proxy'] = http_proxy

        if not https_proxy:
            os.environ['HTTPS_PROXY'] = http_proxy
            os.environ['https_proxy'] = http_proxy
        else:
            os.environ['HTTPS_PROXY'] = https_proxy
            os.environ['https_proxy'] = https_proxy

        # 打印当前代理设置
        logger.info(f"当前代理设置:")
        logger.info(f"HTTP_PROXY: {os.environ.get('HTTP_PROXY', '未设置')}")
        logger.info(f"http_proxy: {os.environ.get('http_proxy', '未设置')}")
        logger.info(f"HTTPS_PROXY: {os.environ.get('HTTPS_PROXY', '未设置')}")
        logger.info(f"https_proxy: {os.environ.get('https_proxy', '未设置')}")

        return True

    logger.warning("未设置代理，可能无法访问Telegram API")
    return False

def mask_sensitive_url(url):
    """
    隐藏URL中的敏感信息
    """
    # 对于Telegram URL，隐藏token
    if url.startswith('tgram://'):
        parts = url.replace('tgram://', '').split('/')
        if len(parts) >= 2:
            return f"tgram://****/{parts[1]}"

    # 对于其他URL，只显示服务类型
    parts = url.split('://')
    if len(parts) >= 2:
        return f"{parts[0]}://****"

    return "****"

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
    global apobj

    # 如果Apprise对象为空，尝试加载配置
    if apobj is None:
        load_apprise_urls()

    # 如果仍然为空，则记录消息并返回
    if apobj is None:
        logger.warning(f"未配置Apprise URLs，无法发送通知")
        return False

    # 确保代理设置正确
    setup_proxy()

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
        logger.info(f"发送通知，标题: {title}, 标签: {tag_str}")

        # 尝试多次发送，最多3次
        max_retries = 3
        for attempt in range(max_retries):
            try:
                # 检查Apprise对象是否有效
                if not apobj:
                    logger.error("Apprise对象无效，重新创建对象")
                    load_apprise_urls()
                    continue

                # 检查servers属性
                if not hasattr(apobj, 'servers'):
                    logger.error("Apprise对象没有servers属性，重新创建对象")
                    load_apprise_urls()
                    continue

                # 检查servers是方法还是属性
                servers_attr = getattr(apobj, 'servers', None)
                if servers_attr is None:
                    logger.error("无法获取servers属性，重新创建对象")
                    load_apprise_urls()
                    continue

                # 如果servers是列表而不是方法
                if not callable(servers_attr):
                    logger.info("检测到Apprise API变更，使用兼容模式")

                    # 打印服务器信息
                    logger.info(f"服务器列表(属性): {len(servers_attr)} 个服务器")
                    for i, server in enumerate(servers_attr):
                        server_url = getattr(server, 'url', '未知')
                        server_type = type(server).__name__
                        logger.info(f"服务器 {i+1}: 类型={server_type}, URL={server_url[:20]}...")

                    # 创建新的Apprise对象，并复制原对象的服务器列表
                    new_apobj = apprise.Apprise()
                    for server in servers_attr:
                        if hasattr(server, 'url'):
                            server_url = server.url
                            logger.info(f"添加服务器URL: {server_url[:20]}...")
                            try:
                                added = new_apobj.add(server_url)
                                logger.info(f"添加结果: {added}")
                            except Exception as e:
                                logger.error(f"添加服务器URL时出错: {e}")

                    # 使用新对象发送通知
                    try:
                        logger.info(f"使用兼容模式发送通知，新对象: {new_apobj}")
                        result = new_apobj.notify(
                            body=message,
                            title=title,
                            attach=attach_param,
                            tag=tag_str
                        )
                        logger.info(f"兼容模式通知结果: {result}")
                    except Exception as e:
                        logger.error(f"兼容模式发送通知时出错: {e}")
                        raise
                else:
                    # 正常发送通知
                    try:
                        # 打印服务器信息
                        servers = servers_attr()
                        logger.info(f"服务器列表(方法): {len(servers)} 个服务器")

                        # 设置详细日志
                        if hasattr(apobj, 'logging'):
                            apobj.logging = True

                        logger.info(f"使用标准模式发送通知")
                        result = apobj.notify(
                            body=message,
                            title=title,
                            attach=attach_param,
                            tag=tag_str
                        )
                        logger.info(f"标准模式通知结果: {result}")
                    except Exception as e:
                        logger.error(f"标准模式发送通知时出错: {e}")
                        raise

                if result:
                    logger.info(f"通知发送成功 (尝试 {attempt+1}/{max_retries})")
                    return True
                else:
                    logger.warning(f"通知发送失败 (尝试 {attempt+1}/{max_retries})")

                    # 如果不是最后一次尝试，重新加载配置
                    if attempt < max_retries - 1:
                        logger.info("重新加载Apprise配置并重试")
                        load_apprise_urls()

            except TypeError as e:
                # 如果出现TypeError，可能是API兼容性问题
                logger.error(f"发送通知时出现TypeError: {e}")
                logger.info("尝试重新加载Apprise配置")
                load_apprise_urls()

            except Exception as e:
                logger.error(f"发送通知时出错 (尝试 {attempt+1}/{max_retries}): {e}")

                # 如果不是最后一次尝试，重新加载配置
                if attempt < max_retries - 1:
                    logger.info("重新加载Apprise配置并重试")
                    load_apprise_urls()

        logger.error(f"通知发送失败，已尝试 {max_retries} 次，尝试使用备用方法")

        # 尝试使用备用方法发送Telegram消息
        try:
            # 从环境变量获取Telegram配置
            apprise_urls = os.environ.get('APPRISE_URLS', '')

            # 提取Telegram信息
            telegram_token = None
            telegram_chat_id = None

            for url in apprise_urls.split(','):
                url = url.strip()
                if url.startswith('tgram://'):
                    # 格式: tgram://TOKEN/CHAT_ID
                    parts = url.replace('tgram://', '').split('/')
                    if len(parts) >= 2:
                        telegram_token = parts[0]
                        telegram_chat_id = parts[1]
                        break

            if telegram_token and telegram_chat_id:
                logger.info(f"尝试使用requests库直接发送Telegram消息")

                # 处理消息格式
                # 1. 替换转义的换行符为实际换行
                processed_message = message.replace('\\n', '\n')

                # 2. 构建完整消息
                text = f"{title}\n\n{processed_message}" if title else processed_message

                # 3. 检查是否包含Markdown格式
                has_markdown = '##' in text or '*' in text or '_' in text or '`' in text or '[' in text

                # 4. 处理Telegram的MarkdownV2格式
                # 在MarkdownV2中，以下字符需要转义: _*[]()~`>#+-=|{}.!
                if has_markdown:
                    # 使用HTML格式，更简单且不需要转义
                    # 将Markdown转换为HTML
                    html_text = text
                    # 替换标题
                    html_text = re.sub(r'# (.*?)(\n|$)', r'<b>\1</b>\n', html_text)
                    html_text = re.sub(r'## (.*?)(\n|$)', r'<b>\1</b>\n', html_text)
                    # 替换粗体
                    html_text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', html_text)
                    # 替换斜体
                    html_text = re.sub(r'\*(.*?)\*', r'<i>\1</i>', html_text)
                    html_text = re.sub(r'_(.*?)_', r'<i>\1</i>', html_text)
                    # 替换链接
                    html_text = re.sub(r'\[(.*?)\]\((.*?)\)', r'<a href="\2">\1</a>', html_text)
                    # 替换代码
                    html_text = re.sub(r'`(.*?)`', r'<code>\1</code>', html_text)

                    # 使用处理后的HTML文本
                    text = html_text
                    parse_mode = "HTML"
                else:
                    # 不包含Markdown格式，使用普通文本
                    parse_mode = "HTML"

                # 构建请求
                telegram_api_url = f"https://api.telegram.org/bot{telegram_token}/sendMessage"
                payload = {
                    "chat_id": telegram_chat_id,
                    "text": text,
                    "parse_mode": parse_mode
                }

                # 记录处理后的消息
                logger.info(f"处理后的消息前100个字符: {text[:100]}...")
                logger.info(f"使用解析模式: {payload['parse_mode']}")

                # 设置代理
                proxies = None
                http_proxy = os.environ.get('HTTP_PROXY')
                if http_proxy:
                    proxies = {
                        "http": http_proxy,
                        "https": http_proxy
                    }
                    logger.info(f"使用代理: {http_proxy}")

                # 发送请求
                response = requests.post(
                    telegram_api_url,
                    data=json.dumps(payload),
                    headers={"Content-Type": "application/json"},
                    proxies=proxies,
                    timeout=30
                )

                # 检查响应
                if response.status_code == 200:
                    response_json = response.json()
                    if response_json.get('ok'):
                        logger.info(f"备用方法发送成功: {response_json}")
                        return True
                    else:
                        logger.error(f"备用方法发送失败，API返回错误: {response_json}")
                else:
                    logger.error(f"备用方法发送失败，HTTP状态码: {response.status_code}, 响应: {response.text}")
            else:
                logger.error("未找到有效的Telegram配置")
        except Exception as e:
            logger.error(f"使用备用方法发送消息时出错: {e}")

        return False

    except Exception as e:
        logger.error(f"发送通知时出错: {e}")
        return False

# 初始化时加载配置
load_apprise_urls()

if __name__ == "__main__":
    # 测试
    result = send_notification("这是一条测试消息", "测试标题")
    print(f"发送结果: {result}")
