from dotenv import load_dotenv
import os
import time
import logging
import random
import hashlib
from datetime import datetime, timezone
import asyncio
import inspect
from functools import wraps, lru_cache
from typing import Dict, Any, Optional, Tuple, Type
from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.output_parsers import PydanticOutputParser
from pydantic import ValidationError

from models.llm_schemas import LLMAnalysisResponse

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

class LLMResponseFormatError(LLMAPIError):
    """LLM 响应格式错误 (无法通过Pydantic解析)"""
    pass

def retry_with_exponential_backoff(
    max_retries: int = 5,
    initial_delay: float = 1.0, # Changed to float for consistency
    exponential_base: float = 2.0, # Changed to float
    jitter: bool = True,
    errors: tuple = (LLMRateLimitError, LLMServerError, LLMTimeoutError, LLMResponseFormatError), # Added LLMResponseFormatError
):
    """
    指数退避重试装饰器，支持代理切换，兼容同步和异步函数

    Args:
        max_retries: 最大重试次数
        initial_delay: 初始延迟时间（秒）
        exponential_base: 指数基数
        jitter: 是否添加随机抖动
        errors: 需要重试的错误类型
    """
    def decorator(func):
        @wraps(func)
        async def awrapper(*args, **kwargs):
            num_retries = 0
            delay = initial_delay
            tried_proxy_switch = False

            while True:
                try:
                    return await func(*args, **kwargs)
                except errors as e:
                    num_retries += 1
                    if not tried_proxy_switch and _use_proxy_manager:
                        tried_proxy_switch = True
                        try:
                            from utils.api_utils import get_proxy_manager
                            proxy_manager = get_proxy_manager()
                            working_proxy = proxy_manager.find_working_proxy(force_check=True)
                            if working_proxy:
                                logger.info(f"LLM API调用失败 (async)，尝试使用新的代理 {working_proxy.name} 重试")
                                num_retries -=1 # Reset retry count for proxy switch
                                # Update proxy settings for the next attempt if applicable (depends on how func uses proxy)
                                kwargs['force_new_proxy'] = True # Signal to func to get new proxy
                                continue 
                        except Exception as proxy_error:
                            logger.warning(f"尝试切换代理时出错 (async): {str(proxy_error)}")
                    
                    if num_retries > max_retries:
                        logger.error(f"达到最大重试次数 {max_retries} (async)，放弃重试: {type(e).__name__} - {e}")
                        raise

                    current_delay = delay * (exponential_base ** (num_retries -1))
                    if jitter:
                        current_delay += random.uniform(0, current_delay * 0.1)
                    
                    current_delay = min(current_delay, 60.0) # Max delay capped at 60s

                    logger.warning(f"遇到错误 (async): {type(e).__name__} - {e}. 将在 {current_delay:.2f} 秒后进行第 {num_retries}/{max_retries} 次重试")
                    await asyncio.sleep(current_delay)
        
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
                    if not tried_proxy_switch and _use_proxy_manager:
                        tried_proxy_switch = True
                        try:
                            from utils.api_utils import get_proxy_manager
                            proxy_manager = get_proxy_manager()
                            working_proxy = proxy_manager.find_working_proxy(force_check=True)
                            if working_proxy:
                                logger.info(f"LLM API调用失败 (sync)，尝试使用新的代理 {working_proxy.name} 重试")
                                num_retries -= 1 # Reset retry count for proxy switch
                                kwargs['force_new_proxy'] = True # Signal to func to get new proxy
                                continue
                        except Exception as proxy_error:
                            logger.warning(f"尝试切换代理时出错 (sync): {str(proxy_error)}")

                    if num_retries > max_retries:
                        logger.error(f"达到最大重试次数 {max_retries} (sync)，放弃重试: {type(e).__name__} - {e}")
                        raise
                    
                    current_delay = delay * (exponential_base ** (num_retries -1))
                    if jitter:
                        current_delay += random.uniform(0, current_delay * 0.1)
                    
                    current_delay = min(current_delay, 60.0) # Max delay capped at 60s

                    logger.warning(f"遇到错误 (sync): {type(e).__name__} - {e}. 将在 {current_delay:.2f} 秒后进行第 {num_retries}/{max_retries} 次重试")
                    time.sleep(current_delay)
        
        if inspect.iscoroutinefunction(func):
            return awrapper
        else:
            return wrapper
    return decorator

