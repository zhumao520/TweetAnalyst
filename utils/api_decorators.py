"""
API装饰器模块
提供API调用相关的装饰器

此模块提供了一组用于API调用的装饰器，包括：
1. 错误处理装饰器
2. 重试装饰器
3. 缓存装饰器
4. 超时控制装饰器
"""

import time
import functools
import traceback
from utils.logger import get_logger
from utils.api_utils import APIError, RateLimitAPIError, TimeoutAPIError, ConnectionAPIError

# 导入统一的错误类型定义
try:
    from utils.error_types import (
        ErrorTypes, classify_error_from_exception,
        is_retryable_error, RETRYABLE_ERROR_TYPES
    )
    HAS_ERROR_TYPES = True
except ImportError:
    HAS_ERROR_TYPES = False

# 创建日志记录器
logger = get_logger('utils.api_decorators')

def handle_api_errors(default_return=None, log_level='error'):
    """
    API错误处理装饰器（使用统一的错误类型定义）

    Args:
        default_return: 发生错误时的默认返回值
        log_level: 日志级别，可选值：debug, info, warning, error, critical

    Returns:
        function: 装饰后的函数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except APIError as e:
                # 使用统一的错误分类
                if HAS_ERROR_TYPES:
                    error_type, error_message = classify_error_from_exception(e)
                    log_func = getattr(logger, log_level)
                    log_func(f"API错误 ({error_type}): {error_message}")
                else:
                    # 回退到原始实现
                    log_func = getattr(logger, log_level)
                    log_func(f"API错误: {str(e)}")

                # 记录更详细的错误信息
                if log_level in ['error', 'critical']:
                    logger.debug(f"错误详情: {traceback.format_exc()}")

                # 返回默认值
                return default_return
            except Exception as e:
                # 使用统一的错误分类处理未预期的错误
                if HAS_ERROR_TYPES:
                    error_type, error_message = classify_error_from_exception(e)
                    logger.error(f"未预期的错误 ({error_type}): {error_message}")
                else:
                    logger.error(f"未预期的错误: {str(e)}")

                logger.debug(f"错误详情: {traceback.format_exc()}")

                # 返回默认值
                return default_return
        return wrapper
    return decorator

def retry_on_error(max_retries=3, retry_delay=1, retry_errors=(APIError,), backoff_factor=2):
    """
    错误重试装饰器（使用统一的错误类型定义）

    Args:
        max_retries: 最大重试次数
        retry_delay: 初始重试延迟（秒）
        retry_errors: 需要重试的错误类型
        backoff_factor: 退避因子，用于计算下一次重试的延迟时间

    Returns:
        function: 装饰后的函数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            last_error = None

            for attempt in range(max_retries):
                try:
                    return func(*args, **kwargs)
                except retry_errors as e:
                    last_error = e

                    # 使用统一的错误分类判断是否可重试
                    should_retry = False
                    if HAS_ERROR_TYPES:
                        error_type, _ = classify_error_from_exception(e)
                        should_retry = is_retryable_error(error_type)
                    else:
                        # 回退到原始逻辑
                        should_retry = True

                    if not should_retry:
                        logger.error(f"错误不可重试，直接抛出: {str(e)}")
                        raise e

                    # 计算下一次重试的延迟时间
                    delay = retry_delay * (backoff_factor ** attempt)

                    # 对于限流错误，可能需要更长的延迟
                    if isinstance(e, RateLimitAPIError):
                        delay = max(delay, 5 * (attempt + 1))

                    logger.warning(f"尝试 {attempt+1}/{max_retries} 失败: {str(e)}，将在 {delay:.1f} 秒后重试")

                    # 如果已经是最后一次尝试，不再等待
                    if attempt < max_retries - 1:
                        time.sleep(delay)

            # 如果所有重试都失败，抛出最后一个错误
            if last_error:
                logger.error(f"重试 {max_retries} 次后仍然失败: {str(last_error)}")
                raise last_error
            else:
                raise RuntimeError("未知错误导致重试失败")
        return wrapper
    return decorator

def cache_result(ttl=300, key_func=None):
    """
    结果缓存装饰器

    Args:
        ttl: 缓存有效期（秒）
        key_func: 缓存键生成函数，如果为None则使用函数名和参数生成

    Returns:
        function: 装饰后的函数
    """
    cache = {}

    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            # 生成缓存键
            if key_func:
                cache_key = key_func(*args, **kwargs)
            else:
                # 默认使用函数名和参数生成缓存键
                arg_str = str(args) + str(sorted(kwargs.items()))
                cache_key = f"{func.__name__}:{arg_str}"

            # 检查缓存
            if cache_key in cache:
                result, timestamp = cache[cache_key]
                if time.time() - timestamp < ttl:
                    logger.debug(f"使用缓存的结果: {cache_key}")
                    return result
                else:
                    # 缓存过期，从缓存中删除
                    del cache[cache_key]

            # 执行函数
            result = func(*args, **kwargs)

            # 缓存结果
            cache[cache_key] = (result, time.time())

            return result

        # 添加清除缓存的方法
        def clear_cache():
            nonlocal cache
            cache = {}
            logger.debug(f"已清除 {func.__name__} 的缓存")

        wrapper.clear_cache = clear_cache

        return wrapper
    return decorator

def timeout(seconds=30):
    """
    超时控制装饰器

    注意：此装饰器需要在支持信号的平台上使用，Windows可能不支持

    Args:
        seconds: 超时时间（秒）

    Returns:
        function: 装饰后的函数
    """
    def decorator(func):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            import signal

            def handler(signum, frame):
                raise TimeoutAPIError(f"函数执行超时 ({seconds}秒)")

            # 设置信号处理器
            original_handler = signal.signal(signal.SIGALRM, handler)
            signal.alarm(seconds)

            try:
                return func(*args, **kwargs)
            finally:
                # 恢复原始信号处理器
                signal.signal(signal.SIGALRM, original_handler)
                signal.alarm(0)
        return wrapper
    return decorator
