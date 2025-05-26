"""
AI轮询服务
提供智能负载均衡、健康检查和缓存功能
"""

import os
import time
import json
import hashlib
import logging
import threading
import traceback
import requests
from datetime import datetime, timedelta, timezone
from typing import Dict, Any, List, Optional, Tuple, Union

from services.config_service import get_config

# 延迟导入，避免循环导入问题
def get_db():
    """获取数据库对象"""
    from web_app import db
    return db

def get_ai_provider_model():
    """获取AI提供商模型"""
    from models.ai_provider import AIProvider
    return AIProvider

def get_ai_request_log_model():
    """获取AI请求日志模型"""
    from models.ai_request_log import AIRequestLog
    return AIRequestLog

# 导入自定义日志记录器
from utils.logger import get_logger

# 创建日志记录器
logger = get_logger('llm')

# 内存缓存
_cache = {}
_cache_lock = threading.Lock()

# 健康检查状态
_health_status = {}
_health_status_lock = threading.Lock()

# 批处理队列
_batch_queue = {}
_batch_queue_lock = threading.Lock()

# 工作线程
_worker_thread = None
_worker_running = False
_last_run_time = None
_health_check_count = 0
_cache_hit_count = 0
_cache_miss_count = 0
_batch_processed_count = 0

def get_available_providers(media_type: str = 'text') -> List:
    """
    获取可用的AI提供商列表，按优先级排序

    Args:
        media_type: 媒体类型，可选值：text, image, video, gif

    Returns:
        List: 可用的AI提供商列表
    """
    try:
        # 获取AI提供商模型
        AIProvider = get_ai_provider_model()

        # 构建查询条件
        query = AIProvider.query.filter_by(is_active=True)

        # 根据媒体类型筛选
        if media_type == 'text':
            query = query.filter_by(supports_text=True)
        elif media_type == 'image':
            query = query.filter_by(supports_image=True)
        elif media_type == 'video':
            query = query.filter_by(supports_video=True)
        elif media_type == 'gif':
            query = query.filter_by(supports_gif=True)

        # 获取所有符合条件的提供商
        providers = query.order_by(AIProvider.priority).all()

        # 过滤不可用的提供商
        result = []
        for provider in providers:
            if is_provider_available(provider.id):
                result.append(provider)

        return result
    except Exception as e:
        logger.error(f"获取可用AI提供商失败: {str(e)}")
        return []

def reset_provider_availability():
    """
    重置所有 AI 提供商的可用性状态
    每隔一段时间运行一次，给不可用的提供商恢复的机会
    """
    try:
        # 清除旧的请求日志，只保留最近的记录
        AIRequestLog = get_ai_request_log_model()
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=1)

        # 使用应用上下文
        from web_app import app, db
        with app.app_context():
            # 删除旧的请求日志
            AIRequestLog.query.filter(AIRequestLog.created_at < cutoff_time).delete()
            db.session.commit()

            logger.info("已重置 AI 提供商可用性状态")
            return True
    except Exception as e:
        logger.error(f"重置 AI 提供商可用性状态时出错: {str(e)}")
        try:
            from web_app import db
            db.session.rollback()
        except:
            pass
        return False

def is_provider_available(provider_id: int) -> bool:
    """
    检查 AI 提供商是否可用

    Args:
        provider_id: 提供商 ID

    Returns:
        bool: 是否可用
    """
    try:
        # 获取提供商的最近几次请求记录
        AIRequestLog = get_ai_request_log_model()

        recent_logs = AIRequestLog.query.filter_by(provider_id=provider_id).order_by(
            AIRequestLog.created_at.desc()
        ).limit(5).all()

        # 如果没有记录，假设可用
        if not recent_logs:
            return True

        # 计算成功率
        success_count = sum(1 for log in recent_logs if log.is_success)

        # 如果最近 5 次中成功 3 次以上，认为可用
        return success_count >= 3

    except Exception as e:
        logger.error(f"检查提供商可用性时出错: {str(e)}")
        # 出错时假设可用，避免完全无法使用
        return True

def get_cache_key(content: str, model: str, provider_id: Optional[int] = None) -> str:
    """
    生成缓存键

    Args:
        content: 请求内容
        model: 模型名称
        provider_id: 提供商ID

    Returns:
        str: 缓存键
    """
    # 规范化内容，去除空白字符
    normalized_content = ' '.join(content.split())

    # 生成哈希
    key_parts = [normalized_content, model]
    if provider_id:
        key_parts.append(str(provider_id))

    key_str = '|'.join(key_parts)
    return hashlib.md5(key_str.encode('utf-8')).hexdigest()

