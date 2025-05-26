#!/usr/bin/env python3
"""
Twitter数据获取 - Twikit实现
基于twikit库的Twitter数据抓取功能
与现有tweety系统完全兼容
"""

import os
import json
import time
import asyncio
import importlib.util
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional, List, Dict, Any
from utils.logger import get_logger
from modules.socialmedia.post import Post
from modules.socialmedia.twitter_utils import (
    extract_media_info,
    extract_author_info,
    create_post_from_tweet,
    set_timeline_metadata,
    batch_create_posts
)
from modules.socialmedia.async_utils import safe_asyncio_run

# 创建日志记录器
logger = get_logger('twitter_twikit')

class TwikitHandler:
    """Twikit库处理器 - 与现有系统完全兼容"""

    def __init__(self):
        self.client = None
        self.initialized = False
        self.cookies_path = Path.home() / '.twitter-handler' / 'cookies.json'
        self.rate_limits = {}
        self.rate_limit_window = 15 * 60  # 15分钟
        self.last_request_time = 0
        self.min_request_interval = 2.0  # 最小请求间隔

    def is_available(self) -> bool:
        """检查twikit库是否可用"""
        try:
            spec = importlib.util.find_spec("twikit")
            return spec is not None
        except ImportError:
            return False

    def get_proxy_config(self):
        """获取代理配置 - 与现有系统兼容"""
        proxy_config = None

        try:
            # 优先从数据库获取代理配置
            from services.proxy_service import find_working_proxy

            proxy_info = find_working_proxy()

            if proxy_info:
                # 构建代理URL
                protocol = proxy_info.get('protocol', 'http')
                host = proxy_info['host']
                port = proxy_info['port']
                username = proxy_info.get('username')
                password = proxy_info.get('password')

                if username and password:
                    proxy_url = f"{protocol}://{username}:{password}@{host}:{port}"
                else:
                    proxy_url = f"{protocol}://{host}:{port}"

                proxy_config = {
                    'http': proxy_url,
                    'https': proxy_url
                }
                logger.info(f"使用数据库中的代理: {proxy_info.get('name', 'Unknown')}")
                return proxy_config
            else:
                logger.info("数据库中未找到可用的代理，尝试使用环境变量")

        except ImportError:
            logger.info("代理服务不可用，尝试使用环境变量")
        except Exception as e:
            logger.warning(f"从数据库获取代理配置时出错: {str(e)}，回退到环境变量")

        # 回退到环境变量
        proxy_url = os.getenv('HTTP_PROXY', '')
        if proxy_url:
            proxy_config = {
                'http': proxy_url,
                'https': proxy_url
            }
            logger.info(f"使用环境变量中的代理: {proxy_url}")

        return proxy_config

    async def initialize(self) -> bool:
        """初始化twikit客户端"""
        if not self.is_available():
            logger.error("twikit库未安装，请运行: pip install twikit")
            return False

        try:
            # 设置SSL环境以解决连接问题
            import ssl
            import os
            os.environ['PYTHONHTTPSVERIFY'] = '0'
            os.environ['CURL_CA_BUNDLE'] = ''
            os.environ['REQUESTS_CA_BUNDLE'] = ''

            # 设置SSL默认上下文
            ssl._create_default_https_context = ssl._create_unverified_context
            logger.info("Twikit: 已设置SSL环境以解决连接问题")

            import twikit

            # 获取代理配置
            proxy_config = self.get_proxy_config()

            # 创建客户端，使用与现有系统兼容的配置
            # 注意：新版twikit使用proxy参数而不是proxies
            if proxy_config:
                # 使用第一个代理URL（http或https都可以）
                proxy_url = proxy_config.get('https') or proxy_config.get('http')
                self.client = twikit.Client('en-US', proxy=proxy_url)
                logger.info(f"Twikit客户端已初始化（使用代理: {proxy_url}）")
            else:
                self.client = twikit.Client('en-US')
                logger.info("Twikit客户端已初始化（直连）")

            # 设置用户代理，与现有系统保持一致
            user_agent = os.getenv('HTTP_HEADER_USER_AGENT',
                'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36')

            if hasattr(self.client, 'set_user_agent'):
                self.client.set_user_agent(user_agent)

            self.initialized = True
            return True

        except Exception as e:
            logger.error(f"初始化twikit客户端失败: {str(e)}")
            return False

    def get_credentials(self) -> Dict[str, Any]:
        """获取Twitter登录凭据 - 与现有系统兼容"""
        credentials = {
            'username': None,
            'email': None,
            'password': None,
            'session': None,
            'source': None
        }

        try:
            # 优先从数据库获取（与现有系统保持一致）
            from services.config_service import get_config

            db_username = get_config('TWITTER_USERNAME')
            db_email = get_config('TWITTER_EMAIL')  # 新增邮箱支持
            db_password = get_config('TWITTER_PASSWORD')
            db_session = get_config('TWITTER_SESSION')

            if db_session and db_session.strip():
                credentials['session'] = db_session
                credentials['source'] = 'database'
                logger.info("使用数据库中的Twitter会话数据")
                return credentials
            elif db_username and db_email and db_password:
                credentials['username'] = db_username
                credentials['email'] = db_email
                credentials['password'] = db_password
                credentials['source'] = 'database'
                logger.info(f"使用数据库中的Twitter账号: {db_username}")
                return credentials
            else:
                logger.info("数据库中未找到完整的Twitter登录凭据，尝试使用环境变量")

        except Exception as e:
            logger.warning(f"从数据库获取Twitter登录凭据时出错: {str(e)}，回退到环境变量")

        # 回退到环境变量
        env_username = os.getenv('TWITTER_USERNAME')
        env_email = os.getenv('TWITTER_EMAIL')
        env_password = os.getenv('TWITTER_PASSWORD')
        env_session = os.getenv('TWITTER_SESSION')

        if env_session and env_session.strip():
            credentials['session'] = env_session
            credentials['source'] = 'environment'
            logger.info("使用环境变量中的Twitter会话")
        elif env_username and env_email and env_password:
            credentials['username'] = env_username
            credentials['email'] = env_email
            credentials['password'] = env_password
            credentials['source'] = 'environment'
            logger.info(f"使用环境变量中的Twitter账号: {env_username}")
        else:
            logger.warning("未找到完整的Twitter登录凭据（需要用户名、邮箱、密码）")

        return credentials

    async def load_session(self) -> bool:
        """加载已保存的会话"""
        try:
            if self.cookies_path.exists():
                self.client.load_cookies(self.cookies_path)
                logger.info("已加载保存的Twitter会话")

                # 验证会话是否有效
                try:
                    # 尝试获取当前用户信息来验证会话
                    await self.client.get_me()
                    logger.info("会话验证成功")
                    return True
                except Exception as e:
                    logger.warning(f"会话验证失败: {str(e)}，需要重新登录")
                    # 删除无效的会话文件
                    try:
                        self.cookies_path.unlink()
                        logger.info("已删除无效的会话文件")
                    except:
                        pass
                    return False
            else:
                logger.info("未找到保存的会话文件")
                return False
        except Exception as e:
            logger.error(f"加载会话失败: {str(e)}")
            return False

    async def login_with_credentials(self, username: str, email: str, password: str, max_retries: int = 3) -> bool:
        """使用凭据登录"""
        # 验证凭据不为空
        if not username or not email or not password:
            logger.error(f"登录凭据不完整: username={bool(username)}, email={bool(email)}, password={bool(password)}")
            return False

        for attempt in range(max_retries):
            try:
                if self.client is None:
                    return False

                logger.info(f"尝试登录用户: {username} (尝试 {attempt + 1}/{max_retries})")

                # 添加请求延迟，模拟人类行为
                await self.add_request_delay()

                await self.client.login(
                    auth_info_1=str(username),
                    auth_info_2=str(email),
                    password=str(password)
                )

                # 验证登录是否成功
                try:
                    await self.client.get_me()
                    logger.info("登录验证成功")
                except Exception as verify_error:
                    logger.warning(f"登录验证失败: {str(verify_error)}")
                    if attempt < max_retries - 1:
                        continue
                    return False

                # 保存会话
                self.cookies_path.parent.mkdir(parents=True, exist_ok=True)
                self.client.save_cookies(self.cookies_path)

                logger.info("登录成功，会话已保存")
                return True

            except Exception as e:
                error_msg = str(e)
                logger.error(f"登录失败 (尝试 {attempt + 1}/{max_retries}): {error_msg}")

                # 提供详细的错误分析（与现有系统保持一致）
                if "elevated authorization" in error_msg.lower():
                    logger.error("🚨 检测到 'elevated authorization' 错误")
                    logger.error("这通常是由于使用了Cloudflare IP导致的")
                elif "challenge" in error_msg.lower():
                    logger.error("需要完成验证挑战")
                elif "rate limit" in error_msg.lower():
                    logger.error("遇到速率限制")
                    # 速率限制时等待更长时间
                    if attempt < max_retries - 1:
                        await asyncio.sleep(60)  # 等待1分钟
                elif "password" in error_msg.lower() or "credential" in error_msg.lower():
                    logger.error("凭据错误，停止重试")
                    return False

                # 如果不是最后一次尝试，等待后重试
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 5  # 递增等待时间
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)

        logger.error("所有登录尝试都失败了")
        return False

    def check_rate_limit(self, endpoint: str) -> bool:
        """检查速率限制"""
        now = time.time()

        if endpoint not in self.rate_limits:
            self.rate_limits[endpoint] = []

        # 移除过期的时间戳
        self.rate_limits[endpoint] = [
            t for t in self.rate_limits[endpoint]
            if now - t < self.rate_limit_window
        ]

        # 根据端点检查限制
        limits = {
            'user_tweets': 300,  # 用户推文: 300次/15分钟
            'search': 180,       # 搜索: 180次/15分钟
            'user_info': 300,    # 用户信息: 300次/15分钟
            'timeline': 180      # 时间线: 180次/15分钟
        }

        limit = limits.get(endpoint, 100)
        return len(self.rate_limits[endpoint]) < limit

    def record_api_call(self, endpoint: str):
        """记录API调用"""
        if endpoint not in self.rate_limits:
            self.rate_limits[endpoint] = []
        self.rate_limits[endpoint].append(time.time())

    async def add_request_delay(self):
        """添加请求延迟，模拟人类行为"""
        now = time.time()
        time_since_last = now - self.last_request_time

        if time_since_last < self.min_request_interval:
            delay = self.min_request_interval - time_since_last
            logger.debug(f"添加请求延迟: {delay:.2f}秒")
            await asyncio.sleep(delay)

        self.last_request_time = time.time()

    async def get_user_tweets(self, user_id: str, limit: int = 10) -> List[Post]:
        """获取用户推文 - 返回与现有系统兼容的Post对象"""
        if not self.check_rate_limit('user_tweets'):
            logger.error("用户推文速率限制已达上限，请稍后再试")
            return []

        max_retries = 3
        for attempt in range(max_retries):
            try:
                if self.client is None:
                    logger.error("Twikit客户端未初始化")
                    return []

                # 添加请求延迟
                await self.add_request_delay()

                # 获取用户信息
                username = user_id.lstrip('@')
                logger.info(f"获取用户 {username} 的信息...")

                user = await self.client.get_user_by_screen_name(username)

                if not user:
                    logger.error(f"找不到用户: {username}")
                    return []

                logger.info(f"获取用户 {username} 的推文 (尝试 {attempt + 1}/{max_retries})...")

                # 获取推文
                tweets = await self.client.get_user_tweets(user_id=user.id, count=limit)
                self.record_api_call('user_tweets')

                if not tweets:
                    logger.warning(f"用户 {username} 没有推文或推文不可访问")
                    return []

                # 使用工具函数批量创建Post对象
                posts = batch_create_posts(tweets, user, username, is_timeline=False)

                logger.info(f"成功获取 {len(posts)} 条推文")
                return posts

            except Exception as e:
                error_msg = str(e)
                logger.error(f"获取推文失败 (尝试 {attempt + 1}/{max_retries}): {error_msg}")

                # 检查是否是速率限制错误
                if "rate limit" in error_msg.lower():
                    logger.warning("遇到速率限制，等待后重试")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(60)  # 等待1分钟
                        continue
                elif "not found" in error_msg.lower():
                    logger.error(f"用户 {username} 不存在")
                    return []
                elif "protected" in error_msg.lower():
                    logger.error(f"用户 {username} 的账号受保护")
                    return []

                # 如果不是最后一次尝试，等待后重试
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("所有重试都失败了")
                    return []

        return []

    def _parse_datetime(self, dt_str):
        """解析日期时间字符串，返回datetime对象"""
        try:
            if isinstance(dt_str, str):
                # 尝试解析ISO格式
                return datetime.fromisoformat(dt_str.replace('Z', '+00:00'))
            elif isinstance(dt_str, datetime):
                return dt_str
            else:
                return datetime.now(timezone.utc)
        except:
            return datetime.now(timezone.utc)

    async def search_tweets(self, query: str, limit: int = 10) -> List[Post]:
        """搜索推文"""
        if not self.check_rate_limit('search'):
            logger.error("搜索速率限制已达上限，请稍后再试")
            return []

        try:
            if self.client is None:
                logger.error("Twikit客户端未初始化")
                return []

            logger.info(f"搜索推文: {query}")

            # 添加请求延迟
            await self.add_request_delay()

            tweets = await self.client.search_tweet(query, product='Top', count=limit)
            self.record_api_call('search')

            # 使用工具函数批量创建Post对象
            posts = batch_create_posts(tweets, None, 'unknown', is_timeline=False)

            logger.info(f"搜索成功获取 {len(posts)} 条推文")
            return posts

        except Exception as e:
            logger.error(f"搜索推文失败: {str(e)}")
            return []

    async def get_timeline_tweets(self, limit: int = 20) -> List[Post]:
        """获取时间线推文 - 与现有系统兼容的接口"""
        if not self.check_rate_limit('timeline'):
            logger.error("时间线速率限制已达上限，请稍后再试")
            return []

        max_retries = 3
        for attempt in range(max_retries):
            try:
                if self.client is None:
                    logger.error("Twikit客户端未初始化")
                    return []

                logger.info(f"获取时间线推文 (尝试 {attempt + 1}/{max_retries})...")

                # 添加请求延迟
                await self.add_request_delay()

                # 获取时间线推文
                tweets = await self.client.get_home_timeline(count=limit)
                self.record_api_call('timeline')

                if not tweets:
                    logger.warning("时间线为空或无法访问")
                    return []

                # 使用工具函数批量创建时间线Post对象
                posts = batch_create_posts(tweets, None, 'Unknown', is_timeline=True)

                logger.info(f"成功获取 {len(posts)} 条时间线推文")
                return posts

            except Exception as e:
                error_msg = str(e)
                logger.error(f"获取时间线推文失败 (尝试 {attempt + 1}/{max_retries}): {error_msg}")

                # 检查是否是速率限制错误
                if "rate limit" in error_msg.lower():
                    logger.warning("遇到速率限制，等待后重试")
                    if attempt < max_retries - 1:
                        await asyncio.sleep(60)  # 等待1分钟
                        continue
                elif "unauthorized" in error_msg.lower():
                    logger.error("未授权访问时间线，可能需要重新登录")
                    return []

                # 如果不是最后一次尝试，等待后重试
                if attempt < max_retries - 1:
                    wait_time = (attempt + 1) * 3
                    logger.info(f"等待 {wait_time} 秒后重试...")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("所有重试都失败了")
                    return []

        return []

    def get_status(self) -> dict:
        """获取twikit状态"""
        return {
            'available': self.is_available(),
            'initialized': self.initialized,
            'session_exists': self.cookies_path.exists(),
            'rate_limits': self.get_rate_limit_status()
        }

    def get_rate_limit_status(self) -> dict:
        """获取速率限制状态"""
        now = time.time()
        status = {}

        for endpoint, timestamps in self.rate_limits.items():
            # 清理过期时间戳
            valid_timestamps = [t for t in timestamps if now - t < self.rate_limit_window]

            limits = {
                'user_tweets': 300, 'search': 180, 'user_info': 300, 'timeline': 180
            }

            limit = limits.get(endpoint, 100)
            used = len(valid_timestamps)
            remaining = max(0, limit - used)

            status[endpoint] = {
                'limit': limit,
                'used': used,
                'remaining': remaining,
                'reset_time': max(valid_timestamps) + self.rate_limit_window if valid_timestamps else now
            }

        return status

