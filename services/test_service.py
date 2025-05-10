"""
测试服务
提供系统测试功能
"""

import os
import time
import json
import logging
import platform
import psutil
from datetime import datetime, timedelta
import requests
from services.config_service import get_config

# 创建日志记录器
logger = logging.getLogger('services.test')

def test_twitter_connection(account_id=None):
    """
    测试Twitter连接

    Args:
        account_id: Twitter账号ID

    Returns:
        dict: 测试结果
    """
    try:
        # 如果未提供账号ID，使用配置中的账号
        if not account_id:
            account_id = get_config('TWITTER_USERNAME', '')
            if not account_id:
                return {
                    "success": False,
                    "message": "未提供Twitter账号ID，且系统未配置默认账号"
                }

        # 导入Twitter模块
        try:
            from twitter.scraper import TwitterScraper
        except ImportError:
            return {
                "success": False,
                "message": "未安装Twitter模块，无法测试连接"
            }

        # 创建Twitter抓取器
        start_time = time.time()
        scraper = TwitterScraper()

        # 获取推文
        try:
            posts = scraper.get_user_tweets(account_id, count=5)
            end_time = time.time()

            if not posts:
                return {
                    "success": False,
                    "message": f"未获取到账号 {account_id} 的推文，请检查账号ID是否正确"
                }

            # 返回成功结果
            first_post = posts[0]
            return {
                "success": True,
                "message": f"成功连接Twitter并获取账号 {account_id} 的推文",
                "data": {
                    "account_id": account_id,
                    "post_count": len(posts),
                    "response_time": f"{end_time - start_time:.2f}秒",
                    "first_post": {
                        "id": first_post.id,
                        "time": first_post.created_at.isoformat(),
                        "content": first_post.text[:100] + ('...' if len(first_post.text) > 100 else '')
                    }
                }
            }
        except Exception as e:
            logger.error(f"获取Twitter推文时出错: {str(e)}")
            return {
                "success": False,
                "message": f"获取Twitter推文失败: {str(e)}"
            }
    except Exception as e:
        logger.error(f"测试Twitter连接时出错: {str(e)}")
        return {
            "success": False,
            "message": f"测试Twitter连接失败: {str(e)}"
        }

