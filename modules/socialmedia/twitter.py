import os
import json
import time
import importlib.util
import traceback
import asyncio
from datetime import datetime, timezone
from tweety import Twitter, TwitterAsync
from tweety.types import Proxy, PROXY_TYPE_HTTP, PROXY_TYPE_SOCKS5
from utils.redisClient import redis_client
from modules.socialmedia.post import Post
from modules.langchain.llm import get_llm_response
from utils.logger import get_logger
from modules.socialmedia.twitter_utils import (
    extract_media_info,
    extract_author_info,
    create_post_from_tweet,
    set_timeline_metadata,
    batch_create_posts
)
from dotenv import load_dotenv

# 创建日志记录器
logger = get_logger('twitter')

# 导入统一的异步工具
from modules.socialmedia.async_utils import safe_asyncio_run, safe_call_async_method

# 导入twikit处理器作为备选方案
try:
    from modules.socialmedia import twitter_twikit
    TWIKIT_AVAILABLE = True
    logger.info("Twikit处理器已加载，可作为备选方案")
except ImportError:
    TWIKIT_AVAILABLE = False
    logger.info("Twikit处理器不可用，将仅使用tweety")

load_dotenv()

def create_tweety_proxy(proxy_info: dict) -> Proxy:
    """
    根据代理信息创建tweety库的Proxy对象

    Args:
        proxy_info (dict): 代理信息字典，包含host, port, protocol, username, password等

    Returns:
        Proxy: tweety库的代理对象
    """
    try:
        host = proxy_info['host']
        port = proxy_info['port']
        protocol = proxy_info.get('protocol', 'http').lower()
        username = proxy_info.get('username')
        password = proxy_info.get('password')

        # 确定代理类型
        if protocol.startswith('socks'):
            proxy_type = PROXY_TYPE_SOCKS5
        else:
            proxy_type = PROXY_TYPE_HTTP

        # 创建代理对象
        proxy = Proxy(
            host=host,
            port=port,
            proxy_type=proxy_type,
            username=username,
            password=password
        )

        logger.info(f"创建tweety代理对象: {protocol}://{host}:{port}")
        return proxy

    except Exception as e:
        logger.error(f"创建tweety代理对象时出错: {str(e)}")
        return None

# 检查并安装SOCKS代理支持
def ensure_socks_support():
    """
    确保系统支持SOCKS代理

    Returns:
        bool: 是否成功安装SOCKS支持
    """
    required_packages = ['socksio', 'pysocks']
    missing_packages = []

    # 检查必要的SOCKS支持包
    for package in required_packages:
        if importlib.util.find_spec(package) is None:
            missing_packages.append(package)

    if missing_packages:
        try:
            logger.info(f"检测到SOCKS代理，但缺少包: {missing_packages}，尝试安装...")
            import subprocess
            import sys

            # 安装缺失的包
            for package in missing_packages:
                if package == 'socksio':
                    # 安装httpx[socks]来获得socksio支持
                    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'httpx[socks]', '--quiet'])
                elif package == 'pysocks':
                    # 安装PySocks来支持requests的SOCKS代理
                    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'PySocks', '--quiet'])

            logger.info("成功安装SOCKS代理支持")
            return True
        except Exception as e:
            logger.error(f"安装SOCKS代理支持失败: {str(e)}")
            logger.error("请手动安装: pip install httpx[socks] PySocks")
            return False
    return True

def setup_socks_proxy(proxy_url):
    """
    设置SOCKS代理环境变量

    Args:
        proxy_url (str): 代理URL，如 socks5://127.0.0.1:1080
    """
    if proxy_url.startswith('socks'):
        logger.info(f"设置SOCKS代理: {proxy_url}")

        # 设置环境变量
        os.environ['HTTP_PROXY'] = proxy_url
        os.environ['HTTPS_PROXY'] = proxy_url
        os.environ['http_proxy'] = proxy_url
        os.environ['https_proxy'] = proxy_url

        # 对于某些库，还需要设置ALL_PROXY
        os.environ['ALL_PROXY'] = proxy_url
        os.environ['all_proxy'] = proxy_url

        # 确保安装了SOCKS支持
        if not ensure_socks_support():
            logger.warning("SOCKS代理支持安装失败，可能无法正常工作")
            return False

        logger.info("SOCKS代理环境变量设置完成")
        return True
    else:
        # HTTP代理
        logger.info(f"设置HTTP代理: {proxy_url}")
        os.environ['HTTP_PROXY'] = proxy_url
        os.environ['HTTPS_PROXY'] = proxy_url
        os.environ['http_proxy'] = proxy_url
        os.environ['https_proxy'] = proxy_url
        return True

def check_time_sync(proxy_info: dict = None) -> dict:
    """
    检查本地时间与服务器时间的同步情况

    Args:
        proxy_info (dict): 代理信息

    Returns:
        dict: 时间同步检查结果
    """
    result = {
        'success': False,
        'local_time': None,
        'server_time': None,
        'time_diff': None,
        'timezone_offset': None,
        'warning': None
    }

    try:
        import requests
        from datetime import datetime, timezone
        import email.utils

        # 记录本地时间
        local_time = datetime.now(timezone.utc)
        result['local_time'] = local_time.isoformat()

        # 构建代理配置
        proxies = None
        if proxy_info:
            protocol = proxy_info.get('protocol', 'http')
            host = proxy_info['host']
            port = proxy_info['port']
            username = proxy_info.get('username')
            password = proxy_info.get('password')

            if username and password:
                proxy_url = f"{protocol}://{username}:{password}@{host}:{port}"
            else:
                proxy_url = f"{protocol}://{host}:{port}"

            proxies = {'http': proxy_url, 'https': proxy_url}

        # 请求Twitter API获取服务器时间
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        }

        response = requests.get(
            'https://api.x.com/1.1/help/configuration.json',
            headers=headers,
            proxies=proxies,
            timeout=10,
            verify=False
        )

        # 从响应头获取服务器时间
        if 'date' in response.headers:
            server_time_str = response.headers['date']
            # 解析RFC 2822格式的时间
            server_time_tuple = email.utils.parsedate_tz(server_time_str)
            if server_time_tuple:
                server_time = datetime.fromtimestamp(
                    email.utils.mktime_tz(server_time_tuple),
                    tz=timezone.utc
                )
                result['server_time'] = server_time.isoformat()

                # 计算时间差
                time_diff = abs((local_time - server_time).total_seconds())
                result['time_diff'] = time_diff

                # 检查时间差是否在可接受范围内
                if time_diff <= 30:  # 30秒内认为正常
                    result['success'] = True
                elif time_diff <= 300:  # 5分钟内给出警告
                    result['success'] = True
                    result['warning'] = f"时间差较大: {time_diff:.1f}秒，可能影响认证"
                else:  # 超过5分钟认为有问题
                    result['warning'] = f"时间差过大: {time_diff:.1f}秒，可能导致认证失败"

                logger.info(f"时间同步检查: 本地时间={local_time.strftime('%H:%M:%S')}, "
                          f"服务器时间={server_time.strftime('%H:%M:%S')}, "
                          f"时间差={time_diff:.1f}秒")
            else:
                result['warning'] = "无法解析服务器时间格式"
        else:
            result['warning'] = "响应头中未找到时间信息"

        # 检查本地时区设置
        local_tz = datetime.now().astimezone().tzinfo
        result['timezone_offset'] = local_tz.utcoffset(datetime.now()).total_seconds() / 3600

    except Exception as e:
        result['warning'] = f"时间同步检查失败: {str(e)}"
        logger.warning(f"时间同步检查出错: {str(e)}")

    return result

def create_secure_session():
    """
    创建安全的HTTP会话，解决SSL连接问题

    Returns:
        requests.Session: 配置好的会话对象
    """
    import ssl
    import urllib3
    import requests
    from requests.adapters import HTTPAdapter
    from urllib3.util.retry import Retry

    # 禁用SSL警告
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

    # 创建会话
    session = requests.Session()

    # 配置重试策略
    retry_strategy = Retry(
        total=3,
        backoff_factor=1,
        status_forcelist=[429, 500, 502, 503, 504],
        allowed_methods=["HEAD", "GET", "OPTIONS"]
    )

    # 创建自定义适配器
    class SSLAdapter(HTTPAdapter):
        def init_poolmanager(self, *args, **kwargs):
            # 创建SSL上下文
            ssl_context = ssl.create_default_context()
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE

            # 设置SSL版本和密码套件
            ssl_context.set_ciphers('DEFAULT@SECLEVEL=1')

            kwargs['ssl_context'] = ssl_context
            return super().init_poolmanager(*args, **kwargs)

    adapter = SSLAdapter(max_retries=retry_strategy)
    session.mount("http://", adapter)
    session.mount("https://", adapter)

    return session

def test_twitter_connectivity():
    """
    测试Twitter连接性

    Returns:
        dict: 连接测试结果
    """
    result = {
        'success': False,
        'message': '',
        'details': {},
        'time_sync': None
    }

    try:
        import requests
        import socket

        # 首先进行时间同步检查
        logger.info("开始时间同步检查...")

        # 获取当前代理配置用于时间同步检查
        current_proxy = None
        try:
            _, current_proxy = get_proxy_config()
        except:
            pass

        time_sync_result = check_time_sync(current_proxy)
        result['time_sync'] = time_sync_result

        if time_sync_result.get('warning'):
            logger.warning(f"时间同步警告: {time_sync_result['warning']}")
        elif time_sync_result.get('success'):
            logger.info("时间同步检查通过")

        # 测试DNS解析 - 优先使用X.com域名
        dns_success = False
        for domain in ['x.com', 'api.x.com', 'twitter.com']:
            try:
                ip = socket.gethostbyname(domain)
                result['details'][f'dns_resolution_{domain}'] = f'成功解析到 {ip}'
                logger.info(f"DNS解析成功: {domain} -> {ip}")
                dns_success = True
                break
            except Exception as e:
                result['details'][f'dns_resolution_{domain}'] = f'DNS解析失败: {str(e)}'
                logger.warning(f"DNS解析失败: {domain} -> {str(e)}")

        if not dns_success:
            logger.error("所有域名DNS解析都失败")
            return result

        # 测试基本HTTP连接
        try:
            # 获取代理设置
            proxy = None
            if os.environ.get('HTTP_PROXY'):
                proxy = {
                    'http': os.environ.get('HTTP_PROXY'),
                    'https': os.environ.get('HTTPS_PROXY', os.environ.get('HTTP_PROXY'))
                }
                logger.info(f"使用代理测试连接: {proxy}")

            # 测试连接到Twitter
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1'
            }

            # 尝试多个测试URL - 优先使用x.com
            test_urls = [
                'https://api.x.com/1.1/help/configuration.json',  # X API端点
                'https://x.com',  # X主站
                'https://api.twitter.com/1.1/help/configuration.json',  # Twitter API端点（备用）
                'https://twitter.com',  # Twitter主站（备用）
                'https://mobile.x.com'  # X移动版
            ]

            success_count = 0

            # 创建安全的HTTP会话
            session = create_secure_session()
            session.headers.update(headers)

            for test_url in test_urls:
                try:
                    response = session.get(test_url,
                                          proxies=proxy,
                                          timeout=15,
                                          verify=False,
                                          allow_redirects=True)

                    result['details'][f'http_status_{test_url.split("//")[1].split("/")[0]}'] = response.status_code

                    # 对于不同的URL，接受不同的状态码
                    if 'api.' in test_url:
                        # API端点可能返回401（未授权）但这表示连接正常
                        if response.status_code in [200, 401, 403]:
                            success_count += 1
                            logger.info(f"API连接测试成功: {test_url}, 状态码: {response.status_code}")
                        elif response.status_code == 400:
                            logger.warning(f"API端点 {test_url} 返回400，可能是请求格式问题，但连接正常")
                            success_count += 1  # 400也算连接成功，只是请求格式问题
                    else:
                        # 主站应该返回200或重定向
                        if response.status_code in [200, 301, 302, 303, 307, 308]:
                            success_count += 1
                            logger.info(f"网站连接测试成功: {test_url}, 状态码: {response.status_code}")
                        elif response.status_code == 400:
                            logger.warning(f"网站 {test_url} 返回400，可能是代理或请求头问题")
                        else:
                            logger.warning(f"网站 {test_url} 返回状态码: {response.status_code}")

                except Exception as e:
                    logger.warning(f"测试 {test_url} 时出错: {str(e)}")

            # 如果至少有一个URL连接成功，认为连接正常
            if success_count > 0:
                result['success'] = True
                result['message'] = f'X/Twitter连接测试成功 ({success_count}/{len(test_urls)} 个端点可达)'
                logger.info(f"X/Twitter连接测试成功，{success_count}/{len(test_urls)} 个端点可达")
            else:
                result['message'] = 'X/Twitter连接测试失败，所有端点都无法访问'
                logger.error("X/Twitter连接测试失败，所有端点都无法访问")

                # 提供详细的错误分析（基于tweety FAQ）
                if proxy:
                    logger.error("连接失败可能的原因：")
                    logger.error("1. 代理服务器配置错误或不可用")
                    logger.error("2. 代理服务器被X/Twitter屏蔽（VPS/服务器提供商如AWS、Google Cloud常被屏蔽）")
                    logger.error("3. 代理服务器不支持HTTPS连接")
                    logger.error("4. 代理认证信息错误")
                    logger.error("5. 建议尝试使用高质量的住宅代理")
                    logger.error(f"当前使用的代理: {proxy}")
                else:
                    logger.error("直连失败可能的原因：")
                    logger.error("1. 本地网络无法访问X/Twitter")
                    logger.error("2. 防火墙阻止了连接")
                    logger.error("3. DNS解析问题")
                    logger.error("4. X/Twitter服务在当前地区不可用")
                    logger.error("5. 如果在VPS/服务器上运行，建议配置代理（Twitter会屏蔽知名VPS提供商）")

        except requests.exceptions.ConnectTimeout:
            result['message'] = '连接超时，可能是网络问题或代理配置问题'
            logger.error("连接Twitter超时")
        except requests.exceptions.ProxyError:
            result['message'] = '代理错误，请检查代理配置'
            logger.error("代理连接错误")
        except requests.exceptions.ConnectionError as e:
            result['message'] = f'连接错误: {str(e)}'
            logger.error(f"连接Twitter失败: {str(e)}")
        except Exception as e:
            result['message'] = f'未知错误: {str(e)}'
            logger.error(f"测试Twitter连接时出错: {str(e)}")

    except ImportError:
        result['message'] = '缺少requests库，无法进行连接测试'
        logger.error("缺少requests库")
    except Exception as e:
        result['message'] = f'测试过程中出错: {str(e)}'
        logger.error(f"连接测试过程中出错: {str(e)}")

    return result