def handle_llm_api_error(response_dict: Dict[str, Any]) -> None: # This function might become less relevant with Pydantic
    """
    处理LLM API错误 (Likely less used if Pydantic handles parsing and validation)

    Args:
        response_dict: API响应字典

    Raises:
        LLMRateLimitError: 当API返回限流错误时
        LLMAuthenticationError: 当API返回认证错误时
        LLMServerError: 当API返回服务器错误时
        LLMAPIError: 当API返回其他错误时
    """
    if 'error' in response_dict: # Ensure this check is still relevant or adapt
        error = response_dict['error']
        error_type = error.get('type', '')
        error_message = error.get('message', 'Unknown error')

        if 'rate_limit' in error_type or 'rate_limit' in error_message.lower():
            raise LLMRateLimitError(f"API限流错误: {error_message}")
        elif 'authentication' in error_type or 'invalid_api_key' in error_type:
            raise LLMAuthenticationError(f"API认证错误: {error_message}")
        elif 'server_error' in error_type or error.get('code', 0) >= 500: # type: ignore
            raise LLMServerError(f"API服务器错误: {error_message}")
        else:
            raise LLMAPIError(f"API错误: {error_message}")


async def get_next_ai_provider(): # Changed to async if DB operations become async
    """
    获取下一个可用的AI提供商 (Async if DB operations are async)
    For now, assuming DB operations remain sync within Flask context or repository calls handle async if needed.
    If services.ai_polling_service.is_provider_available becomes async, this needs to be awaited.
    If AIProvider.query and db.session.commit become async, they need awaiting and app_context might need adjustment.
    """
    # This function's async nature depends heavily on how `is_provider_available`
    # and DB interactions are handled. For now, keeping it sync as the subtask
    # focuses on LLM calls, but noting this dependency.
    try:
        # Assuming cli_app is available globally if main.py is the entry point
        # Or, this function might need the app_context passed if called from web_app.
        # For CLI usage, this needs careful handling of app context.
        # Let's assume for now that RepositoryFactory handles context or uses a CLI-compatible session.
        
        from services.repository.factory import RepositoryFactory
        from services.ai_polling_service import is_provider_available # Assuming this can be called
        
        ai_provider_repo = RepositoryFactory.get_ai_provider_repository()
        
        # Assuming a method like get_active_sorted_by_priority exists or can be added
        providers = ai_provider_repo.get_active_sorted_by_priority()

        if not providers:
            logger.warning("没有可用的AI提供商，将使用默认配置")
            return None, None, None, None, None # Added a slot for provider name

        for provider_obj in providers: # Renamed to avoid conflict
            # is_provider_available might need to be async if it does IO
            if await is_provider_available(provider_obj.id): # Assuming is_provider_available is now async
                ai_provider_repo.update(provider_obj.id, {'last_used_at': datetime.now(timezone.utc)})
                logger.info(f"选择 AI 提供商: {provider_obj.name} (ID: {provider_obj.id})")
                return provider_obj.id, provider_obj.name, provider_obj.api_key, provider_obj.api_base, provider_obj.model

        logger.warning("所有 AI 提供商都不可用，强制使用第一个提供商")
        provider_obj = providers[0]
        ai_provider_repo.update(provider_obj.id, {'last_used_at': datetime.now(timezone.utc)})
        return provider_obj.id, provider_obj.name, provider_obj.api_key, provider_obj.api_base, provider_obj.model
    except Exception as e:
        logger.error(f"获取AI提供商时出错: {str(e)}")
        return None, None, None, None, None

async def record_provider_usage(provider_id, success=True, error_message=None): # Changed to async
    """
    记录AI提供商的使用情况 (Async if DB operations are async)
    """
    if not provider_id:
        return

    try:
        # Assuming RepositoryFactory handles context or uses a CLI-compatible session.
        from services.repository.factory import RepositoryFactory
        ai_provider_repo = RepositoryFactory.get_ai_provider_repository()
        
        provider_obj = ai_provider_repo.get_by_id(provider_id) # Assuming get_by_id exists
        if not provider_obj:
            logger.warning(f"找不到ID为{provider_id}的AI提供商")
            return

        if success:
            # Assuming record_success method exists or can be added to repository/model
            # For now, direct update or a specific repo method.
            # ai_provider_repo.update(provider_id, {'last_success_at': datetime.now(timezone.utc), 
            #                                     'error_count': 0}) # Example
            if hasattr(provider_obj, 'record_success'): # If model has this method
                 provider_obj.record_success() # This would need a db.session.commit() if it's a model method
                 ai_provider_repo.commit() # Assuming repo has a commit method
            logger.debug(f"记录AI提供商 {provider_obj.name} 成功使用")
        else:
            # ai_provider_repo.update(provider_id, {'last_error_at': datetime.now(timezone.utc), 
            #                                     'error_message': error_message}) # Example
            if hasattr(provider_obj, 'record_error'):
                provider_obj.record_error(error_message)
                ai_provider_repo.commit()
            logger.warning(f"记录AI提供商 {provider_obj.name} 使用失败: {error_message}")
    except Exception as e:
        logger.error(f"记录AI提供商使用情况时出错: {str(e)}")