def get_from_cache(cache_key: str) -> Optional[Dict[str, Any]]:
    """
    从缓存中获取结果

    Args:
        cache_key: 缓存键

    Returns:
        Optional[Dict[str, Any]]: 缓存结果
    """
    global _cache_hit_count, _cache_miss_count

    # 检查缓存是否启用
    if get_config('AI_CACHE_ENABLED', 'true').lower() != 'true':
        _cache_miss_count += 1
        return None

    with _cache_lock:
        if cache_key in _cache:
            cache_item = _cache[cache_key]
            # 检查是否过期
            now = datetime.now(timezone.utc)
            if now < cache_item['expires_at']:
                _cache_hit_count += 1
                return cache_item['data']
            else:
                # 过期，删除缓存
                del _cache[cache_key]

    _cache_miss_count += 1
    return None

def save_to_cache(cache_key: str, data: Dict[str, Any], ttl_seconds: int = None) -> None:
    """
    保存结果到缓存

    Args:
        cache_key: 缓存键
        data: 缓存数据
        ttl_seconds: 缓存有效期（秒）
    """
    # 检查缓存是否启用
    if get_config('AI_CACHE_ENABLED', 'true').lower() != 'true':
        return

    # 获取缓存TTL
    if ttl_seconds is None:
        ttl_seconds = int(get_config('AI_CACHE_TTL', '3600'))

    # 计算过期时间
    expires_at = datetime.now(timezone.utc) + timedelta(seconds=ttl_seconds)

    with _cache_lock:
        # 清理过期缓存
        now = datetime.now(timezone.utc)
        expired_keys = [k for k, v in _cache.items() if now >= v['expires_at']]
        for k in expired_keys:
            del _cache[k]

        # 保存新缓存
        _cache[cache_key] = {
            'data': data,
            'expires_at': expires_at,
            'created_at': datetime.now(timezone.utc)
        }

def clear_cache() -> int:
    """
    清空缓存

    Returns:
        int: 清除的缓存项数量
    """
    with _cache_lock:
        count = len(_cache)
        _cache.clear()
        return count

def get_cache_stats() -> Dict[str, Any]:
    """
    获取缓存统计信息

    Returns:
        Dict[str, Any]: 缓存统计信息
    """
    with _cache_lock:
        # 计算缓存大小
        cache_size = sum(len(json.dumps(v['data'])) for v in _cache.values())

        # 计算命中率
        total_requests = _cache_hit_count + _cache_miss_count
        hit_rate = _cache_hit_count / total_requests if total_requests > 0 else 0

        return {
            'cache_items': len(_cache),
            'cache_size_bytes': cache_size,
            'cache_hit_count': _cache_hit_count,
            'cache_miss_count': _cache_miss_count,
            'cache_hit_rate': hit_rate,
            'enabled': get_config('AI_CACHE_ENABLED', 'true').lower() == 'true',
            'ttl_seconds': int(get_config('AI_CACHE_TTL', '3600'))
        }

def add_to_batch_queue(content: str, model: str, provider_id: Optional[int] = None) -> str:
    """
    添加请求到批处理队列

    Args:
        content: 请求内容
        model: 模型名称
        provider_id: 提供商ID

    Returns:
        str: 批处理ID
    """
    # 检查批处理是否启用
    if get_config('AI_BATCH_ENABLED', 'false').lower() != 'true':
        return None

    # 生成批处理ID
    batch_id = hashlib.md5(f"{content}|{model}|{provider_id}|{time.time()}".encode('utf-8')).hexdigest()

    with _batch_queue_lock:
        _batch_queue[batch_id] = {
            'content': content,
            'model': model,
            'provider_id': provider_id,
            'created_at': datetime.now(timezone.utc),
            'status': 'pending'
        }

    return batch_id

def get_batch_status(batch_id: str) -> Dict[str, Any]:
    """
    获取批处理状态

    Args:
        batch_id: 批处理ID

    Returns:
        Dict[str, Any]: 批处理状态
    """
    with _batch_queue_lock:
        if batch_id in _batch_queue:
            return _batch_queue[batch_id]

    return None