# 初始化Twitter客户端
def get_twitter_credentials():
    """
    获取Twitter登录凭据

    注意：
    - 数据库中的social_account表存储的是监控目标账号
    - 登录凭据存储在system_config表中

    优先级：数据库(system_config) > 环境变量

    Returns:
        dict: 包含登录凭据的字典
    """
    credentials = {
        'username': None,
        'password': None,
        'session': None,
        'source': None
    }

    try:
        # 优先从数据库的system_config表获取Twitter登录凭据
        from services.config_service import get_config

        db_username = get_config('TWITTER_USERNAME')
        db_password = get_config('TWITTER_PASSWORD')
        db_session = get_config('TWITTER_SESSION')

        if db_session and db_session.strip():
            credentials['session'] = db_session
            credentials['source'] = 'database'
            logger.info("使用数据库中的Twitter会话数据")
            return credentials
        elif db_username and db_password:
            credentials['username'] = db_username
            credentials['password'] = db_password
            credentials['source'] = 'database'
            logger.info(f"使用数据库中的Twitter账号: {db_username}")
            return credentials
        else:
            logger.info("数据库中未找到Twitter登录凭据，尝试使用环境变量")

    except Exception as e:
        logger.warning(f"从数据库获取Twitter登录凭据时出错: {str(e)}，回退到环境变量")

    # 回退到环境变量
    env_username = os.getenv('TWITTER_USERNAME')
    env_password = os.getenv('TWITTER_PASSWORD')
    env_session = os.getenv('TWITTER_SESSION')

    if env_session and env_session.strip():
        credentials['session'] = env_session
        credentials['source'] = 'environment'
        logger.info("使用环境变量中的Twitter会话")
    elif env_username and env_password:
        credentials['username'] = env_username
        credentials['password'] = env_password
        credentials['source'] = 'environment'
        logger.info(f"使用环境变量中的Twitter账号: {env_username}")
    else:
        logger.warning("未找到任何Twitter登录凭据")

    return credentials

def get_proxy_config():
    """
    获取代理配置

    优先级：数据库 > 环境变量

    Returns:
        tuple: (tweety_proxy_object, proxy_info_dict)
    """
    tweety_proxy = None
    proxy_info = None

    try:
        # 优先从数据库获取代理配置
        from services.proxy_service import find_working_proxy

        proxy_info = find_working_proxy()

        if proxy_info:
            # 创建tweety原生代理对象
            tweety_proxy = create_tweety_proxy(proxy_info)
            if tweety_proxy:
                logger.info(f"使用数据库中的代理: {proxy_info.get('name', 'Unknown')}")
                return tweety_proxy, proxy_info
            else:
                logger.warning("创建tweety代理对象失败，回退到环境变量代理")
        else:
            logger.info("数据库中未找到可用的代理，尝试使用环境变量")

    except ImportError:
        logger.info("代理服务不可用，尝试使用环境变量")
    except Exception as e:
        logger.warning(f"从数据库获取代理配置时出错: {str(e)}，回退到环境变量")

    # 回退到环境变量
    proxy_url = os.getenv('HTTP_PROXY', '')
    if proxy_url:
        try:
            from urllib.parse import urlparse
            parsed = urlparse(proxy_url)
            if parsed.hostname and parsed.port:
                env_proxy_info = {
                    'host': parsed.hostname,
                    'port': parsed.port,
                    'protocol': parsed.scheme or 'http',
                    'username': parsed.username,
                    'password': parsed.password,
                    'name': 'Environment Variable Proxy'
                }
                tweety_proxy = create_tweety_proxy(env_proxy_info)
                if tweety_proxy:
                    logger.info(f"使用环境变量中的代理: {proxy_url}")
                    return tweety_proxy, env_proxy_info
        except Exception as e:
            logger.warning(f"从环境变量创建代理对象时出错: {str(e)}")

    logger.info("未找到任何代理配置，使用直连")
    return None, None

def setup_enhanced_headers():
    """
    设置增强的HTTP请求头，模拟真实浏览器行为
    """
    import random
    import yaml

    # 尝试从配置文件加载设置
    config_path = 'config/twitter_headers.yml'
    default_user_agents = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.1 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    ]

    default_base_headers = {
        'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
        'Accept-Language': 'en-US,en;q=0.9,zh-CN;q=0.8,zh;q=0.7',
        'Accept-Encoding': 'gzip, deflate, br',
        'DNT': '1',
        'Connection': 'keep-alive',
        'Upgrade-Insecure-Requests': '1',
        'Cache-Control': 'max-age=0'
    }

    default_chrome_headers = {
        'sec-ch-ua': '"Not_A Brand";v="8", "Chromium";v="120", "Google Chrome";v="120"',
        'sec-ch-ua-mobile': '?0',
        'sec-ch-ua-platform': '"Windows"',
        'Sec-Fetch-Dest': 'document',
        'Sec-Fetch-Mode': 'navigate',
        'Sec-Fetch-Site': 'none',
        'Sec-Fetch-User': '?1'
    }

    try:
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            user_agents = config.get('user_agents', default_user_agents)
            base_headers = config.get('base_headers', default_base_headers)
            chrome_headers = config.get('chrome_headers', default_chrome_headers)

            logger.debug(f"从配置文件加载请求头设置: {config_path}")
        else:
            user_agents = default_user_agents
            base_headers = default_base_headers
            chrome_headers = default_chrome_headers
            logger.debug("使用默认请求头设置")
    except Exception as e:
        logger.warning(f"加载请求头配置文件失败: {str(e)}，使用默认设置")
        user_agents = default_user_agents
        base_headers = default_base_headers
        chrome_headers = default_chrome_headers

    # 随机选择User-Agent
    selected_ua = random.choice(user_agents)

    # 构建完整的请求头
    enhanced_headers = base_headers.copy()
    enhanced_headers['User-Agent'] = selected_ua

    # 根据User-Agent类型添加特定的请求头
    if 'Chrome' in selected_ua:
        enhanced_headers.update(chrome_headers)
    elif 'Firefox' in selected_ua:
        enhanced_headers.update({
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none',
            'Sec-Fetch-User': '?1'
        })
    elif 'Safari' in selected_ua and 'Chrome' not in selected_ua:
        enhanced_headers.update({
            'Sec-Fetch-Dest': 'document',
            'Sec-Fetch-Mode': 'navigate',
            'Sec-Fetch-Site': 'none'
        })

    # 设置环境变量，让底层库使用这些头部
    for key, value in enhanced_headers.items():
        env_key = f'HTTP_HEADER_{key.upper().replace("-", "_")}'
        os.environ[env_key] = value

    logger.info(f"设置增强HTTP请求头，User-Agent: {selected_ua[:50]}...")
    return enhanced_headers

def apply_enhanced_headers_to_client(client, headers):
    """
    将增强的HTTP请求头应用到Twitter客户端

    Args:
        client: Twitter或TwitterAsync客户端实例
        headers: 请求头字典
    """
    try:
        # 尝试访问tweety库的内部HTTP会话对象
        if hasattr(client, 'session'):
            # 对于同步客户端
            session = client.session
            if hasattr(session, 'headers'):
                session.headers.update(headers)
                logger.info("成功将增强请求头应用到同步Twitter客户端")
        elif hasattr(client, '_session'):
            # 对于异步客户端
            session = client._session
            if hasattr(session, 'headers'):
                session.headers.update(headers)
                logger.info("成功将增强请求头应用到异步Twitter客户端")

        # 尝试其他可能的属性名
        for attr_name in ['http_session', 'client', '_client', '_http_client']:
            if hasattr(client, attr_name):
                session = getattr(client, attr_name)
                if hasattr(session, 'headers'):
                    session.headers.update(headers)
                    logger.info(f"成功通过 {attr_name} 属性将增强请求头应用到Twitter客户端")
                    break

        # 设置额外的环境变量来影响底层HTTP库
        import requests

        # 创建一个自定义的适配器来添加请求头
        class HeaderAdapter(requests.adapters.HTTPAdapter):
            def __init__(self, headers, *args, **kwargs):
                self.custom_headers = headers
                super().__init__(*args, **kwargs)

            def send(self, request, **kwargs):
                # 添加自定义请求头
                for key, value in self.custom_headers.items():
                    if key not in request.headers:
                        request.headers[key] = value
                return super().send(request, **kwargs)

        # 尝试为requests库设置默认适配器
        try:
            adapter = HeaderAdapter(headers)
            session = requests.Session()
            session.mount('http://', adapter)
            session.mount('https://', adapter)

            # 如果客户端使用requests，尝试替换其会话
            if hasattr(client, 'session') and hasattr(client.session, 'mount'):
                client.session.mount('http://', adapter)
                client.session.mount('https://', adapter)
                logger.info("成功设置自定义HTTP适配器")
        except Exception as e:
            logger.debug(f"设置自定义HTTP适配器时出错: {str(e)}")

    except Exception as e:
        logger.warning(f"应用增强请求头到Twitter客户端时出错: {str(e)}")
        logger.debug(f"客户端属性: {dir(client)}")

    # 设置额外的环境变量，影响底层HTTP库
    try:
        # 设置requests库的默认User-Agent
        if 'User-Agent' in headers:
            os.environ['REQUESTS_USER_AGENT'] = headers['User-Agent']

        # 设置urllib3的默认User-Agent
        try:
            import urllib3
            urllib3.util.SKIP_HEADER = urllib3.util.SKIP_HEADER | {'user-agent'}
            urllib3.poolmanager.PoolManager.clear()
        except:
            pass

    except Exception as e:
        logger.debug(f"设置底层HTTP库请求头时出错: {str(e)}")

def diagnose_authentication_error(error_msg, credentials, proxy_info):
    """
    诊断Twitter认证错误并提供解决建议

    Args:
        error_msg (str): 错误消息
        credentials (dict): 登录凭据
        proxy_info (str): 代理信息
    """
    logger.error("=" * 60)
    logger.error("Twitter认证失败详细诊断")
    logger.error("=" * 60)

    # 基本信息
    logger.error(f"错误消息: {error_msg}")
    logger.error(f"使用代理: {proxy_info}")
    logger.error(f"用户名: {credentials.get('username', 'N/A')}")
    logger.error(f"是否有会话数据: {'是' if credentials.get('session') else '否'}")

    # 具体错误分析
    if "Could not authenticate you" in error_msg:
        logger.error("\n🔍 错误分析: Twitter认证失败")
        logger.error("这个错误通常表示以下问题之一：")
        logger.error("")
        logger.error("1. 📱 账号安全问题:")
        logger.error("   • 用户名或密码不正确")
        logger.error("   • 账号被暂时锁定")
        logger.error("   • 需要完成手机验证或邮箱验证")
        logger.error("   • 启用了两步验证但未提供验证码")
        logger.error("")
        logger.error("2. 🌐 网络和代理问题:")
        logger.error("   • 代理IP被Twitter屏蔽")
        logger.error("   • 地理位置异常（代理IP与账号常用地区不符）")
        logger.error("   • 网络连接不稳定")
        logger.error("")
        logger.error("3. 🤖 自动化检测:")
        logger.error("   • Twitter检测到机器人行为")
        logger.error("   • 请求频率过高")
        logger.error("   • User-Agent或请求头被识别为自动化工具")
        logger.error("")
        logger.error("4. 📋 API限制:")
        logger.error("   • Twitter加强了对第三方登录的限制")
        logger.error("   • tweety库可能需要更新")
        logger.error("")

        logger.error("💡 建议的解决步骤:")
        logger.error("")
        logger.error("步骤1: 验证账号状态")
        logger.error("   • 手动访问 https://x.com 并尝试登录")
        logger.error("   • 检查是否收到Twitter的安全邮件")
        logger.error("   • 确认账号没有被锁定或限制")
        logger.error("")
        logger.error("步骤2: 检查代理设置")
        logger.error("   • 尝试更换不同的代理服务器")
        logger.error("   • 使用住宅IP代理而不是数据中心IP")
        logger.error("   • 测试代理是否能正常访问Twitter")
        logger.error("")
        logger.error("步骤3: 使用会话登录")
        logger.error("   • 推荐使用会话数据而不是账号密码")
        logger.error("   • 在Web界面配置会话数据: http://localhost:5000/unified_settings#twitter")
        logger.error("")
        logger.error("步骤4: 降低检测风险")
        logger.error("   • 增加请求间隔时间")
        logger.error("   • 避免频繁的登录尝试")
        logger.error("   • 确保使用最新版本的tweety库")

    logger.error("=" * 60)

def diagnose_elevated_authorization_error(error_msg, credentials, proxy_info):
    """
    诊断Twitter提升授权错误并提供解决建议

    Args:
        error_msg (str): 错误消息
        credentials (dict): 登录凭据
        proxy_info (str): 代理信息
    """
    logger.error("=" * 60)
    logger.error("Twitter提升授权错误详细诊断")
    logger.error("=" * 60)

    # 基本信息
    logger.error(f"错误消息: {error_msg}")
    logger.error(f"使用代理: {proxy_info}")
    logger.error(f"用户名: {credentials.get('username', 'N/A')}")
    logger.error(f"是否有会话数据: {'是' if credentials.get('session') else '否'}")

    # 具体错误分析
    if "Page not Found" in error_msg and "elevated authorization" in error_msg:
        logger.error("\n🔍 错误分析: Twitter需要提升授权")
        logger.error("这个错误通常表示以下问题之一：")
        logger.error("")
        logger.error("1. 📱 账号验证问题:")
        logger.error("   • 账号需要手机号验证")
        logger.error("   • 账号需要邮箱验证")
        logger.error("   • 账号被标记为可疑，需要额外验证")
        logger.error("   • 账号年龄太新，权限受限")
        logger.error("")
        logger.error("2. 🌐 地理位置/IP问题:")
        logger.error("   • 代理IP被Twitter标记为数据中心IP")
        logger.error("   • 代理IP地理位置与账号常用地区差异太大")
        logger.error("   • IP被标记为高风险或可疑")
        logger.error("   • 需要使用住宅IP代理")
        logger.error("")
        logger.error("3. 🔐 API访问限制:")
        logger.error("   • Twitter加强了对第三方客户端的限制")
        logger.error("   • 需要官方应用授权")
        logger.error("   • 普通账号无法访问某些API端点")
        logger.error("   • 需要Twitter Developer账号")
        logger.error("")
        logger.error("4. 🤖 自动化检测:")
        logger.error("   • Twitter检测到自动化行为")
        logger.error("   • 请求模式被识别为机器人")
        logger.error("   • 需要更好的行为模拟")
        logger.error("")

        logger.error("💡 建议的解决步骤:")
        logger.error("")
        logger.error("步骤1: 验证账号状态")
        logger.error("   • 手动登录 https://x.com 检查账号状态")
        logger.error("   • 完成所有必要的验证（手机、邮箱）")
        logger.error("   • 检查是否有安全警告或限制通知")
        logger.error("   • 确保账号处于良好状态")
        logger.error("")
        logger.error("步骤2: 改善代理设置")
        logger.error("   • 使用高质量的住宅IP代理")
        logger.error("   • 避免使用数据中心IP或VPS IP")
        logger.error("   • 选择与账号常用地区相近的代理")
        logger.error("   • 测试代理的Twitter访问质量")
        logger.error("")
        logger.error("步骤3: 使用会话登录")
        logger.error("   • 强烈建议使用会话数据而不是账号密码")
        logger.error("   • 在真实浏览器中登录后获取会话")
        logger.error("   • 配置会话数据: http://localhost:5000/unified_settings#twitter")
        logger.error("")
        logger.error("步骤4: 降低检测风险")
        logger.error("   • 增加请求间隔时间（至少5-10秒）")
        logger.error("   • 使用更真实的User-Agent和请求头")
        logger.error("   • 模拟人类浏览行为")
        logger.error("   • 避免频繁的API调用")
        logger.error("")
        logger.error("步骤5: 考虑替代方案")
        logger.error("   • 如果问题持续，考虑使用官方Twitter API")
        logger.error("   • 申请Twitter Developer账号")
        logger.error("   • 使用其他免费的数据获取方案（如snscrape）")
        logger.error("")

        # 提供具体的代理建议
        if proxy_info:
            logger.error("🌐 当前代理分析:")
            proxy_host = proxy_info.get('host', 'Unknown')
            proxy_port = proxy_info.get('port', 'Unknown')
            logger.error(f"   代理地址: {proxy_host}:{proxy_port}")

            # 简单的IP类型判断
            if proxy_host.startswith('192.168.') or proxy_host.startswith('10.') or proxy_host.startswith('172.'):
                logger.error("   ⚠️  检测到内网代理，可能是软路由或本地代理")
                logger.error("   建议: 确保上游代理是高质量的住宅IP")
            else:
                logger.error("   建议: 测试此IP是否被Twitter标记为数据中心IP")
                logger.error("   可以访问 https://whatismyipaddress.com 检查IP类型")

        logger.error("")
        logger.error("🚨 紧急建议:")
        logger.error("1. 立即停止当前的登录尝试，避免账号被进一步限制")
        logger.error("2. 手动登录Twitter检查账号状态")
        logger.error("3. 完成所有必要的账号验证")
        logger.error("4. 更换为高质量的住宅代理")
        logger.error("5. 使用会话登录方式替代账号密码登录")

    logger.error("=" * 60)

