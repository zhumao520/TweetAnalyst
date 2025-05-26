from dotenv import load_dotenv
import os
import time
import logging
import random
import hashlib
from datetime import datetime, timezone
from functools import wraps, lru_cache
from typing import Dict, Any, Optional, Tuple
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage

# 创建日志记录器
logger = logging.getLogger('llm')

# 导入AI分析日志记录器
try:
    from modules.langchain.ai_logger import ai_logger
except ImportError:
    # 如果导入失败，创建一个空的日志记录器
    logger.warning("无法导入AI分析日志记录器，将使用标准日志记录")
    ai_logger = None

# 尝试导入代理管理器
try:
    from utils.api_utils import get_proxy_manager
    logger.info("成功导入代理管理器")
    _use_proxy_manager = True
except ImportError:
    logger.warning("无法导入代理管理器，将使用环境变量中的代理")
    _use_proxy_manager = False

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
    指数退避重试装饰器，支持代理切换

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
            tried_proxy_switch = False

            while True:
                try:
                    return func(*args, **kwargs)
                except errors as e:
                    num_retries += 1

                    # 在第一次失败时尝试切换代理
                    if not tried_proxy_switch and _use_proxy_manager:
                        tried_proxy_switch = True
                        try:
                            # 尝试导入代理管理器
                            from utils.api_utils import get_proxy_manager

                            # 获取代理管理器
                            proxy_manager = get_proxy_manager()

                            # 强制查找新的可用代理
                            working_proxy = proxy_manager.find_working_proxy(force_check=True)

                            if working_proxy:
                                logger.info(f"LLM API调用失败，尝试使用新的代理 {working_proxy.name} 重试")
                                # 不增加重试计数，因为这是切换代理而不是真正的重试
                                num_retries -= 1
                                # 不等待，立即使用新代理重试
                                continue
                        except Exception as proxy_error:
                            logger.warning(f"尝试切换代理时出错: {str(proxy_error)}")

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



def get_next_ai_provider():
    """
    获取下一个可用的AI提供商

    使用简单的优先级 + 可用性检查策略选择下一个可用的AI提供商

    Returns:
        tuple: (provider_id, api_key, api_base, model) 或者 (None, None, None, None)
    """
    try:
        # 导入Flask应用
        from web_app import app

        # 确保在应用上下文中运行
        with app.app_context():
            # 导入AIProvider模型
            from models.ai_provider import AIProvider
            # 导入is_provider_available函数
            from services.ai_polling_service import is_provider_available

            # 查询所有激活的提供商，按优先级排序
            providers = AIProvider.query.filter_by(is_active=True).order_by(AIProvider.priority).all()

            if not providers:
                logger.warning("没有可用的AI提供商，将使用默认配置")
                return None, None, None, None

            # 遍历所有提供商，找到第一个可用的
            for provider in providers:
                # 检查提供商是否可用
                if is_provider_available(provider.id):
                    # 更新最后使用时间
                    provider.last_used_at = datetime.now(timezone.utc)
                    from web_app import db
                    db.session.commit()

                    logger.info(f"选择 AI 提供商: {provider.name} (ID: {provider.id})")
                    return provider.id, provider.api_key, provider.api_base, provider.model

            # 如果所有提供商都不可用，使用第一个提供商（强制使用）
            logger.warning("所有 AI 提供商都不可用，强制使用第一个提供商")
            provider = providers[0]
            provider.last_used_at = datetime.now(timezone.utc)
            from web_app import db
            db.session.commit()

            return provider.id, provider.api_key, provider.api_base, provider.model
    except Exception as e:
        logger.error(f"获取AI提供商时出错: {str(e)}")
        return None, None, None, None

def record_provider_usage(provider_id, success=True, error_message=None):
    """
    记录AI提供商的使用情况

    Args:
        provider_id: 提供商ID
        success: 是否成功
        error_message: 错误信息
    """
    if not provider_id:
        return

    try:
        # 导入Flask应用
        from web_app import app

        # 确保在应用上下文中运行
        with app.app_context():
            # 导入AIProvider模型
            from models.ai_provider import AIProvider

            # 查询提供商
            provider = AIProvider.query.get(provider_id)
            if not provider:
                logger.warning(f"找不到ID为{provider_id}的AI提供商")
                return

            # 记录使用情况
            if success:
                provider.record_success()
                logger.debug(f"记录AI提供商 {provider.name} 成功使用")
            else:
                provider.record_error(error_message)
                logger.warning(f"记录AI提供商 {provider.name} 使用失败: {error_message}")
    except Exception as e:
        logger.error(f"记录AI提供商使用情况时出错: {str(e)}")