def process_batch_queue() -> int:
    """
    处理批处理队列

    Returns:
        int: 处理的请求数量
    """
    global _batch_processed_count

    # 检查批处理是否启用
    if get_config('AI_BATCH_ENABLED', 'false').lower() != 'true':
        return 0

    processed_count = 0

    with _batch_queue_lock:
        # 按提供商和模型分组
        groups = {}
        for batch_id, item in _batch_queue.items():
            if item['status'] == 'pending':
                key = (item['provider_id'], item['model'])
                if key not in groups:
                    groups[key] = []
                groups[key].append((batch_id, item))

        # 处理每个分组
        for (provider_id, model), items in groups.items():
            # 如果分组中只有一个请求，不进行批处理
            if len(items) == 1:
                continue

            # 合并请求
            batch_ids = [item[0] for item in items]
            contents = [item[1]['content'] for item in items]

            # TODO: 实现批处理逻辑
            # 这里需要根据实际的AI API实现批处理

            # 更新状态
            for batch_id in batch_ids:
                _batch_queue[batch_id]['status'] = 'processed'

            processed_count += len(items)
            _batch_processed_count += len(items)

    return processed_count

def run_health_check() -> Dict[str, Any]:
    """
    运行健康检查

    Returns:
        Dict[str, Any]: 健康检查结果
    """
    global _health_check_count

    try:
        # 检查是否在应用上下文中运行
        from flask import current_app
        if not current_app:
            # 如果不在应用上下文中，导入应用并创建上下文
            from web_app import app
            with app.app_context():
                return _run_health_check_impl()
        else:
            # 已经在应用上下文中
            return _run_health_check_impl()
    except Exception as e:
        logger.error(f"运行健康检查失败: {str(e)}")
        return {'error': str(e)}

