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
    # 尝试从环境变量获取配置
    model = os.getenv("LLM_API_MODEL")
    api_base = os.getenv("LLM_API_BASE")
    api_key = os.getenv("LLM_API_KEY")

    # 尝试从数据库获取配置（如果可能）
    try:
        # 导入配置服务
        from services.config_service import get_config

        # 如果环境变量中没有配置，尝试从数据库获取
        if not model:
            model = get_config("LLM_API_MODEL")
            logger.debug(f"从数据库获取模型配置: {model}")

        if not api_base:
            api_base = get_config("LLM_API_BASE")
            logger.debug(f"从数据库获取API基础URL配置: {api_base}")

        if not api_key:
            api_key = get_config("LLM_API_KEY")
            logger.debug("从数据库获取API密钥配置")
    except Exception as e:
        logger.warning(f"从数据库获取配置时出错: {str(e)}")

    if not model or not api_key:
        raise ValueError("缺少必要的API配置，请检查环境变量或数据库配置")

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
        reasoning_effort = None

        # 检查API类型和模型
        if api_base and 'x.ai' in api_base:
            logger.debug(f"检测到X.AI API，添加reasoning_effort参数")
            reasoning_effort = "high"
        elif model and 'grok-3' in model:
            logger.debug(f"检测到grok-3模型，添加reasoning_effort参数")
            reasoning_effort = "high"

        # 如果有其他特定参数，添加到chat_params
        if model_kwargs:
            chat_params["model_kwargs"] = model_kwargs

        # reasoning_effort参数将在调用时单独传递

        # 创建ChatOpenAI实例
        try:
            chat = ChatOpenAI(**chat_params)

            # 创建消息
            system_content = """
你接下来回答的所有内容都只能是符合我要求的JSON字符串。
请严格遵循以下规则：
1. 只返回有效的JSON格式，不要包含任何其他文本或解释
2. 确保所有键名使用双引号，如 {"key": "value"}
3. 确保所有字符串值使用双引号，如 {"name": "value"}
4. 布尔值使用小写的true或false，如 {"is_valid": true}
5. 数字值不需要引号，如 {"count": 42}
6. 数组使用方括号，如 {"items": ["a", "b", "c"]}
7. 特殊字符需要正确转义，如换行符应该是\\n而不是\n
8. 不要在JSON前后添加任何标记，如```json或```
9. 确保JSON格式正确，可以被Python的json.loads()函数解析

示例格式：
{"should_push": true, "confidence": 85, "reason": "这是一个重要更新", "summary": "内容摘要"}

请确保你的回复是一个可以直接被Python解析的有效JSON字符串。
"""
            messages = [
                SystemMessage(content=system_content),
                HumanMessage(content=prompt)
            ]

            # 获取响应
            logger.debug(f"开始请求LLM API，模型: {model}")

            # 根据是否有reasoning_effort参数决定调用方式
            if reasoning_effort:
                logger.debug(f"使用reasoning_effort={reasoning_effort}调用API")
                response = chat.invoke(messages, reasoning_effort=reasoning_effort)
            else:
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

                # 提供更详细的诊断信息
                diagnostic_message = (
                    f"X.AI API返回404错误，请检查以下可能的问题：\n"
                    f"1. API端点URL可能已更改，当前使用: {api_base}\n"
                    f"2. 模型名称可能不正确，当前使用: {model}\n"
                    f"3. 您的API密钥可能没有访问此模型的权限\n"
                    f"4. X.AI服务可能暂时不可用\n\n"
                    f"建议尝试使用其他API提供商，如Groq (https://api.groq.com/v1)或Anthropic (https://api.anthropic.com/v1)。\n"
                    f"错误详情: {error_message}"
                )
                raise LLMAPIError(diagnostic_message)
            # 检查模型名称错误
            elif 'model not found' in error_message or 'model_not_found' in error_message:
                logger.error(f"模型名称错误: {error_message}")
                logger.error(f"请求的模型: {model}")

                # 提供更详细的诊断信息
                diagnostic_message = (
                    f"模型名称错误: {model}\n"
                    f"请检查模型名称是否正确，不同的API提供商使用不同的模型名称格式。\n"
                    f"常见的模型名称格式：\n"
                    f"- X.AI: grok-3-mini-beta, grok-3-max-beta\n"
                    f"- OpenAI: gpt-4-turbo, gpt-3.5-turbo\n"
                    f"- Anthropic: claude-3-opus, claude-3-sonnet\n"
                    f"- Groq: llama3-8b-8192, llama3-70b-8192\n"
                    f"错误详情: {error_message}"
                )
                raise LLMAPIError(diagnostic_message)
            else:
                # 重新抛出原始异常，但添加更多上下文
                logger.error(f"LLM API调用未知错误: {error_message}")
                logger.error(f"API基础URL: {api_base}")
                logger.error(f"模型: {model}")
                raise

    except Exception as e:
        error_message = str(e).lower()

        # 根据错误消息分类异常
        if "timeout" in error_message or "timed out" in error_message:
            logger.error(f"LLM API请求超时: {error_message}")
            diagnostic_message = (
                f"API请求超时，可能的原因：\n"
                f"1. 网络连接不稳定\n"
                f"2. API服务器响应时间过长\n"
                f"3. 代理服务器配置问题\n\n"
                f"建议：\n"
                f"- 检查网络连接\n"
                f"- 增加请求超时时间\n"
                f"- 检查代理服务器配置\n"
                f"错误详情: {error_message}"
            )
            raise LLMTimeoutError(diagnostic_message)
        elif "rate limit" in error_message:
            logger.error(f"LLM API限流: {error_message}")
            diagnostic_message = (
                f"API限流，可能的原因：\n"
                f"1. 超过了API提供商的请求频率限制\n"
                f"2. 超过了API提供商的并发请求限制\n\n"
                f"建议：\n"
                f"- 减少请求频率\n"
                f"- 实现请求队列和重试机制\n"
                f"- 考虑升级API计划\n"
                f"错误详情: {error_message}"
            )
            raise LLMRateLimitError(diagnostic_message)
        elif "authentication" in error_message or "api key" in error_message or "unauthorized" in error_message:
            logger.error(f"LLM API认证错误: {error_message}")
            diagnostic_message = (
                f"API认证错误，可能的原因：\n"
                f"1. API密钥无效或已过期\n"
                f"2. API密钥没有访问请求资源的权限\n"
                f"3. API密钥格式不正确\n\n"
                f"建议：\n"
                f"- 检查API密钥是否正确\n"
                f"- 在API提供商的控制台中重新生成API密钥\n"
                f"- 确认API密钥有访问请求资源的权限\n"
                f"错误详情: {error_message}"
            )
            raise LLMAuthenticationError(diagnostic_message)
        elif "5" in error_message[:3] or "server error" in error_message:  # 5xx错误
            logger.error(f"LLM API服务器错误: {error_message}")
            diagnostic_message = (
                f"API服务器错误，可能的原因：\n"
                f"1. API提供商的服务器暂时不可用\n"
                f"2. API提供商的服务器过载\n"
                f"3. API提供商正在进行维护\n\n"
                f"建议：\n"
                f"- 稍后重试\n"
                f"- 检查API提供商的状态页面\n"
                f"- 考虑使用备用API提供商\n"
                f"错误详情: {error_message}"
            )
            raise LLMServerError(diagnostic_message)
        elif "connectionerror" in error_message or "connection error" in error_message or "apiconnectionerror" in error_message:
            logger.error(f"LLM API连接错误: {error_message}")
            logger.error(f"API基础URL: {api_base}")
            logger.error(f"模型: {model}")

            # 尝试进行网络诊断
            try:
                import socket
                import subprocess

                # 尝试解析域名
                domain = api_base.split("//")[-1].split("/")[0]
                logger.error(f"尝试解析域名: {domain}")
                try:
                    ip_address = socket.gethostbyname(domain)
                    logger.error(f"域名解析结果: {ip_address}")
                except Exception as dns_error:
                    logger.error(f"域名解析失败: {str(dns_error)}")

                # 尝试ping
                try:
                    ping_result = subprocess.run(["ping", "-c", "1", domain], capture_output=True, text=True, timeout=5)
                    logger.error(f"Ping结果: {'成功' if ping_result.returncode == 0 else '失败'}")
                except Exception as ping_error:
                    logger.error(f"Ping测试失败: {str(ping_error)}")

            except Exception as diag_error:
                logger.error(f"网络诊断失败: {str(diag_error)}")

            diagnostic_message = (
                f"API连接错误，无法连接到API服务器。\n"
                f"API基础URL: {api_base}\n"
                f"模型: {model}\n"
                f"异常类型: {type(e).__name__}\n"
                f"错误详情: {error_message}\n\n"
                f"可能的原因：\n"
                f"1. 网络连接问题\n"
                f"2. DNS解析失败\n"
                f"3. 防火墙或代理限制\n"
                f"4. API端点可能已更改\n"
                f"5. SSL/TLS证书问题\n\n"
                f"建议：\n"
                f"- 检查网络连接\n"
                f"- 检查DNS配置\n"
                f"- 检查防火墙或代理设置\n"
                f"- 尝试使用其他API提供商\n"
                f"- 查看日志获取更多诊断信息"
            )
            raise LLMAPIError(diagnostic_message)
        else:
            logger.error(f"LLM API调用错误: {error_message}")
            # 记录更多上下文信息以便调试
            logger.error(f"API基础URL: {api_base}")
            logger.error(f"模型: {model}")
            logger.error(f"异常类型: {type(e).__name__}")

            diagnostic_message = (
                f"API调用错误，未能识别的错误类型。\n"
                f"API基础URL: {api_base}\n"
                f"模型: {model}\n"
                f"异常类型: {type(e).__name__}\n"
                f"错误详情: {error_message}\n\n"
                f"建议：\n"
                f"- 检查API配置\n"
                f"- 查看日志获取更多信息\n"
                f"- 联系API提供商获取支持"
            )
            raise LLMAPIError(diagnostic_message)

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
