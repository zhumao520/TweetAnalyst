from dotenv import load_dotenv
import os
import time
import logging
import random
import hashlib
from functools import wraps, lru_cache
from typing import Dict, Any
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# 创建日志记录器
logger = logging.getLogger('llm')

# 加载环境变量
load_dotenv()

# 定义API错误类型
class LLMAPIError(Exception):
    """LLM API调用错误基类"""
    pass

class LLMRateLimitError(LLMAPIError):
    """LLM API限流错误"""
    pass

class LLMAuthenticationError(LLMAPIError):
    """LLM API认证错误"""
    pass

class LLMServerError(LLMAPIError):
    """LLM API服务器错误"""
    pass

class LLMTimeoutError(LLMAPIError):
    """LLM API超时错误"""
    pass

def retry_with_exponential_backoff(
    max_retries: int = 5,
    initial_delay: float = 1,
    exponential_base: float = 2,
    jitter: bool = True,
    errors: tuple = (LLMRateLimitError, LLMServerError, LLMTimeoutError),
):
    """
    指数退避重试装饰器

    Args:
        max_retries: 最大重试次数
        initial_delay: 初始延迟时间（秒）
        exponential_base: 指数基数
        jitter: 是否添加随机抖动
        errors: 需要重试的错误类型
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            num_retries = 0
            delay = initial_delay

            while True:
                try:
                    return func(*args, **kwargs)
                except errors as e:
                    num_retries += 1
                    if num_retries > max_retries:
                        logger.error(f"达到最大重试次数 {max_retries}，放弃重试")
                        raise

                    # 计算延迟时间
                    delay *= exponential_base * (1 + 0.1 * random.random() if jitter else 1)

                    logger.warning(f"遇到错误: {str(e)}. 将在 {delay:.2f} 秒后进行第 {num_retries}/{max_retries} 次重试")
                    time.sleep(delay)
        return wrapper
    return decorator

def handle_llm_api_error(response_dict: Dict[str, Any]) -> None:
    """
    处理LLM API错误

    Args:
        response_dict: API响应字典

    Raises:
        LLMRateLimitError: 当API返回限流错误时
        LLMAuthenticationError: 当API返回认证错误时
        LLMServerError: 当API返回服务器错误时
        LLMAPIError: 当API返回其他错误时
    """
    if 'error' in response_dict:
        error = response_dict['error']
        error_type = error.get('type', '')
        error_message = error.get('message', 'Unknown error')

        if 'rate_limit' in error_type or 'rate_limit' in error_message.lower():
            raise LLMRateLimitError(f"API限流错误: {error_message}")
        elif 'authentication' in error_type or 'invalid_api_key' in error_type:
            raise LLMAuthenticationError(f"API认证错误: {error_message}")
        elif 'server_error' in error_type or error.get('code', 0) >= 500:
            raise LLMServerError(f"API服务器错误: {error_message}")
        else:
            raise LLMAPIError(f"API错误: {error_message}")

@retry_with_exponential_backoff()
def get_llm_response(prompt: str) -> str:
    """
    使用 langchain-openai 调用模型获取响应

    Args:
        prompt (str): 输入的提示词

    Returns:
        str: 模型的完整响应文本

    Raises:
        LLMAuthenticationError: 当API密钥无效时
        LLMRateLimitError: 当API限流时
        LLMServerError: 当API服务器错误时
        LLMTimeoutError: 当API请求超时时
        LLMAPIError: 当API返回其他错误时
        ValueError: 当参数无效时
    """
    if not prompt or not isinstance(prompt, str):
        raise ValueError("提示词必须是非空字符串")

    # 获取API配置
    model = os.getenv("LLM_API_MODEL")
    api_base = os.getenv("LLM_API_BASE")
    api_key = os.getenv("LLM_API_KEY")

    if not model or not api_key:
        raise ValueError("缺少必要的API配置，请检查环境变量")

    logger.debug(f"使用模型 {model} 处理提示词")

    try:
        # 验证API基础URL格式
        if api_base and not api_base.startswith(('http://', 'https://')):
            logger.error(f"无效的API基础URL: {api_base}")
            raise ValueError(f"无效的API基础URL: {api_base}")

        logger.debug(f"使用自定义API基础URL: {api_base}")

        # 初始化 ChatOpenAI 客户端
        start_time = time.time()

        # 创建ChatOpenAI实例的基本参数
        chat_params = {
            "model": model,
            "openai_api_base": api_base,
            "openai_api_key": api_key,
            "temperature": 0,
            "request_timeout": 60
        }

        # 根据不同的API提供商添加特定参数
        model_kwargs = {}

        # 检查API类型和模型
        if api_base and 'x.ai' in api_base:
            logger.debug(f"检测到X.AI API，添加reasoning_effort参数")
            model_kwargs["reasoning_effort"] = "high"
        elif model and 'grok-3' in model:
            logger.debug(f"检测到grok-3模型，添加reasoning_effort参数")
            model_kwargs["reasoning_effort"] = "high"

        # 如果有特定参数，添加到chat_params
        if model_kwargs:
            chat_params["model_kwargs"] = model_kwargs

        # 创建ChatOpenAI实例
        try:
            chat = ChatOpenAI(**chat_params)

            # 创建消息
            system_content = """
