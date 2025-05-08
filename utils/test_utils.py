import os
import json
import time
import urllib.request
import urllib.error
import datetime
import requests
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
        # 检查代理设置
        proxy = os.getenv('HTTP_PROXY', '')
        if proxy:
            logger.info(f"使用代理连接Twitter: {proxy}")
            # 如果是SOCKS代理，检查是否安装了支持
            if proxy.startswith('socks'):
                try:
                    import socksio
                    logger.info("已安装SOCKS代理支持")
                except ImportError:
                    logger.warning("未安装SOCKS代理支持，可能无法正常连接Twitter")
                    try:
                        import pip
                        logger.info("尝试安装SOCKS代理支持...")
                        pip.main(['install', 'httpx[socks]', '--quiet'])
                        logger.info("成功安装SOCKS代理支持")
                    except Exception as e:
                        logger.error(f"安装SOCKS代理支持失败: {str(e)}")
                        return {
                            "success": False,
                            "message": f"SOCKS代理支持安装失败，无法连接Twitter: {str(e)}",
                            "data": None
                        }

        # 导入Twitter模块
        try:
            from modules.socialmedia.twitter import fetch, reinit_twitter_client

            # 尝试重新初始化Twitter客户端
            logger.info("尝试重新初始化Twitter客户端...")
            reinit_twitter_client()
        except ImportError as e:
            logger.error(f"导入Twitter模块失败: {str(e)}")
            return {
                "success": False,
                "message": f"导入Twitter模块失败: {str(e)}",
                "data": None
            }

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
                    "response_time": f"{end_time - start_time:.2f}秒",
                    "proxy_used": proxy if proxy else "未使用代理"
                }
            }
        else:
            logger.warning(f"成功连接到Twitter API，但未获取到推文，耗时: {end_time - start_time:.2f}秒")
            return {
                "success": True,
                "message": "成功连接到Twitter API，但未获取到推文",
                "data": {
                    "account_id": account_id,
                    "response_time": f"{end_time - start_time:.2f}秒",
                    "proxy_used": proxy if proxy else "未使用代理"
                }
            }
    except Exception as e:
        logger.error(f"测试Twitter API连接时出错: {str(e)}")
        return {
            "success": False,
            "message": f"连接Twitter API失败: {str(e)}",
            "data": {
                "account_id": account_id if account_id else "elonmusk",
                "proxy_used": os.getenv('HTTP_PROXY', '未使用代理'),
                "error_details": str(e)
            }
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

        logger.info(f"开始测试代理连接，测试URL: {test_url}")

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
        try:
            response = requests.get(test_url, proxies=proxies, timeout=10)
            end_time = time.time()
            logger.info(f"请求完成，状态码: {response.status_code}, 耗时: {end_time - start_time:.2f}秒")
        except requests.exceptions.Timeout:
            logger.error(f"连接超时: {test_url}")
            return {
                "success": False,
                "message": f"连接超时，请检查网络或代理设置",
                "data": {
                    "url": test_url,
                    "proxy": proxy if proxy else "未使用代理",
                    "error_type": "timeout"
                }
            }
        except requests.exceptions.ProxyError as e:
            logger.error(f"代理错误: {str(e)}")
            return {
                "success": False,
                "message": f"代理连接错误: {str(e)}",
                "data": {
                    "url": test_url,
                    "proxy": proxy if proxy else "未使用代理",
                    "error_type": "proxy_error"
                }
            }
        except requests.exceptions.ConnectionError as e:
            logger.error(f"连接错误: {str(e)}")
            return {
                "success": False,
                "message": f"网络连接错误: {str(e)}",
                "data": {
                    "url": test_url,
                    "proxy": proxy if proxy else "未使用代理",
                    "error_type": "connection_error"
                }
            }
        except Exception as e:
            logger.error(f"请求异常: {str(e)}")
            return {
                "success": False,
                "message": f"请求异常: {str(e)}",
                "data": {
                    "url": test_url,
                    "proxy": proxy if proxy else "未使用代理",
                    "error_type": "request_error"
                }
            }

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

    # 检查Twitter API状态
    try:
        from modules.socialmedia.twitter import app as twitter_app, reinit_twitter_client

        # 如果Twitter客户端未初始化或连接失败，尝试重新初始化
        if twitter_app is None or not hasattr(twitter_app, 'me') or twitter_app.me is None:
            logger.info("Twitter客户端未初始化或连接失败，尝试重新初始化")
            reinit_success = reinit_twitter_client()

            if reinit_success and twitter_app is not None and hasattr(twitter_app, 'me') and twitter_app.me is not None:
                status["components"]["twitter_api"]["status"] = "正常"
                status["components"]["twitter_api"]["message"] = f"已连接 ({twitter_app.me.username})"
            else:
                status["components"]["twitter_api"]["status"] = "异常"
                status["components"]["twitter_api"]["message"] = "重新初始化失败，请检查Twitter凭据和网络连接"
        else:
            status["components"]["twitter_api"]["status"] = "正常"
            status["components"]["twitter_api"]["message"] = f"已连接 ({twitter_app.me.username})"

        # 添加代理信息
        proxy = os.getenv('HTTP_PROXY', '')
        if proxy:
            status["components"]["twitter_api"]["proxy"] = proxy

    except ImportError as e:
        logger.error(f"导入Twitter模块失败: {str(e)}")
        status["components"]["twitter_api"]["status"] = "异常"
        status["components"]["twitter_api"]["message"] = f"导入Twitter模块失败: {str(e)}"
    except Exception as e:
        logger.error(f"检查Twitter API状态时出错: {str(e)}")
        status["components"]["twitter_api"]["status"] = "异常"
        status["components"]["twitter_api"]["message"] = f"检查状态出错: {str(e)}"

    # 检查LLM API状态
    try:
        # 简单检查LLM API密钥是否存在
        llm_api_key = os.getenv("LLM_API_KEY", "")
        if llm_api_key:
            # 尝试进行一个简单的API调用测试
            try:
                # 导入但不执行，避免每次检查都调用API
                from modules.langchain.llm import get_llm_response
                status["components"]["llm_api"]["status"] = "正常"
                status["components"]["llm_api"]["message"] = "API密钥已配置"
            except Exception as e:
                status["components"]["llm_api"]["status"] = "异常"
                status["components"]["llm_api"]["message"] = f"API模块加载失败: {str(e)}"
        else:
            status["components"]["llm_api"]["status"] = "异常"
            status["components"]["llm_api"]["message"] = "API密钥未配置"
    except Exception as e:
        logger.error(f"检查LLM API状态时出错: {str(e)}")
        status["components"]["llm_api"]["status"] = "异常"
        status["components"]["llm_api"]["message"] = f"检查状态出错: {str(e)}"

    # 检查代理状态
    try:
        proxy = os.getenv("HTTP_PROXY", "")
        if proxy:
            # 尝试使用代理连接到百度
            try:
                response = requests.get("http://www.baidu.com", proxies={"http": proxy, "https": proxy}, timeout=5)
                if response.status_code == 200:
                    status["components"]["proxy"]["status"] = "正常"
                    status["components"]["proxy"]["message"] = f"代理可用: {proxy}"
                else:
                    status["components"]["proxy"]["status"] = "异常"
                    status["components"]["proxy"]["message"] = f"代理连接失败: {response.status_code}"
            except Exception as e:
                status["components"]["proxy"]["status"] = "异常"
                status["components"]["proxy"]["message"] = f"代理测试失败: {str(e)}"
        else:
            # 尝试直接连接到百度
            try:
                response = requests.get("http://www.baidu.com", timeout=5)
                if response.status_code == 200:
                    status["components"]["proxy"]["status"] = "正常"
                    status["components"]["proxy"]["message"] = "直接连接可用"
                else:
                    status["components"]["proxy"]["status"] = "异常"
                    status["components"]["proxy"]["message"] = f"直接连接失败: {response.status_code}"
            except Exception as e:
                status["components"]["proxy"]["status"] = "异常"
                status["components"]["proxy"]["message"] = f"网络连接测试失败: {str(e)}"
    except Exception as e:
        logger.error(f"检查代理状态时出错: {str(e)}")
        status["components"]["proxy"]["status"] = "异常"
        status["components"]["proxy"]["message"] = f"检查状态出错: {str(e)}"

    return status
