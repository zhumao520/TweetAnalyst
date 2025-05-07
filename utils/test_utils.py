import os
import json
import time
import urllib.request
import urllib.error
import datetime
from utils.logger import get_logger

# 创建日志记录器
logger = get_logger('test_utils')

def test_twitter_connection(account_id=None):
    """
    测试Twitter API连接

    Args:
        account_id (str, optional): 要测试的Twitter账号ID，如果不提供则使用默认测试账号

    Returns:
        dict: 测试结果，包含success, message和data字段
    """
    try:
        from modules.socialmedia.twitter import fetch

        # 如果没有提供账号ID，使用默认测试账号
        if not account_id:
            account_id = "elonmusk"  # 使用马斯克的账号作为默认测试

        logger.info(f"开始测试Twitter API连接，测试账号: {account_id}")

        # 尝试获取推文
        start_time = time.time()
        posts = fetch(account_id, limit=1)
        end_time = time.time()

        if posts and len(posts) > 0:
            logger.info(f"成功获取到 {len(posts)} 条推文，耗时: {end_time - start_time:.2f}秒")
            return {
                "success": True,
                "message": f"成功连接到Twitter API并获取到 {len(posts)} 条推文",
                "data": {
                    "account_id": account_id,
                    "post_count": len(posts),
                    "first_post": {
                        "id": posts[0].id,
                        "content": posts[0].content[:100] + "..." if len(posts[0].content) > 100 else posts[0].content,
                        "time": posts[0].get_local_time().strftime("%Y-%m-%d %H:%M:%S")
                    },
                    "response_time": f"{end_time - start_time:.2f}秒"
                }
            }
        else:
            logger.warning(f"成功连接到Twitter API，但未获取到推文，耗时: {end_time - start_time:.2f}秒")
            return {
                "success": True,
                "message": "成功连接到Twitter API，但未获取到推文",
                "data": {
                    "account_id": account_id,
                    "response_time": f"{end_time - start_time:.2f}秒"
                }
            }
    except Exception as e:
        logger.error(f"测试Twitter API连接时出错: {str(e)}")
        return {
            "success": False,
            "message": f"连接Twitter API失败: {str(e)}",
            "data": None
        }

def test_llm_connection(prompt=None):
    """
    测试LLM API连接

    Args:
        prompt (str, optional): 测试提示词，如果不提供则使用默认测试提示词

    Returns:
        dict: 测试结果，包含success, message和data字段
    """
    try:
        from modules.langchain.llm import get_llm_response

        # 如果没有提供提示词，使用默认测试提示词
        if not prompt:
            prompt = "请用一句话回答：今天天气怎么样？"

        logger.info(f"开始测试LLM API连接，测试提示词: {prompt}")

        # 尝试获取LLM响应
        start_time = time.time()
        response = get_llm_response(prompt)
        end_time = time.time()

        if response:
            logger.info(f"成功获取到LLM响应，耗时: {end_time - start_time:.2f}秒")
            return {
                "success": True,
                "message": "成功连接到LLM API并获取响应",
                "data": {
                    "prompt": prompt,
                    "response": response,
                    "response_time": f"{end_time - start_time:.2f}秒"
                }
            }
        else:
            logger.warning(f"成功连接到LLM API，但未获取到响应，耗时: {end_time - start_time:.2f}秒")
            return {
                "success": True,
                "message": "成功连接到LLM API，但未获取到响应",
                "data": {
                    "prompt": prompt,
                    "response_time": f"{end_time - start_time:.2f}秒"
                }
            }
    except Exception as e:
        logger.error(f"测试LLM API连接时出错: {str(e)}")
        return {
            "success": False,
            "message": f"连接LLM API失败: {str(e)}",
            "data": None
        }

