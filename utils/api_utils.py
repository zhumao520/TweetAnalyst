"""
API工具模块
提供统一的API调用和错误处理功能

此模块提供了一组用于API调用的工具函数，包括：
1. 统一的错误处理机制
2. 请求重试机制
3. 请求缓存
4. 请求超时控制
5. 高级代理支持（多代理自动切换和故障转移）
"""

import os
import time
import json
import logging
import requests
import hashlib
import threading
from functools import wraps
from urllib.parse import urlparse
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import List, Dict, Union, Optional, Tuple, Any, Callable
from requests.exceptions import RequestException, Timeout, ConnectionError

# 创建日志记录器
from utils.logger import get_logger
logger = get_logger('utils.api_utils')

# 导入统一的错误类型定义
from utils.error_types import (
    ErrorTypes, ERROR_TYPE_MAPPING, ERROR_MESSAGES,
    RETRYABLE_ERROR_TYPES, NON_RETRYABLE_ERROR_TYPES,
    get_error_type_from_status_code, get_error_message,
    is_retryable_error, classify_error_from_exception,
    create_error_response
)

# 全局缓存字典
_request_cache = {}
_cache_ttl = 300  # 缓存有效期（秒）

# 禁用不安全请求警告
try:
    import urllib3
    urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
except ImportError:
    logger.warning("无法导入urllib3，不安全请求警告将不会被禁用")

# 全局代理管理器实例
_proxy_manager = None
_proxy_manager_lock = threading.Lock()


# 导入数据库模型中的ProxyConfig
try:
    from models.proxy_config import ProxyConfig as DBProxyConfig
except ImportError:
    logger.warning("无法导入数据库模型中的ProxyConfig，将使用内存中的代理配置")

    # 如果无法导入数据库模型，使用内存中的代理配置类
    class DBProxyConfig:
        """代理配置类（内存版本）"""

        def __init__(self,
                    host: str,
                    port: int,
                    protocol: str = 'http',
                    username: str = None,
                    password: str = None,
                    priority: int = 0,
                    name: str = None,
                    is_active: bool = True):
            self.id = None
            self.host = host
            self.port = port
            self.protocol = protocol.lower()
            self.username = username
            self.password = password
            self.priority = priority
            self.name = name or f"{protocol}://{host}:{port}"
            self.is_active = is_active

            # 验证协议
            if self.protocol not in ['http', 'socks5']:
                raise ValueError("协议必须是 'http' 或 'socks5'")

        def get_proxy_url(self):
            """获取代理URL"""
            auth_str = ""
            if self.username and self.password:
                auth_str = f"{self.username}:{self.password}@"
            return f"{self.protocol}://{auth_str}{self.host}:{self.port}"

        def get_proxy_dict(self):
            """获取代理字典，用于requests库"""
            proxy_url = self.get_proxy_url()
            return {
                'http': proxy_url,
                'https': proxy_url
            }

        def to_dict(self):
            """转换为字典"""
            return {
                'id': self.id,
                'name': self.name,
                'host': self.host,
                'port': self.port,
                'protocol': self.protocol,
                'username': self.username,
                'password': '******' if self.password else None,
                'priority': self.priority,
                'is_active': self.is_active
            }

        def __str__(self) -> str:
            return self.name

        def __repr__(self) -> str:
            return f"DBProxyConfig(name='{self.name}', priority={self.priority})"

# 为了向后兼容，保留ProxyConfig类，但使其继承自DBProxyConfig
class ProxyConfig(DBProxyConfig):
    """代理配置类（向后兼容）"""

    def __init__(self,
                host: str,
                port: int,
                protocol: str = 'http',
                username: str = None,
                password: str = None,
                priority: int = 0,
                name: str = None):
        """
        初始化代理配置

        Args:
            host: 代理服务器主机名或IP
            port: 代理服务器端口
            protocol: 代理协议 ('http' 或 'socks5')
            username: 代理认证用户名 (可选)
            password: 代理认证密码 (可选)
            priority: 优先级 (数字越小优先级越高)
            name: 代理名称 (可选，用于日志)
        """
        super().__init__(
            host=host,
            port=port,
            protocol=protocol,
            username=username,
            password=password,
            priority=priority,
            name=name,
            is_active=True
        )


