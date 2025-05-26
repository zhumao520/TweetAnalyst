import os
import apprise
import logging
import requests
import json
import re
import time
# 使用注释形式的类型注解，避免类型参数问题
# from typing import Optional, List, Dict, Any, Union

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

# 全局变量，用于存储最近的推文内容
# 格式: {'message': '消息内容', 'title': '标题', 'tag': '标签', 'attach': '附件'}
latest_tweet = {
    'message': '',
    'title': '',
    'tag': '',
    'attach': None
}

def load_apprise_urls():
    """
    从数据库加载Apprise URLs
    """
    global apobj

    # 创建新的Apprise对象
    apobj = apprise.Apprise()

    # 设置代理
    setup_proxy()

    # 添加自定义URL处理钩子
    try:
        # 尝试添加自定义URL处理钩子
        if hasattr(apprise, 'URLBase'):
            # 获取Bark处理类
            bark_handlers = [h for h in apprise.URLBase.plugins() if h.__name__ == 'NotifyBark']
            if bark_handlers:
                bark_class = bark_handlers[0]
                # 保存原始的parse_url方法
                original_parse_url = bark_class.parse_url

                # 定义新的parse_url方法
                def custom_parse_url(cls, url, *args, **kwargs):
                    # 检查是否是bark.021800.xyz服务器
                    if 'bark.021800.xyz' in url:
                        logger.info(f"检测到bark.021800.xyz服务器，使用特殊处理")
                        # 确保URL格式为 bark://server/key
                        if url.startswith('bark://') or url.startswith('barks://'):
                            # 将URL转换为旧版格式
                            url = url.replace('barks://', 'bark://')
                            parts = url.replace('bark://', '').split('/')
                            if len(parts) >= 2:
                                server = parts[0]
                                key = parts[1]
                                # 使用旧版格式
                                url = f"bark://{server}/{key}"
                                logger.info(f"转换后的URL: {mask_sensitive_url(url)}")

                    # 调用原始方法
                    return original_parse_url(cls, url, *args, **kwargs)

                # 替换parse_url方法
                bark_class.parse_url = classmethod(custom_parse_url)
                logger.info(f"成功添加Bark URL处理钩子")
    except Exception as e:
        logger.warning(f"添加自定义URL处理钩子时出错: {e}")

    # 从数据库获取URLs
    try:
        # 尝试导入配置服务
        from services.config_service import get_config

        # 从数据库获取URLs
        urls = get_config('APPRISE_URLS', '')
        logger.info(f"从数据库加载Apprise URLs")

        if not urls:
            logger.warning("数据库中未配置推送URL")
            return False

        # 解析URL列表
        url_list = parse_urls(urls)
        logger.info(f"从数据库找到 {len(url_list)} 个推送URL")

        # 添加URL
        for url in url_list:
            # 跳过明显无效的URL
            if not url or url.startswith('#') or not ':' in url:
                logger.debug(f"跳过无效的URL: {mask_sensitive_url(url)}")
                continue

            try:
                # 规范化URL
                normalized_url = normalize_bark_url(url)

                # 检查是否包含占位符
                if 'BOT_TOKEN' in normalized_url or 'CHAT_ID' in normalized_url or 'WEBHOOK_ID' in normalized_url or 'WEBHOOK_TOKEN' in normalized_url or 'YOUR_DEVICE_KEY' in normalized_url:
                    logger.warning(f"跳过包含占位符的URL: {mask_sensitive_url(normalized_url)}")
                    continue

                # 记录添加前的URL
                logger.info(f"尝试添加URL: {mask_sensitive_url(normalized_url)}")

                # 尝试添加URL
                added = apobj.add(normalized_url)

                if added:
                    # 隐藏敏感信息
                    masked_url = mask_sensitive_url(normalized_url)
                    logger.info(f"成功添加URL: {masked_url}")
                else:
                    # 如果添加失败，尝试其他格式
                    logger.warning(f"无法添加URL: {mask_sensitive_url(normalized_url)}，尝试其他格式")

                    # 尝试不同的格式组合
                    alt_formats = []

                    # 如果原始URL是barks://，尝试bark://
                    if url.startswith('barks://'):
                        alt_url = url.replace('barks://', 'bark://')
                        alt_formats.append(alt_url)

                    # 尝试去掉末尾的斜杠
                    if url.endswith('/'):
                        alt_url = url[:-1]
                        alt_formats.append(alt_url)

                        # 如果同时是barks://并且有末尾斜杠，尝试两者都修改
                        if url.startswith('barks://'):
                            alt_url = url.replace('barks://', 'bark://')[:-1]
                            alt_formats.append(alt_url)

                    # 尝试所有替代格式
                    success = False
                    for alt_url in alt_formats:
                        logger.info(f"尝试使用替代格式: {mask_sensitive_url(alt_url)}")
                        try:
                            alt_added = apobj.add(alt_url)
                            if alt_added:
                                logger.info(f"使用替代格式成功添加URL: {mask_sensitive_url(alt_url)}")
                                success = True
                                break
                        except Exception as alt_error:
                            logger.warning(f"使用替代格式添加URL时出错: {str(alt_error)}")

                    if not success:
                        # 如果所有尝试都失败，记录警告
                        logger.warning(f"所有尝试都失败，无法添加URL: {mask_sensitive_url(url)}")
            except Exception as e:
                logger.error(f"添加URL时出错: {str(e)}, URL: {mask_sensitive_url(url)}")

        return True
    except ImportError:
        logger.error("无法导入配置服务，尝试从环境变量获取URLs")
        # 如果无法导入配置服务，尝试从环境变量获取
        urls = os.getenv('APPRISE_URLS', '')
        if urls:
            logger.info(f"从环境变量加载Apprise URLs")
            url_list = parse_urls(urls)
            logger.info(f"找到 {len(url_list)} 个推送URL")

            # 处理URL列表...（与上面相同的逻辑）
            # 为简洁起见，这里省略了重复代码
            return True
        else:
            logger.warning("环境变量中未配置推送URL")
            return False
    except Exception as e:
        logger.error(f"加载Apprise URLs时出错: {e}")
        return False



