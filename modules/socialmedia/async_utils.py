"""
异步工具模块
提供统一的异步处理函数，解决事件循环冲突问题
"""

import asyncio
import concurrent.futures
from typing import Any, Coroutine
from utils.logger import get_logger

logger = get_logger('async_utils')


def safe_asyncio_run(coro: Coroutine) -> Any:
    """
    安全地运行异步协程，处理事件循环冲突

    Args:
        coro: 协程对象

    Returns:
        协程的返回值

    Raises:
        Exception: 协程执行过程中的异常
    """
    try:
        # 尝试获取当前事件循环
        loop = asyncio.get_running_loop()
        # 如果已有运行中的循环，在新线程中运行
        logger.debug("检测到运行中的事件循环，在新线程中执行异步操作")

        def run_in_thread():
            # 在新线程中创建新的事件循环
            new_loop = asyncio.new_event_loop()
            asyncio.set_event_loop(new_loop)
            try:
                return new_loop.run_until_complete(coro)
            finally:
                new_loop.close()

        with concurrent.futures.ThreadPoolExecutor() as executor:
            future = executor.submit(run_in_thread)
            return future.result()  # 等待完成
    except RuntimeError as e:
        if "no running event loop" in str(e).lower() or "no current event loop" in str(e).lower():
            # 如果没有运行中的循环，直接使用asyncio.run
            logger.debug("没有运行中的事件循环，直接执行异步操作")
            return asyncio.run(coro)
        else:
            # 其他RuntimeError，尝试在新线程中运行
            logger.debug(f"事件循环错误: {str(e)}，在新线程中执行异步操作")

            def run_in_thread():
                new_loop = asyncio.new_event_loop()
                asyncio.set_event_loop(new_loop)
                try:
                    return new_loop.run_until_complete(coro)
                finally:
                    new_loop.close()

            with concurrent.futures.ThreadPoolExecutor() as executor:
                future = executor.submit(run_in_thread)
                return future.result()
    except Exception as e:
        logger.error(f"执行异步操作时出错: {str(e)}")
        raise


def is_coroutine_function(func) -> bool:
    """
    检查函数是否为协程函数

    Args:
        func: 要检查的函数

    Returns:
        bool: 是否为协程函数
    """
    import inspect
    return inspect.iscoroutinefunction(func)


def safe_call_async_method(obj, method_name: str, *args, **kwargs) -> Any:
    """
    安全地调用对象的异步方法

    Args:
        obj: 对象实例
        method_name: 方法名称
        *args: 位置参数
        **kwargs: 关键字参数

    Returns:
        方法的返回值
    """
    if not hasattr(obj, method_name):
        raise AttributeError(f"对象 {type(obj).__name__} 没有方法 {method_name}")

    method = getattr(obj, method_name)

    # 先调用方法获取结果
    result = method(*args, **kwargs)

    # 检查结果是否为协程对象
    import inspect
    if inspect.iscoroutine(result):
        # 如果返回协程对象，说明是异步方法
        logger.debug(f"调用异步方法: {type(obj).__name__}.{method_name}")
        return safe_asyncio_run(result)
    else:
        # 如果返回普通值，说明是同步方法
        logger.debug(f"调用同步方法: {type(obj).__name__}.{method_name}")
        return result


class AsyncContextManager:
    """
    异步上下文管理器，用于管理异步资源
    """

    def __init__(self, async_obj, init_method: str = None, cleanup_method: str = None):
        """
        初始化异步上下文管理器

        Args:
            async_obj: 异步对象
            init_method: 初始化方法名
            cleanup_method: 清理方法名
        """
        self.async_obj = async_obj
        self.init_method = init_method
        self.cleanup_method = cleanup_method
        self.initialized = False

    def __enter__(self):
        """进入上下文"""
        if self.init_method and hasattr(self.async_obj, self.init_method):
            try:
                safe_call_async_method(self.async_obj, self.init_method)
                self.initialized = True
                logger.debug(f"异步对象初始化成功: {self.init_method}")
            except Exception as e:
                logger.error(f"异步对象初始化失败: {str(e)}")
                raise
        return self.async_obj

    def __exit__(self, exc_type, exc_val, exc_tb):
        """退出上下文"""
        if self.cleanup_method and hasattr(self.async_obj, self.cleanup_method) and self.initialized:
            try:
                safe_call_async_method(self.async_obj, self.cleanup_method)
                logger.debug(f"异步对象清理成功: {self.cleanup_method}")
            except Exception as e:
                logger.warning(f"异步对象清理失败: {str(e)}")


def run_async_with_timeout(coro: Coroutine, timeout: float = 30.0) -> Any:
    """
    运行异步协程并设置超时

    Args:
        coro: 协程对象
        timeout: 超时时间（秒）

    Returns:
        协程的返回值

    Raises:
        asyncio.TimeoutError: 超时异常
        Exception: 其他异常
    """
    async def _run_with_timeout():
        return await asyncio.wait_for(coro, timeout=timeout)

    return safe_asyncio_run(_run_with_timeout())


def batch_run_async(coros: list, max_concurrent: int = 5) -> list:
    """
    批量运行异步协程，限制并发数

    Args:
        coros: 协程列表
        max_concurrent: 最大并发数

    Returns:
        结果列表
    """
    async def _batch_run():
        semaphore = asyncio.Semaphore(max_concurrent)

        async def _run_with_semaphore(coro):
            async with semaphore:
                return await coro

        tasks = [_run_with_semaphore(coro) for coro in coros]
        return await asyncio.gather(*tasks, return_exceptions=True)

    return safe_asyncio_run(_batch_run())


# 导出主要函数
__all__ = [
    'safe_asyncio_run',
    'is_coroutine_function',
    'safe_call_async_method',
    'AsyncContextManager',
    'run_async_with_timeout',
    'batch_run_async'
]