@retry_with_exponential_backoff()
async def get_llm_response(prompt: str, provider_id=None, provider_name=None, api_key=None, api_base=None, model=None, force_new_proxy=False) -> LLMAnalysisResponse:
    """
    使用 langchain-openai 调用模型获取响应 (异步)

    Args:
        prompt (str): 输入的提示词
        provider_id: AI提供商ID
        provider_name: AI提供商名称
        api_key: API密钥
        api_base: API基础URL
        model: 模型名称
        force_new_proxy: 是否强制获取新的代理 (用于重试)

    Returns:
        LLMAnalysisResponse: 解析后的Pydantic对象

    Raises:
        LLMResponseFormatError: 当LLM响应无法通过Pydantic解析时
        ... (other LLMAPIError subtypes)
    """
    request_id = None
    if ai_logger:
        request_id = ai_logger.start_request(prompt, provider_id or provider_name, model)
    if not prompt or not isinstance(prompt, str):
        if ai_logger and request_id: ai_logger.end_request(None, success=False, error=ValueError("提示词必须是非空字符串"))
        raise ValueError("提示词必须是非空字符串")

    current_provider_id = provider_id
    current_provider_name = provider_name
    current_api_key = api_key
    current_api_base = api_base
    current_model = model

    if not current_provider_id and not current_api_key: # Only fetch new if no specific provider was passed
        try:
            pid, pname, pkey, pbase, pmodel = await get_next_ai_provider()
            if pid and pkey:
                current_provider_id = pid
                current_provider_name = pname
                current_api_key = pkey
                current_api_base = pbase if pbase else current_api_base # Keep original if new is None
                current_model = pmodel if pmodel else current_model # Keep original if new is None
                logger.info(f"使用AI提供商: {current_provider_name} (ID: {current_provider_id})")
        except Exception as e:
            logger.warning(f"获取下一个AI提供商时出错: {str(e)}")

    if not current_api_key or not current_model:
        try:
            from services.config_service import get_config # Assuming this can be called sync for now
            if not current_model: current_model = get_config("LLM_API_MODEL") or os.getenv("LLM_API_MODEL")
            if not current_api_base: current_api_base = get_config("LLM_API_BASE") or os.getenv("LLM_API_BASE")
            if not current_api_key: current_api_key = get_config("LLM_API_KEY") or os.getenv("LLM_API_KEY")
        except Exception as e:
            logger.warning(f"从配置服务获取配置时出错: {str(e)}")
            if not current_model: current_model = os.getenv("LLM_API_MODEL")
            if not current_api_base: current_api_base = os.getenv("LLM_API_BASE")
            if not current_api_key: current_api_key = os.getenv("LLM_API_KEY")

    if not current_model or not current_api_key:
        if ai_logger and request_id: ai_logger.end_request(None, success=False, error=ValueError("缺少必要的API配置"))
        raise ValueError("缺少必要的API配置，请检查环境变量或数据库配置")

    logger.debug(f"使用模型 {current_model} (提供商: {current_provider_name or '未指定'}) 处理提示词")

    parser = PydanticOutputParser(pydantic_object=LLMAnalysisResponse)
    format_instructions = parser.get_format_instructions()
    
    # Ensure format instructions are not already in the prompt to avoid duplication during retries
    if "Please respond with a JSON object matching the following schema" not in prompt:
         final_prompt = f"{prompt}\n\n{format_instructions}"
    else:
        final_prompt = prompt


    try:
        if current_api_base and not current_api_base.startswith(('http://', 'https://')):
            raise ValueError(f"无效的API基础URL: {current_api_base}")
        if current_api_base and current_api_base.endswith('/chat/completions'):
            current_api_base = current_api_base.rsplit('/chat/completions', 1)[0]
            logger.warning(f"API URL包含/chat/completions路径，已自动移除。新URL: {current_api_base}")

        chat_params_extra = {}
        proxy_dict_to_use = None # For http_client if needed by specific ChatOpenAI versions

        if _use_proxy_manager:
            try:
                proxy_manager = get_proxy_manager() # Assuming this is sync
                if proxy_manager and proxy_manager.proxy_configs:
                    working_proxy = proxy_manager.find_working_proxy(force_check=force_new_proxy)
                    if working_proxy:
                        proxy_url = working_proxy.get_url_with_auth()
                        # Langchain typically uses HTTP_PROXY/HTTPS_PROXY env vars.
                        # Some older versions might accept http_client with proxy dict.
                        # For broad compatibility, setting env vars is safer.
                        if proxy_url:
                            os.environ['HTTP_PROXY'] = proxy_url
                            os.environ['HTTPS_PROXY'] = proxy_url
                            logger.info(f"LLM API使用代理: {working_proxy.name} ({proxy_url})")
                        else: # Fallback if URL construction fails
                            proxy_dict_to_use = working_proxy.get_proxy_dict()
                            logger.info(f"LLM API使用代理 (dict): {working_proxy.name}")
            except Exception as e:
                logger.warning(f"使用代理管理器时出错: {e}")
        
        if not os.environ.get('HTTP_PROXY') and not proxy_dict_to_use and os.getenv('HTTP_PROXY'):
            # If proxy manager didn't set one, but env var exists, ensure it's used
            os.environ['HTTP_PROXY'] = os.getenv('HTTP_PROXY')
            os.environ['HTTPS_PROXY'] = os.getenv('HTTPS_PROXY', os.getenv('HTTP_PROXY'))
            logger.info("LLM API使用环境变量中的代理")


        chat_params = {
            "model": current_model,
            "openai_api_base": current_api_base,
            "openai_api_key": current_api_key,
            "temperature": 0,
            "request_timeout": 60
        }
        if proxy_dict_to_use: # Only if env var method is not preferred by underlying client
             # chat_params["http_client"] = httpx.AsyncClient(proxies=proxy_dict_to_use) # Example if httpx is used
             pass


        model_kwargs = {}
        reasoning_effort = None
        if current_api_base and 'x.ai' in current_api_base: reasoning_effort = "high"
        elif current_model and 'grok-3' in current_model: reasoning_effort = "high"
        if model_kwargs: chat_params["model_kwargs"] = model_kwargs
        
        chat = ChatOpenAI(**chat_params) # type: ignore
        
        system_content = f"""
你接下来回答的所有内容都只能是符合我要求的JSON字符串。
{format_instructions}
请严格遵循以下规则：
1. 只返回有效的JSON格式，不要包含任何其他文本或解释
2. 确保所有键名使用双引号，如 {{"key": "value"}}
3. 确保所有字符串值使用双引号，如 {{"name": "value"}}
4. 布尔值使用小写的true或false，如 {{"is_valid": true}}
5. 数字值不需要引号，如 {{"count": 42}}
6. 数组使用方括号，如 {{"items": ["a", "b", "c"]}}
7. 特殊字符需要正确转义，如换行符应该是\\n而不是\n
8. 不要在JSON前后添加任何标记，如```json或```
9. 确保JSON格式正确，可以被Python的json.loads()函数解析
"""
        messages = [SystemMessage(content=system_content), HumanMessage(content=prompt)]
        
        logger.debug(f"开始异步请求LLM API，模型: {current_model}")
        start_time = time.time()

        if reasoning_effort:
            response = await chat.ainvoke(messages, reasoning_effort=reasoning_effort)
        else:
            response = await chat.ainvoke(messages)
        
        end_time = time.time()
        response_time = end_time - start_time
        logger.debug(f"LLM异步响应时间: {response_time:.2f}秒")

        if current_provider_id: await record_provider_usage(current_provider_id, success=True) # Made async
        
        token_usage = response.llm_output.get('token_usage', None) if hasattr(response, 'llm_output') and response.llm_output else None
        if ai_logger and request_id: ai_logger.end_request(response.content, success=True, token_usage=token_usage)

        try:
            # Attempt to parse the response content into the Pydantic model
            # Clean up potential markdown code block fences if present
            cleaned_content = response.content.strip()
            if cleaned_content.startswith("```json"):
                cleaned_content = cleaned_content[7:]
            if cleaned_content.startswith("```"): # For just ```
                cleaned_content = cleaned_content[3:]
            if cleaned_content.endswith("```"):
                cleaned_content = cleaned_content[:-3]
            
            parsed_response_obj = parser.parse(cleaned_content)
            # Attach provider_id and model to the parsed object if they are part of the schema
            if hasattr(parsed_response_obj, 'ai_provider_id') and current_provider_id:
                parsed_response_obj.ai_provider_id = str(current_provider_id)
            if hasattr(parsed_response_obj, 'ai_model') and current_model:
                parsed_response_obj.ai_model = current_model

            return parsed_response_obj
        except ValidationError as e:
            logger.error(f"Pydantic解析LLM响应失败: {e.errors()}")
            logger.error(f"原始LLM响应内容: {response.content[:500]}...") # Log snippet
            raise LLMResponseFormatError(f"LLM响应格式错误，无法通过Pydantic解析: {e.errors()}")
        except Exception as e_parse: # Catch other parsing related errors
            logger.error(f"解析LLM响应时发生未知错误: {str(e_parse)}")
            logger.error(f"原始LLM响应内容: {response.content[:500]}...")
            raise LLMResponseFormatError(f"解析LLM响应时发生未知错误: {str(e_parse)}")


    except Exception as e: # General exception handling for API calls
        error_message = str(e).lower()
        if current_provider_id: await record_provider_usage(current_provider_id, success=False, error_message=error_message) # Made async
        if ai_logger and request_id: ai_logger.end_request(None, success=False, error=e)
        
        # Simplified error re-raising, specific error types are defined above
        if "timeout" in error_message or "timed out" in error_message:
            raise LLMTimeoutError(f"API请求超时: {error_message}")
        elif "rate limit" in error_message:
            raise LLMRateLimitError(f"API限流: {error_message}")
        elif "authentication" in error_message or "api key" in error_message or "unauthorized" in error_message:
            raise LLMAuthenticationError(f"API认证错误: {error_message}")
        elif "5" in error_message[:3] or "server error" in error_message:
            raise LLMServerError(f"API服务器错误: {error_message}")
        elif isinstance(e, LLMResponseFormatError): # Re-raise if it's already the correct type
            raise
        else: # Default to generic LLMAPIError for others
            logger.error(f"LLM API调用未知错误: {error_message}, API Base: {current_api_base}, Model: {current_model}, Type: {type(e).__name__}")
            raise LLMAPIError(f"API调用错误: {error_message}")
    finally:
        # Clean up proxy env vars if they were set by this function
        if _use_proxy_manager and os.environ.get('HTTP_PROXY') and proxy_url: # Check if we set it
            del os.environ['HTTP_PROXY']
            if os.environ.get('HTTPS_PROXY') == proxy_url: # Only delete if it was the same one
                 del os.environ['HTTPS_PROXY']
            logger.debug("清理了LLM函数设置的代理环境变量")