你接下来回答的所有内容都只能是符合我要求的json字符串同。
字符串中如果有一些特殊的字符需要做好转义，确保最终这个json字符串可以在python中被正确解析。
在最终的回答中除了json字符串本身，不需要其它额外的信息，也不要在json内容前后额外增加markdown的三个点转义。
"""
            messages = [
                SystemMessage(content=system_content),
                HumanMessage(content=prompt)
            ]

            # 获取响应
            logger.debug(f"开始请求LLM API，模型: {model}")
            response = chat.invoke(messages)

            end_time = time.time()
            logger.debug(f"LLM响应时间: {end_time - start_time:.2f}秒")

            return response.content

        except Exception as api_error:
            error_message = str(api_error).lower()

            # 检查是否返回了HTML而不是JSON
            if "unexpected token '<'" in error_message:
                logger.error(f"API返回了HTML而不是JSON，可能是认证问题或API端点错误: {error_message}")
                raise LLMAuthenticationError(f"API返回了非JSON响应，请检查API密钥和基础URL")

            # 检查X.AI API特定错误
            elif '404' in error_message and 'x.ai' in api_base:
                logger.error(f"X.AI API返回404错误，可能是API端点已更改或需要特殊访问权限: {error_message}")
                logger.error(f"尝试访问的URL: {api_base}")
                logger.error(f"使用的模型: {model}")
                raise LLMAPIError(f"X.AI API返回404错误，请检查API端点和访问权限。建议尝试使用其他API提供商，如Groq (https://api.groq.com/v1)。错误详情: {error_message}")
            else:
                # 重新抛出原始异常
                raise

    except Exception as e:
        error_message = str(e).lower()

        # 根据错误消息分类异常
        if "timeout" in error_message or "timed out" in error_message:
            logger.error(f"LLM API请求超时: {error_message}")
            raise LLMTimeoutError(f"API请求超时: {error_message}")
        elif "rate limit" in error_message:
            logger.error(f"LLM API限流: {error_message}")
            raise LLMRateLimitError(f"API限流: {error_message}")
        elif "authentication" in error_message or "api key" in error_message:
            logger.error(f"LLM API认证错误: {error_message}")
            raise LLMAuthenticationError(f"API认证错误: {error_message}")
        elif "5" in error_message[:3]:  # 5xx错误
            logger.error(f"LLM API服务器错误: {error_message}")
            raise LLMServerError(f"API服务器错误: {error_message}")
        else:
            logger.error(f"LLM API调用错误: {error_message}")
            raise LLMAPIError(f"API调用错误: {error_message}")

# 添加缓存支持

# 使用LRU缓存装饰器创建缓存函数
@lru_cache(maxsize=100)
def _cached_response(prompt_hash: str, response: str) -> str:
    """
    缓存LLM响应的内部函数

    Args:
        prompt_hash: 提示词的哈希值
        response: LLM响应

    Returns:
        str: 传入的响应（用于缓存）
    """
    return response

def get_llm_response_with_cache(prompt: str, use_cache: bool = True) -> str:
    """
    带缓存的LLM响应获取

    Args:
        prompt: 提示词
        use_cache: 是否使用缓存

    Returns:
        str: LLM响应
    """
    if not use_cache:
        return get_llm_response(prompt)

    # 计算提示词的哈希值作为缓存键
    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()

    # 检查缓存
    try:
        # 尝试从缓存获取响应
        cached = _cached_response(prompt_hash, None)
        if cached is not None:
            logger.debug(f"缓存命中: {prompt_hash[:8]}...")
            return cached
    except Exception:
        # 如果缓存查询失败，忽略错误
        pass

    # 缓存未命中或查询失败，调用API
    response = get_llm_response(prompt)

    # 更新缓存
    try:
        _cached_response(prompt_hash, response)
    except Exception as e:
        logger.warning(f"更新缓存失败: {str(e)}")

    return response