class ProxyManager:
    """代理管理器，支持多代理自动切换和故障转移"""

    def __init__(self,
                 proxy_configs: List[ProxyConfig] = None,
                 test_url: str = "https://www.google.com/generate_204",
                 timeout: int = 10,
                 max_retries: int = 3,
                 verify_ssl: bool = False,
                 parallel_tests: bool = True):
        """
        初始化代理管理器

        Args:
            proxy_configs: 代理配置列表
            test_url: 用于测试代理连接的URL
            timeout: 请求超时时间(秒)
            max_retries: 最大重试次数
            verify_ssl: 是否验证SSL证书
            parallel_tests: 是否并行测试代理
        """
        self.proxy_configs = proxy_configs or []
        self.test_url = test_url
        self.timeout = timeout
        self.max_retries = max_retries
        self.verify_ssl = verify_ssl
        self.parallel_tests = parallel_tests
        self._working_proxy = None
        self._last_check_time = 0
        self._check_interval = 60  # 秒

        # 按优先级排序代理配置
        self._sort_proxies()

    def add_proxy(self, proxy_config: ProxyConfig) -> None:
        """添加代理配置"""
        self.proxy_configs.append(proxy_config)
        self._sort_proxies()
        self._working_proxy = None  # 重置工作代理

    def _sort_proxies(self) -> None:
        """按优先级排序代理配置（数字越大优先级越高）"""
        self.proxy_configs.sort(key=lambda x: x.priority, reverse=True)

    def _test_proxy(self, proxy_config: ProxyConfig) -> Tuple[bool, Optional[float]]:
        """
        测试单个代理是否工作

        Returns:
            (成功标志, 响应时间(秒))
        """
        proxies = proxy_config.get_proxy_dict()
        start_time = time.time()

        try:
            response = requests.get(
                self.test_url,
                proxies=proxies,
                timeout=self.timeout,
                verify=self.verify_ssl
            )
            elapsed = time.time() - start_time

            if response.status_code < 400:
                logger.info(f"代理 {proxy_config.name} 测试成功，响应时间: {elapsed:.2f}秒")
                return True, elapsed
            else:
                logger.warning(f"代理 {proxy_config.name} 返回错误状态码: {response.status_code}")
                return False, None

        except Exception as e:
            logger.warning(f"代理 {proxy_config.name} 测试失败: {type(e).__name__}: {str(e)}")
            return False, None

    def find_working_proxy(self, force_check: bool = False) -> Optional[ProxyConfig]:
        """
        查找工作的代理

        Args:
            force_check: 是否强制重新检查所有代理

        Returns:
            工作的代理配置，如果没有则返回None
        """
        current_time = time.time()

        # 如果已有工作代理且不需要强制检查，直接返回
        if (self._working_proxy and
            not force_check and
            current_time - self._last_check_time < self._check_interval):
            return self._working_proxy

        self._last_check_time = current_time

        if not self.proxy_configs:
            logger.warning("没有配置代理")
            return None

        if self.parallel_tests:
            return self._find_working_proxy_parallel()
        else:
            return self._find_working_proxy_sequential()

    def _find_working_proxy_sequential(self) -> Optional[ProxyConfig]:
        """按顺序测试代理"""
        for proxy in self.proxy_configs:
            success, _ = self._test_proxy(proxy)
            if success:
                self._working_proxy = proxy
                return proxy

        self._working_proxy = None
        logger.error("所有代理都不可用")
        return None

    def _find_working_proxy_parallel(self) -> Optional[ProxyConfig]:
        """并行测试所有代理"""
        if not self.proxy_configs:
            return None

        with ThreadPoolExecutor(max_workers=min(len(self.proxy_configs), 10)) as executor:
            # 提交所有代理测试任务
            future_to_proxy = {
                executor.submit(self._test_proxy, proxy): proxy
                for proxy in self.proxy_configs
            }

            # 收集结果
            working_proxies = []

            for future in as_completed(future_to_proxy):
                proxy = future_to_proxy[future]
                try:
                    success, elapsed = future.result()
                    if success:
                        working_proxies.append((proxy, elapsed))
                except Exception as e:
                    logger.error(f"测试代理 {proxy.name} 时发生错误: {e}")

            # 按响应时间排序可用代理
            if working_proxies:
                working_proxies.sort(key=lambda x: x[1])  # 按响应时间排序
                self._working_proxy = working_proxies[0][0]  # 选择最快的代理
                return self._working_proxy

            self._working_proxy = None
            logger.error("所有代理都不可用")
            return None

    def request(self,
                method: str,
                url: str,
                **kwargs) -> requests.Response:
        """
        使用可用代理发送HTTP请求

        Args:
            method: HTTP方法 ('get', 'post', 等)
            url: 请求URL
            **kwargs: 传递给requests的其他参数

        Returns:
            requests.Response对象

        Raises:
            RequestException: 如果所有代理都失败
        """
        # 设置默认参数
        kwargs.setdefault('timeout', self.timeout)
        kwargs.setdefault('verify', self.verify_ssl)

        # 尝试使用缓存的工作代理
        if self._working_proxy:
            try:
                kwargs['proxies'] = self._working_proxy.get_proxy_dict()
                response = getattr(requests, method.lower())(url, **kwargs)
                return response
            except RequestException as e:
                logger.warning(f"使用缓存代理 {self._working_proxy.name} 请求失败: {e}")
                # 缓存的代理失败，继续尝试其他代理

        # 尝试所有代理
        last_exception = None
        for attempt in range(self.max_retries):
            # 查找工作代理
            proxy = self.find_working_proxy(force_check=(attempt > 0))
            if not proxy:
                raise RequestException("所有代理都不可用")

            try:
                kwargs['proxies'] = proxy.get_proxy_dict()
                response = getattr(requests, method.lower())(url, **kwargs)
                return response
            except RequestException as e:
                logger.warning(f"尝试 {attempt+1}/{self.max_retries}: 代理 {proxy.name} 请求失败: {e}")
                last_exception = e
                # 标记当前代理为不可用
                if proxy == self._working_proxy:
                    self._working_proxy = None

        # 所有尝试都失败
        if last_exception:
            raise last_exception
        else:
            raise RequestException("所有代理请求尝试都失败")

    def get(self, url: str, **kwargs) -> requests.Response:
        """发送GET请求"""
        return self.request('get', url, **kwargs)

    def post(self, url: str, **kwargs) -> requests.Response:
        """发送POST请求"""
        return self.request('post', url, **kwargs)

    def put(self, url: str, **kwargs) -> requests.Response:
        """发送PUT请求"""
        return self.request('put', url, **kwargs)

    def delete(self, url: str, **kwargs) -> requests.Response:
        """发送DELETE请求"""
        return self.request('delete', url, **kwargs)