def _run_health_check_impl() -> Dict[str, Any]:
    """
    健康检查的实际实现

    Returns:
        Dict[str, Any]: 健康检查结果
    """
    global _health_check_count

    try:
        # 获取AI提供商模型
        AIProvider = get_ai_provider_model()

        # 获取所有活跃的提供商
        providers = AIProvider.query.filter_by(is_active=True).all()

        logger.info(f"开始运行健康检查，共有 {len(providers)} 个活跃的AI提供商")

        results = {}
        for provider in providers:
            try:
                # 构建健康检查请求
                check_content = "Hello, this is a health check."

                # 记录开始时间
                start_time = time.time()

                # 实际调用AI API进行健康检查
                is_success = False
                response_time = 0
                error_message = None
                response_content = None

                try:
                    # 设置超时时间
                    timeout = 10  # 10秒超时

                    # 根据提供商类型选择合适的API调用方式
                    if provider.api_base and provider.api_key:
                        # 构建API请求
                        headers = {
                            "Content-Type": "application/json",
                            "Authorization": f"Bearer {provider.api_key}"
                        }

                        # 根据API提供商和模型名称构建合适的请求体
                        api_base_lower = provider.api_base.lower()
                        model_lower = provider.model.lower()

                        # 完全尊重用户输入的URL，不做任何添加或删减
                        request_url = provider.api_base
                        logger.info(f"使用用户提供的URL: {request_url}")

                        # 判断是否使用OpenAI风格的聊天API（仅用于构建请求体）
                        use_chat_api = (
                            # OpenAI
                            "gpt" in model_lower or "openai" in api_base_lower or
                            # X.AI (Grok)
                            "grok" in model_lower or "x.ai" in api_base_lower or
                            # Anthropic
                            "claude" in model_lower or "anthropic" in api_base_lower or
                            # Mistral AI
                            "mistral" in model_lower or "mistral.ai" in api_base_lower or
                            # Groq
                            "llama" in model_lower or "groq" in api_base_lower or
                            # Google Gemini
                            "gemini" in model_lower or "googleapis.com" in api_base_lower or
                            # Cohere
                            "command" in model_lower or "cohere" in api_base_lower or
                            # Together AI
                            "together.xyz" in api_base_lower
                        )

                        if use_chat_api:
                            # OpenAI风格聊天API
                            payload = {
                                "model": provider.model,
                                "messages": [{"role": "user", "content": check_content}],
                                "max_tokens": 10
                            }

                            # 为X.AI (Grok)添加reasoning_effort参数
                            if "grok" in model_lower or "x.ai" in api_base_lower:
                                payload["reasoning_effort"] = "high"
                        else:
                            # 通用API格式（旧式完成API）
                            payload = {
                                "prompt": check_content,
                                "max_tokens": 10
                            }

                        # 检查是否有代理配置
                        proxies = None
                        try:
                            # 尝试导入代理管理器
                            from utils.api_utils import get_proxy_manager

                            # 获取代理管理器
                            proxy_manager = get_proxy_manager()

                            # 检查是否有可用的代理
                            if proxy_manager and proxy_manager.proxy_configs:
                                # 有代理配置，使用代理
                                working_proxy = proxy_manager.find_working_proxy()
                                if working_proxy:
                                    proxies = working_proxy.get_proxy_dict()
                                    logger.info(f"健康检查使用代理: {working_proxy.name}")
                        except Exception as e:
                            logger.warning(f"获取代理配置时出错: {str(e)}")

                        # 如果代理管理器未提供代理，尝试使用环境变量
                        if not proxies and os.environ.get('HTTP_PROXY'):
                            proxies = {
                                'http': os.environ.get('HTTP_PROXY'),
                                'https': os.environ.get('HTTPS_PROXY', os.environ.get('HTTP_PROXY'))
                            }
                            logger.info("健康检查使用环境变量中的代理")

                        # 发送请求，如果有代理则使用代理
                        response = requests.post(
                            request_url,
                            headers=headers,
                            json=payload,
                            timeout=timeout,
                            proxies=proxies
                        )

                        # 计算响应时间
                        response_time = time.time() - start_time

                        # 检查响应状态
                        if response.status_code == 200:
                            is_success = True
                            response_content = response.text[:200]  # 只保存前200个字符
                        else:
                            error_message = f"API返回错误: {response.status_code} - {response.text[:200]}"
                    else:
                        error_message = "提供商缺少API基础URL或API密钥"

                except requests.Timeout:
                    error_message = "API请求超时"
                    response_time = timeout
                except requests.RequestException as e:
                    error_message = f"API请求异常: {str(e)}"
                    response_time = time.time() - start_time
                except Exception as e:
                    error_message = f"健康检查异常: {str(e)}"
                    response_time = time.time() - start_time

                # 记录日志
                if is_success:
                    # 记录成功的健康检查
                    logger.info(f"健康检查成功: 提供商={provider.name}, 模型={provider.model}, 响应时间={response_time:.2f}秒")
                else:
                    # 记录失败的健康检查
                    logger.warning(f"健康检查失败: 提供商={provider.name}, 模型={provider.model}, 错误={error_message}")

                # 获取AI请求日志模型
                AIRequestLog = get_ai_request_log_model()

                # 记录健康检查日志
                AIRequestLog.create_log(
                    provider_id=provider.id,
                    request_type='health_check',
                    request_content=check_content,
                    response_content=response_content or "Health check successful" if is_success else "Health check failed",
                    is_success=is_success,
                    error_message=error_message,
                    response_time=response_time
                )

                results[provider.id] = {
                    'provider_name': provider.name,
                    'is_success': is_success,
                    'response_time': response_time,
                    'error_message': error_message
                }

                _health_check_count += 1

            except Exception as e:
                logger.error(f"健康检查提供商 {provider.name} 失败: {str(e)}")

                # 获取AI请求日志模型
                AIRequestLog = get_ai_request_log_model()

                # 记录健康检查日志
                AIRequestLog.create_log(
                    provider_id=provider.id,
                    request_type='health_check',
                    request_content=check_content,
                    is_success=False,
                    error_message=str(e)
                )

                results[provider.id] = {
                    'provider_name': provider.name,
                    'is_success': False,
                    'error_message': str(e)
                }

                _health_check_count += 1

        # 记录健康检查完成
        logger.info(f"健康检查完成，检查了 {len(results)} 个提供商")
        return results
    except Exception as e:
        logger.error(f"健康检查实现出错: {str(e)}")
        return {'error': str(e)}