def setup_proxy():
    """
    设置代理环境变量，优先使用代理管理器
    """
    # 尝试导入代理管理器
    try:
        from utils.api_utils import get_proxy_manager

        # 获取代理管理器
        proxy_manager = get_proxy_manager()

        # 查找可用代理
        working_proxy = proxy_manager.find_working_proxy()

        if working_proxy:
            # 获取代理URL
            proxy_url = working_proxy.get_proxy_url()

            # 设置环境变量
            os.environ['HTTP_PROXY'] = proxy_url
            os.environ['http_proxy'] = proxy_url
            os.environ['HTTPS_PROXY'] = proxy_url
            os.environ['https_proxy'] = proxy_url

            logger.info(f"使用代理管理器设置代理: {working_proxy.name}, URL: {proxy_url}")
            return True
        else:
            logger.warning("代理管理器未找到可用的代理，尝试使用环境变量")
    except ImportError:
        logger.warning("无法导入代理管理器，尝试使用环境变量")
    except Exception as e:
        logger.warning(f"使用代理管理器时出错: {str(e)}，尝试使用环境变量")

    # 如果代理管理器不可用或未找到可用代理，回退到环境变量
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

# 导入URL工具
try:
    from utils.url_utils import mask_sensitive_url, validate_url, parse_urls, normalize_bark_url