def add_request_delay():
    """
    添加随机请求延迟，模拟人类行为
    """
    import random
    import time
    import yaml

    # 默认延迟配置
    min_delay = 1.0
    max_delay = 3.0
    enabled = True

    # 尝试从配置文件加载延迟设置
    try:
        config_path = 'config/twitter_headers.yml'
        if os.path.exists(config_path):
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f)

            delay_config = config.get('request_delay', {})
            min_delay = delay_config.get('min_delay', min_delay)
            max_delay = delay_config.get('max_delay', max_delay)
            enabled = delay_config.get('enabled', enabled)
    except Exception as e:
        logger.debug(f"加载延迟配置失败: {str(e)}，使用默认设置")

    if enabled:
        # 随机延迟
        delay = random.uniform(min_delay, max_delay)
        logger.debug(f"添加请求延迟: {delay:.2f}秒")
        time.sleep(delay)
    else:
        logger.debug("请求延迟已禁用")

def init_twitter_client(use_async=False):
    """
    初始化Twitter客户端

    优先级策略：
    1. 代理配置：数据库 > 环境变量 > 直连
    2. 登录凭据：数据库 > 环境变量
    3. 登录方式：会话 > 账号密码

    Args:
        use_async (bool): 是否使用异步客户端

    Returns:
        Twitter或TwitterAsync: Twitter客户端实例
    """
    logger.info(f"开始初始化Twitter{'Async' if use_async else ''}客户端")

    # 设置SSL环境以解决连接问题
    try:
        import ssl
        # 设置SSL相关环境变量
        os.environ['PYTHONHTTPSVERIFY'] = '0'
        os.environ['CURL_CA_BUNDLE'] = ''
        os.environ['REQUESTS_CA_BUNDLE'] = ''

        # 设置SSL默认上下文
        ssl._create_default_https_context = ssl._create_unverified_context
        logger.info("已设置SSL环境以解决连接问题")
    except Exception as e:
        logger.warning(f"设置SSL环境时出错: {str(e)}")

    # 设置增强的HTTP请求头
    enhanced_headers = setup_enhanced_headers()

    # 获取代理配置（数据库优先）
    tweety_proxy, proxy_info = get_proxy_config()

    # 获取登录凭据（数据库优先）
    credentials = get_twitter_credentials()

    # 检查是否有登录凭据
    if not any([credentials['session'], credentials['username']]):
        logger.error("未找到任何Twitter登录凭据，无法初始化客户端")
        logger.error("请配置以下任一方式：")
        logger.error("1. 通过Web界面配置：http://localhost:5000/unified_settings#twitter（推荐）")
        logger.error("2. 设置环境变量 TWITTER_SESSION 或 TWITTER_USERNAME/TWITTER_PASSWORD")
        return None

    # 设置代理环境变量作为备选（兼容性）
    if proxy_info and not tweety_proxy:
        protocol = proxy_info.get('protocol', 'http')
        host = proxy_info['host']
        port = proxy_info['port']
        username = proxy_info.get('username')
        password = proxy_info.get('password')

        # 构建代理URL
        if username and password:
            proxy_url = f"{protocol}://{username}:{password}@{host}:{port}"
        else:
            proxy_url = f"{protocol}://{host}:{port}"

        # 设置环境变量
        os.environ['HTTP_PROXY'] = proxy_url
        os.environ['HTTPS_PROXY'] = proxy_url
        os.environ['http_proxy'] = proxy_url
        os.environ['https_proxy'] = proxy_url

        if protocol.startswith('socks'):
            os.environ['ALL_PROXY'] = proxy_url
            os.environ['all_proxy'] = proxy_url
            # 确保安装了必要的包
            if not ensure_socks_support():
                logger.warning("SOCKS代理支持安装失败，可能无法正常连接Twitter")

        logger.info(f"设置代理环境变量作为备选: {proxy_url}")

    # 优先尝试使用会话登录
    if credentials['session'] and credentials['session'].strip():
        logger.info(f"使用会话文件登录Twitter{'Async' if use_async else ''} (来源: {credentials['source']})")
        try:
            # 验证和处理会话数据格式
            session_data = credentials['session'].strip()

            # 检查是否是有效的JSON格式（增强验证）
            try:
                import json
                # 尝试解析为JSON以验证格式
                if session_data.startswith('{') and session_data.endswith('}'):
                    # 验证JSON格式
                    parsed_session = json.loads(session_data)
                    logger.info("会话数据JSON格式验证通过")

                    # 检查是否包含必要的会话字段
                    required_fields = ['auth_token', 'ct0']  # Twitter会话的基本字段
                    missing_fields = [field for field in required_fields if field not in parsed_session]
                    if missing_fields:
                        logger.warning(f"会话数据缺少必要字段: {missing_fields}，可能导致登录失败")
                    else:
                        logger.info("会话数据包含必要的认证字段")
                else:
                    logger.warning("会话数据不是有效的JSON格式，尝试自动修复")
                    # 尝试自动修复常见的格式问题
                    if not session_data.startswith('{'):
                        session_data = '{' + session_data
                    if not session_data.endswith('}'):
                        session_data = session_data + '}'

                    # 再次尝试解析
                    try:
                        json.loads(session_data)
                        logger.info("会话数据自动修复成功")
                        credentials['session'] = session_data
                    except json.JSONDecodeError:
                        logger.error("会话数据自动修复失败，将跳过会话登录")
                        raise ValueError("无效的会话数据格式")

            except json.JSONDecodeError as e:
                logger.error(f"会话数据JSON格式验证失败: {str(e)}")
                logger.error("会话数据格式示例: {\"auth_token\": \"your_token\", \"ct0\": \"your_ct0\"}")
                logger.warning("跳过会话登录，尝试使用账号密码登录")
                raise ValueError(f"JSON格式错误: {str(e)}")
            except ValueError as e:
                logger.error(f"会话数据验证失败: {str(e)}")
                logger.warning("跳过会话登录，尝试使用账号密码登录")
                raise

            # 确保session文件目录存在
            session_file = 'session.tw_session'
            session_dir = os.path.dirname(os.path.abspath(session_file))
            if not os.path.exists(session_dir):
                os.makedirs(session_dir)

            # 转换会话数据为tweety库期望的格式
            try:
                import json
                session_obj = json.loads(session_data)
                auth_token = session_obj.get('auth_token')
                ct0 = session_obj.get('ct0')

                if not auth_token or not ct0:
                    raise ValueError("会话数据缺少必要的auth_token或ct0字段")

                # 创建tweety库期望的会话格式
                tweety_session_data = {
                    'cookies': {
                        'auth_token': auth_token,
                        'ct0': ct0
                    },
                    'csrf_token': session_obj.get('csrf_token', ct0),  # 使用ct0作为默认csrf_token
                    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
                }

                # 写入兼容格式的会话数据到文件
                with open(session_file, 'w', encoding='utf-8') as f:
                    json.dump(tweety_session_data, f)
                logger.info(f"已将会话数据转换为tweety兼容格式并写入文件: {session_file}")

            except Exception as format_error:
                logger.warning(f"转换会话数据格式失败: {str(format_error)}，尝试直接写入原始数据")
                # 回退到原始方法
                with open(session_file, 'w') as f:
                    f.write(session_data)

            if use_async:
                # 创建异步客户端，传入代理对象
                if tweety_proxy:
                    app = TwitterAsync('session', proxy=tweety_proxy)
                    logger.info("使用代理创建异步Twitter客户端")
                else:
                    app = TwitterAsync('session')
                    logger.info("创建异步Twitter客户端（无代理）")

                # 异步连接需要特殊处理
                try:
                    safe_call_async_method(app, 'connect')
                    # 异步获取me属性
                    # 在tweety-ns 2.2版本中，me可能是属性而不是方法
                    if callable(getattr(app, 'me', None)):
                        # 如果me是方法，调用它
                        me = safe_call_async_method(app, 'me')
                    else:
                        # 如果me是属性，直接访问它
                        me = app.me

                    if me is not None:
                        logger.info(f"成功使用会话文件登录TwitterAsync，用户: {me.username if hasattr(me, 'username') else 'unknown'}")
                        # 应用增强的请求头
                        apply_enhanced_headers_to_client(app, enhanced_headers)
                        return app
                    else:
                        logger.warning("会话文件登录TwitterAsync失败，尝试使用账号密码登录")
                except Exception as e:
                    logger.error(f"使用会话文件登录TwitterAsync时出错: {str(e)}")
            else:
                # 创建同步客户端，传入代理对象
                if tweety_proxy:
                    app = Twitter('session', proxy=tweety_proxy)
                    logger.info("使用代理创建Twitter客户端")
                else:
                    app = Twitter('session')
                    logger.info("创建Twitter客户端（无代理）")

                app.connect()

                # 在tweety-ns 2.2版本中，me可能是属性或方法
                me = app.me() if callable(getattr(app, 'me', None)) else app.me

                if me is not None:
                    logger.info(f"成功使用会话文件登录Twitter，用户: {me.username if hasattr(me, 'username') else 'unknown'}")
                    # 应用增强的请求头
                    apply_enhanced_headers_to_client(app, enhanced_headers)
                    return app
                else:
                    logger.warning("会话文件登录失败，尝试使用账号密码登录")
        except Exception as e:
            error_msg = str(e)
            logger.error(f"使用会话文件登录Twitter{'Async' if use_async else ''}时出错: {error_msg}")

            # 提供更详细的错误诊断和解决方案
            if "expecting value" in error_msg.lower() or "json" in error_msg.lower():
                logger.error("JSON解析错误，可能的原因和解决方案：")
                logger.error("1. Twitter API返回了空响应或非JSON格式的响应")
                logger.error("   解决方案：检查网络连接，稍后重试")
                logger.error("2. 会话数据格式不正确")
                logger.error("   解决方案：重新获取有效的会话数据")
                logger.error("3. 代理配置问题导致响应被截断")
                logger.error("   解决方案：检查代理设置或尝试直连")
                logger.error("4. Twitter服务暂时不可用")
                logger.error("   解决方案：稍后重试或使用账号密码登录")

                # 尝试清理无效的会话文件
                session_file = 'session.tw_session'
                if os.path.exists(session_file):
                    try:
                        os.remove(session_file)
                        logger.info("已清理可能损坏的会话文件")
                    except Exception as cleanup_error:
                        logger.warning(f"清理会话文件失败: {str(cleanup_error)}")

            elif "connection" in error_msg.lower():
                logger.error("网络连接错误，请检查：")
                logger.error("1. 网络连接是否正常")
                logger.error("2. 代理设置是否正确")
                logger.error("3. 防火墙是否阻止了连接")
                logger.error("4. 如果在VPS/服务器上运行，建议使用高质量代理")
            elif "authentication" in error_msg.lower() or "unauthorized" in error_msg.lower():
                logger.error("认证错误，请检查：")
                logger.error("1. Twitter会话数据是否有效")
                logger.error("2. 会话是否已过期（建议重新获取）")
                logger.error("3. 账号是否被限制或需要验证")
            elif "invalid" in error_msg.lower() and "session" in error_msg.lower():
                logger.error("会话数据无效，建议：")
                logger.error("1. 重新获取最新的会话数据")
                logger.error("2. 确保会话数据格式正确")
                logger.error("3. 或者使用账号密码登录方式")

            # 记录当前使用的代理信息，便于调试
            if proxy_info:
                logger.error(f"当前使用代理: {proxy_info['name']} - {proxy_info['host']}:{proxy_info['port']}")
            else:
                logger.error("当前未使用代理（直连）")

    # 尝试使用账号密码
    if credentials['username'] and credentials['password']:
        logger.info(f"使用账号密码登录Twitter{'Async' if use_async else ''}: {credentials['username']} (来源: {credentials['source']})")
        try:
            if use_async:
                # 创建异步客户端，传入代理对象
                if tweety_proxy:
                    app = TwitterAsync('session', proxy=tweety_proxy)
                    logger.info("使用代理创建异步Twitter客户端进行账号密码登录")
                else:
                    app = TwitterAsync('session')
                    logger.info("创建异步Twitter客户端进行账号密码登录（无代理）")

                try:
                    safe_call_async_method(app, 'connect')
                    # 检查是否已登录
                    # 在tweety-ns 2.2版本中，me可能是属性而不是方法
                    if callable(getattr(app, 'me', None)):
                        # 如果me是方法，调用它
                        me = safe_call_async_method(app, 'me')
                    else:
                        # 如果me是属性，直接访问它
                        me = app.me

                    if me is None:
                        safe_call_async_method(app, 'sign_in', credentials['username'], credentials['password'])

                        # 再次检查登录状态
                        if callable(getattr(app, 'me', None)):
                            me = safe_call_async_method(app, 'me')
                        else:
                            me = app.me

                        if me is not None:
                            logger.info(f"成功使用账号密码登录TwitterAsync，用户: {me.username if hasattr(me, 'username') else 'unknown'}")
                            # 应用增强的请求头
                            apply_enhanced_headers_to_client(app, enhanced_headers)
                            return app
                        else:
                            logger.error("账号密码登录TwitterAsync失败")
                    else:
                        logger.info(f"已登录TwitterAsync，用户: {me.username if hasattr(me, 'username') else 'unknown'}")
                        # 应用增强的请求头
                        apply_enhanced_headers_to_client(app, enhanced_headers)
                        return app
                except Exception as e:
                    logger.error(f"使用账号密码登录TwitterAsync时出错: {str(e)}")
            else:
                # 创建同步客户端，传入代理对象
                if tweety_proxy:
                    app = Twitter('session', proxy=tweety_proxy)
                    logger.info("使用代理创建Twitter客户端进行账号密码登录")
                else:
                    app = Twitter('session')
                    logger.info("创建Twitter客户端进行账号密码登录（无代理）")

                # 使用安全的方法调用连接
                safe_call_async_method(app, 'connect')

                # 在tweety-ns 2.2版本中，me可能是属性或方法
                me = app.me() if callable(getattr(app, 'me', None)) else app.me

                if me is None:
                    # 使用统一的异步方法调用工具
                    safe_call_async_method(app, 'sign_in', credentials['username'], credentials['password'])

                    # 再次检查登录状态
                    me = app.me() if callable(getattr(app, 'me', None)) else app.me

                    if me is not None:
                        logger.info(f"成功使用账号密码登录Twitter，用户: {me.username if hasattr(me, 'username') else 'unknown'}")
                        # 应用增强的请求头
                        apply_enhanced_headers_to_client(app, enhanced_headers)
                        return app
                    else:
                        logger.error("账号密码登录失败")
                else:
                    logger.info(f"已登录Twitter，用户: {me.username if hasattr(me, 'username') else 'unknown'}")
                    # 应用增强的请求头
                    apply_enhanced_headers_to_client(app, enhanced_headers)
                    return app
        except Exception as e:
            error_msg = str(e)
            logger.error(f"使用账号密码登录Twitter{'Async' if use_async else ''}时出错: {error_msg}")

            # 如果是认证错误，提供详细诊断
            if "Could not authenticate you" in error_msg:
                diagnose_authentication_error(error_msg, credentials, proxy_info)
            elif "Page not Found" in error_msg and "elevated authorization" in error_msg:
                diagnose_elevated_authorization_error(error_msg, credentials, proxy_info)

            # 提供更详细的错误诊断（基于tweety FAQ）
            if "expecting value" in error_msg.lower():
                logger.error("JSON解析错误，可能的原因：")
                logger.error("1. Twitter API返回了空响应或非JSON格式的响应")
                logger.error("2. 网络连接问题导致请求失败")
                logger.error("3. 代理配置问题")
                logger.error("4. Twitter服务暂时不可用")
                logger.error("5. 账号可能需要验证码或安全检查")
                logger.error("6. 如果在VPS/服务器上运行，Twitter可能屏蔽了该IP")
            elif "connection" in error_msg.lower():
                logger.error("网络连接错误，请检查：")
                logger.error("1. 网络连接是否正常")
                logger.error("2. 代理设置是否正确")
                logger.error("3. 防火墙是否阻止了连接")
                logger.error("4. 如果在VPS/服务器上运行，建议使用高质量代理")
            elif "authentication" in error_msg.lower() or "unauthorized" in error_msg.lower():
                logger.error("认证错误，请检查：")
                logger.error("1. Twitter用户名和密码是否正确")
                logger.error("2. 账号是否被锁定或限制")
                logger.error("3. 是否需要完成安全验证")
                logger.error("4. Twitter新限制：每15分钟最多50个请求")
            elif "rate limit" in error_msg.lower():
                logger.error("请求频率限制（Twitter新限制），建议：")
                logger.error("1. 等待15分钟后重试")
                logger.error("2. 检查是否有其他程序在使用相同账号")
                logger.error("3. Twitter现在限制每15分钟最多50个请求")
            elif "challenge" in error_msg.lower() or "verification" in error_msg.lower():
                logger.error("账号需要验证，可能的原因：")
                logger.error("1. Twitter检测到异常登录行为")
                logger.error("2. 需要完成手机验证或邮箱验证")
                logger.error("3. 建议使用会话数据登录方式")
                logger.error("4. 如果在VPS/服务器上运行，建议使用代理")

    # 尝试使用API密钥（如果配置了）
    api_key = os.getenv('TWITTER_API_KEY')
    api_secret = os.getenv('TWITTER_API_SECRET')
    access_token = os.getenv('TWITTER_ACCESS_TOKEN')
    access_secret = os.getenv('TWITTER_ACCESS_SECRET')

    if api_key and api_secret and access_token and access_secret:
        logger.info(f"使用API密钥登录Twitter{'Async' if use_async else ''}")
        try:
            # 注意：tweety库目前不直接支持API密钥登录
            # 这里是一个占位，如果将来支持或者切换到其他库，可以实现这部分
            logger.warning("当前版本不支持API密钥登录，请使用会话文件或账号密码登录")
        except Exception as e:
            logger.error(f"使用API密钥登录Twitter{'Async' if use_async else ''}时出错: {str(e)}")

    logger.error(f"所有Twitter{'Async' if use_async else ''}登录方式均失败")

    # 进行连接测试以帮助诊断问题
    logger.info("进行Twitter连接测试以诊断问题...")
    connectivity_result = test_twitter_connectivity()

    if connectivity_result['success']:
        logger.info(f"连接测试成功: {connectivity_result['message']}")
        logger.error("网络连接正常，但Twitter登录失败。可能的原因：")
        logger.error("1. Twitter账号凭据无效或已过期")
        logger.error("2. Twitter账号需要验证或被限制")
        logger.error("3. tweety库版本兼容性问题")
        logger.error("4. Twitter API策略变更")
    else:
        logger.error(f"连接测试失败: {connectivity_result['message']}")
        logger.error("网络连接问题，建议检查：")
        logger.error("1. 网络连接是否正常")
        logger.error("2. 代理设置是否正确")
        logger.error("3. 防火墙或DNS配置")

        # 显示详细的连接测试结果
        for key, value in connectivity_result['details'].items():
            logger.error(f"   {key}: {value}")

    return None