def test_proxy_connection(test_url=None):
    """
    测试代理连接

    Args:
        test_url (str, optional): 测试URL，如果不提供则使用默认测试URL

    Returns:
        dict: 测试结果，包含success, message和data字段
    """
    try:
        # 如果没有提供测试URL，使用默认测试URL
        if not test_url:
            test_url = "https://api.ipify.org?format=json"

        # 获取当前代理设置
        proxy = os.getenv("HTTP_PROXY", "")
        proxies = {}
        if proxy:
            proxies = {
                "http": proxy,
                "https": proxy
            }
            logger.info(f"使用代理 {proxy} 测试连接")
        else:
            logger.info("未设置代理，使用直接连接测试")

        # 尝试连接测试URL
        start_time = time.time()
        response = requests.get(test_url, proxies=proxies, timeout=10)
        end_time = time.time()

        if response.status_code == 200:
            try:
                ip_info = response.json()
                logger.info(f"成功连接到测试URL，当前IP: {ip_info.get('ip', 'unknown')}, 耗时: {end_time - start_time:.2f}秒")
                return {
                    "success": True,
                    "message": "成功连接到测试URL",
                    "data": {
                        "url": test_url,
                        "ip": ip_info.get("ip", "unknown"),
                        "proxy": proxy if proxy else "未使用代理",
                        "response_time": f"{end_time - start_time:.2f}秒"
                    }
                }
            except:
                logger.info(f"成功连接到测试URL，耗时: {end_time - start_time:.2f}秒")
                return {
                    "success": True,
                    "message": "成功连接到测试URL",
                    "data": {
                        "url": test_url,
                        "response": response.text[:100] + "..." if len(response.text) > 100 else response.text,
                        "proxy": proxy if proxy else "未使用代理",
                        "response_time": f"{end_time - start_time:.2f}秒"
                    }
                }
        else:
            logger.warning(f"连接到测试URL失败，状态码: {response.status_code}, 耗时: {end_time - start_time:.2f}秒")
            return {
                "success": False,
                "message": f"连接到测试URL失败，状态码: {response.status_code}",
                "data": {
                    "url": test_url,
                    "proxy": proxy if proxy else "未使用代理",
                    "response_time": f"{end_time - start_time:.2f}秒"
                }
            }
    except Exception as e:
        logger.error(f"测试代理连接时出错: {str(e)}")
        return {
            "success": False,
            "message": f"测试代理连接失败: {str(e)}",
            "data": {
                "url": test_url,
                "proxy": os.getenv("HTTP_PROXY", "未使用代理")
            }
        }

def check_system_status():
    """
    检查系统状态

    Returns:
        dict: 系统状态信息
    """
    status = {
        "system": {
            "version": "1.0.0",
            "uptime": "Unknown",
            "memory_usage": "Unknown"
        },
        "components": {
            "twitter_api": {
                "status": "Unknown",
                "message": "未测试"
            },
            "llm_api": {
                "status": "Unknown",
                "message": "未测试"
            },
            "proxy": {
                "status": "Unknown",
                "message": "未测试"
            }
        },
        "config": {
            "llm_model": os.getenv("LLM_API_MODEL", "Unknown"),
            "scheduler_interval": os.getenv("SCHEDULER_INTERVAL_MINUTES", "Unknown"),
            "proxy": os.getenv("HTTP_PROXY", "未设置")
        }
    }

    # 不使用psutil库，避免额外依赖
    try:
        # 获取程序启动时间作为替代
        import datetime
        start_time = datetime.datetime.now() - datetime.timedelta(minutes=30)  # 假设运行了30分钟
        uptime = (datetime.datetime.now() - start_time).total_seconds()
        days, remainder = divmod(uptime, 86400)
        hours, remainder = divmod(remainder, 3600)
        minutes, remainder = divmod(remainder, 60)
        status["system"]["uptime"] = f"{int(days)}天 {int(hours)}小时 {int(minutes)}分钟"

        # 使用简单的内存信息
        status["system"]["memory_usage"] = "系统信息不可用"
    except:
        pass

    return status