def test_llm_connection(prompt=None, model=None):
    """
    测试LLM连接

    Args:
        prompt: 测试提示词
        model: 模型名称

    Returns:
        dict: 测试结果
    """
    try:
        # 如果未提供提示词，使用默认提示词
        if not prompt:
            prompt = "请用一句话回答：今天天气怎么样？"

        # 如果未提供模型，使用配置中的模型
        if not model:
            model = get_config('LLM_API_MODEL', 'grok-3-mini-beta')

        # 获取API密钥和基础URL
        api_key = get_config('LLM_API_KEY', '')
        api_base = get_config('LLM_API_BASE', 'https://api.x.ai/v1')

        if not api_key:
            return {
                "success": False,
                "message": "未配置LLM API密钥"
            }

        # 导入OpenAI模块
        try:
            from openai import OpenAI
        except ImportError:
            return {
                "success": False,
                "message": "未安装OpenAI模块，无法测试连接"
            }

        # 创建OpenAI客户端
        client = OpenAI(api_key=api_key, base_url=api_base)

        # 发送请求
        start_time = time.time()

        # 检查是否为xAI的grok-3模型，添加reasoning_effort参数
        if model and 'grok-3' in model:
            logger.info(f"检测到grok-3模型，添加reasoning_effort参数")
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ],
                reasoning_effort="high"  # 添加推理努力参数
            )
        else:
            response = client.chat.completions.create(
                model=model,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
        end_time = time.time()

        # 构建响应数据
        response_data = {
            "prompt": prompt,
            "response": response.choices[0].message.content,
            "response_time": f"{end_time - start_time:.2f}秒",
            "model": model
        }

        # 如果有reasoning_content，添加到响应中
        if hasattr(response.choices[0].message, 'reasoning_content') and response.choices[0].message.reasoning_content:
            response_data["reasoning_content"] = response.choices[0].message.reasoning_content

        # 返回成功结果
        return {
            "success": True,
            "message": f"成功连接LLM API并获取响应",
            "data": response_data
        }
    except Exception as e:
        logger.error(f"测试LLM连接时出错: {str(e)}")
        return {
            "success": False,
            "message": f"测试LLM连接失败: {str(e)}"
        }

def test_proxy_connection(test_url=None):
    """
    测试代理连接

    Args:
        test_url: 测试URL

    Returns:
        dict: 测试结果
    """
    try:
        # 如果未提供测试URL，使用默认URL
        if not test_url:
            test_url = "https://api.ipify.org?format=json"

        # 获取代理设置
        proxy = get_config('HTTP_PROXY', '')

        # 设置代理
        proxies = {}
        if proxy:
            if proxy.startswith('socks'):
                proxies = {
                    'http': proxy,
                    'https': proxy
                }
            else:
                proxies = {
                    'http': proxy,
                    'https': proxy
                }

        # 发送请求
        start_time = time.time()
        response = requests.get(test_url, proxies=proxies, timeout=10)
        end_time = time.time()

        # 检查响应
        if response.status_code != 200:
            return {
                "success": False,
                "message": f"请求失败，状态码: {response.status_code}"
            }

        # 尝试解析JSON响应
        try:
            data = response.json()
        except:
            data = {"text": response.text[:100] + ('...' if len(response.text) > 100 else '')}

        # 返回成功结果
        return {
            "success": True,
            "message": "成功连接测试URL",
            "data": {
                "url": test_url,
                "ip": data.get("ip", "未知"),
                "proxy": proxy or "未使用代理",
                "response_time": f"{end_time - start_time:.2f}秒",
                "response": data
            }
        }
    except Exception as e:
        logger.error(f"测试代理连接时出错: {str(e)}")
        return {
            "success": False,
            "message": f"测试代理连接失败: {str(e)}"
        }

def check_system_status():
    """
    检查系统状态

    Returns:
        dict: 系统状态信息
    """
    try:
        # 获取系统信息
        system_info = {
            "version": "1.0.0",  # 系统版本
            "uptime": get_uptime(),
            "platform": platform.platform(),
            "python": platform.python_version()
        }

        # 获取配置信息
        config_info = {
            "llm_model": get_config('LLM_API_MODEL', 'grok-3-mini-beta'),
            "scheduler_interval": get_config('SCHEDULER_INTERVAL_MINUTES', '30'),
            "proxy": get_config('HTTP_PROXY', '未设置')
        }

        # 获取组件状态
        components_status = {
            "twitter_api": {
                "status": "未测试",
                "last_check": None
            },
            "llm_api": {
                "status": "未测试",
                "last_check": None
            },
            "proxy": {
                "status": "未测试",
                "last_check": None
            }
        }

        # 返回系统状态
        return {
            "system": system_info,
            "config": config_info,
            "components": components_status
        }
    except Exception as e:
        logger.error(f"检查系统状态时出错: {str(e)}")
        return {
            "system": {
                "version": "1.0.0",
                "error": str(e)
            },
            "config": {},
            "components": {}
        }

def get_uptime():
    """
    获取系统运行时间

    Returns:
        str: 运行时间
    """
    try:
        # 获取进程启动时间
        process = psutil.Process(os.getpid())
        start_time = datetime.fromtimestamp(process.create_time())
        uptime = datetime.now() - start_time

        # 格式化运行时间
        days = uptime.days
        hours, remainder = divmod(uptime.seconds, 3600)
        minutes, seconds = divmod(remainder, 60)

        if days > 0:
            return f"{days}天 {hours}小时 {minutes}分钟"
        elif hours > 0:
            return f"{hours}小时 {minutes}分钟"
        else:
            return f"{minutes}分钟 {seconds}秒"
    except Exception as e:
        logger.error(f"获取系统运行时间时出错: {str(e)}")
        return "未知"