def get_proxy_manager(force_new=False):
    """
    获取全局代理管理器实例

    Args:
        force_new: 是否强制创建新实例

    Returns:
        ProxyManager: 代理管理器实例
    """
    global _proxy_manager

    if _proxy_manager is None or force_new:
        with _proxy_manager_lock:
            if _proxy_manager is None or force_new:
                # 创建代理配置
                proxy_configs = []

                # 尝试从数据库加载代理配置
                try:
                    # 导入代理服务
                    from services.proxy_service import get_all_proxies

                    # 获取所有激活的代理配置
                    db_proxies = get_all_proxies()

                    if db_proxies:
                        logger.info(f"从数据库加载了 {len(db_proxies)} 个代理配置")

                        # 将数据库代理配置转换为ProxyConfig对象
                        for proxy_dict in db_proxies:
                            if proxy_dict.get('is_active', True):
                                try:
                                    proxy = DBProxyConfig(
                                        host=proxy_dict['host'],
                                        port=proxy_dict['port'],
                                        protocol=proxy_dict['protocol'],
                                        username=proxy_dict.get('username'),
                                        password=proxy_dict.get('password'),
                                        priority=proxy_dict.get('priority', 0),
                                        name=proxy_dict.get('name'),
                                        is_active=True
                                    )
                                    proxy.id = proxy_dict.get('id')
                                    proxy_configs.append(proxy)
                                except Exception as e:
                                    logger.warning(f"转换代理配置时出错: {e}")
                except ImportError:
                    logger.warning("无法导入代理服务，将不从数据库加载代理配置")
                except Exception as e:
                    logger.warning(f"从数据库加载代理配置时出错: {e}")

                # 如果数据库中没有代理配置，尝试从环境变量加载
                if not proxy_configs:
                    logger.info("数据库中没有代理配置，尝试从环境变量加载")

                    # 尝试添加HTTP代理
                    http_proxy = os.environ.get('HTTP_PROXY')
                    if http_proxy:
                        try:
                            # 解析代理URL
                            parsed = urlparse(http_proxy)
                            host = parsed.hostname
                            port = parsed.port
                            username = parsed.username
                            password = parsed.password

                            if host and port:
                                proxy_configs.append(
                                    ProxyConfig(
                                        host=host,
                                        port=port,
                                        protocol='http',
                                        username=username,
                                        password=password,
                                        priority=1,
                                        name="HTTP_PROXY环境变量"
                                    )
                                )
                        except Exception as e:
                            logger.warning(f"解析HTTP_PROXY环境变量时出错: {e}")

                    # 尝试添加HTTPS代理
                    https_proxy = os.environ.get('HTTPS_PROXY')
                    if https_proxy and https_proxy != http_proxy:
                        try:
                            # 解析代理URL
                            parsed = urlparse(https_proxy)
                            host = parsed.hostname
                            port = parsed.port
                            username = parsed.username
                            password = parsed.password

                            if host and port:
                                proxy_configs.append(
                                    ProxyConfig(
                                        host=host,
                                        port=port,
                                        protocol='http',
                                        username=username,
                                        password=password,
                                        priority=2,
                                        name="HTTPS_PROXY环境变量"
                                    )
                                )
                        except Exception as e:
                            logger.warning(f"解析HTTPS_PROXY环境变量时出错: {e}")

                # 创建代理管理器
                _proxy_manager = ProxyManager(
                    proxy_configs=proxy_configs,
                    test_url="https://www.google.com/generate_204",
                    timeout=10,
                    max_retries=3,
                    verify_ssl=False,
                    parallel_tests=True
                )

                logger.info(f"已创建代理管理器，配置了 {len(proxy_configs)} 个代理")

    return _proxy_manager