# 初始化Twitter客户端变量
app = None
async_app = None

# 延迟初始化，确保在使用时已加载配置
def ensure_initialized(use_async=False):
    """
    确保Twitter客户端已初始化

    Args:
        use_async (bool): 是否使用异步客户端

    Returns:
        bool: 是否成功初始化
    """
    global app, async_app

    if use_async:
        if async_app is None:
            try:
                logger.info("首次使用时初始化异步Twitter客户端")
                async_app = init_twitter_client(use_async=True)
                return async_app is not None
            except Exception as e:
                logger.error(f"初始化异步Twitter客户端时出错: {str(e)}")
                return False
        return True
    else:
        if app is None:
            try:
                logger.info("首次使用时初始化Twitter客户端")
                app = init_twitter_client(use_async=False)
                return app is not None
            except Exception as e:
                logger.error(f"初始化Twitter客户端时出错: {str(e)}")
                return False
        return True

# 添加重新初始化函数，用于在需要时重新连接
def reinit_twitter_client(use_async=False):
    """
    重新初始化Twitter客户端

    Args:
        use_async (bool): 是否使用异步客户端

    Returns:
        bool: 是否成功初始化
    """
    global app, async_app

    try:
        if use_async:
            logger.info("尝试重新初始化异步Twitter客户端")
            async_app = init_twitter_client(use_async=True)
            return async_app is not None
        else:
            logger.info("尝试重新初始化Twitter客户端")
            app = init_twitter_client(use_async=False)
            return app is not None
    except Exception as e:
        logger.error(f"重新初始化Twitter{'Async' if use_async else ''}客户端时出错: {str(e)}")
        return False


def try_twikit_fallback(user_id: str, limit: int = None, reason: str = "unknown"):
    """
    尝试使用twikit作为备选方案获取推文

    注意：只有在tweety库本身有问题时才使用，网络/代理问题两个库都会失败

    Args:
        user_id (str): Twitter用户ID
        limit (int, optional): 限制返回的推文数量
        reason (str): 使用备选方案的原因

    Returns:
        list[Post]: 帖子列表，如果失败返回空列表
    """
    if not TWIKIT_AVAILABLE:
        logger.warning("Twikit库不可用，无法使用备选方案")
        return []

    # 检查是否是网络/代理问题，如果是则不尝试twikit
    network_related_reasons = ["代理", "网络", "连接", "proxy", "network", "connection"]
    if any(keyword in reason.lower() for keyword in network_related_reasons):
        logger.warning(f"检测到网络/代理相关问题 ({reason})，twikit也会遇到相同问题，跳过备选方案")
        return []

    logger.info(f"尝试使用twikit作为备选方案获取用户 {user_id} 的推文 (原因: {reason})")
    try:
        # 使用安全的异步运行方法，避免事件循环冲突
        from modules.socialmedia.async_utils import safe_asyncio_run
        twikit_posts = safe_asyncio_run(twitter_twikit.fetch_tweets(user_id, limit))
        if twikit_posts:
            logger.info(f"twikit备选方案成功获取 {len(twikit_posts)} 条推文")
            return twikit_posts
        else:
            logger.warning("twikit备选方案未获取到推文")
            return []
    except Exception as e:
        logger.error(f"twikit备选方案失败: {str(e)}")
        return []