# 全局处理器实例
twikit_handler = TwikitHandler()

# 与现有系统兼容的接口函数
async def initialize() -> bool:
    """初始化twikit处理器"""
    return await twikit_handler.initialize()

async def fetch_tweets(user_id: str, limit: int = None) -> List[Post]:
    """
    获取指定用户的最新推文 - 与现有系统兼容的接口

    Args:
        user_id (str): Twitter用户ID
        limit (int, optional): 限制返回的推文数量

    Returns:
        List[Post]: 帖子列表
    """
    try:
        # 确保初始化
        if not twikit_handler.initialized:
            if not await initialize():
                logger.error("Twikit初始化失败")
                return []

        # 尝试加载已有会话
        session_loaded = await twikit_handler.load_session()

        # 如果会话无效或不存在，尝试登录
        if not session_loaded:
            credentials = twikit_handler.get_credentials()

            username = credentials.get('username')
            email = credentials.get('email')
            password = credentials.get('password')

            if username and email and password:
                # 尝试登录
                if not await twikit_handler.login_with_credentials(
                    username,
                    email,
                    password
                ):
                    logger.error("自动登录失败")
                    return []
            else:
                logger.error(f"未找到完整的Twitter登录凭据（需要用户名、邮箱、密码）")
                logger.error(f"当前凭据状态: username={bool(username)}, email={bool(email)}, password={bool(password)}")
                return []

        # 获取推文
        return await twikit_handler.get_user_tweets(user_id, limit or 10)

    except Exception as e:
        logger.error(f"获取推文时出错: {str(e)}")
        return []

