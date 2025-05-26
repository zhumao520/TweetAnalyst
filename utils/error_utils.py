"""
错误处理工具
提供错误处理和日志记录功能
"""

import logging
import traceback
import functools
from typing import Callable, Any, Dict, Optional, TypeVar, cast

# 定义类型变量
T = TypeVar('T')

# 获取日志记录器
logger = logging.getLogger(__name__)

def log_exceptions(
    logger_instance: Optional[logging.Logger] = None,
    error_message: str = "执行函数时出错",
    log_traceback: bool = True,
    default_return: Any = None
) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """
    装饰器：记录函数执行过程中的异常
    
    Args:
        logger_instance: 日志记录器实例，如果为None则使用默认日志记录器
        error_message: 错误消息前缀
        log_traceback: 是否记录完整的堆栈跟踪
        default_return: 发生异常时的默认返回值
        
    Returns:
        装饰后的函数
    """
    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @functools.wraps(func)
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            log = logger_instance or logger
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # 构建详细的错误消息
                detailed_message = f"{error_message}: {str(e)}"
                
                # 记录错误
                log.error(detailed_message)
                
                # 如果需要，记录堆栈跟踪
                if log_traceback:
                    log.debug(f"堆栈跟踪: {traceback.format_exc()}")
                
                # 返回默认值
                return default_return
        return cast(Callable[..., T], wrapper)
    return decorator

def format_error_details(exception: Exception) -> Dict[str, str]:
    """
    格式化异常详情
    
    Args:
        exception: 异常对象
        
    Returns:
        Dict[str, str]: 包含异常详情的字典
    """
    return {
        'exception': str(exception),
        'traceback': traceback.format_exc()
    }

def safe_execute(
    func: Callable[..., T],
    *args: Any,
    error_message: str = "执行函数时出错",
    logger_instance: Optional[logging.Logger] = None,
    default_return: Any = None,
    **kwargs: Any
) -> T:
    """
    安全执行函数，捕获并记录异常
    
    Args:
        func: 要执行的函数
        *args: 函数的位置参数
        error_message: 错误消息前缀
        logger_instance: 日志记录器实例，如果为None则使用默认日志记录器
        default_return: 发生异常时的默认返回值
        **kwargs: 函数的关键字参数
        
    Returns:
        函数的返回值，如果发生异常则返回default_return
    """
    log = logger_instance or logger
    try:
        return func(*args, **kwargs)
    except Exception as e:
        # 构建详细的错误消息
        detailed_message = f"{error_message}: {str(e)}"
        
        # 记录错误
        log.error(detailed_message)
        log.debug(f"堆栈跟踪: {traceback.format_exc()}")
        
        # 返回默认值
        return default_return