class APIError(Exception):
    """API调用错误基类"""
    def __init__(self, message, status_code=None, response=None):
        self.message = message
        self.status_code = status_code
        self.response = response
        super().__init__(message)

class ConnectionAPIError(APIError):
    """连接错误"""
    pass

class TimeoutAPIError(APIError):
    """超时错误"""
    pass

class AuthenticationAPIError(APIError):
    """认证错误"""
    pass

class RateLimitAPIError(APIError):
    """限流错误"""
    pass

class ServerAPIError(APIError):
    """服务器错误"""
    pass

class ClientAPIError(APIError):
    """客户端错误"""
    pass

class ResponseParseError(APIError):
    """响应解析错误"""
    pass

def _generate_cache_key(url, method, data=None, params=None, headers=None):
    """
    生成缓存键

    Args:
        url: 请求URL
        method: 请求方法
        data: 请求数据
        params: 请求参数
        headers: 请求头

    Returns:
        str: 缓存键
    """
    # 创建一个包含所有请求信息的字典
    cache_dict = {
        'url': url,
        'method': method,
        'data': data,
        'params': params
    }

    # 如果headers中有Authorization，只保留前10个字符，避免泄露完整的认证信息
    if headers and 'Authorization' in headers:
        headers_copy = headers.copy()
        auth = headers_copy['Authorization']
        headers_copy['Authorization'] = auth[:10] + '...' if len(auth) > 10 else auth
        cache_dict['headers'] = headers_copy
    else:
        cache_dict['headers'] = headers

    # 将字典转换为JSON字符串
    cache_str = json.dumps(cache_dict, sort_keys=True)

    # 使用MD5生成哈希值
    return hashlib.md5(cache_str.encode()).hexdigest()