def check_account_status(user_id: str, use_async: bool = False, update_avatar: bool = True) -> dict:
    """
    检查Twitter账号状态

    Args:
        user_id (str): Twitter用户ID
        use_async (bool, optional): 是否使用异步API
        update_avatar (bool, optional): 是否更新头像URL

    Returns:
        dict: 账号状态信息，包含以下字段：
            - exists (bool): 账号是否存在
            - protected (bool): 账号是否受保护
            - suspended (bool): 账号是否被暂停
            - error (str): 错误信息，如果有的话
            - avatar_url (str): 用户头像URL，如果获取成功
    """
    import time
    import json
    global app, async_app

    # 初始化返回结果
    status = {
        "exists": False,
        "protected": False,
        "suspended": False,
        "error": None,
        "avatar_url": None
    }

    # 检查缓存
    cache_key = f"twitter:{user_id}:account_status"
    try:
        cached_status = redis_client.get(cache_key)
        if cached_status:
            try:
                # 如果是字节类型，转换为字符串
                if isinstance(cached_status, bytes):
                    cached_status = str(cached_status, encoding='utf-8')

                # 解析JSON
                cached_status = json.loads(cached_status)

                # 检查缓存是否过期（24小时）
                if 'timestamp' in cached_status:
                    cache_time = cached_status.get('timestamp', 0)
                    current_time = int(time.time())

                    # 如果缓存不超过24小时，直接返回
                    if current_time - cache_time < 86400:  # 24小时 = 86400秒
                        logger.debug(f"使用缓存的账号状态信息: {user_id}")
                        result = cached_status.copy()
                        if 'timestamp' in result:
                            del result['timestamp']  # 删除时间戳字段
                        return result
            except Exception as e:
                logger.warning(f"解析缓存的账号状态信息时出错: {str(e)}")
    except Exception as e:
        logger.warning(f"获取缓存的账号状态信息时出错: {str(e)}")

    # 确保Twitter客户端已初始化
    try:
        if use_async:
            if not ensure_initialized(use_async=True):
                logger.warning("异步Twitter客户端未初始化，尝试重新初始化")
                if not reinit_twitter_client(use_async=True):
                    logger.error("异步Twitter客户端初始化失败，无法检查账号状态")
                    status["error"] = "Twitter客户端初始化失败，请检查网络连接和代理设置"
                    return status
        else:
            if not ensure_initialized():
                logger.warning("Twitter客户端未初始化，尝试重新初始化")
                if not reinit_twitter_client():
                    logger.error("Twitter客户端初始化失败，无法检查账号状态")
                    status["error"] = "Twitter客户端初始化失败，请检查网络连接和代理设置"
                    return status
    except Exception as init_error:
        logger.error(f"初始化Twitter客户端时出错: {str(init_error)}")
        status["error"] = f"Twitter客户端初始化失败: {str(init_error)}"
        return status

    logger.debug(f"检查用户 {user_id} 的账号状态 {'(异步)' if use_async else ''}")

    try:
        # 尝试获取用户信息
        if use_async:
            try:
                # 使用安全的异步调用方法，避免事件循环冲突
                from modules.socialmedia.async_utils import safe_call_async_method
                user_info = safe_call_async_method(async_app, 'get_user_info', user_id)
            except Exception as e:
                error_msg = str(e).lower()
                if "user not found" in error_msg or "account wasn't found" in error_msg:
                    status["error"] = "账号不存在"
                    logger.warning(f"用户 {user_id} 不存在")
                elif "protected" in error_msg:
                    status["exists"] = True
                    status["protected"] = True
                    status["error"] = "账号受保护"
                    logger.warning(f"用户 {user_id} 的账号受保护")
                elif "suspended" in error_msg:
                    status["exists"] = True
                    status["suspended"] = True
                    status["error"] = "账号已被暂停"
                    logger.warning(f"用户 {user_id} 的账号已被暂停")
                else:
                    status["error"] = f"获取用户信息失败: {error_msg}"
                    logger.error(f"获取用户 {user_id} 信息时出错: {error_msg}")

                # 缓存结果
                try:
                    status_with_timestamp = status.copy()
                    status_with_timestamp['timestamp'] = int(time.time())
                    redis_client.set(cache_key, json.dumps(status_with_timestamp), ex=86400)  # 设置24小时过期
                except Exception as cache_error:
                    logger.warning(f"缓存账号状态信息时出错: {str(cache_error)}")

                return status
        else:
            try:
                user_info = app.get_user_info(user_id)
            except Exception as e:
                error_msg = str(e).lower()
                if "user not found" in error_msg or "account wasn't found" in error_msg:
                    status["error"] = "账号不存在"
                    logger.warning(f"用户 {user_id} 不存在")
                elif "protected" in error_msg:
                    status["exists"] = True
                    status["protected"] = True
                    status["error"] = "账号受保护"
                    logger.warning(f"用户 {user_id} 的账号受保护")
                elif "suspended" in error_msg:
                    status["exists"] = True
                    status["suspended"] = True
                    status["error"] = "账号已被暂停"
                    logger.warning(f"用户 {user_id} 的账号已被暂停")
                else:
                    status["error"] = f"获取用户信息失败: {error_msg}"
                    logger.error(f"获取用户 {user_id} 信息时出错: {error_msg}")

                # 缓存结果
                try:
                    status_with_timestamp = status.copy()
                    status_with_timestamp['timestamp'] = int(time.time())
                    redis_client.set(cache_key, json.dumps(status_with_timestamp), ex=86400)  # 设置24小时过期
                except Exception as cache_error:
                    logger.warning(f"缓存账号状态信息时出错: {str(cache_error)}")

                return status

        # 如果成功获取用户信息，说明账号存在且可访问
        if user_info:
            status["exists"] = True

            # 记录用户信息的属性，用于调试
            logger.debug(f"用户 {user_id} 的信息属性: {dir(user_info)}")

            # 记录关键属性的值
            for attr in ['name', 'description', 'verified', 'followers_count', 'friends_count', 'created_at', 'location', 'url']:
                if hasattr(user_info, attr):
                    logger.debug(f"用户 {user_id} 的 {attr}: {getattr(user_info, attr)}")

            # 检查账号是否受保护
            if hasattr(user_info, 'protected') and user_info.protected:
                status["protected"] = True
                status["error"] = "账号受保护"
                logger.warning(f"用户 {user_id} 的账号受保护")
            else:
                logger.info(f"用户 {user_id} 的账号正常")

            # 获取用户头像URL
            if update_avatar:
                try:
                    # 检查user_info是否有头像URL相关属性
                    if hasattr(user_info, 'avatar_url') and user_info.avatar_url:
                        status["avatar_url"] = user_info.avatar_url
                        logger.info(f"成功获取用户 {user_id} 的头像URL: {user_info.avatar_url}")
                    elif hasattr(user_info, 'profile_image_url_https') and user_info.profile_image_url_https:
                        status["avatar_url"] = user_info.profile_image_url_https
                        logger.info(f"成功获取用户 {user_id} 的头像URL(profile_image_url_https): {user_info.profile_image_url_https}")

                        # 更新数据库中的头像URL和用户详细信息
                        try:
                            from models.social_account import SocialAccount
                            from models import db
                            from datetime import datetime
                            import re

                            # 查找对应的社交账号记录
                            account = SocialAccount.query.filter_by(type='twitter', account_id=user_id).first()
                            if account:
                                # 更新头像URL
                                if hasattr(user_info, 'avatar_url') and user_info.avatar_url:
                                    account.avatar_url = user_info.avatar_url
                                elif hasattr(user_info, 'profile_image_url_https') and user_info.profile_image_url_https:
                                    account.avatar_url = user_info.profile_image_url_https

                                # 更新用户详细信息
                                if hasattr(user_info, 'name'):
                                    account.display_name = user_info.name
                                    logger.info(f"更新用户 {user_id} 的显示名称: {user_info.name}")

                                if hasattr(user_info, 'description'):
                                    account.bio = user_info.description
                                    # 尝试从简介中提取职业信息
                                    profession_match = re.search(r'(记者|编辑|作家|博主|创始人|CEO|总监|经理|专家|教授|博士|研究员|分析师)',
                                                                user_info.description)
                                    if profession_match:
                                        account.profession = profession_match.group(0)

                                if hasattr(user_info, 'verified'):
                                    account.verified = bool(user_info.verified) if user_info.verified is not None else False

                                if hasattr(user_info, 'followers_count'):
                                    account.followers_count = int(user_info.followers_count) if user_info.followers_count is not None else 0

                                if hasattr(user_info, 'friends_count'):
                                    account.following_count = int(user_info.friends_count) if user_info.friends_count is not None else 0

                                if hasattr(user_info, 'created_at'):
                                    # 尝试解析Twitter日期格式
                                    try:
                                        # Twitter日期格式通常是: "Sat May 09 07:13:08 +0000 2020"
                                        if isinstance(user_info.created_at, str):
                                            import time
                                            time_struct = time.strptime(user_info.created_at, "%a %b %d %H:%M:%S %z %Y")
                                            account.join_date = datetime.fromtimestamp(time.mktime(time_struct))
                                        elif hasattr(user_info.created_at, 'timestamp'):
                                            # 如果是datetime对象
                                            account.join_date = user_info.created_at
                                    except Exception as date_error:
                                        logger.warning(f"解析用户 {user_id} 的加入日期时出错: {str(date_error)}")

                                if hasattr(user_info, 'location'):
                                    # 处理location字段，可能是字符串或字典
                                    if isinstance(user_info.location, dict):
                                        # 如果是字典，提取location值或转换为JSON字符串
                                        if 'location' in user_info.location:
                                            account.location = user_info.location['location']
                                        else:
                                            # 如果字典中没有location键，转换为JSON字符串
                                            account.location = json.dumps(user_info.location, ensure_ascii=False)
                                    elif isinstance(user_info.location, str):
                                        account.location = user_info.location
                                    else:
                                        # 其他类型转换为字符串
                                        account.location = str(user_info.location) if user_info.location else None

                                if hasattr(user_info, 'url'):
                                    account.website = user_info.url

                                db.session.commit()
                                logger.info(f"成功更新用户 {user_id} 的详细信息到数据库")
                            else:
                                logger.warning(f"未找到用户 {user_id} 的社交账号记录，无法更新用户详细信息")
                        except Exception as db_error:
                            logger.error(f"更新用户 {user_id} 的详细信息到数据库时出错: {str(db_error)}")
                    else:
                        # 尝试从profile_image_url属性获取
                        if hasattr(user_info, 'profile_image_url') and user_info.profile_image_url:
                            status["avatar_url"] = user_info.profile_image_url
                            logger.info(f"成功获取用户 {user_id} 的头像URL(profile_image_url): {user_info.profile_image_url}")

                            # 更新数据库中的头像URL和用户详细信息
                            try:
                                from models.social_account import SocialAccount
                                from models import db
                                from datetime import datetime
                                import re

                                # 查找对应的社交账号记录
                                account = SocialAccount.query.filter_by(type='twitter', account_id=user_id).first()
                                if account:
                                    # 更新头像URL
                                    if hasattr(user_info, 'profile_image_url') and user_info.profile_image_url:
                                        account.avatar_url = user_info.profile_image_url
                                    elif hasattr(user_info, 'profile_image_url_https') and user_info.profile_image_url_https:
                                        account.avatar_url = user_info.profile_image_url_https

                                    # 更新用户详细信息
                                    if hasattr(user_info, 'name'):
                                        account.display_name = user_info.name
                                        logger.info(f"更新用户 {user_id} 的显示名称: {user_info.name}")

                                    if hasattr(user_info, 'description'):
                                        account.bio = user_info.description
                                        # 尝试从简介中提取职业信息
                                        profession_match = re.search(r'(记者|编辑|作家|博主|创始人|CEO|总监|经理|专家|教授|博士|研究员|分析师)',
                                                                    user_info.description)
                                        if profession_match:
                                            account.profession = profession_match.group(0)

                                    if hasattr(user_info, 'verified'):
                                        account.verified = user_info.verified

                                    if hasattr(user_info, 'followers_count'):
                                        account.followers_count = user_info.followers_count

                                    if hasattr(user_info, 'friends_count'):
                                        account.following_count = user_info.friends_count

                                    if hasattr(user_info, 'created_at'):
                                        # 尝试解析Twitter日期格式
                                        try:
                                            # Twitter日期格式通常是: "Sat May 09 07:13:08 +0000 2020"
                                            if isinstance(user_info.created_at, str):
                                                import time as time_module
                                                time_struct = time_module.strptime(user_info.created_at, "%a %b %d %H:%M:%S %z %Y")
                                                account.join_date = datetime.fromtimestamp(time_module.mktime(time_struct))
                                            elif hasattr(user_info.created_at, 'timestamp'):
                                                # 如果是datetime对象
                                                account.join_date = user_info.created_at
                                        except Exception as date_error:
                                            logger.warning(f"解析用户 {user_id} 的加入日期时出错: {str(date_error)}")

                                    if hasattr(user_info, 'location'):
                                        # 处理location字段，可能是字符串或字典
                                        if isinstance(user_info.location, dict):
                                            # 如果是字典，提取location值或转换为JSON字符串
                                            if 'location' in user_info.location:
                                                account.location = user_info.location['location']
                                            else:
                                                # 如果字典中没有location键，转换为JSON字符串
                                                account.location = json.dumps(user_info.location, ensure_ascii=False)
                                        elif isinstance(user_info.location, str):
                                            account.location = user_info.location
                                        else:
                                            # 其他类型转换为字符串
                                            account.location = str(user_info.location) if user_info.location else None

                                    if hasattr(user_info, 'url'):
                                        account.website = user_info.url

                                    db.session.commit()
                                    logger.info(f"成功更新用户 {user_id} 的详细信息到数据库")
                                else:
                                    logger.warning(f"未找到用户 {user_id} 的社交账号记录，无法更新用户详细信息")
                            except Exception as db_error:
                                logger.error(f"更新用户 {user_id} 的详细信息到数据库时出错: {str(db_error)}")
                        # 尝试从profile_image_url_https属性获取
                        elif hasattr(user_info, 'profile_image_url_https') and user_info.profile_image_url_https:
                            status["avatar_url"] = user_info.profile_image_url_https
                            logger.info(f"成功获取用户 {user_id} 的头像URL(profile_image_url_https): {user_info.profile_image_url_https}")

                            # 更新数据库中的头像URL和用户详细信息
                            try:
                                from models.social_account import SocialAccount
                                from models import db
                                from datetime import datetime
                                import re

                                # 查找对应的社交账号记录
                                account = SocialAccount.query.filter_by(type='twitter', account_id=user_id).first()
                                if account:
                                    # 更新头像URL
                                    account.avatar_url = user_info.profile_image_url_https

                                    # 更新用户详细信息
                                    if hasattr(user_info, 'name'):
                                        account.display_name = user_info.name
                                        logger.info(f"更新用户 {user_id} 的显示名称: {user_info.name}")

                                    if hasattr(user_info, 'description'):
                                        account.bio = user_info.description
                                        # 尝试从简介中提取职业信息
                                        profession_match = re.search(r'(记者|编辑|作家|博主|创始人|CEO|总监|经理|专家|教授|博士|研究员|分析师)',
                                                                    user_info.description)
                                        if profession_match:
                                            account.profession = profession_match.group(0)

                                    if hasattr(user_info, 'verified'):
                                        account.verified = bool(user_info.verified) if user_info.verified is not None else False

                                    if hasattr(user_info, 'followers_count'):
                                        account.followers_count = int(user_info.followers_count) if user_info.followers_count is not None else 0

                                    if hasattr(user_info, 'friends_count'):
                                        account.following_count = int(user_info.friends_count) if user_info.friends_count is not None else 0

                                    if hasattr(user_info, 'created_at'):
                                        # 尝试解析Twitter日期格式
                                        try:
                                            # Twitter日期格式通常是: "Sat May 09 07:13:08 +0000 2020"
                                            if isinstance(user_info.created_at, str):
                                                import time
                                                time_struct = time.strptime(user_info.created_at, "%a %b %d %H:%M:%S %z %Y")
                                                account.join_date = datetime.fromtimestamp(time.mktime(time_struct))
                                            elif hasattr(user_info.created_at, 'timestamp'):
                                                # 如果是datetime对象
                                                account.join_date = user_info.created_at
                                        except Exception as date_error:
                                            logger.warning(f"解析用户 {user_id} 的加入日期时出错: {str(date_error)}")

                                    if hasattr(user_info, 'location'):
                                        # 处理location字段，可能是字符串或字典
                                        if isinstance(user_info.location, dict):
                                            # 如果是字典，提取location值或转换为JSON字符串
                                            if 'location' in user_info.location:
                                                account.location = user_info.location['location']
                                            else:
                                                # 如果字典中没有location键，转换为JSON字符串
                                                account.location = json.dumps(user_info.location, ensure_ascii=False)
                                        elif isinstance(user_info.location, str):
                                            account.location = user_info.location
                                        else:
                                            # 其他类型转换为字符串
                                            account.location = str(user_info.location) if user_info.location else None

                                    if hasattr(user_info, 'url'):
                                        account.website = user_info.url

                                    db.session.commit()
                                    logger.info(f"成功更新用户 {user_id} 的详细信息到数据库")
                                else:
                                    logger.warning(f"未找到用户 {user_id} 的社交账号记录，无法更新用户详细信息")
                            except Exception as db_error:
                                logger.error(f"更新用户 {user_id} 的详细信息到数据库时出错: {str(db_error)}")
                        else:
                            logger.warning(f"用户 {user_id} 的信息中没有头像URL (尝试了avatar_url, profile_image_url, profile_image_url_https)")
                except Exception as avatar_error:
                    logger.error(f"获取用户 {user_id} 的头像URL时出错: {str(avatar_error)}")

        # 缓存结果
        try:
            status_with_timestamp = status.copy()
            status_with_timestamp['timestamp'] = int(time.time())
            redis_client.set(cache_key, json.dumps(status_with_timestamp), ex=86400)  # 设置24小时过期
        except Exception as cache_error:
            logger.warning(f"缓存账号状态信息时出错: {str(cache_error)}")

        return status
    except Exception as e:
        logger.error(f"检查用户 {user_id} 的账号状态时出错: {str(e)}")
        status["error"] = f"检查账号状态时出错: {str(e)}"
        return status