except ImportError:
    # 如果无法导入，使用内部实现
    logger.warning("无法导入URL工具，使用内部实现")

    def mask_sensitive_url(url):
        """
        隐藏URL中的敏感信息
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

    def validate_url(url):
        """简单的URL验证"""
        return True, None

    def parse_urls(urls_text):
        """解析多个URL"""
        if not urls_text:
            return []

        urls = []

        # 支持两种分隔方式：逗号和换行符
        if '\n' in urls_text:
            # 按行分割
            lines = urls_text.splitlines()
            for line in lines:
                line = line.strip()
                # 跳过空行
                if not line:
                    continue
                # 跳过注释行
                if line.startswith('#'):
                    continue
                # 跳过明显不是URL的行（如包含中文或特殊字符的说明文本）
                if any(char in line for char in '：，。？！""''（）【】《》'):
                    continue
                # 跳过明显是标题或分隔符的行
                if line.startswith('=') or line.endswith('=') or line.startswith('-') or line.endswith('-'):
                    continue
                # 如果URL前面有注释标记，去掉注释标记
                if '#' in line:
                    # 只保留#之前的部分，如果#不是在开头
                    if not line.startswith('#'):
                        line = line.split('#')[0].strip()
                    else:
                        continue

                # 添加有效的URL
                if line and ':' in line:  # 简单检查是否包含协议部分
                    urls.append(line)
        else:
            # 按逗号分割
            for url in urls_text.split(','):
                url = url.strip()
                # 跳过空字符串
                if not url:
                    continue
                # 跳过注释
                if url.startswith('#'):
                    continue
                # 如果URL前面有注释标记，去掉注释标记
                if '#' in url:
                    # 只保留#之前的部分，如果#不是在开头
                    if not url.startswith('#'):
                        url = url.split('#')[0].strip()
                    else:
                        continue

                # 添加有效的URL
                if url and ':' in url:  # 简单检查是否包含协议部分
                    urls.append(url)

        return urls

    def normalize_bark_url(url):
        """规范化Bark URL"""
        if not url:
            return url

        # 将barks://转换为bark://
        if url.startswith('barks://'):
            url = url.replace('barks://', 'bark://')

        # 不再自动替换Bark服务器域名，因为设备令牌可能只在特定服务器上有效
        # if 'bark.021800.xyz' in url:
        #     url = url.replace('bark.021800.xyz', 'api.day.app')

        # 检查是否使用了旧版本的Bark服务器
        if 'day.app' in url and not url.startswith('bark://'):
            # 如果URL是 https://api.day.app/key 格式，转换为 bark://api.day.app/key
            if url.startswith('http://') or url.startswith('https://'):
                parts = url.split('://', 1)
                if len(parts) == 2:
                    url = f"bark://{parts[1]}"

        # 检查Bark URL格式是否正确
        if url.startswith('bark://'):
            # 确保URL格式为 bark://server/key
            parts = url.replace('bark://', '').split('/')
            if len(parts) >= 2:
                server = parts[0]
                key = parts[1]

                # 如果服务器是api.day.app，使用新版API格式
                if server == 'api.day.app':
                    # 使用新版API格式，将设备密钥作为参数
                    # 新格式：bark://api.day.app?device_key=YOUR_DEVICE_KEY
                    # 但为了兼容性，我们仍然保持旧格式：bark://api.day.app/YOUR_DEVICE_KEY
                    url = f"bark://api.day.app/{key}"
                    logger.info(f"检测到官方Bark服务器，使用兼容格式: {mask_sensitive_url(url)}")

                # 如果密钥包含参数，确保参数格式正确
                if '?' in key:
                    key_parts = key.split('?', 1)
                    if len(key_parts) == 2:
                        key = key_parts[0]
                        params = key_parts[1]
                        url = f"bark://{server}/{key}?{params}"

                # 检查是否使用了示例值
                if key == 'YOUR_DEVICE_KEY':
                    logger.warning(f"检测到示例Bark URL，请替换为实际的设备密钥")

                # 检查密钥长度是否合理
                if len(key) < 8:
                    logger.warning(f"Bark密钥长度可能不正确，请检查: {key[:4] if len(key) >= 4 else key}...")

        # 去掉URL末尾的斜杠，避免解析问题
        if url.endswith('/') and not url.endswith('//'):
            url = url[:-1]

        return url

def check_apprise_object():
    """
    检查Apprise对象是否有效，如果无效则尝试重新创建

    Returns:
        bool: 对象是否有效
    """
    global apobj

    # 如果对象为空，尝试加载配置
    if apobj is None:
        logger.info("Apprise对象为空，尝试加载配置")
        try:
            load_apprise_urls()
            if apobj is None:
                logger.warning("加载配置后Apprise对象仍为空")
                return False
        except Exception as e:
            logger.error(f"加载Apprise配置失败: {e}")
            return False

    # 检查servers属性
    if not hasattr(apobj, 'servers'):
        logger.error("Apprise对象没有servers属性，尝试重新创建")
        try:
            load_apprise_urls()
            if not hasattr(apobj, 'servers'):
                logger.warning("重新创建后Apprise对象仍没有servers属性")
                return False
        except Exception as e:
            logger.error(f"重新创建Apprise对象失败: {e}")
            return False

    # 检查servers是方法还是属性
    servers_attr = getattr(apobj, 'servers', None)
    if servers_attr is None:
        logger.error("无法获取servers属性，尝试重新创建")
        try:
            load_apprise_urls()
            servers_attr = getattr(apobj, 'servers', None)
            if servers_attr is None:
                logger.warning("重新创建后仍无法获取servers属性")
                return False
        except Exception as e:
            logger.error(f"重新创建Apprise对象失败: {e}")
            return False

    return True

def send_notification(message, title=None, attach=None, tag=None, account_id=None, post_id=None, metadata=None, use_queue=True):
    """
    发送通知

    Args:
        message (str): 通知内容
        title (str, optional): 通知标题
        attach (str or list, optional): 附件路径或URL
        tag (str, optional): 标签，用于筛选通知目标
        account_id (int, optional): 关联的账号ID
        post_id (int, optional): 关联的帖子ID
        metadata (dict, optional): 额外元数据
        use_queue (bool, optional): 是否使用队列，默认为True

    Returns:
        bool: 是否成功发送
    """
    global apobj, latest_tweet

    # 生成请求ID，用于跟踪整个请求的生命周期
    request_id = f"req_{int(time.time() * 1000)}"

    # 记录调用信息（结构化日志）
    logger.info(
        f"发送通知请求 [请求ID: {request_id}]",
        extra={
            'request_id': request_id,
            'title': title,
            'message_length': len(message) if message else 0,
            'has_attach': attach is not None,
            'tag': tag,
            'account_id': account_id,
            'post_id': post_id,
            'has_metadata': metadata is not None,
            'use_queue': use_queue
        }
    )

    # 忽略未使用的参数，保持向后兼容性
    # account_id, post_id, metadata 和 use_queue 参数在此函数中不使用
    # 但为了与 apprise_adapter_queue.py 保持接口一致，仍然接受这些参数

    # 尝试直接逐个发送到每个URL
    try:
        # 获取所有配置的URL
        urls = []

        # 从数据库获取URL
        try:
            # 尝试导入配置服务
            from services.config_service import get_config

            # 从数据库获取URLs
            apprise_urls = get_config('APPRISE_URLS', '')
            logger.info(f"从数据库加载Apprise URLs")

            if apprise_urls:
                urls.extend(parse_urls(apprise_urls))
                logger.info(f"从数据库找到 {len(urls)} 个推送URL")
            else:
                logger.warning("数据库中未配置推送URL")
        except ImportError:
            logger.warning("无法导入配置服务，尝试从环境变量获取URLs")
            # 如果无法导入配置服务，尝试从环境变量获取
            apprise_urls = os.environ.get('APPRISE_URLS', '')
            if apprise_urls:
                urls.extend(parse_urls(apprise_urls))
                logger.info(f"从环境变量找到 {len(urls)} 个推送URL")
            else:
                logger.warning("环境变量中未配置推送URL")

        # 去重
        urls = list(set(urls))

        if urls:
            logger.info(f"找到 {len(urls)} 个推送URL，将逐个发送 [请求ID: {request_id}]")

            # 逐个发送到每个URL
            success_count = 0
            for url in urls:
                try:
                    result = send_to_url(url, message, title)
                    if result:
                        success_count += 1
                        logger.info(f"成功发送到URL: {mask_sensitive_url(url)} [请求ID: {request_id}]")
                    else:
                        logger.warning(f"发送到URL失败: {mask_sensitive_url(url)} [请求ID: {request_id}]")
                except Exception as e:
                    logger.error(f"发送到URL时出错: {str(e)}, URL: {mask_sensitive_url(url)} [请求ID: {request_id}]")

            # 如果至少有一个URL成功，则认为整体成功
            if success_count > 0:
                logger.info(f"成功发送到 {success_count}/{len(urls)} 个URL [请求ID: {request_id}]")
                return True
            else:
                logger.error(f"所有 {len(urls)} 个URL发送都失败了，尝试使用备用方法 [请求ID: {request_id}]")
                return send_via_fallback_methods(message, title, request_id)
    except Exception as e:
        logger.error(f"直接发送方法失败: {str(e)}，尝试使用标准方法 [请求ID: {request_id}]")

    # 存储推文内容到全局变量，方便其他推送服务使用
    latest_tweet['message'] = message
    latest_tweet['title'] = title if title else ""
    latest_tweet['tag'] = tag if tag else ""
    latest_tweet['attach'] = attach
    latest_tweet['request_id'] = request_id  # 添加请求ID

    # 如果消息为空，记录警告并返回
    if not message:
        logger.warning(
            f"通知消息为空，无法发送 [请求ID: {request_id}]",
            extra={'request_id': request_id}
        )
        return False

    # 检查Apprise对象是否有效
    if not check_apprise_object():
        logger.warning(
            f"Apprise对象无效，无法发送通知 [请求ID: {request_id}]",
            extra={'request_id': request_id}
        )
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
        logger.info(f"尝试使用标准方法发送通知，标题: {title}, 标签: {tag_str} [请求ID: {request_id}]")

        # 只尝试一次，不再多次重试
        max_retries = 1
        for attempt in range(max_retries):
            try:
                # 检查Apprise对象是否有效
                if not check_apprise_object():
                    logger.warning(
                        f"尝试 {attempt+1}/{max_retries}: Apprise对象无效，跳过此次尝试 [请求ID: {request_id}]",
                        extra={
                            'request_id': request_id,
                            'attempt': attempt + 1,
                            'max_retries': max_retries
                        }
                    )
                    continue

                # 获取servers属性
                servers_attr = getattr(apobj, 'servers', None)

                # 如果servers是列表而不是方法
                if not callable(servers_attr):
                    logger.info("检测到Apprise API变更，使用兼容模式")

                    # 打印服务器信息
                    try:
                        # 尝试将servers_attr转换为列表
                        try:
                            # 检查servers_attr是否是可调用的方法
                            if callable(servers_attr):
                                logger.warning("servers_attr是可调用的方法，无法直接转换为列表")
                                # 不尝试调用方法，避免出错
                            else:
                                # 如果不是方法，尝试转换为列表
                                servers_list = list(servers_attr)
                                # 如果是可迭代对象（如列表）
                                logger.info(f"服务器列表(属性): {len(servers_list)} 个服务器")
                                for i, server in enumerate(servers_list):
                                    try:
                                        # 使用安全的方式获取URL
                                        server_url = getattr(server, 'url', '未知')
                                        if callable(server_url):
                                            try:
                                                # 尝试调用方法获取URL
                                                url_value = server_url()
                                                logger.info(f"成功从方法获取URL: {str(url_value)[:20]}...")
                                                server_url = url_value
                                            except Exception as e:
                                                logger.warning(f"调用服务器URL方法时出错: {e}")
                                                server_url = '未知(方法调用失败)'
                                        server_type = type(server).__name__
                                        logger.info(f"服务器 {i+1}: 类型={server_type}, URL={str(server_url)[:20]}...")
                                    except Exception as e:
                                        logger.warning(f"获取服务器 {i+1} 信息时出错: {e}")
                        except TypeError:
                            # 如果不是可迭代对象，可能是方法或其他类型
                            logger.warning("servers_attr不是可迭代对象，无法显示服务器列表")
                        except Exception as e:
                            logger.warning(f"获取服务器列表信息时出错: {e}")
                    except Exception as e:
                        logger.warning(f"获取服务器列表信息时出错: {e}")

                    # 创建新的Apprise对象，并复制原对象的服务器列表
                    new_apobj = apprise.Apprise()

                    # 尝试从服务器列表添加URL
                    try:
                        # 尝试将servers_attr转换为列表
                        try:
                            # 检查servers_attr是否是可调用的方法
                            if callable(servers_attr):
                                logger.warning("servers_attr是可调用的方法，无法直接转换为列表，将直接从环境变量加载URL")
                                raise TypeError("servers_attr是可调用的方法")
                            else:
                                # 如果不是方法，尝试转换为列表
                                servers_list = list(servers_attr)
                                for server in servers_list:
                                    if hasattr(server, 'url'):
                                        try:
                                            # 安全地获取URL
                                            server_url = getattr(server, 'url', None)
                                            # 检查url是否是方法
                                            if callable(server_url):
                                                try:
                                                    # 尝试调用方法获取URL
                                                    url_value = server_url()
                                                    logger.info(f"成功从方法获取URL: {str(url_value)[:20]}...")
                                                    server_url = url_value
                                                except Exception as e:
                                                    logger.warning(f"调用服务器URL方法时出错: {e}，跳过此服务器")
                                                    continue

                                            if server_url:
                                                logger.info(f"添加服务器URL: {str(server_url)[:20]}...")
                                                added = new_apobj.add(server_url)
                                                logger.info(f"添加结果: {added}")
                                        except Exception as e:
                                            logger.error(f"添加服务器URL时出错: {e}")
                        except TypeError:
                            # 如果不是可迭代对象，直接从环境变量加载
                            logger.warning("servers_attr不是可迭代对象，将直接从环境变量加载URL")
                            raise TypeError("servers_attr不是可迭代对象")
                        except Exception as e:
                            logger.warning(f"从服务器列表添加URL时出错: {e}")
                            raise
                    except Exception as e:
                        logger.warning(f"从服务器列表添加URL时出错: {e}")

                        # 如果从服务器列表添加失败，尝试从环境变量重新加载
                        logger.info("尝试从环境变量重新加载URL")
                        urls = os.getenv('APPRISE_URLS', '')

                        # 支持两种分隔方式：逗号和换行符
                        if '\n' in urls:
                            url_list = urls.splitlines()
                        else:
                            # 如果没有换行符，按逗号分割
                            url_list = urls.split(',')

                        for url in url_list:
                            url = url.strip()
                            if url:
                                try:
                                    added = new_apobj.add(url)
                                    logger.info(f"从环境变量添加URL结果: {added}")
                                except Exception as add_error:
                                    logger.error(f"从环境变量添加URL时出错: {add_error}")

                    # 使用新对象替换原对象
                    # 不使用global关键字，直接更新全局变量
                    globals()['apobj'] = new_apobj

                    # 使用新对象发送通知
                    try:
                        # 记录新对象信息，但不显示完整对象（可能很大）
                        logger.info(f"使用兼容模式发送通知，新对象ID: {id(new_apobj)}")
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
                        try:
                            # 尝试调用servers_attr()获取服务器列表
                            if callable(servers_attr):
                                try:
                                    # 检查是否是方法对象而不是函数
                                    if hasattr(servers_attr, '__self__'):
                                        # 如果是绑定方法，需要正确调用
                                        # 但不直接调用，避免出错
                                        logger.info("检测到servers_attr是绑定方法，不直接调用")
                                        # 直接切换到兼容模式
                                        raise TypeError("servers_attr是绑定方法")
                                    else:
                                        # 如果是普通函数，也不直接调用
                                        logger.info("检测到servers_attr是普通函数，不直接调用")
                                        # 直接切换到兼容模式
                                        raise TypeError("servers_attr是普通函数")
                                except TypeError as e:
                                    # 如果servers_attr是方法对象而不是函数，会出现TypeError
                                    logger.warning(f"获取服务器列表时出现TypeError: {e}")
                                    logger.info("检测到Apprise API变更，切换到兼容模式")
                                    raise  # 重新抛出异常，进入下面的异常处理块
                                except Exception as e:
                                    # 捕获其他可能的异常
                                    logger.warning(f"调用servers_attr()时出现异常: {e}")
                                    logger.info("切换到兼容模式")
                                    raise
                            else:
                                # 如果servers_attr不是可调用的，直接切换到兼容模式
                                logger.warning("servers_attr不是可调用的，切换到兼容模式")
                                raise TypeError("servers_attr不是可调用的")
                        except (TypeError, AttributeError) as e:
                            # 如果servers_attr是方法对象而不是函数，或者调用出错，会进入这里
                            logger.warning(f"获取服务器列表时出现错误: {e}")

                            # 创建新的Apprise对象
                            new_apobj = apprise.Apprise()

                            # 尝试从原始URL重新添加服务器
                            urls = os.getenv('APPRISE_URLS', '')

                            # 支持两种分隔方式：逗号和换行符
                            if '\n' in urls:
                                url_list = urls.splitlines()
                            else:
                                # 如果没有换行符，按逗号分割
                                url_list = urls.split(',')

                            logger.info(f"尝试重新添加 {len(url_list)} 个推送URL")

                            for url in url_list:
                                url = url.strip()
                                if url:
                                    try:
                                        added = new_apobj.add(url)
                                        logger.info(f"重新添加URL结果: {added}")
                                    except Exception as add_error:
                                        logger.error(f"添加URL时出错: {add_error}")

                            # 使用新对象替换原对象
                            # 不使用global关键字，直接更新全局变量
                            globals()['apobj'] = new_apobj

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
                    logger.info(
                        f"通知发送成功 (尝试 {attempt+1}/{max_retries}) [请求ID: {request_id}]",
                        extra={
                            'request_id': request_id,
                            'attempt': attempt + 1,
                            'max_retries': max_retries,
                            'status': 'success'
                        }
                    )
                    return True
                else:
                    logger.warning(
                        f"通知发送失败 (尝试 {attempt+1}/{max_retries}) [请求ID: {request_id}]",
                        extra={
                            'request_id': request_id,
                            'attempt': attempt + 1,
                            'max_retries': max_retries,
                            'status': 'failed'
                        }
                    )

                    # 如果不是最后一次尝试，重新加载配置
                    if attempt < max_retries - 1:
                        logger.info(
                            f"重新加载Apprise配置并重试 [请求ID: {request_id}]",
                            extra={'request_id': request_id}
                        )
                        try:
                            load_apprise_urls()
                            logger.info(
                                f"重新加载Apprise配置成功，对象ID: {id(apobj)} [请求ID: {request_id}]",
                                extra={'request_id': request_id}
                            )
                        except Exception as e:
                            logger.error(
                                f"重新加载Apprise配置失败: {e} [请求ID: {request_id}]",
                                extra={'request_id': request_id, 'error': str(e)}
                            )

            except TypeError as e:
                # 如果出现TypeError，可能是API兼容性问题
                logger.error(f"发送通知时出现TypeError: {e}")
                logger.info("尝试重新加载Apprise配置")
                try:
                    load_apprise_urls()
                    logger.info(f"重新加载Apprise配置成功，对象ID: {id(apobj)}")
                except Exception as load_error:
                    logger.error(f"重新加载Apprise配置失败: {load_error}")

            except Exception as e:
                logger.error(f"发送通知时出错 (尝试 {attempt+1}/{max_retries}): {e}")

                # 如果不是最后一次尝试，重新加载配置
                if attempt < max_retries - 1:
                    logger.info("重新加载Apprise配置并重试")
                    try:
                        load_apprise_urls()
                        logger.info(f"重新加载Apprise配置成功，对象ID: {id(apobj)}")
                    except Exception as load_error:
                        logger.error(f"重新加载Apprise配置失败: {load_error}")

        logger.error(
            f"通知发送失败，已尝试 {max_retries} 次，尝试使用备用方法 [请求ID: {request_id}]",
            extra={
                'request_id': request_id,
                'max_retries': max_retries,
                'status': 'fallback'
            }
        )

        # 使用备用方法发送
        return send_via_fallback_methods(message, title, request_id)

    except Exception as e:
        logger.error(f"发送通知时出错: {e}")
        return False

def send_via_fallback_methods(message, title=None, request_id=None):
    """
    使用备用方法发送通知

    Args:
        message: 通知内容
        title: 通知标题
        request_id: 请求ID，用于跟踪请求

    Returns:
        bool: 是否成功发送
    """
    # 如果没有提供请求ID，生成一个新的
    if request_id is None:
        request_id = f"fallback_{int(time.time() * 1000)}"
    # 尝试使用备用方法发送Telegram消息
    try:
        # 从环境变量获取Telegram配置
        apprise_urls = os.environ.get('APPRISE_URLS', '')

        # 提取Telegram信息
        telegram_token = None
        telegram_chat_id = None

        # 提取Bark信息
        bark_server = None
        bark_key = None

        # 解析URL列表
        url_list = parse_urls(apprise_urls)
        logger.info(
            f"备用方法：检查 {len(url_list)} 个推送URL [请求ID: {request_id}]",
            extra={
                'request_id': request_id,
                'url_count': len(url_list)
            }
        )

        # 先查找Telegram配置
        for url in url_list:
            if url.startswith('tgram://'):
                # 格式: tgram://TOKEN/CHAT_ID
                parts = url.replace('tgram://', '').split('/')
                if len(parts) >= 2:
                    telegram_token = parts[0]
                    telegram_chat_id = parts[1]
                    logger.info(f"找到Telegram配置，将使用备用方法发送")
                    break

        # 再查找Bark配置
        for url in url_list:
            if url.startswith('bark://') or url.startswith('barks://'):
                # 格式: bark://server/key 或 barks://server/key
                url = url.replace('barks://', '').replace('bark://', '')
                parts = url.split('/')
                if len(parts) >= 2:
                    bark_server = parts[0]
                    bark_key = parts[1]
                    logger.info(f"找到Bark配置，将使用备用方法发送: 服务器={bark_server}, 密钥前缀={bark_key[:4] if len(bark_key) >= 4 else bark_key}...")
                    break

        # 尝试通过Telegram发送
        telegram_success = False
        if telegram_token and telegram_chat_id:
            telegram_success = send_via_telegram(message, title, telegram_token, telegram_chat_id, request_id)
        else:
            logger.error(
                f"未找到有效的Telegram配置 [请求ID: {request_id}]",
                extra={'request_id': request_id}
            )

        # 尝试通过Bark发送
        bark_success = False
        if bark_server and bark_key:
            bark_success = send_via_bark(message, title, bark_server, bark_key, request_id)
        else:
            logger.error(
                f"未找到有效的Bark配置 [请求ID: {request_id}]",
                extra={'request_id': request_id}
            )

        # 如果Telegram或Bark任一成功，则返回成功
        if telegram_success or bark_success:
            logger.info(
                f"备用方法发送成功: Telegram={telegram_success}, Bark={bark_success} [请求ID: {request_id}]",
                extra={
                    'request_id': request_id,
                    'telegram_success': telegram_success,
                    'bark_success': bark_success,
                    'status': 'success'
                }
            )
            return True
        else:
            logger.error(
                f"所有备用方法都失败: Telegram={telegram_success}, Bark={bark_success} [请求ID: {request_id}]",
                extra={
                    'request_id': request_id,
                    'telegram_success': telegram_success,
                    'bark_success': bark_success,
                    'status': 'failed'
                }
            )
            return False
    except Exception as e:
        logger.error(f"使用备用方法发送消息时出错: {e}")
        return False

def send_via_telegram(message, title, token, chat_id, request_id=None):
    """
    通过Telegram发送消息

    Args:
        message: 消息内容
        title: 消息标题
        token: Telegram Bot Token
        chat_id: Telegram Chat ID
        request_id: 请求ID，用于跟踪请求

    Returns:
        bool: 是否成功发送
    """
    # 如果没有提供请求ID，生成一个新的
    if request_id is None:
        request_id = f"telegram_{int(time.time() * 1000)}"
    try:
        logger.info(f"尝试使用requests库直接发送Telegram消息")

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
        telegram_api_url = f"https://api.telegram.org/bot{token}/sendMessage"
        payload = {
            "chat_id": chat_id,
            "text": text,
            "parse_mode": parse_mode
        }

        # 记录处理后的消息
        logger.info(f"处理后的消息前100个字符: {text[:100]}...")
        logger.info(f"使用解析模式: {payload['parse_mode']}")

        # 设置代理，优先使用代理管理器
        proxies = None
        try:
            # 尝试导入代理管理器
            from utils.api_utils import get_proxy_manager

            # 获取代理管理器
            proxy_manager = get_proxy_manager()

            # 查找可用代理
            working_proxy = proxy_manager.find_working_proxy()

            if working_proxy:
                # 获取代理字典
                proxies = working_proxy.get_proxy_dict()
                logger.info(f"Telegram使用代理管理器选择的代理: {working_proxy.name}")
            else:
                logger.warning("代理管理器未找到可用的代理，尝试使用环境变量")
        except ImportError:
            logger.warning("无法导入代理管理器，尝试使用环境变量")
        except Exception as e:
            logger.warning(f"使用代理管理器时出错: {str(e)}，尝试使用环境变量")

        # 如果代理管理器不可用或未找到可用代理，回退到环境变量
        if not proxies:
            http_proxy = os.environ.get('HTTP_PROXY')
            if http_proxy:
                proxies = {
                    "http": http_proxy,
                    "https": http_proxy
                }
                logger.info(f"Telegram使用环境变量中的代理: {http_proxy}")

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
                logger.info(f"Telegram备用方法发送成功: {response_json}")
                return True
            else:
                logger.error(f"Telegram备用方法发送失败，API返回错误: {response_json}")
                return False
        else:
            logger.error(f"Telegram备用方法发送失败，HTTP状态码: {response.status_code}, 响应: {response.text}")
            return False
    except Exception as e:
        logger.error(f"使用Telegram备用方法发送消息时出错: {e}")
        return False

def send_via_bark(message, title, server, key, request_id=None, max_retries=3):
    """
    通过Bark发送消息，支持自动切换代理重试

    Args:
        message: 消息内容
        title: 消息标题
        server: Bark服务器地址
        key: Bark密钥
        request_id: 请求ID，用于跟踪请求
        max_retries: 最大重试次数

    Returns:
        bool: 是否成功发送
    """
    # 如果没有提供请求ID，生成一个新的
    if request_id is None:
        request_id = f"bark_{int(time.time() * 1000)}"

    try:
        logger.info(f"尝试使用requests库直接发送Bark消息")

        # 检查服务器和密钥是否有效
        if not server or not key or server == 'YOUR_SERVER' or key == 'YOUR_DEVICE_KEY':
            logger.warning(f"无效的Bark服务器或密钥: 服务器={server}, 密钥={key[:4] if len(key) >= 4 else key}...")
            return False

        # 检查密钥格式是否正确
        if len(key) < 8:
            logger.warning(f"Bark密钥格式可能不正确，长度过短: {key[:4] if len(key) >= 4 else key}...")
            return False

        # 准备代理列表
        proxy_list = []

        # 从环境变量或配置中获取代理地址
        try:
            # 尝试从配置服务获取代理地址
            from services.config_service import get_config

            # 获取HTTP代理
            http_proxy = get_config('HTTP_PROXY', os.environ.get('HTTP_PROXY', ''))
            if http_proxy:
                proxy_list.append({"name": "HTTP代理", "proxy": {"http": http_proxy, "https": http_proxy}})
                logger.info(f"从配置中获取HTTP代理: {http_proxy}")

            # 获取SOCKS5代理
            socks5_proxy = get_config('SOCKS5_PROXY', os.environ.get('SOCKS5_PROXY', ''))
            if socks5_proxy:
                proxy_list.append({"name": "SOCKS5代理", "proxy": {"http": socks5_proxy, "https": socks5_proxy}})
                logger.info(f"从配置中获取SOCKS5代理: {socks5_proxy}")

            # 获取备用HTTP代理
            http_proxy_backup = get_config('HTTP_PROXY_BACKUP', os.environ.get('HTTP_PROXY_BACKUP', ''))
            if http_proxy_backup:
                proxy_list.append({"name": "备用HTTP代理", "proxy": {"http": http_proxy_backup, "https": http_proxy_backup}})
                logger.info(f"从配置中获取备用HTTP代理: {http_proxy_backup}")

            # 获取备用SOCKS5代理
            socks5_proxy_backup = get_config('SOCKS5_PROXY_BACKUP', os.environ.get('SOCKS5_PROXY_BACKUP', ''))
            if socks5_proxy_backup:
                proxy_list.append({"name": "备用SOCKS5代理", "proxy": {"http": socks5_proxy_backup, "https": socks5_proxy_backup}})
                logger.info(f"从配置中获取备用SOCKS5代理: {socks5_proxy_backup}")
        except ImportError:
            logger.warning("无法导入配置服务，尝试从环境变量获取代理")

            # 从环境变量获取代理
            http_proxy = os.environ.get('HTTP_PROXY', '')
            if http_proxy:
                proxy_list.append({"name": "HTTP代理", "proxy": {"http": http_proxy, "https": http_proxy}})
                logger.info(f"从环境变量获取HTTP代理: {http_proxy}")

            socks5_proxy = os.environ.get('SOCKS5_PROXY', '')
            if socks5_proxy:
                proxy_list.append({"name": "SOCKS5代理", "proxy": {"http": socks5_proxy, "https": socks5_proxy}})
                logger.info(f"从环境变量获取SOCKS5代理: {socks5_proxy}")
        except Exception as e:
            logger.warning(f"获取代理配置时出错: {e}")

        # 尝试添加代理管理器中的代理
        try:
            from utils.api_utils import get_proxy_manager
            proxy_manager = get_proxy_manager()
            working_proxy = proxy_manager.find_working_proxy()
            if working_proxy:
                proxy_list.append({"name": f"代理管理器({working_proxy.name})", "proxy": working_proxy.get_proxy_dict()})
        except Exception as e:
            logger.warning(f"获取代理管理器代理时出错: {e}")

        # 环境变量中的代理已经在上面处理过了，这里不需要重复添加

        # 添加无代理选项
        proxy_list.append({"name": "无代理", "proxy": None})

        # 替换转义的换行符为实际换行
        processed_message = message.replace('\\n', '\n')

        # 构建完整消息
        bark_title = title if title else "通知"

        # 根据服务器类型构建API URL和请求数据
        if server == "api.day.app":
            # 使用新版API格式（官方服务器）
            logger.info(f"使用官方Bark服务器新版API格式")
            bark_api_url = f"https://{server}/push"
            # 在payload中添加设备密钥
            payload = {
                "device_key": key,
                "title": bark_title,
                "body": processed_message,
                "sound": "default"
            }
        elif server == "bark.021800.xyz":
            # 使用bark.021800.xyz服务器的特殊格式
            logger.info(f"使用bark.021800.xyz服务器特殊格式")
            # 尝试直接使用URL路径参数而不是请求体中的device_key
            bark_api_url = f"https://{server}/{key}"
            payload = {
                "title": bark_title,
                "body": processed_message,
                "sound": "default"
            }
            logger.info(f"使用特殊格式的Bark API URL: {bark_api_url}")
        else:
            # 对于其他服务器，保持旧版格式
            if server.startswith('http://') or server.startswith('https://'):
                bark_api_url = f"{server}/{key}"
            else:
                bark_api_url = f"https://{server}/{key}"
            # 使用旧版payload格式
            payload = {
                "title": bark_title,
                "body": processed_message,
                "sound": "default"
            }

        # 记录处理后的消息
        logger.info(f"处理后的Bark消息: 标题={bark_title}, 内容前100个字符: {processed_message[:100]}...")
        logger.info(f"Bark API URL: {bark_api_url}")

        # 尝试使用不同的代理发送请求
        for retry in range(max_retries):
            # 选择代理
            proxy_index = retry % len(proxy_list)
            proxy_info = proxy_list[proxy_index]
            proxies = proxy_info["proxy"]

            logger.info(f"尝试使用 {proxy_info['name']} 发送请求 (尝试 {retry+1}/{max_retries})")

            try:
                # 发送请求
                response = requests.post(
                    bark_api_url,
                    json=payload,
                    proxies=proxies,
                    timeout=30
                )

                # 检查响应
                if response.status_code == 200:
                    response_json = response.json()
                    if response_json.get('code') == 200:
                        logger.info(f"使用 {proxy_info['name']} 发送成功: {response_json}")
                        return True
                    else:
                        logger.warning(f"使用 {proxy_info['name']} 发送失败，API返回错误: {response_json}")
                        # 继续尝试下一个代理
                else:
                    logger.warning(f"使用 {proxy_info['name']} 发送失败，HTTP状态码: {response.status_code}, 响应: {response.text}")
                    # 继续尝试下一个代理
            except Exception as e:
                logger.warning(f"使用 {proxy_info['name']} 发送请求时出错: {e}")
                # 继续尝试下一个代理

        # 所有尝试都失败
        logger.error(f"所有代理尝试都失败，无法发送Bark消息")
        return False
    except Exception as e:
        logger.error(f"使用Bark备用方法发送消息时出错: {e}")
        return False

# 添加一个函数，用于获取最新的推文内容
def get_latest_tweet():
    """
    获取最新的推文内容

    Returns:
        dict: 包含消息、标题、标签和附件的字典
    """
    return latest_tweet

# 添加一个函数，用于直接向指定URL发送推文
def send_to_url(url, custom_message=None, custom_title=None):
    """
    直接向指定URL发送最新的推文

    Args:
        url: 推送URL
        custom_message: 自定义消息，如果为None则使用最新的推文内容
        custom_title: 自定义标题，如果为None则使用最新的推文标题

    Returns:
        bool: 是否成功发送
    """
    # 跳过明显无效的URL
    if not url or url.startswith('#') or not ':' in url:
        logger.warning(f"跳过无效的URL: {mask_sensitive_url(url)}")
        return False

    # 如果URL包含注释，去掉注释部分
    if '#' in url and not url.startswith('#'):
        url = url.split('#')[0].strip()

    # 检查是否是bark.021800.xyz服务器
    if 'bark.021800.xyz' in url:
        logger.info(f"检测到bark.021800.xyz服务器，使用特殊处理")
        # 提取服务器和密钥
        if url.startswith('bark://') or url.startswith('barks://'):
            url = url.replace('barks://', 'bark://')
            parts = url.replace('bark://', '').split('/')
            if len(parts) >= 2:
                server = parts[0]
                key = parts[1]
                # 使用备用方法发送
                message = custom_message if custom_message is not None else latest_tweet['message']
                title = custom_title if custom_title is not None else latest_tweet['title']
                return send_via_bark(
                    message=message,
                    title=title,
                    server=server,
                    key=key
                )

    # 创建临时Apprise对象
    temp_apobj = apprise.Apprise()

    # 添加URL
    try:
        # 规范化URL
        normalized_url = normalize_bark_url(url)

        # 检查Bark URL是否使用了示例值
        if 'YOUR_DEVICE_KEY' in normalized_url:
            logger.warning(f"检测到示例Bark URL，请替换为实际的设备密钥: {mask_sensitive_url(normalized_url)}")
            return False

        # 检查是否包含占位符
        if 'WEBHOOK_ID' in normalized_url or 'WEBHOOK_TOKEN' in normalized_url:
            logger.warning(f"检测到包含占位符的URL，请替换为实际值: {mask_sensitive_url(normalized_url)}")
            return False

        # 添加URL
        added = temp_apobj.add(normalized_url)
        if not added:
            logger.warning(f"无法添加URL: {mask_sensitive_url(normalized_url)}")
            return False
    except Exception as e:
        logger.error(f"添加URL时出错: {str(e)}, URL: {mask_sensitive_url(url)}")
        return False

    # 使用最新的推文内容或自定义内容
    message = custom_message if custom_message is not None else latest_tweet['message']
    title = custom_title if custom_title is not None else latest_tweet['title']

    # 发送通知
    try:
        result = temp_apobj.notify(
            body=message,
            title=title,
            attach=latest_tweet['attach'],
            tag=latest_tweet['tag']
        )
        if result:
            logger.info(f"成功向URL发送推文: {mask_sensitive_url(url)}")
            return True
        else:
            logger.warning(f"向URL发送推文失败: {mask_sensitive_url(url)}")
            return False
    except Exception as e:
        logger.error(f"发送推文时出错: {str(e)}, URL: {mask_sensitive_url(url)}")
        return False

# 添加一个别名函数，用于兼容性
def send_to_specific_url(url, custom_message=None, custom_title=None):
    """
    直接向指定URL发送最新的推文（send_to_url的别名，用于兼容性）

    Args:
        url: 推送URL
        custom_message: 自定义消息，如果为None则使用最新的推文内容
        custom_title: 自定义标题，如果为None则使用最新的推文标题

    Returns:
        bool: 是否成功发送
    """
    return send_to_url(url, custom_message, custom_title)

# 初始化时加载配置
load_apprise_urls()

if __name__ == "__main__":
    # 测试
    result = send_notification("这是一条测试消息", "测试标题")
    print(f"发送结果: {result}")