def _classify_error(status_code, error=None):
    """
    根据状态码和错误类型分类错误（使用统一的错误类型定义）

    Args:
        status_code: HTTP状态码
        error: 原始错误

    Returns:
        Exception: 分类后的错误
    """
    # 使用统一的错误分类函数
    if error:
        error_type, error_message = classify_error_from_exception(error, status_code)
    else:
        error_type = get_error_type_from_status_code(status_code) if status_code else ErrorTypes.UNKNOWN
        error_message = get_error_message(error_type, status_code)

    # 根据错误类型创建相应的异常
    if error_type == ErrorTypes.TIMEOUT:
        return TimeoutAPIError(error_message, status_code)
    elif error_type == ErrorTypes.CONNECTION:
        return ConnectionAPIError(error_message, status_code)
    elif error_type == ErrorTypes.AUTH:
        return AuthenticationAPIError(error_message, status_code)
    elif error_type == ErrorTypes.RATE_LIMIT:
        return RateLimitAPIError(error_message, status_code)
    elif error_type == ErrorTypes.SERVER:
        return ServerAPIError(error_message, status_code)
    elif error_type == ErrorTypes.CLIENT:
        return ClientAPIError(error_message, status_code)
    elif error_type == ErrorTypes.PARSE:
        return ResponseParseError(error_message, status_code)
    else:
        return APIError(error_message, status_code)