@retry_with_exponential_backoff()
def get_llm_response(prompt: str, provider_id=None, api_key=None, api_base=None, model=None) -> str:
    """
    使用 langchain-openai 调用模型获取响应

    支持指定AI提供商或使用默认配置

    Args:
        prompt (str): 输入的提示词
        provider_id: AI提供商ID，用于记录使用情况
        api_key: API密钥，如果为None则使用默认配置
        api_base: API基础URL，如果为None则使用默认配置
        model: 模型名称，如果为None则使用默认配置

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
    # 使用AI分析日志记录器记录请求开始
    request_id = None
    if ai_logger:
        request_id = ai_logger.start_request(prompt, provider_id, model)
    if not prompt or not isinstance(prompt, str):
        raise ValueError("提示词必须是非空字符串")

    # 如果没有指定AI提供商，尝试获取下一个可用的提供商
    if not provider_id and not api_key:
        try:
            # 获取下一个可用的AI提供商
            next_provider_id, next_api_key, next_api_base, next_model = get_next_ai_provider()

            # 如果成功获取到提供商，使用其配置
            if next_provider_id and next_api_key:
                provider_id = next_provider_id
                api_key = next_api_key
                if next_api_base:
                    api_base = next_api_base
                if next_model:
                    model = next_model

                logger.info(f"使用AI提供商ID: {provider_id}")
        except Exception as e:
            logger.warning(f"获取下一个AI提供商时出错: {str(e)}")

    # 如果仍然没有API密钥，从配置中获取
    if not api_key or not model:
        # 获取API配置
        # 优先从数据库获取配置，确保使用最新设置
        try:
            # 导入配置服务
            from services.config_service import get_config, init_config

            # 使用统一的配置初始化函数，确保配置是最新的
            try:
                # 不强制刷新，不验证，避免不必要的日志
                result = init_config(force=False, validate=False)
                if result['success']:
                    logger.debug("配置已初始化")
                else:
                    logger.warning(f"配置初始化失败: {result['message']}")
            except Exception as init_error:
                logger.warning(f"初始化配置时出错: {str(init_error)}")

            # 直接从配置服务获取配置（优先级高于环境变量）
            if not model:
                model = get_config("LLM_API_MODEL")
                if model:
                    logger.debug(f"从配置服务获取模型配置: {model}")

            if not api_base:
                api_base = get_config("LLM_API_BASE")
                if api_base:
                    logger.debug(f"从配置服务获取API基础URL配置: {api_base}")

            if not api_key:
                api_key = get_config("LLM_API_KEY")
                if api_key:
                    logger.debug("从配置服务获取API密钥配置")

            # 如果数据库中没有配置，尝试从环境变量获取
            if not model:
                model = os.getenv("LLM_API_MODEL")
                logger.debug(f"从环境变量获取模型配置: {model}")

            if not api_base:
                api_base = os.getenv("LLM_API_BASE")
                logger.debug(f"从环境变量获取API基础URL配置: {api_base}")

            if not api_key:
                api_key = os.getenv("LLM_API_KEY")
                logger.debug("从环境变量获取API密钥配置")

        except Exception as e:
            # 如果从数据库获取失败，回退到环境变量
            logger.warning(f"从数据库获取配置时出错: {str(e)}")
            if not model:
                model = os.getenv("LLM_API_MODEL")
            if not api_base:
                api_base = os.getenv("LLM_API_BASE")
            if not api_key:
                api_key = os.getenv("LLM_API_KEY")
            logger.debug("回退到环境变量获取配置")

    if not model or not api_key:
        raise ValueError("缺少必要的API配置，请检查环境变量或数据库配置")

    logger.debug(f"使用模型 {model} 处理提示词")

    try:
        # 验证API基础URL格式
        if api_base and not api_base.startswith(('http://', 'https://')):
            logger.error(f"无效的API基础URL: {api_base}")
            raise ValueError(f"无效的API基础URL: {api_base}")

        # 检查URL是否已经包含/chat/completions路径，如果包含则移除
        if api_base and api_base.endswith('/chat/completions'):
            # 移除/chat/completions路径，只保留基础URL
            api_base = api_base.rsplit('/chat/completions', 1)[0]
            logger.warning(f"检测到API URL包含/chat/completions路径，已自动移除以避免路径重复。新URL: {api_base}")

        logger.debug(f"使用用户提供的API URL: {api_base}")

        # 完全尊重用户输入的URL，不做任何解析或修改
        # 用户负责提供正确的完整URL
        chat_params_extra = {}

        # 初始化 ChatOpenAI 客户端
        start_time = time.time()

        # 设置代理
        proxy = None
        # 记录已尝试过的代理，避免重复使用
        tried_proxies = set()

        if _use_proxy_manager:
            try:
                # 获取代理管理器
                proxy_manager = get_proxy_manager()

                # 检查是否有代理配置
                if proxy_manager and proxy_manager.proxy_configs:
                    # 有代理配置，使用代理
                    working_proxy = proxy_manager.find_working_proxy()
                    if working_proxy:
                        proxy = working_proxy.get_proxy_dict()
                        # 记录当前使用的代理名称，用于后续可能的切换
                        current_proxy_name = working_proxy.name
                        tried_proxies.add(current_proxy_name)
                        logger.info(f"LLM API使用代理管理器选择的代理: {current_proxy_name}")
                else:
                    logger.info("未配置代理，使用直连方式")
            except Exception as e:
                logger.warning(f"使用代理管理器时出错: {e}")

        # 如果代理管理器未提供代理，尝试使用环境变量
        if not proxy and os.environ.get('HTTP_PROXY'):
            proxy = {
                'http': os.environ.get('HTTP_PROXY'),
                'https': os.environ.get('HTTPS_PROXY', os.environ.get('HTTP_PROXY'))
            }
            logger.info("LLM API使用环境变量中的代理")

        # 创建ChatOpenAI实例的基本参数
        chat_params = {
            "model": model,
            "openai_api_base": api_base,  # 直接使用用户提供的URL
            "openai_api_key": api_key,
            "temperature": 0,
            "request_timeout": 60
        }

        # 如果有代理，通过环境变量设置（兼容所有API提供商）
        if proxy:
            logger.info(f"设置代理环境变量")
            # 统一使用环境变量设置代理，避免http_client_kwargs兼容性问题
            if 'http' in proxy:
                os.environ['HTTP_PROXY'] = proxy['http']
            if 'https' in proxy:
                os.environ['HTTPS_PROXY'] = proxy['https']
            logger.debug(f"已通过环境变量设置代理: HTTP_PROXY={os.environ.get('HTTP_PROXY')}, HTTPS_PROXY={os.environ.get('HTTPS_PROXY')}")

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
            response_time = end_time - start_time
            logger.debug(f"LLM响应时间: {response_time:.2f}秒")

            # 记录AI提供商使用成功
            if provider_id:
                record_provider_usage(provider_id, success=True)
                logger.info(f"AI提供商 ID: {provider_id} 成功使用，响应时间: {response_time:.2f}秒")

            # 获取token使用情况（如果可用）
            token_usage = None
            try:
                if hasattr(response, 'llm_output') and response.llm_output:
                    token_usage = response.llm_output.get('token_usage', None)
            except Exception as e:
                logger.debug(f"获取token使用情况时出错: {str(e)}")

            # 使用AI分析日志记录器记录请求结束
            if ai_logger:
                ai_logger.end_request(response.content, success=True, token_usage=token_usage)

            return response.content

        except Exception as api_error:
            error_message = str(api_error).lower()

            # 记录AI提供商使用失败
            if provider_id:
                record_provider_usage(provider_id, success=False, error_message=error_message)
                logger.warning(f"AI提供商 ID: {provider_id} 使用失败: {error_message}")

            # 使用AI分析日志记录器记录请求失败
            if ai_logger:
                ai_logger.end_request(None, success=False, error=api_error)

            # 尝试切换代理并重试
            if _use_proxy_manager and len(tried_proxies) < 3:  # 最多尝试3个不同的代理
                try:
                    # 获取代理管理器
                    proxy_manager = get_proxy_manager()

                    # 强制查找新的可用代理，排除已尝试过的代理
                    for _ in range(5):  # 最多尝试5次查找新代理
                        working_proxy = proxy_manager.find_working_proxy(force_check=True)
                        if working_proxy and working_proxy.name not in tried_proxies:
                            # 找到了新的未尝试过的代理
                            logger.info(f"API调用失败，尝试使用新的代理 {working_proxy.name} 重试")

                            # 更新代理设置
                            proxy = working_proxy.get_proxy_dict()
                            tried_proxies.add(working_proxy.name)

                            # 更新代理设置（统一使用环境变量）
                            logger.info(f"切换代理后设置环境变量")
                            # 统一使用环境变量设置代理，避免http_client_kwargs兼容性问题
                            if 'http' in proxy:
                                os.environ['HTTP_PROXY'] = proxy['http']
                            if 'https' in proxy:
                                os.environ['HTTPS_PROXY'] = proxy['https']
                            logger.debug(f"已通过环境变量设置代理: HTTP_PROXY={os.environ.get('HTTP_PROXY')}, HTTPS_PROXY={os.environ.get('HTTPS_PROXY')}")

                            # 重新创建ChatOpenAI实例并重试
                            chat = ChatOpenAI(**chat_params)

                            # 重新创建消息
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

                            # 重新获取响应
                            logger.debug(f"使用新代理重新请求LLM API，模型: {model}")

                            # 根据是否有reasoning_effort参数决定调用方式
                            if reasoning_effort:
                                logger.debug(f"使用reasoning_effort={reasoning_effort}调用API")
                                response = chat.invoke(messages, reasoning_effort=reasoning_effort)
                            else:
                                response = chat.invoke(messages)

                            end_time = time.time()
                            response_time = end_time - start_time
                            logger.debug(f"LLM响应时间: {response_time:.2f}秒")

                            # 记录AI提供商使用成功
                            if provider_id:
                                record_provider_usage(provider_id, success=True)
                                logger.info(f"使用新代理后，AI提供商 ID: {provider_id} 成功使用，响应时间: {response_time:.2f}秒")

                            # 使用AI分析日志记录器记录请求成功
                            if ai_logger:
                                ai_logger.end_request(response.content, success=True)

                            return response.content

                    # 如果尝试了多个代理但都没有找到新的可用代理
                    logger.warning("尝试了多个代理但未找到新的可用代理，继续抛出原始异常")

                except Exception as proxy_error:
                    logger.warning(f"尝试切换代理时出错: {str(proxy_error)}，继续抛出原始异常")

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

        # 尝试切换代理并重试
        if _use_proxy_manager and len(tried_proxies) < 3:  # 最多尝试3个不同的代理
            try:
                # 获取代理管理器
                proxy_manager = get_proxy_manager()

                # 强制查找新的可用代理，排除已尝试过的代理
                for _ in range(5):  # 最多尝试5次查找新代理
                    working_proxy = proxy_manager.find_working_proxy(force_check=True)
                    if working_proxy and working_proxy.name not in tried_proxies:
                        # 找到了新的未尝试过的代理
                        logger.info(f"外层异常处理：API调用失败，尝试使用新的代理 {working_proxy.name} 重试")

                        # 更新代理设置
                        proxy = working_proxy.get_proxy_dict()
                        tried_proxies.add(working_proxy.name)

                        # 重新创建ChatOpenAI实例并重试
                        # 创建ChatOpenAI实例的基本参数
                        chat_params = {
                            "model": model,
                            "openai_api_base": api_base,
                            "openai_api_key": api_key,
                            "temperature": 0,
                            "request_timeout": 60
                        }

                        # 设置代理环境变量（统一方式）
                        logger.info(f"外层异常处理：设置代理环境变量")
                        # 统一使用环境变量设置代理，避免http_client_kwargs兼容性问题
                        if 'http' in proxy:
                            os.environ['HTTP_PROXY'] = proxy['http']
                        if 'https' in proxy:
                            os.environ['HTTPS_PROXY'] = proxy['https']
                        logger.debug(f"已通过环境变量设置代理: HTTP_PROXY={os.environ.get('HTTP_PROXY')}, HTTPS_PROXY={os.environ.get('HTTPS_PROXY')}")

                        # 重新创建ChatOpenAI实例
                        chat = ChatOpenAI(**chat_params)

                        # 重新创建消息
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

                        # 重新获取响应
                        logger.debug(f"使用新代理重新请求LLM API，模型: {model}")

                        # 根据是否有reasoning_effort参数决定调用方式
                        if reasoning_effort:
                            logger.debug(f"使用reasoning_effort={reasoning_effort}调用API")
                            response = chat.invoke(messages, reasoning_effort=reasoning_effort)
                        else:
                            response = chat.invoke(messages)

                        end_time = time.time()
                        response_time = end_time - start_time
                        logger.debug(f"LLM响应时间: {response_time:.2f}秒")

                        # 记录AI提供商使用成功
                        if provider_id:
                            record_provider_usage(provider_id, success=True)
                            logger.info(f"使用新代理后，AI提供商 ID: {provider_id} 成功使用，响应时间: {response_time:.2f}秒")

                        # 使用AI分析日志记录器记录请求成功
                        if ai_logger:
                            ai_logger.end_request(response.content, success=True)

                        return response.content

                # 如果尝试了多个代理但都没有找到新的可用代理
                logger.warning("尝试了多个代理但未找到新的可用代理，继续抛出原始异常")

            except Exception as proxy_error:
                logger.warning(f"尝试切换代理时出错: {str(proxy_error)}，继续抛出原始异常")

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

            # 尝试进行网络诊断 - 使用更安全的方法
            try:
                import socket

                # 尝试解析域名
                domain = api_base.split("//")[-1].split("/")[0]
                logger.error(f"尝试解析域名: {domain}")
                try:
                    ip_address = socket.gethostbyname(domain)
                    logger.error(f"域名解析结果: {ip_address}")
                except Exception as dns_error:
                    logger.error(f"域名解析失败: {str(dns_error)}")

                # 尝试使用socket连接测试 - 这是最安全的方法，适用于Docker环境
                try:
                    # 创建socket连接测试
                    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                    s.settimeout(2)
                    port = 443 if api_base.startswith('https') else 80
                    result = s.connect_ex((domain, port))
                    s.close()

                    if result == 0:
                        logger.error(f"连接测试成功: 可以连接到 {domain}:{port}")
                    else:
                        logger.error(f"连接测试失败: 无法连接到 {domain}:{port}, 错误码: {result}")
                except Exception as conn_error:
                    logger.error(f"连接测试失败: {str(conn_error)}")

                # 不再尝试使用ping命令，因为它在Docker容器中通常不可用
                logger.error("跳过ping测试，在Docker容器中通常不可用")

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

            # 使用AI分析日志记录器记录请求失败
            if ai_logger:
                ai_logger.end_request(None, success=False, error=e)

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

def get_llm_response_with_cache(prompt: str, use_cache: bool = True, provider_id=None, api_key=None, api_base=None, model=None) -> tuple:
    """
    带缓存的LLM响应获取，支持多AI提供商

    Args:
        prompt: 提示词
        use_cache: 是否使用缓存
        provider_id: AI提供商ID，用于记录使用情况
        api_key: API密钥，如果为None则使用默认配置
        api_base: API基础URL，如果为None则使用默认配置
        model: 模型名称，如果为None则使用默认配置

    Returns:
        tuple: (响应内容, 提供商信息字典)
    """
    # 使用AI分析日志记录器记录提供商选择
    if ai_logger and provider_id:
        ai_logger.log_provider_selection(provider_id, model or "未指定")
    # 如果没有指定AI提供商，尝试获取下一个可用的提供商
    if not provider_id and not api_key:
        try:
            # 获取下一个可用的AI提供商
            next_provider_id, next_api_key, next_api_base, next_model = get_next_ai_provider()

            # 如果成功获取到提供商，使用其配置
            if next_provider_id and next_api_key:
                provider_id = next_provider_id
                api_key = next_api_key
                if next_api_base:
                    api_base = next_api_base
                if next_model:
                    model = next_model

                logger.info(f"使用AI提供商ID: {provider_id}")
        except Exception as e:
            logger.warning(f"获取下一个AI提供商时出错: {str(e)}")

    # 创建提供商信息字典
    provider_info = {
        "provider_id": provider_id,
        "model": model
    }

    if not use_cache:
        response = get_llm_response(prompt, provider_id, api_key, api_base, model)
        return response, provider_info

    # 计算提示词的哈希值作为缓存键
    prompt_hash = hashlib.md5(prompt.encode()).hexdigest()

    # 检查缓存
    try:
        # 尝试从缓存获取响应
        cached = _cached_response(prompt_hash, None)
        if cached is not None:
            logger.debug(f"缓存命中: {prompt_hash[:8]}...")
            provider_info["cached"] = True

            # 使用AI分析日志记录器记录缓存命中
            if ai_logger:
                ai_logger.log_cache_operation("读取", prompt_hash)
                # 记录一个完整的请求-响应周期，但标记为缓存命中
                request_id = ai_logger.start_request(prompt, provider_id, model)
                ai_logger.end_request(cached, success=True, cached=True)

            return cached, provider_info
    except Exception:
        # 如果缓存查询失败，忽略错误
        pass

    # 缓存未命中或查询失败，调用API
    response = get_llm_response(prompt, provider_id, api_key, api_base, model)
    provider_info["cached"] = False

    # 更新缓存
    try:
        _cached_response(prompt_hash, response)
        # 使用AI分析日志记录器记录缓存更新
        if ai_logger:
            ai_logger.log_cache_operation("写入", prompt_hash)
    except Exception as e:
        logger.warning(f"更新缓存失败: {str(e)}")
        # 使用AI分析日志记录器记录缓存更新失败
        if ai_logger:
            ai_logger.log_cache_operation("写入", prompt_hash, success=False, error=e)

    return response, provider_info