async def fetch_timeline_tweets(limit: int = 20) -> List[Post]:
    """
    获取时间线推文 - 与现有系统兼容的接口

    Args:
        limit (int): 限制返回的推文数量

    Returns:
        List[Post]: 帖子列表
    """
    try:
        # 确保初始化
        if not twikit_handler.initialized:
            if not await initialize():
                logger.error("Twikit初始化失败")
                return []

        # 尝试加载已有会话
        session_loaded = await twikit_handler.load_session()

        # 如果会话无效或不存在，尝试登录
        if not session_loaded:
            credentials = twikit_handler.get_credentials()

            username = credentials.get('username')
            email = credentials.get('email')
            password = credentials.get('password')

            if username and email and password:
                # 尝试登录
                if not await twikit_handler.login_with_credentials(
                    username,
                    email,
                    password
                ):
                    logger.error("自动登录失败")
                    return []
            else:
                logger.error(f"未找到完整的Twitter登录凭据（需要用户名、邮箱、密码）")
                logger.error(f"当前凭据状态: username={bool(username)}, email={bool(email)}, password={bool(password)}")
                return []

        # 获取时间线推文
        return await twikit_handler.get_timeline_tweets(limit)

    except Exception as e:
        logger.error(f"获取时间线推文时出错: {str(e)}")
        return []

def is_available() -> bool:
    """检查twikit是否可用"""
    return twikit_handler.is_available()

def get_status() -> dict:
    """获取twikit状态"""
    return twikit_handler.get_status()

# 导出主要函数
__all__ = [
    'fetch_tweets',
    'fetch_timeline_tweets',
    'initialize',
    'is_available',
    'get_status',
    'twikit_handler'
]