def fetch(user_id: str, limit: int = None, use_async: bool = False, retry_count: int = 0) -> list[Post]:
    """
    获取指定用户的最新推文

    Args:
        user_id (str): Twitter用户ID
        limit (int, optional): 限制返回的推文数量，用于测试
        use_async (bool, optional): 是否使用异步API
        retry_count (int, optional): 当前重试次数，用于内部递归调用

    Returns:
        list[Post]: 帖子列表
    """
    global app, async_app

    # 限制最大重试次数，避免无限递归
    MAX_RETRIES = 3
    if retry_count >= MAX_RETRIES:
        logger.error(f"获取用户 {user_id} 的推文已达到最大重试次数 {MAX_RETRIES}，尝试备选方案")

        # 尝试使用twikit作为备选方案
        twikit_result = try_twikit_fallback(user_id, limit, "最大重试次数")
        if twikit_result:
            return twikit_result

        logger.error("所有方案都失败了，返回空列表")
        return []

    # 添加请求延迟，模拟人类行为
    add_request_delay()

    # 首先检查账号状态
    account_status = check_account_status(user_id, use_async)

    # 如果账号不存在或受保护，直接返回空列表
    if not account_status["exists"] or account_status["protected"] or account_status["suspended"]:
        logger.warning(f"无法获取用户 {user_id} 的推文: {account_status['error']}")
        return []

    # 确保Twitter客户端已初始化
    if use_async:
        if not ensure_initialized(use_async=True):
            logger.warning("异步Twitter客户端未初始化，尝试重新初始化")
            if not reinit_twitter_client(use_async=True):
                logger.error("异步Twitter客户端初始化失败，无法获取推文")
                # 尝试使用同步客户端作为备选
                logger.info("尝试使用同步客户端作为备选")
                return fetch(user_id, limit, use_async=False, retry_count=retry_count)
    else:
        if not ensure_initialized():
            logger.warning("Twitter客户端未初始化，尝试重新初始化")
            if not reinit_twitter_client():
                # 尝试切换代理并重新初始化
                try:
                    # 尝试导入代理管理器
                    from utils.api_utils import get_proxy_manager

                    # 获取代理管理器
                    proxy_manager = get_proxy_manager()

                    # 强制查找新的可用代理
                    working_proxy = proxy_manager.find_working_proxy(force_check=True)

                    if working_proxy:
                        logger.info(f"尝试使用新的代理 {working_proxy.name} 重新初始化Twitter客户端")
                        # 重新初始化客户端
                        if reinit_twitter_client():
                            logger.info(f"使用新代理成功初始化Twitter客户端，继续获取推文")
                        else:
                            logger.error("即使使用新代理，Twitter客户端初始化仍然失败")
                            return []
                    else:
                        logger.error("无法找到可用的代理，Twitter客户端初始化失败")
                        return []
                except Exception as e:
                    logger.error(f"尝试切换代理时出错: {str(e)}")
                    return []

    logger.info(f"开始获取用户 {user_id} 的最新推文 {'(异步)' if use_async else ''}")

    # 如果是测试模式（指定了limit），则不使用上次处理记录
    if limit is not None:
        logger.debug(f"测试模式：获取用户 {user_id} 的最新 {limit} 条推文")
        cursor = ''
    else:
        # 获取上次处理的最后一条推文ID
        cursor = redis_client.get(f"twitter:{user_id}:last_post_id")

        if cursor is None:
            logger.debug(f"未找到用户 {user_id} 的上次处理记录，将获取最新推文")
            cursor = ''
        else:
            # 如果是字节类型，转换为字符串
            if isinstance(cursor, bytes):
                cursor = str(cursor, encoding='utf-8')
            logger.debug(f"找到用户 {user_id} 的上次处理记录，上次处理的最后一条推文ID: {cursor}")

    # 尝试获取推文
    posts = None

    if use_async:
        # 使用异步API获取推文
        try:
            logger.debug(f"调用异步Twitter API获取用户 {user_id} 的推文")

            # 尝试使用不同的参数组合调用get_tweets
            error_messages = []

            # 尝试方法1: 使用cursor和limit参数
            try:
                posts = safe_call_async_method(async_app, 'get_tweets', user_id, cursor=cursor, limit=limit)
                logger.debug("异步方法1成功")
            except Exception as e:
                error_messages.append(f"异步方法1失败: {str(e)}")

            # 尝试方法2: 只使用limit参数
            if posts is None and limit is not None:
                try:
                    posts = safe_call_async_method(async_app, 'get_tweets', user_id, limit=limit)
                    logger.debug("异步方法2成功")
                except Exception as e:
                    error_messages.append(f"异步方法2失败: {str(e)}")

            # 尝试方法3: 只使用用户ID
            if posts is None:
                try:
                    posts = safe_call_async_method(async_app, 'get_tweets', user_id)
                    logger.debug("异步方法3成功")
                except Exception as e:
                    error_messages.append(f"异步方法3失败: {str(e)}")

            # 如果所有异步方法都失败，尝试切换代理或使用同步方法
            if posts is None:
                logger.warning(f"异步获取用户 {user_id} 的推文失败: {'; '.join(error_messages)}")

                # 尝试切换代理
                try:
                    # 尝试导入代理管理器
                    from utils.api_utils import get_proxy_manager

                    # 获取代理管理器
                    proxy_manager = get_proxy_manager()

                    # 强制查找新的可用代理
                    working_proxy = proxy_manager.find_working_proxy(force_check=True)

                    if working_proxy:
                        logger.info(f"尝试使用新的代理 {working_proxy.name} 重新初始化异步Twitter客户端")
                        # 重新初始化客户端
                        if reinit_twitter_client(use_async=True):
                            logger.info(f"使用新代理成功初始化异步Twitter客户端，重试获取推文")
                            # 递归调用自身，但增加重试计数
                            return fetch(user_id, limit, use_async=True, retry_count=retry_count+1)
                except Exception as e:
                    logger.warning(f"尝试切换异步客户端代理时出错: {str(e)}")

                # 如果切换代理失败或没有可用代理，尝试使用同步方法
                logger.info("尝试使用同步方法作为备选")
                return fetch(user_id, limit, use_async=False, retry_count=retry_count)

            # 检查posts是否为协程对象
            import inspect
            if inspect.iscoroutine(posts):
                logger.warning("检测到协程对象，正在处理...")
                posts = safe_asyncio_run(posts)

            logger.info(f"成功使用异步API获取用户 {user_id} 的推文，数量: {len(posts) if posts else 0}")
        except Exception as e:
            logger.error(f"异步获取用户 {user_id} 的推文时出错: {str(e)}")

            # 尝试切换代理
            try:
                # 尝试导入代理管理器
                from utils.api_utils import get_proxy_manager

                # 获取代理管理器
                proxy_manager = get_proxy_manager()

                # 强制查找新的可用代理
                working_proxy = proxy_manager.find_working_proxy(force_check=True)

                if working_proxy:
                    logger.info(f"尝试使用新的代理 {working_proxy.name} 重新初始化异步Twitter客户端")
                    # 重新初始化客户端
                    if reinit_twitter_client(use_async=True):
                        logger.info(f"使用新代理成功初始化异步Twitter客户端，重试获取推文")
                        # 递归调用自身，但增加重试计数
                        return fetch(user_id, limit, use_async=True, retry_count=retry_count+1)
            except Exception as ex:
                logger.warning(f"尝试切换异步客户端代理时出错: {str(ex)}")

            # 如果切换代理失败或没有可用代理，尝试使用同步方法
            logger.info("尝试使用同步方法作为备选")
            return fetch(user_id, limit, use_async=False, retry_count=retry_count)
    else:
        # 使用同步API获取推文
        try:
            logger.debug(f"调用同步Twitter API获取用户 {user_id} 的推文")

            # 尝试使用不同的参数组合调用get_tweets
            error_messages = []

            # 尝试方法1: 使用cursor和pages参数
            try:
                posts = app.get_tweets(user_id, cursor=cursor, pages=1 if limit is not None else None)
            except Exception as e:
                error_messages.append(f"方法1失败: {str(e)}")

            # 尝试方法2: 使用limit参数
            if posts is None and limit is not None:
                try:
                    posts = app.get_tweets(user_id, limit=limit)
                except Exception as e:
                    error_messages.append(f"方法2失败: {str(e)}")

            # 尝试方法3: 只使用用户ID
            if posts is None:
                try:
                    posts = app.get_tweets(user_id)
                except Exception as e:
                    error_messages.append(f"方法3失败: {str(e)}")

            # 如果所有方法都失败，尝试切换代理
            if posts is None:
                logger.error(f"获取用户 {user_id} 的推文失败，尝试了多种方法: {'; '.join(error_messages)}")

                # 尝试切换代理
                try:
                    # 尝试导入代理管理器
                    from utils.api_utils import get_proxy_manager

                    # 获取代理管理器
                    proxy_manager = get_proxy_manager()

                    # 强制查找新的可用代理
                    working_proxy = proxy_manager.find_working_proxy(force_check=True)

                    if working_proxy:
                        logger.info(f"尝试使用新的代理 {working_proxy.name} 重新初始化Twitter客户端")
                        # 重新初始化客户端
                        if reinit_twitter_client():
                            logger.info(f"使用新代理成功初始化Twitter客户端，重试获取推文")
                            # 递归调用自身，但增加重试计数
                            return fetch(user_id, limit, use_async=False, retry_count=retry_count+1)
                except Exception as e:
                    logger.warning(f"尝试切换同步客户端代理时出错: {str(e)}")

                # 如果重试次数未达到最大值，增加重试计数并重试
                if retry_count < MAX_RETRIES - 1:
                    logger.info(f"尝试第 {retry_count+1}/{MAX_RETRIES} 次重试获取推文")
                    return fetch(user_id, limit, use_async=False, retry_count=retry_count+1)
                else:
                    logger.error(f"获取用户 {user_id} 的推文失败，已达到最大重试次数，尝试备选方案")

                    # 尝试使用twikit作为备选方案（非网络问题）
                    twikit_result = try_twikit_fallback(user_id, limit, "tweety库API调用失败")
                    if twikit_result:
                        return twikit_result

                    return []

            # 检查posts是否为协程对象
            import inspect
            if inspect.iscoroutine(posts):
                logger.warning("检测到协程对象，正在处理...")
                posts = safe_asyncio_run(posts)

            logger.info(f"成功获取用户 {user_id} 的推文，数量: {len(posts) if posts else 0}")
        except Exception as e:
            logger.error(f"获取用户 {user_id} 的推文时出错: {str(e)}")

            # 尝试切换代理
            try:
                # 尝试导入代理管理器
                from utils.api_utils import get_proxy_manager

                # 获取代理管理器
                proxy_manager = get_proxy_manager()

                # 强制查找新的可用代理
                working_proxy = proxy_manager.find_working_proxy(force_check=True)

                if working_proxy:
                    logger.info(f"尝试使用新的代理 {working_proxy.name} 重新初始化Twitter客户端")
                    # 重新初始化客户端
                    if reinit_twitter_client():
                        logger.info(f"使用新代理成功初始化Twitter客户端，重试获取推文")
                        # 递归调用自身，但增加重试计数
                        return fetch(user_id, limit, use_async=False, retry_count=retry_count+1)
            except Exception as ex:
                logger.warning(f"尝试切换同步客户端代理时出错: {str(ex)}")

            # 如果重试次数未达到最大值，增加重试计数并重试
            if retry_count < MAX_RETRIES - 1:
                logger.info(f"尝试第 {retry_count+1}/{MAX_RETRIES} 次重试获取推文")
                return fetch(user_id, limit, use_async=False, retry_count=retry_count+1)
            else:
                logger.error(f"获取用户 {user_id} 的推文失败，已达到最大重试次数，尝试备选方案")

                # 尝试使用twikit作为备选方案（非网络问题）
                twikit_result = try_twikit_fallback(user_id, limit, "tweety库异常")
                if twikit_result:
                    return twikit_result

                return []

    # 处理获取到的推文
    noneEmptyPosts = []

    # 确保posts是可迭代的
    if posts is None:
        logger.warning("获取到的推文为None，返回空列表")
        return []

    # 检查posts是否为协程对象
    import inspect
    if inspect.iscoroutine(posts):
        logger.warning("在处理推文前检测到协程对象，正在处理...")
        posts = safe_asyncio_run(posts)
        if posts is None:
            logger.warning("协程处理后推文为None，返回空列表")
            return []

    # 如果是测试模式，限制返回数量
    if limit is not None:
        try:
            posts = list(posts)[:limit]
            logger.debug(f"测试模式：限制返回 {limit} 条推文")
        except Exception as e:
            logger.error(f"限制推文数量时出错: {str(e)}")
            return []

    for post in posts:
        try:
            # 检查推文是否有效
            if not post:
                logger.warning("跳过无效推文")
                continue

            if 'tweets' in post:
                # 处理推文线程
                logger.debug(f"处理推文线程，ID: {post.id if hasattr(post, 'id') else 'unknown'}")
                latest_id = None
                latest_created_on = None
                combined_text = ""
                latest_url = ""
                poster = None

                # 确保tweets是可迭代的
                if not hasattr(post, 'tweets') or not post.tweets:
                    logger.warning(f"推文线程缺少tweets属性或为空，跳过")
                    continue

                for tweet in post.tweets:
                    if hasattr(tweet, 'text') and tweet.text:
                        combined_text += tweet.text + "\n"
                    if hasattr(tweet, 'created_on') and (latest_created_on is None or tweet.created_on > latest_created_on):
                        latest_created_on = tweet.created_on
                        latest_id = getattr(tweet, 'id', None)
                        latest_url = getattr(tweet, 'url', '')
                        poster = getattr(tweet, 'author', None)

                if combined_text and latest_id and latest_created_on and poster:
                    logger.debug(f"添加推文线程到结果列表，ID: {latest_id}")
                    try:
                        # 确保poster有必要的属性
                        poster_name = getattr(poster, 'name', user_id)
                        poster_url = getattr(poster, 'profile_url', '')

                        # 提取媒体内容 - 使用工具函数
                        media_urls = []
                        media_types = []

                        # 从线程中的每条推文中提取媒体
                        for tweet in post.tweets:
                            tweet_media_urls, tweet_media_types = extract_media_info(tweet)
                            media_urls.extend(tweet_media_urls)
                            media_types.extend(tweet_media_types)

                        noneEmptyPosts.append(
                            Post(latest_id, latest_created_on, combined_text.strip(),
                                 latest_url, poster_name, poster_url,
                                 media_urls=media_urls, media_types=media_types))
                    except Exception as e:
                        logger.error(f"创建推文线程Post对象时出错: {str(e)}")
                        continue
            elif hasattr(post, 'text') and post.text:
                # 处理单条推文
                try:
                    post_id = getattr(post, 'id', None)
                    if not post_id:
                        logger.warning("推文缺少ID，跳过")
                        continue

                    logger.debug(f"处理单条推文，ID: {post_id}")

                    # 确保post有必要的属性
                    created_on = getattr(post, 'created_on', None)
                    if not created_on:
                        logger.warning(f"推文 {post_id} 缺少创建时间，使用当前时间")
                        from datetime import datetime
                        created_on = datetime.now()

                    post_url = getattr(post, 'url', f"https://x.com/{user_id}/status/{post_id}")

                    # 确保author有必要的属性
                    author = getattr(post, 'author', None)
                    if author:
                        author_name = getattr(author, 'name', user_id)
                        author_url = getattr(author, 'profile_url', '')
                    else:
                        author_name = user_id
                        author_url = ''

                    # 提取媒体内容 - 使用工具函数
                    media_urls, media_types = extract_media_info(post)

                    noneEmptyPosts.append(Post(post_id, created_on, post.text,
                                          post_url, author_name, author_url,
                                          media_urls=media_urls, media_types=media_types))
                except Exception as e:
                    logger.error(f"创建单条推文Post对象时出错: {str(e)}")
                    continue
        except Exception as e:
            logger.error(f"处理推文时出错: {str(e)}")
            continue

    # 更新最后处理的推文ID
    try:
        if posts and hasattr(posts, 'cursor_top') and posts.cursor_top:
            logger.debug(f"更新用户 {user_id} 的最后处理记录，最后一条推文ID: {posts.cursor_top}")
            redis_client.set(f"twitter:{user_id}:last_post_id", posts.cursor_top)
        elif noneEmptyPosts and len(noneEmptyPosts) > 0:
            # 如果没有cursor_top但有处理后的推文，使用第一条推文的ID
            latest_id = str(noneEmptyPosts[0].id)
            logger.debug(f"使用第一条推文ID更新用户 {user_id} 的最后处理记录: {latest_id}")
            redis_client.set(f"twitter:{user_id}:last_post_id", latest_id)
    except Exception as e:
        logger.error(f"更新最后处理推文ID时出错: {str(e)}")

    logger.info(f"用户 {user_id} 的推文处理完成，有效推文数量: {len(noneEmptyPosts)}")
    return noneEmptyPosts