def api_request(url, method='GET', data=None, params=None, headers=None, timeout=30,
                retries=3, retry_delay=1, use_cache=False, cache_ttl=None,
                verify_ssl=True, allow_redirects=True, proxy=None):
    """
    统一的API请求函数

    Args:
        url: 请求URL
        method: 请求方法，默认为GET
        data: 请求数据
        params: 请求参数
        headers: 请求头
        timeout: 超时时间（秒）
        retries: 重试次数
        retry_delay: 重试延迟（秒）
        use_cache: 是否使用缓存
        cache_ttl: 缓存有效期（秒），默认为全局缓存有效期
        verify_ssl: 是否验证SSL证书
        allow_redirects: 是否允许重定向
        proxy: 代理设置，如果为None则使用环境变量中的代理

    Returns:
        dict: 响应数据

    Raises:
        APIError: API调用错误
    """
    # 规范化方法名
    method = method.upper()

    # 检查缓存
    if use_cache and method == 'GET':
        cache_key = _generate_cache_key(url, method, data, params, headers)
        cached_response = _request_cache.get(cache_key)
        if cached_response:
            # 检查缓存是否过期
            if time.time() - cached_response['timestamp'] < (cache_ttl or _cache_ttl):
                logger.debug(f"使用缓存的响应: {url}")
                return cached_response['data']
            else:
                # 缓存过期，从缓存中删除
                del _request_cache[cache_key]

    # 设置代理
    proxies = None
    if proxy:
        # 使用指定的代理
        if isinstance(proxy, dict):
            # 如果已经是代理字典，直接使用
            proxies = proxy
        else:
            # 如果是字符串，创建代理字典
            proxies = {
                'http': proxy,
                'https': proxy
            }
    elif proxy is None:
        # 如果没有指定代理，尝试使用服务层的代理管理
        try:
            # 导入代理服务
            from services.proxy_service import find_working_proxy

            # 查找可用的代理
            working_proxy = find_working_proxy()
            if working_proxy:
                # 构建代理字典
                protocol = working_proxy.get('protocol', 'http')
                host = working_proxy['host']
                port = working_proxy['port']
                username = working_proxy.get('username')
                password = working_proxy.get('password')

                # 构建代理URL
                if username and password:
                    proxy_url = f"{protocol}://{username}:{password}@{host}:{port}"
                else:
                    proxy_url = f"{protocol}://{host}:{port}"

                proxies = {
                    'http': proxy_url,
                    'https': proxy_url
                }
                logger.debug(f"使用服务层选择的代理: {working_proxy.get('name', 'Unknown')}")
        except ImportError:
            logger.warning("无法导入代理服务，尝试使用代理管理器")

            # 回退到代理管理器
            try:
                proxy_manager = get_proxy_manager()
                working_proxy = proxy_manager.find_working_proxy()
                if working_proxy:
                    proxies = working_proxy.get_proxy_dict()
                    logger.debug(f"使用代理管理器选择的代理: {working_proxy.name}")
            except Exception as e:
                logger.warning(f"使用代理管理器时出错: {e}")
        except Exception as e:
            logger.warning(f"使用代理服务时出错: {e}")

            # 如果代理服务失败，回退到环境变量代理
            if os.environ.get('HTTP_PROXY'):
                proxies = {
                    'http': os.environ.get('HTTP_PROXY'),
                    'https': os.environ.get('HTTPS_PROXY', os.environ.get('HTTP_PROXY'))
                }
                logger.debug("使用环境变量中的代理")

    # 如果仍然没有代理，使用环境变量
    if proxies is None and os.environ.get('HTTP_PROXY'):
        proxies = {
            'http': os.environ.get('HTTP_PROXY'),
            'https': os.environ.get('HTTPS_PROXY', os.environ.get('HTTP_PROXY'))
        }
        logger.debug("使用环境变量中的代理")

    # 记录请求信息
    logger.debug(f"API请求: {method} {url}")
    if params:
        logger.debug(f"请求参数: {params}")
    if data:
        # 如果数据太大，只记录前100个字符
        log_data = str(data)
        if len(log_data) > 100:
            log_data = log_data[:100] + '...'
        logger.debug(f"请求数据: {log_data}")

    # 执行请求，支持重试
    response = None
    last_error = None

    for attempt in range(retries):
        try:
            response = requests.request(
                method=method,
                url=url,
                json=data if method in ['POST', 'PUT', 'PATCH'] and isinstance(data, (dict, list)) else None,
                data=data if method in ['POST', 'PUT', 'PATCH'] and not isinstance(data, (dict, list)) else None,
                params=params,
                headers=headers,
                timeout=timeout,
                verify=verify_ssl,
                allow_redirects=allow_redirects,
                proxies=proxies
            )

            # 检查响应状态码
            if not response.ok:
                error = _classify_error(response.status_code)
                error.response = response

                # 对于某些错误不重试
                if isinstance(error, (AuthenticationAPIError, ClientAPIError)) and not isinstance(error, RateLimitAPIError):
                    raise error

                last_error = error
                logger.warning(f"API请求失败 (尝试 {attempt+1}/{retries}): {error.message}")

                # 如果是限流错误，增加重试延迟
                if isinstance(error, RateLimitAPIError):
                    retry_delay = retry_delay * (attempt + 1)

                # 如果已经是最后一次尝试，抛出错误
                if attempt == retries - 1:
                    raise error

                # 等待后重试
                time.sleep(retry_delay)
                continue

            # 尝试解析JSON响应
            try:
                result = response.json()
            except ValueError:
                # 如果响应不是JSON格式，返回文本内容
                result = {'text': response.text, 'content_type': response.headers.get('Content-Type')}

            # 缓存响应
            if use_cache and method == 'GET':
                _request_cache[cache_key] = {
                    'data': result,
                    'timestamp': time.time()
                }

            # 记录成功响应
            logger.debug(f"API请求成功: {method} {url}")

            return result

        except RequestException as e:
            # 处理请求异常
            status_code = response.status_code if response else None
            error = _classify_error(status_code, e)
            last_error = error

            logger.warning(f"API请求异常 (尝试 {attempt+1}/{retries}): {str(e)}")

            # 如果已经是最后一次尝试，抛出错误
            if attempt == retries - 1:
                raise error

            # 等待后重试
            time.sleep(retry_delay)

    # 如果所有重试都失败，抛出最后一个错误
    if last_error:
        raise last_error
    else:
        raise APIError("未知错误")

def get(url, **kwargs):
    """
    发送GET请求

    Args:
        url: 请求URL
        **kwargs: 其他参数，与api_request相同

    Returns:
        dict: 响应数据
    """
    return api_request(url, method='GET', **kwargs)

def post(url, data=None, **kwargs):
    """
    发送POST请求

    Args:
        url: 请求URL
        data: 请求数据
        **kwargs: 其他参数，与api_request相同

    Returns:
        dict: 响应数据
    """
    return api_request(url, method='POST', data=data, **kwargs)