def ai_polling_worker():
    """AI轮询工作线程"""
    global _last_run_time, _worker_running

    # 导入Flask应用
    from web_app import app

    logger.info("AI轮询工作线程已启动")

    while _worker_running:
        try:
            # 使用应用上下文
            with app.app_context():
                # 记录开始时间
                start_time = time.time()
                _last_run_time = datetime.now(timezone.utc)

                # 获取健康检查间隔
                interval_seconds = int(get_config('AI_HEALTH_CHECK_INTERVAL', '30'))

                # 检查是否启用自动健康检查
                auto_health_check_enabled = get_config('AI_AUTO_HEALTH_CHECK_ENABLED', 'true').lower() == 'true'

                # 如果启用了自动健康检查，则运行健康检查
                if auto_health_check_enabled:
                    health_results = run_health_check()
                    logger.info(f"自动健康检查完成，检查了 {len(health_results)} 个提供商")
                else:
                    logger.info("自动健康检查已禁用，跳过健康检查")

                # 处理批处理队列
                if get_config('AI_BATCH_ENABLED', 'false').lower() == 'true':
                    processed = process_batch_queue()
                    if processed > 0:
                        logger.info(f"批处理队列处理完成，处理了 {processed} 个请求")

            # 计算需要等待的时间
            elapsed = time.time() - start_time
            wait_time = max(0, interval_seconds - elapsed)

            # 等待指定时间
            if wait_time > 0:
                # 使用小的时间间隔检查_worker_running，以便能够及时响应停止请求
                check_interval = 1.0  # 1秒
                for _ in range(int(wait_time / check_interval)):
                    if not _worker_running:
                        break
                    time.sleep(check_interval)

                # 处理剩余的等待时间
                remaining = wait_time % check_interval
                if remaining > 0 and _worker_running:
                    time.sleep(remaining)

        except Exception as e:
            logger.error(f"AI轮询工作线程出错: {str(e)}")
            # 出错后等待一段时间再继续
            time.sleep(5)

    logger.info("AI轮询工作线程已停止")

def start_ai_polling_worker():
    """启动AI轮询工作线程"""
    global _worker_thread, _worker_running

    # 检查是否启用AI轮询
    try:
        ai_polling_enabled = get_config('AI_POLLING_ENABLED', 'true').lower() == 'true'
    except Exception as e:
        logger.error(f"获取环境变量出错: {str(e)}，使用默认值true")
        ai_polling_enabled = True

    if not ai_polling_enabled:
        logger.info("AI轮询功能已禁用，不启动工作线程")
        return False

    # 检查线程是否已经在运行
    if _worker_thread is not None and _worker_thread.is_alive():
        logger.info("AI轮询工作线程已在运行")
        return True

    # 创建并启动线程
    _worker_running = True
    _worker_thread = threading.Thread(target=ai_polling_worker, daemon=True)
    _worker_thread.start()

    logger.info("AI轮询工作线程已启动")
    return True

def stop_ai_polling_worker():
    """停止AI轮询工作线程"""
    global _worker_running

    if _worker_thread is not None and _worker_thread.is_alive():
        logger.info("正在停止AI轮询工作线程...")
        _worker_running = False

        # 等待线程结束，最多等待5秒
        _worker_thread.join(timeout=5.0)

        if _worker_thread.is_alive():
            logger.warning("AI轮询工作线程未能在5秒内停止")
            return False
        else:
            logger.info("AI轮询工作线程已停止")
            return True
    else:
        logger.info("AI轮询工作线程未在运行")
        return True

def get_worker_status():
    """获取工作线程状态"""
    return {
        'running': _worker_running and _worker_thread is not None and _worker_thread.is_alive(),
        'last_run_time': _last_run_time.isoformat() if _last_run_time else None,
        'health_check_count': _health_check_count,
        'cache_hit_count': _cache_hit_count,
        'cache_miss_count': _cache_miss_count,
        'batch_processed_count': _batch_processed_count,
        'interval_seconds': int(get_config('AI_HEALTH_CHECK_INTERVAL', '30'))
    }

# 创建AI轮询服务类，提供统一的接口
class AIPollingService:
    """AI轮询服务类"""

    def start(self):
        """启动AI轮询服务"""
        return start_ai_polling_worker()

    def stop(self):
        """停止AI轮询服务"""
        return stop_ai_polling_worker()

    def get_status(self):
        """获取服务状态"""
        return get_worker_status()

    def run_health_check(self):
        """运行健康检查"""
        try:
            # 检查是否在应用上下文中运行
            from flask import current_app
            if not current_app:
                # 如果不在应用上下文中，导入应用并创建上下文
                from web_app import app
                with app.app_context():
                    return run_health_check()
            else:
                # 已经在应用上下文中
                return run_health_check()
        except Exception as e:
            logger.error(f"运行健康检查服务出错: {str(e)}")
            return {'error': str(e)}

    def clear_cache(self):
        """清空缓存"""
        return clear_cache()

    def get_cache_stats(self):
        """获取缓存统计信息"""
        return get_cache_stats()

    def get_available_providers(self, media_type='text'):
        """获取可用的AI提供商列表"""
        return get_available_providers(media_type)

    def reset_provider_availability(self):
        """重置所有 AI 提供商的可用性状态"""
        return reset_provider_availability()

# 创建全局AI轮询服务实例
ai_polling_service = AIPollingService()