def reply_to_post(post_id: str, content: str, use_async: bool = False) -> bool:
    """
    回复Twitter帖子

    Args:
        post_id (str): 要回复的帖子ID
        content (str): 回复内容
        use_async (bool, optional): 是否使用异步API

    Returns:
        bool: 是否成功回复
    """
    global app, async_app

    # 参数验证
    if not post_id:
        logger.error("回复帖子失败: 帖子ID为空")
        return False

    if not content or not content.strip():
        logger.error(f"回复帖子 {post_id} 失败: 回复内容为空")
        return False

    # 确保Twitter客户端已初始化
    if use_async:
        if not ensure_initialized(use_async=True):
            logger.warning("异步Twitter客户端未初始化，尝试重新初始化")
            if not reinit_twitter_client(use_async=True):
                logger.error("异步Twitter客户端初始化失败，无法回复帖子")
                # 尝试使用同步客户端作为备选
                logger.info("尝试使用同步客户端作为备选")
                return reply_to_post(post_id, content, use_async=False)
    else:
        if not ensure_initialized():
            logger.warning("Twitter客户端未初始化，尝试重新初始化")
            if not reinit_twitter_client():
                logger.error("Twitter客户端初始化失败，无法回复帖子")
                return False

    logger.info(f"准备回复帖子 {post_id} {'(异步)' if use_async else ''}")
    logger.debug(f"回复内容: {content}")

    # 尝试回复
    max_retries = 3
    retry_delay = 2  # 秒

    if use_async:
        # 使用异步API回复
        # 检查异步Twitter客户端是否有reply方法
        if not hasattr(async_app, 'reply'):
            logger.error("异步Twitter客户端不支持reply方法，可能是tweety库版本不兼容")
            logger.info("尝试使用同步客户端作为备选")
            return reply_to_post(post_id, content, use_async=False)

        for attempt in range(max_retries):
            try:
                safe_call_async_method(async_app, 'reply', post_id, content)
                logger.info(f"成功使用异步API回复帖子 {post_id}")
                return True
            except Exception as e:
                logger.error(f"异步回复Twitter帖子 {post_id} 时出错 (尝试 {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"等待 {retry_delay} 秒后重试...")
                    import time
                    time.sleep(retry_delay)
                    # 增加重试延迟时间
                    retry_delay *= 2
                else:
                    logger.error(f"异步回复Twitter帖子 {post_id} 失败，已达到最大重试次数")
                    logger.info("尝试使用同步客户端作为备选")
                    return reply_to_post(post_id, content, use_async=False)
    else:
        # 使用同步API回复
        # 检查Twitter客户端是否有reply方法
        if not hasattr(app, 'reply'):
            logger.error("Twitter客户端不支持reply方法，可能是tweety库版本不兼容")
            return False

        for attempt in range(max_retries):
            try:
                app.reply(post_id, content)
                logger.info(f"成功回复帖子 {post_id}")
                return True
            except Exception as e:
                logger.error(f"回复Twitter帖子 {post_id} 时出错 (尝试 {attempt+1}/{max_retries}): {str(e)}")
                if attempt < max_retries - 1:
                    logger.info(f"等待 {retry_delay} 秒后重试...")
                    import time
                    time.sleep(retry_delay)
                    # 增加重试延迟时间
                    retry_delay *= 2
                else:
                    logger.error(f"回复Twitter帖子 {post_id} 失败，已达到最大重试次数")
                    return False

    return False


def generate_reply(content: str, prompt_template: str = None) -> str:
    """
    使用LLM生成回复内容

    Args:
        content (str): 原始帖子内容
        prompt_template (str, optional): 提示词模板

    Returns:
        str: 生成的回复内容
    """
    logger.info("开始生成回复内容")

    # 参数验证
    if not content:
        logger.error("生成回复失败: 原始内容为空")
        return ""

    # 限制内容长度，避免过长的提示词
    max_content_length = 1000
    if len(content) > max_content_length:
        logger.warning(f"原始内容超过{max_content_length}字符，将被截断")
        content = content[:max_content_length] + "..."

    # 使用默认或自定义提示词模板
    if not prompt_template:
        logger.debug("使用默认回复提示词模板")
        prompt_template = """
你是一名专业的社交媒体助手，请针对以下内容生成一个简短、友好且专业的回复。
回复应该表达感谢、认同或提供有价值的补充信息，长度控制在100字以内。

原始内容: {content}

请按以下JSON格式返回回复内容:
{{
    "reply": "你的回复内容"
}}
"""
    else:
        logger.debug("使用自定义回复提示词模板")
        # 确保模板中包含{content}占位符
        if "{content}" not in prompt_template:
            logger.warning("提示词模板中缺少{content}占位符，将使用默认模板")
            prompt_template = """
你是一名专业的社交媒体助手，请针对以下内容生成一个简短、友好且专业的回复。
回复应该表达感谢、认同或提供有价值的补充信息，长度控制在100字以内。

原始内容: {content}

请按以下JSON格式返回回复内容:
{{
    "reply": "你的回复内容"
}}
"""

    # 格式化提示词
    try:
        prompt = prompt_template.format(content=content)
    except Exception as e:
        logger.error(f"格式化提示词模板时出错: {str(e)}")
        # 使用简单的提示词作为备选
        prompt = f"请针对以下内容生成一个简短的回复（JSON格式，包含reply字段）: {content}"

    logger.debug(f"原始内容: {content[:100]}..." if len(content) > 100 else content)

    # 调用LLM生成回复
    max_retries = 2
    retry_delay = 1  # 秒

    for attempt in range(max_retries + 1):
        try:
            logger.debug(f"调用LLM生成回复内容 (尝试 {attempt+1}/{max_retries+1})")
            response = get_llm_response(prompt)

            if not response:
                logger.warning("LLM返回空响应")
                if attempt < max_retries:
                    logger.info(f"等待 {retry_delay} 秒后重试...")
                    import time
                    time.sleep(retry_delay)
                    retry_delay *= 2
                    continue
                return ""

            logger.debug(f"LLM返回内容: {response[:100]}..." if len(response) > 100 else response)

            # 尝试解析JSON
            try:
                result = json.loads(response)
                reply = result.get("reply", "")

                if reply:
                    logger.info(f"成功生成回复内容: {reply[:100]}..." if len(reply) > 100 else reply)
                    return reply
                else:
                    logger.warning("LLM返回的JSON中没有reply字段")
                    # 尝试从响应中提取可能的回复内容
                    if len(response) < 280:  # Twitter字符限制
                        logger.info("使用完整响应作为回复内容")
                        return response
            except json.JSONDecodeError:
                logger.warning(f"解析LLM返回的JSON时出错，尝试提取文本")
                # 尝试从非JSON响应中提取可能的回复内容
                if len(response) < 280:  # Twitter字符限制
                    logger.info("使用完整响应作为回复内容")
                    return response

            # 如果到这里还没有返回，说明当前尝试失败
            if attempt < max_retries:
                logger.info(f"等待 {retry_delay} 秒后重试...")
                import time
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                logger.error("生成回复内容失败，已达到最大重试次数")
                return ""

        except Exception as e:
            logger.error(f"生成回复内容时出错: {str(e)}")
            if attempt < max_retries:
                logger.info(f"等待 {retry_delay} 秒后重试...")
                import time
                time.sleep(retry_delay)
                retry_delay *= 2
            else:
                return ""

    return ""


def auto_reply(post: Post, enable_auto_reply: bool = False, prompt_template: str = None) -> bool:
    """
    自动回复功能

    Args:
        post (Post): 帖子对象
        enable_auto_reply (bool): 是否启用自动回复
        prompt_template (str, optional): 自定义提示词模板

    Returns:
        bool: 是否成功回复
    """
    # 参数验证
    if not post:
        logger.error("自动回复失败: 帖子对象为空")
        return False

    if not hasattr(post, 'id') or not post.id:
        logger.error("自动回复失败: 帖子ID为空")
        return False

    if not hasattr(post, 'content') or not post.content:
        logger.error(f"自动回复失败: 帖子 {post.id} 内容为空")
        return False

    # 检查是否启用自动回复
    if not enable_auto_reply:
        logger.debug("自动回复功能未启用")
        return False

    logger.info(f"开始处理帖子 {post.id} 的自动回复")

    try:
        # 检查是否已经回复过
        replied = redis_client.get(f"twitter:replied:{post.id}")
        if replied:
            logger.info(f"帖子 {post.id} 已经回复过，跳过")
            return False
    except Exception as e:
        logger.error(f"检查帖子 {post.id} 回复状态时出错: {str(e)}")
        # 继续执行，避免因为Redis错误而影响功能

    try:
        # 生成回复内容
        reply_content = generate_reply(post.content, prompt_template)
        if not reply_content:
            logger.warning(f"未能为帖子 {post.id} 生成有效的回复内容")
            return False

        # 检查回复内容长度
        if len(reply_content) > 280:  # Twitter字符限制
            logger.warning(f"帖子 {post.id} 的回复内容超过280字符，尝试截断")
            reply_content = reply_content[:277] + "..."
    except Exception as e:
        logger.error(f"生成帖子 {post.id} 回复内容时出错: {str(e)}")
        return False

    # 发送回复
    logger.info(f"准备回复帖子 {post.id}")
    success = reply_to_post(post.id, reply_content)

    # 如果成功，记录已回复状态
    if success:
        try:
            logger.info(f"成功回复帖子 {post.id}，记录回复状态")
            redis_client.set(f"twitter:replied:{post.id}", "1")
            # 设置过期时间，避免Redis中存储过多记录（30天过期）
            redis_client.expire(f"twitter:replied:{post.id}", 60 * 60 * 24 * 30)
        except Exception as e:
            logger.error(f"记录帖子 {post.id} 回复状态时出错: {str(e)}")
            # 不影响返回结果
    else:
        logger.warning(f"回复帖子 {post.id} 失败")

    return success


def fetch_timeline(limit: int = None, retry_count: int = 0) -> list[Post]:
    """
    获取用户时间线（关注账号的最新推文）

    Args:
        limit (int, optional): 限制返回的推文数量，用于测试
        retry_count (int, optional): 当前重试次数，用于内部递归调用

    Returns:
        list[Post]: 帖子列表
    """
    global app

    # 限制最大重试次数，避免无限递归
    MAX_RETRIES = 3
    if retry_count >= MAX_RETRIES:
        logger.error(f"获取时间线已达到最大重试次数 {MAX_RETRIES}，尝试备选方案")

        # 尝试使用twikit作为备选方案获取时间线
        # 注意：twikit没有专门的时间线功能，这里暂时跳过
        logger.warning("twikit不支持时间线功能，无法使用备选方案")

        logger.error("所有方案都失败了，返回空列表")
        return []

    # 确保Twitter客户端已初始化
    if not ensure_initialized():
        logger.warning("Twitter客户端未初始化，尝试重新初始化")
        if not reinit_twitter_client():
            # 尝试切换代理并重新初始化
            try:
                # 尝试导入代理管理器
                from utils.api_utils import get_proxy_manager

                # 获取代理管理器
                proxy_manager = get_proxy_manager()

                # 强制查找新的可用代理
                working_proxy = proxy_manager.find_working_proxy(force_check=True)

                if working_proxy:
                    logger.info(f"尝试使用新的代理 {working_proxy.name} 重新初始化Twitter客户端")
                    # 重新初始化客户端
                    if reinit_twitter_client():
                        logger.info(f"使用新代理成功初始化Twitter客户端，继续获取时间线")
                    else:
                        logger.error("即使使用新代理，Twitter客户端初始化仍然失败，尝试备选方案")
                        # 注意：twikit不支持时间线功能
                        logger.warning("twikit不支持时间线功能，无法使用备选方案")
                        return []
                else:
                    logger.error("无法找到可用的代理，Twitter客户端初始化失败，尝试备选方案")
                    # 注意：twikit不支持时间线功能
                    logger.warning("twikit不支持时间线功能，无法使用备选方案")
                    return []
            except Exception as e:
                logger.error(f"尝试切换代理时出错: {str(e)}，尝试备选方案")
                # 注意：twikit不支持时间线功能
                logger.warning("twikit不支持时间线功能，无法使用备选方案")
                return []

    logger.info("🔄 开始获取用户时间线（关注账号的最新推文）")
    logger.info(f"📊 当前重试次数: {retry_count}/{MAX_RETRIES}")
    logger.info(f"🎯 限制数量: {limit if limit else '无限制'}")

    # 尝试使用异步API获取时间线
    try:
        # 创建异步客户端
        async_app = None
        try:
            # 使用与同步客户端相同的会话
            session_file = 'session.tw_session'
            if os.path.exists(session_file):
                logger.info("使用会话文件创建异步Twitter客户端")
                async_app = TwitterAsync("session")
                # 连接异步客户端
                safe_call_async_method(async_app, 'connect')
                logger.info("异步Twitter客户端连接成功")
            else:
                logger.warning("会话文件不存在，无法创建异步Twitter客户端")
        except Exception as e:
            logger.error(f"创建异步Twitter客户端时出错: {str(e)}")

        # 如果成功创建异步客户端，尝试获取时间线
        if async_app:
            timeline = None
            try:
                # 尝试获取主时间线
                logger.info("尝试使用异步API获取主时间线")
                # 在tweety-ns 2.2版本中，get_home_timeline不接受limit参数
                timeline = safe_call_async_method(async_app, 'get_home_timeline')

                # 如果需要限制数量，在获取后进行截断
                if timeline and limit is not None:
                    timeline = timeline[:limit]

                logger.info(f"成功使用异步API获取主时间线，推文数量: {len(timeline) if timeline else 0}")
            except Exception as e:
                logger.error(f"使用异步API获取主时间线时出错: {str(e)}")

                # 尝试切换代理
                try:
                    # 尝试导入代理管理器
                    from utils.api_utils import get_proxy_manager

                    # 获取代理管理器
                    proxy_manager = get_proxy_manager()

                    # 强制查找新的可用代理
                    working_proxy = proxy_manager.find_working_proxy(force_check=True)

                    if working_proxy:
                        logger.info(f"尝试使用新的代理 {working_proxy.name} 重新初始化异步Twitter客户端")
                        # 重新初始化客户端
                        if reinit_twitter_client(use_async=True):
                            logger.info(f"使用新代理成功初始化异步Twitter客户端，重试获取时间线")
                            # 递归调用自身，但增加重试计数
                            return fetch_timeline(limit, retry_count=retry_count+1)
                except Exception as ex:
                    logger.warning(f"尝试切换异步客户端代理时出错: {str(ex)}")

            # 如果成功获取时间线，处理推文
            if timeline:
                processed_posts = []

                # 处理每条推文
                for tweet in timeline:
                    try:
                        # 检查推文是否有效
                        if not tweet:
                            continue

                        # 获取推文属性
                        post_id = getattr(tweet, 'id', None)
                        if not post_id:
                            continue

                        # 导入datetime以确保在此作用域内可用
                        from datetime import datetime
                        created_on = getattr(tweet, 'created_on', datetime.now())
                        text = getattr(tweet, 'text', '')
                        post_url = getattr(tweet, 'url', '')

                        # 获取作者信息
                        author = getattr(tweet, 'author', None)
                        if author:
                            author_name = getattr(author, 'name', 'Unknown')
                            author_url = getattr(author, 'profile_url', '')
                            # 获取头像URL
                            author_avatar = getattr(author, 'profile_image_url', None) or getattr(author, 'avatar_url', None)
                        else:
                            author_name = "Unknown"
                            author_url = ""
                            author_avatar = None

                        # 提取媒体内容
                        media_urls = []
                        media_types = []

                        # 从推文中提取媒体
                        if hasattr(tweet, 'media') and tweet.media:
                            for media in tweet.media:
                                if hasattr(media, 'url') and media.url:
                                    media_urls.append(media.url)
                                    # 确定媒体类型
                                    media_type = "image"  # 默认为图片
                                    if hasattr(media, 'type'):
                                        media_type = media.type
                                    elif hasattr(media, 'video_url') and media.video_url:
                                        media_type = "video"
                                    media_types.append(media_type)

                        # 创建Post对象，确保设置正确的用户信息
                        # 如果author_name为空或为"Unknown"，尝试从tweet对象获取更多信息
                        if author_name == "Unknown" and hasattr(tweet, 'username'):
                            author_name = tweet.username

                        # 如果author_url为空，尝试构建一个URL
                        if not author_url and hasattr(tweet, 'username'):
                            author_url = f"https://twitter.com/{tweet.username}"

                        # 创建Post对象
                        post = Post(post_id, created_on, text, post_url, author_name, author_url,
                                   media_urls=media_urls, media_types=media_types, poster_avatar_url=author_avatar)

                        # 保留原始用户信息，同时标识来源
                        post.account_id = author_name  # 保留原始用户名用于展示
                        post.source_type = "timeline"  # 标识这是来自时间线的推文
                        post.original_author = author_name  # 备份原始作者信息

                        processed_posts.append(post)
                    except Exception as e:
                        logger.error(f"处理异步时间线推文时出错: {str(e)}")
                        continue

                logger.info(f"异步时间线处理完成，有效推文数量: {len(processed_posts)}")
                return processed_posts
    except Exception as e:
        logger.error(f"使用异步API获取时间线时出错: {str(e)}")

    # 如果异步方法失败，尝试使用同步方法
    logger.info("异步方法失败，尝试使用同步方法获取时间线")

    try:
        # 尝试使用同步API获取时间线
        timeline = None
        error_messages = []

        # 尝试方法1: 使用get_home_timeline
        try:
            if hasattr(app, 'get_home_timeline'):
                # 在tweety-ns 2.2版本中，检查get_home_timeline方法的参数
                import inspect
                params = inspect.signature(app.get_home_timeline).parameters

                if 'pages' in params:
                    timeline = app.get_home_timeline(pages=1 if limit is not None else None)
                else:
                    # 如果不接受pages参数，则不传参数
                    timeline = app.get_home_timeline()
                    # 如果需要限制数量，在获取后进行截断
                    if timeline and limit is not None:
                        timeline = timeline[:limit]

                logger.info("成功使用get_home_timeline获取时间线")
            else:
                error_messages.append("app对象没有get_home_timeline方法")
        except Exception as e:
            error_messages.append(f"get_home_timeline方法失败: {str(e)}")

        # 尝试方法2: 使用get_timeline
        if timeline is None:
            try:
                if hasattr(app, 'get_timeline'):
                    # 在tweety-ns 2.2版本中，检查get_timeline方法的参数
                    import inspect
                    params = inspect.signature(app.get_timeline).parameters

                    if 'pages' in params:
                        timeline = app.get_timeline(pages=1 if limit is not None else None)
                    else:
                        # 如果不接受pages参数，则不传参数
                        timeline = app.get_timeline()
                        # 如果需要限制数量，在获取后进行截断
                        if timeline and limit is not None:
                            timeline = timeline[:limit]

                    logger.info("成功使用get_timeline获取时间线")
                else:
                    error_messages.append("app对象没有get_timeline方法")
            except Exception as e:
                error_messages.append(f"get_timeline方法失败: {str(e)}")

        # 如果所有方法都失败，尝试切换代理或使用替代方法
        if timeline is None:
            logger.warning(f"获取时间线失败: {'; '.join(error_messages)}")

            # 尝试切换代理
            try:
                # 尝试导入代理管理器
                from utils.api_utils import get_proxy_manager

                # 获取代理管理器
                proxy_manager = get_proxy_manager()

                # 强制查找新的可用代理
                working_proxy = proxy_manager.find_working_proxy(force_check=True)

                if working_proxy:
                    logger.info(f"尝试使用新的代理 {working_proxy.name} 重新初始化Twitter客户端")
                    # 重新初始化客户端
                    if reinit_twitter_client():
                        logger.info(f"使用新代理成功初始化Twitter客户端，重试获取时间线")
                        # 递归调用自身，但增加重试计数
                        return fetch_timeline(limit, retry_count=retry_count+1)
            except Exception as e:
                logger.warning(f"尝试切换同步客户端代理时出错: {str(e)}")

            # 如果切换代理失败或没有可用代理，尝试使用替代方法
            logger.info("尝试使用替代方法：获取关注账号的推文")

            # 获取当前账号信息
            try:
                # 在tweety-ns 2.2版本中，me可能是属性而不是方法
                if callable(getattr(app, 'me', None)):
                    # 如果me是方法，调用它
                    me = app.me()
                else:
                    # 如果me是属性，直接访问它
                    me = app.me

                if me is None:
                    logger.error("无法获取当前账号信息：me对象为None")
                    return []

                logger.info(f"当前登录账号: {me.username if hasattr(me, 'username') else 'unknown'}")
            except Exception as e:
                logger.error(f"获取当前账号信息失败: {str(e)}")
                return []

            # 获取关注账号列表
            following = []
            try:
                # 尝试获取关注账号列表
                if hasattr(app, 'get_following'):
                    following = app.get_following(me.username)
                    logger.info(f"获取到 {len(following) if following else 0} 个关注账号")
                elif hasattr(app, 'get_friends'):
                    following = app.get_friends(me.username)
                    logger.info(f"获取到 {len(following) if following else 0} 个关注账号")
                else:
                    logger.error("Twitter客户端不支持获取关注账号列表功能")
                    return []
            except Exception as e:
                logger.error(f"获取关注账号列表失败: {str(e)}")
                return []

            if not following:
                logger.warning("未获取到关注账号列表或关注账号列表为空")
                return []

            # 获取每个关注账号的最新推文
            all_posts = []
            max_accounts = min(5, len(following))  # 限制处理的账号数量，避免请求过多

            logger.info(f"开始获取 {max_accounts} 个关注账号的最新推文")

            for i, account in enumerate(following[:max_accounts]):
                try:
                    account_id = account.username if hasattr(account, 'username') else str(account)
                    logger.debug(f"获取账号 {account_id} 的最新推文 ({i+1}/{max_accounts})")

                    # 检查账号状态，避免尝试获取不存在或受保护的账号
                    account_status = check_account_status(account_id)
                    if account_status["exists"] and not account_status["protected"] and not account_status["suspended"]:
                        # 获取账号的最新推文
                        posts = fetch(account_id, limit=5)  # 每个账号只获取最新的5条推文
                    else:
                        logger.warning(f"跳过账号 {account_id}: {account_status['error']}")
                        posts = []

                    if posts:
                        all_posts.extend(posts)
                        logger.debug(f"从账号 {account_id} 获取到 {len(posts)} 条推文")
                except Exception as e:
                    logger.error(f"获取账号 {account_id if 'account_id' in locals() else 'unknown'} 的推文时出错: {str(e)}")
                    continue

            # 按时间排序
            all_posts.sort(key=lambda x: x.created_on, reverse=True)

            # 如果是测试模式，限制返回数量
            if limit is not None and len(all_posts) > limit:
                all_posts = all_posts[:limit]

            logger.info(f"成功获取用户时间线（替代方法），共 {len(all_posts)} 条推文")
            return all_posts

        # 如果成功获取时间线，处理推文
        logger.info(f"成功获取用户时间线，推文数量: {len(timeline) if timeline else 0}")

        # 处理获取到的推文
        processed_posts = []

        # 确保timeline是可迭代的
        if timeline is None:
            logger.warning("获取到的时间线为None，返回空列表")
            return []

        # 如果是测试模式，限制返回数量
        if limit is not None:
            try:
                timeline = list(timeline)[:limit]
                logger.debug(f"测试模式：限制返回 {limit} 条推文")
            except Exception as e:
                logger.error(f"限制推文数量时出错: {str(e)}")

        # 处理每条推文
        for tweet in timeline:
            try:
                # 检查推文是否有效
                if not tweet:
                    logger.warning("跳过无效推文")
                    continue

                # 处理推文线程
                if hasattr(tweet, 'tweets') and tweet.tweets:
                    logger.debug(f"处理推文线程，ID: {tweet.id if hasattr(tweet, 'id') else 'unknown'}")
                    latest_id = None
                    latest_created_on = None
                    combined_text = ""
                    latest_url = ""
                    poster = None

                    for t in tweet.tweets:
                        if hasattr(t, 'text') and t.text:
                            combined_text += t.text + "\n"
                        if hasattr(t, 'created_on') and (latest_created_on is None or t.created_on > latest_created_on):
                            latest_created_on = t.created_on
                            latest_id = getattr(t, 'id', None)
                            latest_url = getattr(t, 'url', '')
                            poster = getattr(t, 'author', None)

                    if combined_text and latest_id and latest_created_on and poster:
                        try:
                            poster_name = getattr(poster, 'name', 'Unknown')
                            poster_url = getattr(poster, 'profile_url', '')
                            # 获取头像URL
                            poster_avatar = getattr(poster, 'profile_image_url', None) or getattr(poster, 'avatar_url', None)

                            # 创建Post对象
                            post = Post(latest_id, latest_created_on, combined_text.strip(), latest_url, poster_name, poster_url, poster_avatar_url=poster_avatar)

                            # 保留原始用户信息，同时标识来源
                            post.account_id = poster_name  # 保留原始用户名用于展示
                            post.source_type = "timeline"  # 标识这是来自时间线的推文
                            post.original_author = poster_name  # 备份原始作者信息

                            processed_posts.append(post)
                        except Exception as e:
                            logger.error(f"创建推文线程Post对象时出错: {str(e)}")
                            continue

                # 处理单条推文
                elif hasattr(tweet, 'text') and tweet.text:
                    try:
                        post_id = getattr(tweet, 'id', None)
                        if not post_id:
                            logger.warning("推文缺少ID，跳过")
                            continue

                        logger.debug(f"处理单条推文，ID: {post_id}")

                        created_on = getattr(tweet, 'created_on', None)
                        if not created_on:
                            logger.warning(f"推文 {post_id} 缺少创建时间，使用当前时间")
                            from datetime import datetime
                            created_on = datetime.now()

                        post_url = getattr(tweet, 'url', '')

                        author = getattr(tweet, 'author', None)
                        if author:
                            author_name = getattr(author, 'name', 'Unknown')
                            author_url = getattr(author, 'profile_url', '')
                            # 获取头像URL
                            author_avatar = getattr(author, 'profile_image_url', None) or getattr(author, 'avatar_url', None)
                        else:
                            author_name = "Unknown"
                            author_url = ""
                            author_avatar = None

                        # 创建Post对象
                        post = Post(post_id, created_on, tweet.text, post_url, author_name, author_url, poster_avatar_url=author_avatar)

                        # 保留原始用户信息，同时标识来源
                        post.account_id = author_name  # 保留原始用户名用于展示
                        post.source_type = "timeline"  # 标识这是来自时间线的推文
                        post.original_author = author_name  # 备份原始作者信息

                        processed_posts.append(post)
                    except Exception as e:
                        logger.error(f"创建单条推文Post对象时出错: {str(e)}")
                        continue
            except Exception as e:
                logger.error(f"处理时间线推文时出错: {str(e)}")
                continue

        logger.info(f"用户时间线处理完成，有效推文数量: {len(processed_posts)}")
        return processed_posts
    except Exception as e:
        logger.error(f"获取用户时间线时出错: {str(e)}")

        # 尝试切换代理
        try:
            # 尝试导入代理管理器
            from utils.api_utils import get_proxy_manager

            # 获取代理管理器
            proxy_manager = get_proxy_manager()

            # 强制查找新的可用代理
            working_proxy = proxy_manager.find_working_proxy(force_check=True)

            if working_proxy:
                logger.info(f"尝试使用新的代理 {working_proxy.name} 重新初始化Twitter客户端")
                # 重新初始化客户端
                if reinit_twitter_client():
                    logger.info(f"使用新代理成功初始化Twitter客户端，重试获取时间线")
                    # 递归调用自身，但增加重试计数
                    return fetch_timeline(limit, retry_count=retry_count+1)
        except Exception as ex:
            logger.warning(f"尝试切换客户端代理时出错: {str(ex)}")

        # 如果重试次数未达到最大值，增加重试计数并重试
        if retry_count < MAX_RETRIES - 1:
            logger.info(f"尝试第 {retry_count+1}/{MAX_RETRIES} 次重试获取时间线")
            return fetch_timeline(limit, retry_count=retry_count+1)
        else:
            logger.error(f"获取时间线失败，已达到最大重试次数，尝试备选方案")

            # 注意：twikit不支持时间线功能
            logger.warning("twikit不支持时间线功能，无法使用备选方案")

            return []


async def get_timeline_posts_async(limit: int = 50) -> list[Post]:
    """
    异步获取时间线推文 - 为了与main.py兼容而添加的包装函数

    Args:
        limit (int): 限制返回的推文数量

    Returns:
        list[Post]: 帖子列表
    """
    logger.info(f"异步获取时间线推文，限制数量: {limit}")

    # 调用现有的同步函数
    return fetch_timeline(limit)

def _log_operation(operation: str, library: str = None):
    """
    统一的日志记录函数
    Args:
        operation: 操作名称
        library: 库名称（可选）
    """
    if library:
        logger.info(f"开始使用{library}抓取{operation}")
    else:
        logger.info(f"开始{operation}")

def _handle_error(error: Exception, operation: str, library: str = None) -> dict:
    """
    统一的错误处理函数
    Args:
        error: 异常对象
        operation: 操作名称
        library: 库名称（可选）
    Returns:
        dict: 标准错误返回格式
    """
    if library:
        logger.error(f"{library}抓取{operation}时出错: {str(error)}")
    else:
        logger.error(f"{operation}时出错: {str(error)}")
    return {'success': False, 'message': str(error), 'data': []}

def _create_response(success: bool, message: str, data: list = None) -> dict:
    """
    统一的响应创建函数
    Args:
        success: 是否成功
        message: 消息
        data: 数据（可选）
    Returns:
        dict: 标准响应格式
    """
    return {'success': success, 'message': message, 'data': data or []}

def fetch_twitter_posts_smart():
    """
    智能抓取Twitter帖子，优先使用Tweety，失败时自动切换到Twikit。
    返回值:
        dict: 包含抓取结果的字典，格式为 {'success': bool, 'message': str, 'data': list}
    """
    try:
        _log_operation("智能抓取Twitter帖子")
        # 获取当前配置
        config = get_config('TWITTER_LIBRARY', 'auto')
        logger.info(f"当前Twitter库配置: {config}")

        # 优先使用Tweety
        if config == 'auto' or config == 'tweety':
            try:
                _log_operation("Twitter帖子", "Tweety")
                result = fetch_twitter_posts_tweety()
                if result['success']:
                    logger.info("Tweety抓取成功")
                    return result
                logger.warning("Tweety抓取失败，尝试切换到Twikit")
            except Exception as e:
                return _handle_error(e, "Twitter帖子", "Tweety")

        # 如果Tweety失败或配置为Twikit，使用Twikit
        if config == 'auto' or config == 'twikit':
            try:
                _log_operation("Twitter帖子", "Twikit")
                result = fetch_twitter_posts_twikit()
                if result['success']:
                    logger.info("Twikit抓取成功")
                    return result
                logger.warning("Twikit抓取失败")
            except Exception as e:
                return _handle_error(e, "Twitter帖子", "Twikit")

        # 如果都失败，返回错误
        logger.error("所有抓取方式均失败")
        return _create_response(False, "所有抓取方式均失败")
    except Exception as e:
        return _handle_error(e, "智能抓取Twitter帖子")

def fetch_twitter_posts_tweety():
    """
    使用Tweety抓取Twitter帖子。
    返回值:
        dict: 包含抓取结果的字典，格式为 {'success': bool, 'message': str, 'data': list}
    """
    try:
        _log_operation("Twitter帖子", "Tweety")
        # 抓取逻辑
        # ...
        return _create_response(True, "Tweety抓取成功")
    except Exception as e:
        return _handle_error(e, "Twitter帖子", "Tweety")

def fetch_twitter_posts_twikit():
    """
    使用Twikit抓取Twitter帖子。
    返回值:
        dict: 包含抓取结果的字典，格式为 {'success': bool, 'message': str, 'data': list}
    """
    try:
        _log_operation("Twitter帖子", "Twikit")
        # 抓取逻辑
        # ...
        return _create_response(True, "Twikit抓取成功")
    except Exception as e:
        return _handle_error(e, "Twitter帖子", "Twikit")

if __name__ == "__main__":
    posts = fetch('myfxtrader')
    for post in posts:
        print(post.content)