def put(url, data=None, **kwargs):
    """
    发送PUT请求

    Args:
        url: 请求URL
        data: 请求数据
        **kwargs: 其他参数，与api_request相同

    Returns:
        dict: 响应数据
    """
    return api_request(url, method='PUT', data=data, **kwargs)

def delete(url, **kwargs):
    """
    发送DELETE请求

    Args:
        url: 请求URL
        **kwargs: 其他参数，与api_request相同

    Returns:
        dict: 响应数据
    """
    return api_request(url, method='DELETE', **kwargs)

def clear_cache():
    """
    清除请求缓存
    """
    global _request_cache
    _request_cache = {}
    logger.debug("已清除API请求缓存")


def proxy_request(url, method='GET', data=None, params=None, headers=None, timeout=30,
                 retries=3, retry_delay=1, use_cache=False, cache_ttl=None,
                 verify_ssl=False, allow_redirects=True):
    """
    使用代理管理器发送请求

    此函数与api_request类似，但直接使用代理管理器，自动选择最佳代理

    Args:
        url: 请求URL
        method: 请求方法，默认为GET
        data: 请求数据
        params: 请求参数
        headers: 请求头
        timeout: 超时时间（秒）
        retries: 重试次数
        retry_delay: 重试延迟（秒）
        use_cache: 是否使用缓存
        cache_ttl: 缓存有效期（秒），默认为全局缓存有效期
        verify_ssl: 是否验证SSL证书
        allow_redirects: 是否允许重定向

    Returns:
        dict: 响应数据

    Raises:
        APIError: API调用错误
    """
    try:
        # 获取代理管理器
        proxy_manager = get_proxy_manager()

        # 使用代理管理器的方法发送请求
        method = method.lower()
        if method not in ['get', 'post', 'put', 'delete']:
            raise ValueError(f"不支持的HTTP方法: {method}")

        # 准备请求参数
        kwargs = {
            'timeout': timeout,
            'verify': verify_ssl,
            'allow_redirects': allow_redirects,
            'headers': headers,
            'params': params
        }

        # 根据方法添加数据
        if method in ['post', 'put', 'patch']:
            if isinstance(data, (dict, list)):
                kwargs['json'] = data
            else:
                kwargs['data'] = data

        # 发送请求
        response = getattr(proxy_manager, method)(url, **kwargs)

        # 解析响应
        try:
            result = response.json()
        except ValueError:
            # 如果响应不是JSON格式，返回文本内容
            result = {'text': response.text, 'content_type': response.headers.get('Content-Type')}

        # 缓存响应
        if use_cache and method == 'get':
            cache_key = _generate_cache_key(url, method.upper(), data, params, headers)
            _request_cache[cache_key] = {
                'data': result,
                'timestamp': time.time()
            }

        return result

    except RequestException as e:
        # 将RequestException转换为APIError
        status_code = getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None
        error = _classify_error(status_code, e)
        raise error

    except Exception as e:
        # 处理其他异常
        logger.error(f"代理请求时出错: {str(e)}")
        raise APIError(f"代理请求时出错: {str(e)}")


def proxy_get(url, **kwargs):
    """
    使用代理管理器发送GET请求

    Args:
        url: 请求URL
        **kwargs: 其他参数，与proxy_request相同

    Returns:
        dict: 响应数据
    """
    return proxy_request(url, method='GET', **kwargs)


def proxy_post(url, data=None, **kwargs):
    """
    使用代理管理器发送POST请求

    Args:
        url: 请求URL
        data: 请求数据
        **kwargs: 其他参数，与proxy_request相同

    Returns:
        dict: 响应数据
    """
    return proxy_request(url, method='POST', data=data, **kwargs)


def proxy_put(url, data=None, **kwargs):
    """
    使用代理管理器发送PUT请求

    Args:
        url: 请求URL
        data: 请求数据
        **kwargs: 其他参数，与proxy_request相同

    Returns:
        dict: 响应数据
    """
    return proxy_request(url, method='PUT', data=data, **kwargs)


def proxy_delete(url, **kwargs):
    """
    使用代理管理器发送DELETE请求

    Args:
        url: 请求URL
        **kwargs: 其他参数，与proxy_request相同

    Returns:
        dict: 响应数据
    """
    return proxy_request(url, method='DELETE', **kwargs)