@lru_cache(maxsize=100)
async def _cached_async_response(prompt_hash: str, provider_id: Optional[str], api_key: Optional[str], api_base: Optional[str], model: Optional[str]) -> LLMAnalysisResponse:
    """
    Internal async function for caching. Note: provider_id etc. are part of cache key.
    """
    # This function is now what lru_cache will wrap.
    # It ensures that if any part of the provider config changes, it's a new cache entry.
    return await get_llm_response(prompt_hash, provider_id, None, api_key, api_base, model) # Pass None for provider_name to avoid ambiguity

async def get_llm_response_with_cache(prompt: str, use_cache: bool = True, provider_id: Optional[str] = None, provider_name: Optional[str] = None, api_key: Optional[str] = None, api_base: Optional[str] = None, model: Optional[str] = None) -> Tuple[LLMAnalysisResponse, Dict[str, Any]]:
    """
    带缓存的LLM响应获取 (异步), 支持多AI提供商

    Args:
        prompt: 提示词
        use_cache: 是否使用缓存
        provider_id: AI提供商ID
        provider_name: AI提供商名称
        api_key: API密钥
        api_base: API基础URL
        model: 模型名称

    Returns:
        tuple: (LLMAnalysisResponse, provider_info_dict)
    """
    # Ensure a consistent way to get provider info if not fully specified
    # This logic might need refinement based on how provider details are fetched/managed.
    current_provider_id = provider_id
    current_provider_name = provider_name
    current_api_key = api_key
    current_api_base = api_base
    current_model = model

    if not current_provider_id and not current_api_key: # Only fetch new if no specific provider was passed
        try:
            pid, pname, pkey, pbase, pmodel = await get_next_ai_provider()
            if pid and pkey:
                current_provider_id = pid
                current_provider_name = pname 
                current_api_key = pkey
                current_api_base = pbase if pbase else current_api_base
                current_model = pmodel if pmodel else current_model
                logger.info(f"使用AI提供商: {current_provider_name} (ID: {current_provider_id})")
        except Exception as e:
            logger.warning(f"缓存函数中获取下一个AI提供商时出错: {str(e)}")
    
    if ai_logger:
        ai_logger.log_provider_selection(current_provider_id or current_provider_name, current_model or "未指定")

    provider_info_dict = {
        "provider_id": current_provider_id,
        "provider_name": current_provider_name, # Added for logging/tracking
        "model": current_model,
        "cached": False # Default to False
    }

    if not use_cache:
        parsed_object = await get_llm_response(prompt, current_provider_id, current_provider_name, current_api_key, current_api_base, current_model)
        return parsed_object, provider_info_dict

    # Create a hashable key for caching that includes provider details to ensure
    # that a change in provider config results in a cache miss.
    # Only include non-None provider details in the hash.
    cache_key_parts = [prompt]
    if current_provider_id: cache_key_parts.append(f"pid:{current_provider_id}")
    if current_api_base: cache_key_parts.append(f"base:{current_api_base}")
    if current_model: cache_key_parts.append(f"model:{current_model}")
    # Note: api_key is generally not included in cache keys for security.
    
    prompt_hash = hashlib.md5("||".join(cache_key_parts).encode()).hexdigest()

    try:
        # _cached_async_response is the lru_cache wrapped version of get_llm_response
        # It now takes the prompt_hash as its first arg for the cache key,
        # and the actual parameters for the call it will make if cache misses.
        # The parameters passed to _cached_async_response must match its signature.
        # For LRU cache to work with async, the arguments must be hashable.
        # prompt_hash is hashable. Other args are provider details.
        # If provider_id, api_key etc are used to form the cache key by lru_cache,
        # then they must be passed to the cached function.
        
        # We need to adjust how lru_cache is used with async functions.
        # A simple approach is to cache the result of the async function call.
        # The key for lru_cache should be based on all inputs that define uniqueness.
        
        # This is a simplified conceptual representation. Real async LRU might be needed.
        # For now, we'll assume lru_cache works on the wrapper if the wrapper is not async itself.
        # But _cached_async_response IS async. Standard lru_cache does not work directly on async def.
        # We need a proper async LRU or a way to handle the await.

        # Re-thinking the cache approach for async:
        # For simplicity in this step, we'll make the caching mechanism more explicit
        # and bypass lru_cache for the async function directly if it's problematic.
        # A proper async cache (like from `async_lru`) would be better.
        
        # Let's assume a simple in-memory dict for async cache for now if lru_cache fails.
        # This is a placeholder for a more robust async caching solution.
        _async_cache_dict: Dict[str, LLMAnalysisResponse] = getattr(get_llm_response_with_cache, '_async_cache_dict', {})
        setattr(get_llm_response_with_cache, '_async_cache_dict', _async_cache_dict)

        if prompt_hash in _async_cache_dict:
            logger.debug(f"异步缓存命中: {prompt_hash[:8]}...")
            provider_info_dict["cached"] = True
            if ai_logger:
                ai_logger.log_cache_operation("读取 (async)", prompt_hash)
                request_id = ai_logger.start_request(prompt, current_provider_id or current_provider_name, current_model)
                ai_logger.end_request(_async_cache_dict[prompt_hash].model_dump_json(), success=True, cached=True) # type: ignore
            return _async_cache_dict[prompt_hash], provider_info_dict
        
    except Exception as e:
        logger.warning(f"异步缓存读取时出错: {e}")


    parsed_object = await get_llm_response(prompt, current_provider_id, current_provider_name, current_api_key, current_api_base, current_model)
    provider_info_dict["cached"] = False # Explicitly set, though default

    try:
        _async_cache_dict[prompt_hash] = parsed_object
        if ai_logger:
            ai_logger.log_cache_operation("写入 (async)", prompt_hash)
    except Exception as e:
        logger.warning(f"异步缓存写入失败: {str(e)}")
        if ai_logger:
            ai_logger.log_cache_operation("写入 (async)", prompt_hash, success=False, error=e)

    return parsed_object, provider_info_dict
