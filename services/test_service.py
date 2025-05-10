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

        # 导入LangChain模块
        try:
            from langchain_openai import ChatOpenAI
            from langchain_core.messages import HumanMessage, SystemMessage
        except ImportError:
            return {
                "success": False,
                "message": "未安装LangChain模块，无法测试连接"
            }

        # 发送请求
        start_time = time.time()

        # 确定API提供商
        api_provider = "标准OpenAI兼容API"
        if api_base:
            if 'x.ai' in api_base:
                api_provider = "X.AI API"
            elif 'groq.com' in api_base:
                api_provider = "Groq API"
            elif 'anthropic.com' in api_base:
                api_provider = "Anthropic API"
            elif 'mistral.ai' in api_base:
                api_provider = "Mistral AI API"
            elif 'openai.com' in api_base:
                api_provider = "OpenAI API"
            else:
                logger.info(f"使用自定义API基础URL: {api_base}")

        # 准备ChatOpenAI参数
        chat_params = {
            "model": model,
            "openai_api_base": api_base,
            "openai_api_key": api_key,
            "temperature": 0,
            "request_timeout": 60
        }

        # 根据API类型和模型添加特定参数
        model_kwargs = {}

        # 检查API类型和模型
        if 'x.ai' in api_base:
            logger.info(f"检测到{api_provider}，添加reasoning_effort参数")
            model_kwargs["reasoning_effort"] = "high"
        elif 'grok-' in model:
            logger.info(f"检测到grok模型，添加reasoning_effort参数")
            model_kwargs["reasoning_effort"] = "high"

        # 如果有特定参数，添加到chat_params
        if model_kwargs:
            chat_params["model_kwargs"] = model_kwargs

        # 调用API
        try:
            # 记录API信息
            logger.info(f"使用{api_provider}测试连接，模型: {model}")
            logger.info(f"API基础URL: {api_base}")
            logger.info(f"请求参数: {chat_params}")

            # 创建ChatOpenAI实例
            chat = ChatOpenAI(**chat_params)

            # 创建消息
            messages = [
                HumanMessage(content=prompt)
            ]

            # 发送请求
            response = chat.invoke(messages)

        except Exception as api_error:
            error_str = str(api_error).lower()
            if '404' in error_str:
                logger.error(f"{api_provider}返回404错误，可能是API端点不正确或模型名称错误: {error_str}")
                logger.error(f"尝试访问的URL: {api_base}")
                logger.error(f"使用的模型: {model}")
                logger.error(f"完整错误信息: {api_error}")
                raise Exception(f"{api_provider}返回404错误。请检查:\n1. API基础URL是否正确\n2. 模型名称是否正确\n3. 您是否有访问该模型的权限\n\n错误详情: {error_str}")
            else:
                raise
        end_time = time.time()

        # 构建响应数据
        response_data = {
            "prompt": prompt,
            "response": response.content,
            "response_time": f"{end_time - start_time:.2f}秒",
            "model": model
        }

        # 注意：LangChain的响应对象没有reasoning_content属性
        # 如果将来需要这个功能，可能需要通过其他方式获取

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
        # 获取代理设置
        proxy = get_config('HTTP_PROXY', '')

        # 设置代理
        proxies = {}
        if proxy:
            proxies = {
                'http': proxy,
                'https': proxy
            }
            logger.info(f"使用代理: {proxy}")
        else:
            logger.info("未使用代理")

        # 如果用户提供了特定的测试URL，只测试该URL
        if test_url:
            logger.info(f"使用用户提供的测试URL: {test_url}")
            return test_single_url(test_url, proxies)

        # 否则，同时测试国内和国外网站
        logger.info("同时测试国内和国外网站")

        # 测试国内网站（百度）
        baidu_url = "http://www.baidu.com"
        logger.info(f"测试国内网站: {baidu_url}")
        baidu_result = test_single_url(baidu_url, proxies, is_json=False)

        # 测试国外网站（Google）
        foreign_url = "https://www.google.com/generate_204"
        logger.info(f"测试国外网站: {foreign_url}")
        # Google的测试URL返回204状态码，不是JSON格式
        foreign_result = test_single_url(foreign_url, proxies, is_json=False)

        # 分析结果
        baidu_success = baidu_result.get("success", False)
        foreign_success = foreign_result.get("success", False)

        # 生成诊断信息
        if baidu_success and foreign_success:
            diagnosis = "代理工作正常，可以访问国内和国外网站"
            success = True
        elif baidu_success and not foreign_success:
            diagnosis = "代理可以访问国内网站，但无法访问国外网站。可能是代理服务器本身无法访问国外网站。"
            success = False
        elif not baidu_success and foreign_success:
            diagnosis = "代理可以访问国外网站，但无法访问国内网站。这种情况比较少见，可能是代理配置有特殊限制。"
            success = False
        else:
            diagnosis = "代理完全无法工作。请检查代理服务器是否正常运行，以及代理地址和端口是否正确。"
            success = False

        # 返回综合结果
        return {
            "success": success,
            "message": diagnosis,
            "data": {
                "baidu_test": {
                    "url": baidu_url,
                    "success": baidu_success,
                    "message": baidu_result.get("message", ""),
                    "status_code": baidu_result.get("data", {}).get("status_code", 0)
                },
                "foreign_test": {
                    "url": foreign_url,
                    "success": foreign_success,
                    "message": foreign_result.get("message", ""),
                    "status_code": foreign_result.get("data", {}).get("status_code", 0)
                },
                "proxy": proxy or "未使用代理"
            }
        }
    except Exception as e:
        logger.error(f"测试代理连接时出错: {str(e)}")
        return {
            "success": False,
            "message": f"测试代理连接失败: {str(e)}"
        }

def test_single_url(url, proxies, timeout=10, is_json=True):
    """
    测试单个URL的连接

    Args:
        url: 测试URL
        proxies: 代理设置
        timeout: 超时时间（秒）
        is_json: 是否期望JSON响应

    Returns:
        dict: 测试结果
    """
    try:
        # 发送请求
        start_time = time.time()
        response = requests.get(url, proxies=proxies, timeout=timeout)
        end_time = time.time()

        # 检查响应
        # 对于Google的测试URL，204状态码表示成功
        if url == "https://www.google.com/generate_204" and response.status_code == 204:
            # 204状态码是正常的，表示连接成功
            pass
        elif response.status_code != 200 and response.status_code != 204:
            return {
                "success": False,
                "message": f"请求失败，状态码: {response.status_code}",
                "data": {
                    "url": url,
                    "status_code": response.status_code,
                    "response_time": f"{end_time - start_time:.2f}秒"
                }
            }

        # 尝试解析响应
        if is_json:
            try:
                data = response.json()
            except:
                data = {"text": response.text[:100] + ('...' if len(response.text) > 100 else '')}
        else:
            # 对于非JSON响应，只保存前100个字符
            data = {"text": response.text[:100] + ('...' if len(response.text) > 100 else '')}

        # 返回成功结果
        return {
            "success": True,
            "message": "成功连接测试URL",
            "data": {
                "url": url,
                "status_code": response.status_code,
                "ip": data.get("ip", "未知") if is_json else "不适用",
                "response_time": f"{end_time - start_time:.2f}秒",
                "response": data
            }
        }
    except Exception as e:
        logger.error(f"测试URL {url} 时出错: {str(e)}")
        return {
            "success": False,
            "message": f"测试URL连接失败: {str(e)}",
            "data": {
                "url": url,
                "error": str(e)
            }
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
