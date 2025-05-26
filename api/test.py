"""
测试API模块
处理所有测试相关的API请求
"""

import logging
import time
import datetime
import os
import glob
import shutil
import json
from flask import Blueprint, request, jsonify, session, current_app
from utils.test_utils import test_twitter_connection, test_llm_connection, test_proxy_connection, check_system_status
from models import db, AnalysisResult

# 创建日志记录器
logger = logging.getLogger('api.test')

# 创建Blueprint
test_api = Blueprint('test_api', __name__, url_prefix='/test')

@test_api.route('/system/status', methods=['GET'])
def get_system_status_api():
    """获取系统状态API"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 使用统一的系统状态服务
        logger.info("获取系统状态")
        from services.system_status_service import get_system_status
        status_data = get_system_status()

        # 返回与首页兼容的格式
        return jsonify({
            "success": True,
            "database_status": status_data['database']['status'],
            "ai_status": status_data['ai_service']['status'],
            "notification_status": status_data['notification']['status'],
            "proxy_status": status_data['proxy']['status'],
            "twitter_status": status_data['twitter']['status'],
            "core_scraping_status": status_data['core_scraping']['status'],
            "timestamp": status_data['timestamp']
        })
    except Exception as e:
        logger.error(f"获取系统状态时出错: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"获取系统状态失败: {str(e)}",
            "database_status": "error",
            "ai_status": "error",
            "notification_status": "error",
            "proxy_status": "error",
            "twitter_status": "error",
            "core_scraping_status": "error",
            "timestamp": datetime.datetime.now().timestamp()
        }), 500

@test_api.route('/twitter', methods=['POST'])
def test_twitter():
    """测试Twitter API连接"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    # 获取请求参数
    try:
        data = request.get_json() or {}
        logger.debug(f"收到JSON数据: {data}")
    except Exception as e:
        logger.error(f"解析JSON数据时出错: {str(e)}")
        if request.content_type == 'application/x-www-form-urlencoded':
            data = request.form.to_dict()
            logger.debug(f"收到表单数据: {data}")
        else:
            logger.error(f"不支持的Content-Type: {request.content_type}")
            return jsonify({"success": False, "message": f"不支持的Content-Type: {request.content_type}"}), 415
    account_id = data.get('account_id', '')

    # 执行测试
    logger.info(f"开始测试Twitter连接，账号ID: {account_id}")
    result = test_twitter_connection(account_id)

    if result['success']:
        logger.info("Twitter连接测试成功")
    else:
        logger.warning(f"Twitter连接测试失败: {result['message']}")

    return jsonify(result)

@test_api.route('/llm', methods=['POST'])
def test_llm():
    """测试LLM API连接"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    # 获取请求参数
    try:
        data = request.get_json() or {}
        logger.debug(f"收到JSON数据: {data}")
    except Exception as e:
        logger.error(f"解析JSON数据时出错: {str(e)}")
        if request.content_type == 'application/x-www-form-urlencoded':
            data = request.form.to_dict()
            logger.debug(f"收到表单数据: {data}")
        else:
            logger.error(f"不支持的Content-Type: {request.content_type}")
            return jsonify({"success": False, "message": f"不支持的Content-Type: {request.content_type}"}), 415
    prompt = data.get('prompt', '')
    model = data.get('model', '')

    # 执行测试
    logger.info(f"开始测试LLM连接，模型: {model}")
    result = test_llm_connection(prompt, model)

    if result['success']:
        logger.info("LLM连接测试成功")
    else:
        logger.warning(f"LLM连接测试失败: {result['message']}")

    return jsonify(result)

@test_api.route('/proxy', methods=['POST'])
def test_proxy():
    """测试代理连接（向后兼容）"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    # 获取请求参数
    try:
        data = request.get_json() or {}
        logger.debug(f"收到JSON数据: {data}")
    except Exception as e:
        logger.error(f"解析JSON数据时出错: {str(e)}")
        if request.content_type == 'application/x-www-form-urlencoded':
            data = request.form.to_dict()
            logger.debug(f"收到表单数据: {data}")
        else:
            logger.error(f"不支持的Content-Type: {request.content_type}")
            return jsonify({"success": False, "message": f"不支持的Content-Type: {request.content_type}"}), 415
    test_url = data.get('url', '')
    proxy_url = data.get('proxy_url', '')  # 可选参数，允许指定特定的代理URL进行测试

    # 如果提供了特定的代理URL，尝试使用该代理进行测试
    if proxy_url:
        logger.info(f"使用指定的代理URL进行测试: {proxy_url}")
        try:
            # 尝试从代理服务中查找匹配的代理配置
            from services.proxy_service import get_all_proxies, test_proxy as test_specific_proxy
            from urllib.parse import urlparse

            # 解析代理URL
            parsed = urlparse(proxy_url)
            protocol = parsed.scheme
            host = parsed.hostname
            port = parsed.port

            # 查找匹配的代理配置
            proxies = get_all_proxies()
            proxy_id = None

            for proxy in proxies:
                if (proxy['host'] == host and
                    proxy['port'] == port and
                    proxy['protocol'] == protocol):
                    proxy_id = proxy['id']
                    break

            # 如果找到匹配的代理配置，使用代理服务的测试函数
            if proxy_id:
                logger.info(f"找到匹配的代理配置ID: {proxy_id}，使用代理服务测试")
                result = test_specific_proxy(proxy_id, test_url)
                return jsonify(result)
            else:
                logger.warning(f"未找到匹配的代理配置，将创建临时代理配置进行测试")
                # 如果没有找到匹配的代理配置，可以创建一个临时的代理配置进行测试
                # 但这里我们选择继续使用代理管理器进行测试
        except ImportError:
            logger.warning("无法导入代理服务，将使用代理管理器进行测试")
        except Exception as e:
            logger.error(f"尝试使用代理服务测试时出错: {str(e)}")

    # 使用代理管理器执行测试
    logger.info(f"开始测试代理连接，URL: {test_url}")

    # 导入代理管理器
    from utils.api_utils import get_proxy_manager
    from utils.api_decorators import handle_api_errors

    # 使用装饰器处理错误
    @handle_api_errors(default_return={"success": False, "message": "代理连接测试失败"})
    def test_with_proxy_manager():
        try:
            # 获取代理管理器
            proxy_manager = get_proxy_manager()

            # 如果提供了特定的代理URL，尝试创建临时代理配置
            if proxy_url:
                from utils.api_utils import ProxyConfig
                from urllib.parse import urlparse

                # 解析代理URL
                parsed = urlparse(proxy_url)
                protocol = parsed.scheme
                host = parsed.hostname
                port = parsed.port
                username = parsed.username
                password = parsed.password

                if host and port and protocol:
                    # 创建临时代理配置
                    temp_proxy = ProxyConfig(
                        host=host,
                        port=port,
                        protocol=protocol,
                        username=username,
                        password=password,
                        name="临时测试代理"
                    )

                    # 测试临时代理
                    success, elapsed = proxy_manager._test_proxy(temp_proxy)

                    if success:
                        # 使用临时代理发送请求
                        start_time = time.time()
                        proxies = temp_proxy.get_proxy_dict()

                        if test_url:
                            # 使用用户指定的URL测试
                            import requests
                            response = requests.get(test_url, proxies=proxies, timeout=10, verify=False)
                            status_code = response.status_code
                        else:
                            # 使用默认URL测试
                            import requests
                            response = requests.get("https://www.google.com/generate_204", proxies=proxies, timeout=10, verify=False)
                            status_code = response.status_code

                        end_time = time.time()
                        response_time = end_time - start_time

                        return {
                            "success": True,
                            "message": "代理连接测试成功",
                            "data": {
                                "url": test_url or "https://www.google.com/generate_204",
                                "status": "connected",
                                "status_code": status_code,
                                "response_time": f"{response_time:.2f}秒",
                                "proxy": proxy_url
                            }
                        }
                    else:
                        return {
                            "success": False,
                            "message": "指定的代理无法连接",
                            "data": {
                                "url": test_url,
                                "status": "proxy_error",
                                "proxy": proxy_url
                            }
                        }

            # 查找可用代理
            working_proxy = proxy_manager.find_working_proxy(force_check=True)

            if not working_proxy:
                return {
                    "success": False,
                    "message": "未找到可用的代理",
                    "data": {
                        "url": test_url,
                        "status": "no_proxy"
                    }
                }

            # 使用代理发送请求
            start_time = time.time()
            if test_url:
                # 使用用户指定的URL测试
                response = proxy_manager.get(test_url, timeout=10)
                status_code = response.status_code
            else:
                # 使用默认URL测试
                response = proxy_manager.get(proxy_manager.test_url, timeout=10)
                status_code = response.status_code

            end_time = time.time()
            response_time = end_time - start_time

            return {
                "success": True,
                "message": "代理连接测试成功",
                "data": {
                    "url": test_url or proxy_manager.test_url,
                    "status": "connected",
                    "status_code": status_code,
                    "response_time": f"{response_time:.2f}秒",
                    "proxy": working_proxy.name
                }
            }
        except Exception as e:
            logger.error(f"代理测试失败: {str(e)}")
            return {
                "success": False,
                "message": f"代理连接测试失败: {str(e)}",
                "data": {
                    "url": test_url,
                    "status": "error"
                }
            }

    # 执行测试
    try:
        result = test_with_proxy_manager()

        if result['success']:
            logger.info("代理连接测试成功")
        else:
            logger.warning(f"代理连接测试失败: {result.get('message', '未知错误')}")

        return jsonify(result)
    except Exception as e:
        # 如果装饰器没有捕获到错误，这里作为备用
        logger.error(f"代理连接测试出错: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"代理连接测试失败: {str(e)}",
            "data": {
                "url": test_url,
                "status": "error"
            }
        })

@test_api.route('/check_all_proxies', methods=['POST'])
def check_all_proxies():
    """检查所有代理状态"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 导入代理管理器
        from utils.api_utils import get_proxy_manager

        # 获取代理管理器
        proxy_manager = get_proxy_manager()

        # 获取所有代理配置
        proxy_configs = proxy_manager.proxy_configs

        # 测试所有代理
        proxy_results = []
        for proxy in proxy_configs:
            success, elapsed = proxy_manager._test_proxy(proxy)
            proxy_results.append({
                "name": proxy.name,
                "host": proxy.host,
                "port": proxy.port,
                "protocol": proxy.protocol,
                "priority": proxy.priority,
                "working": success,
                "response_time": f"{elapsed:.2f}秒" if elapsed else None
            })

        # 获取当前工作的代理
        working_proxy = proxy_manager.find_working_proxy()
        working_proxy_info = None
        if working_proxy:
            working_proxy_info = {
                "name": working_proxy.name,
                "host": working_proxy.host,
                "port": working_proxy.port,
                "protocol": working_proxy.protocol
            }

        return jsonify({
            "success": True,
            "message": "代理状态检查完成",
            "data": {
                "proxies": proxy_results,
                "working_proxy": working_proxy_info
            }
        })
    except Exception as e:
        logger.error(f"检查代理状态时出错: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"检查代理状态失败: {str(e)}"
        }), 500

@test_api.route('/notification', methods=['POST'])
def test_notification():
    """测试推送"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        try:
            data = request.get_json() or {}
            logger.debug(f"收到JSON数据: {data}")
        except Exception as e:
            logger.error(f"解析JSON数据时出错: {str(e)}")
            if request.content_type == 'application/x-www-form-urlencoded':
                data = request.form.to_dict()
                logger.debug(f"收到表单数据: {data}")
            else:
                logger.error(f"不支持的Content-Type: {request.content_type}")
                return jsonify({"success": False, "message": f"不支持的Content-Type: {request.content_type}"}), 415
        urls = data.get('urls', '')

        # 如果没有提供URLs，从系统配置中获取
        if not urls:
            # 从环境变量或配置服务获取
            try:
                from services.config_service import get_config
                urls = get_config('APPRISE_URLS', '')
                logger.info(f"从系统配置获取推送URLs")
            except Exception as e:
                logger.error(f"从系统配置获取推送URLs时出错: {str(e)}")

            # 如果仍然没有URLs，尝试从环境变量直接获取
            if not urls:
                urls = os.getenv('APPRISE_URLS', '')
                logger.info(f"从环境变量获取推送URLs")

            # 如果仍然没有URLs，返回错误
            if not urls:
                return jsonify({"success": False, "message": "未配置推送URL，请在系统设置中配置"}), 400

            logger.info(f"使用系统配置的推送URLs进行测试")

        # 导入Apprise
        try:
            import apprise
        except ImportError:
            return jsonify({"success": False, "message": "未安装Apprise库，无法发送推送"}), 500

        # 创建Apprise对象
        apobj = apprise.Apprise()

        # 添加URL
        valid_urls = 0
        invalid_urls = []
        for url in urls.splitlines():
            url = url.strip()
            if url:
                try:
                    added = apobj.add(url)
                    if added:
                        valid_urls += 1
                        logger.debug(f"成功添加推送URL: {url}")
                    else:
                        invalid_urls.append(url)
                        logger.warning(f"无法添加推送URL: {url}")
                except Exception as e:
                    invalid_urls.append(url)
                    logger.error(f"添加推送URL时出错: {url}, 错误: {str(e)}")

        if not valid_urls:
            return jsonify({
                "success": False,
                "message": "未添加有效的推送URL，请检查URL格式",
                "data": {"invalid_urls": invalid_urls}
            }), 400

        # 添加时间戳到测试消息
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        # 检查代理设置
        proxy = os.getenv("HTTP_PROXY", "")
        if not proxy and "telegram" in urls.lower():
            logger.warning("检测到Telegram URL但未设置代理，Telegram通常需要代理才能连接")

        # 获取详细的错误信息
        error_details = []

        # 发送测试消息
        start_time = time.time()
        max_retries = 2
        retry_count = 0

        while retry_count < max_retries:
            try:
                # 记录重试信息
                if retry_count > 0:
                    logger.info(f"第 {retry_count} 次重试发送推送消息")

                # 发送通知
                result = apobj.notify(
                    title=f"TweetAnalyst测试通知 ({timestamp})",
                    body=f"这是一条测试通知，如果您收到此消息，说明推送设置正确。时间: {timestamp}"
                )
                end_time = time.time()

                # 检查结果
                if result:
                    logger.info("推送测试成功")
                    return jsonify({
                        "success": True,
                        "message": "推送测试成功",
                        "data": {
                            "sent_to": f"{len(apobj.servers)}个目标",
                            "response_time": f"{end_time - start_time:.2f}秒",
                            "proxy_used": proxy if proxy else "未使用代理",
                            "note": "注意：请确保在实际配置中使用相同的URL格式。多个URL应使用换行符分隔，而不是逗号。"
                        }
                    })
                else:
                    # 收集错误信息
                    # 兼容不同版本的Apprise库
                    servers = apobj.servers
                    if callable(servers):
                        servers = servers()

                    for server in servers:
                        if hasattr(server, 'last_error') and server.last_error:
                            error_info = f"{server.url}: {server.last_error}"
                            logger.error(f"推送服务错误: {error_info}")
                            error_details.append(error_info)

                    # 如果没有收集到具体错误，记录一个通用错误
                    if not error_details:
                        error_details.append("未知错误，请检查网络连接和代理设置")

                    # 如果还有重试机会，继续重试
                    if retry_count < max_retries - 1:
                        retry_count += 1
                        logger.info(f"推送失败，将在1秒后重试 ({retry_count}/{max_retries})")
                        time.sleep(1)
                        continue
                    else:
                        break
            except Exception as e:
                error_msg = str(e)
                logger.error(f"发送推送消息时出错: {error_msg}")
                error_details.append(error_msg)

                # 如果还有重试机会，继续重试
                if retry_count < max_retries - 1:
                    retry_count += 1
                    logger.info(f"推送异常，将在1秒后重试 ({retry_count}/{max_retries})")
                    time.sleep(1)
                    continue
                else:
                    break

        # 所有重试都失败
        logger.warning("推送测试失败")

        # 构建错误消息
        error_message = "推送发送失败"
        if error_details:
            error_message += f"，错误: {'; '.join(error_details)}"

        # 添加可能的解决方案
        solutions = []
        if "telegram" in urls.lower():
            if not proxy:
                solutions.append("Telegram通常需要代理才能连接，请设置HTTP代理")
            else:
                solutions.append(f"当前使用的代理 {proxy} 可能无法连接Telegram，请尝试其他代理")

        solutions.append("检查URL格式是否正确")
        solutions.append("确认网络连接是否正常")

        return jsonify({
            "success": False,
            "message": error_message,
            "data": {
                "urls": urls,
                "error_details": error_details,
                "possible_solutions": solutions,
                "proxy_used": proxy if proxy else "未使用代理"
            }
        })
    except Exception as e:
        logger.error(f"测试推送时出错: {str(e)}")
        return jsonify({"success": False, "message": f"测试推送失败: {str(e)}"}), 500

@test_api.route('/auto_reply', methods=['POST'])
def test_auto_reply():
    """测试自动回复功能"""
    logger.info("开始测试自动回复功能")

    try:
        # 获取请求参数
        try:
            data = request.get_json() or {}
            logger.debug(f"收到JSON数据: {data}")
        except Exception as e:
            logger.error(f"解析JSON数据时出错: {str(e)}")
            if request.content_type == 'application/x-www-form-urlencoded':
                data = request.form.to_dict()
                logger.debug(f"收到表单数据: {data}")
            else:
                logger.error(f"不支持的Content-Type: {request.content_type}")
                return jsonify({"success": False, "message": f"不支持的Content-Type: {request.content_type}"}), 415

        # 获取测试内容和提示词
        content = data.get('content', '')
        prompt_template = data.get('prompt_template', '')

        if not content:
            return jsonify({"success": False, "message": "测试内容不能为空"}), 400

        # 导入生成回复的函数
        try:
            from modules.socialmedia.twitter import generate_reply
        except ImportError:
            logger.error("未找到自动回复模块")
            return jsonify({"success": False, "message": "未找到自动回复模块，无法测试"}), 500

        # 生成回复
        reply = generate_reply(content, prompt_template)

        if reply:
            logger.info("自动回复测试成功")
            return jsonify({
                "success": True,
                "message": "自动回复测试成功",
                "reply": reply
            })
        else:
            logger.warning("自动回复测试失败：未能生成回复内容")
            return jsonify({
                "success": False,
                "message": "未能生成回复内容"
            }), 500
    except Exception as e:
        logger.error(f"测试自动回复时出错: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"测试自动回复时出错: {str(e)}"
        }), 500

@test_api.route('/send_notification', methods=['POST'])
def send_test_notification():
    """发送测试推送消息"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        try:
            data = request.get_json() or {}
            logger.debug(f"收到JSON数据: {data}")
        except Exception as e:
            logger.error(f"解析JSON数据时出错: {str(e)}")
            if request.content_type == 'application/x-www-form-urlencoded':
                data = request.form.to_dict()
                logger.debug(f"收到表单数据: {data}")
            else:
                logger.error(f"不支持的Content-Type: {request.content_type}")
                return jsonify({"success": False, "message": f"不支持的Content-Type: {request.content_type}"}), 415

        # 获取消息内容
        message = data.get('message', '')
        if not message:
            return jsonify({"success": False, "message": "消息内容不能为空"}), 400

        # 导入推送模块
        try:
            from modules.bots.apprise_adapter import send_notification
        except ImportError:
            logger.error("未找到推送模块")
            return jsonify({"success": False, "message": "未找到推送模块，无法发送推送"}), 500

        # 获取推送配置
        from services.config_service import get_config
        apprise_urls = get_config('APPRISE_URLS', '')

        # 如果配置服务中没有，尝试从环境变量获取
        if not apprise_urls:
            apprise_urls = os.getenv('APPRISE_URLS', '')
            logger.info(f"从环境变量获取推送URLs")

        # 如果仍然没有，返回错误
        if not apprise_urls:
            logger.warning("未配置推送URL")
            return jsonify({"success": False, "message": "未配置推送URL，请先在系统设置中配置推送"}), 400

        logger.info(f"使用推送URLs发送测试消息")

        # 添加时间戳到消息
        timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        title = f"TweetAnalyst测试消息 ({timestamp})"

        # 发送推送
        logger.info(f"开始发送测试推送消息: {message}")
        result = send_notification(message=message, title=title)

        if result:
            logger.info("测试推送消息发送成功")
            return jsonify({
                "success": True,
                "message": "测试推送消息发送成功",
                "data": {
                    "timestamp": timestamp,
                    "title": title,
                    "message": message
                }
            })
        else:
            logger.warning("测试推送消息发送失败")
            return jsonify({
                "success": False,
                "message": "测试推送消息发送失败，请检查推送配置和网络连接"
            })
    except Exception as e:
        logger.error(f"发送测试推送消息时出错: {str(e)}")
        return jsonify({"success": False, "message": f"发送测试推送消息失败: {str(e)}"}), 500

@test_api.route('/system_status', methods=['GET'])
def get_system_status():
    """获取系统状态"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    # 获取系统状态
    logger.info("获取系统状态")
    system_status = check_system_status()

    return jsonify({"success": True, "data": system_status})

@test_api.route('/preview_export', methods=['POST'])
def preview_export():
    """预览导出数据"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        try:
            data = request.get_json() or {}
            logger.debug(f"收到JSON数据: {data}")
        except Exception as e:
            logger.error(f"解析JSON数据时出错: {str(e)}")
            if request.content_type == 'application/x-www-form-urlencoded':
                data = request.form.to_dict()
                logger.debug(f"收到表单数据: {data}")
            else:
                logger.error(f"不支持的Content-Type: {request.content_type}")
                return jsonify({"success": False, "message": f"不支持的Content-Type: {request.content_type}"}), 415

        # 获取导出类型和范围
        export_types = data.get('types', [])
        export_scope = data.get('scope', 'all')

        if not export_types:
            return jsonify({"success": False, "message": "未指定导出数据类型"}), 400

        # 从数据库获取预览数据
        preview_data = {}

        # 账号数据预览
        if 'accounts' in export_types:
            from models import SocialAccount
            accounts = SocialAccount.query.limit(5).all()
            preview_data['accounts'] = [account.to_dict() for account in accounts]

        # 分析结果预览
        if 'results' in export_types:
            from models import AnalysisResult

            # 根据导出范围调整查询
            if export_scope == 'recent':
                # 最近30天的数据
                cutoff_date = datetime.datetime.now() - datetime.timedelta(days=30)
                results = AnalysisResult.query.filter(AnalysisResult.created_at >= cutoff_date).limit(5).all()
            elif export_scope == 'essential':
                # 核心配置不包含分析结果
                results = []
            else:
                # 所有数据
                results = AnalysisResult.query.limit(5).all()

            # 转换为字典
            preview_data['results'] = []
            for result in results:
                result_dict = {
                    'post_id': result.post_id,
                    'platform': result.social_network,  # 使用social_network字段作为platform
                    'account_id': result.account_id,
                    'content': result.content[:100] + '...' if result.content and len(result.content) > 100 else result.content,
                    'is_relevant': result.is_relevant,
                    'confidence': result.confidence,
                    'reason': result.reason,
                    'analysis': result.analysis[:100] + '...' if result.analysis and len(result.analysis) > 100 else result.analysis,
                    'created_at': result.created_at.isoformat() if result.created_at else None
                }
                preview_data['results'].append(result_dict)

        # 配置数据预览
        if 'configs' in export_types:
            from models import SystemConfig

            # 获取配置数据
            configs = SystemConfig.query.all()

            # 分类配置
            config_data = {
                'llm': [],
                'twitter': [],
                'notification': [],
                'other': []
            }

            for config in configs:
                config_dict = {
                    'key': config.key,
                    'value': '******' if config.is_secret else config.value,
                    'description': config.description,
                    'is_secret': config.is_secret
                }

                # 根据键名分类
                if config.key.startswith('LLM_'):
                    config_data['llm'].append(config_dict)
                elif config.key.startswith('TWITTER_'):
                    config_data['twitter'].append(config_dict)
                elif config.key.startswith('NOTIFICATION_') or config.key.startswith('PUSH_'):
                    config_data['notification'].append(config_dict)
                else:
                    config_data['other'].append(config_dict)

            preview_data['configs'] = config_data

        # 通知配置预览
        if 'notifications' in export_types:
            from models import NotificationService

            services = NotificationService.query.limit(5).all()
            preview_data['notification_services'] = []

            for service in services:
                service_dict = {
                    'name': service.name,
                    'service_type': service.service_type,
                    'config_url': '******' if service.config_url else '',
                    'is_active': service.is_active
                }
                preview_data['notification_services'].append(service_dict)

        # 添加元数据
        preview_data['version'] = '1.1'
        preview_data['export_time'] = datetime.datetime.now().isoformat()
        preview_data['export_type'] = 'preview'

        return jsonify({
            "success": True,
            "message": "成功生成导出数据预览",
            "data": preview_data
        })

    except Exception as e:
        logger.error(f"生成导出数据预览时出错: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"生成导出数据预览失败: {str(e)}"
        }), 500

@test_api.route('/validate_import_file', methods=['POST'])
def validate_import_file():
    """验证导入文件"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        try:
            data = request.get_json() or {}
            logger.debug(f"收到JSON数据: {data}")
        except Exception as e:
            logger.error(f"解析JSON数据时出错: {str(e)}")
            if request.content_type == 'application/x-www-form-urlencoded':
                data = request.form.to_dict()
                logger.debug(f"收到表单数据: {data}")
            else:
                logger.error(f"不支持的Content-Type: {request.content_type}")
                return jsonify({"success": False, "message": f"不支持的Content-Type: {request.content_type}"}), 415

        # 获取文件数据
        file_data = data.get('file_data', {})

        if not file_data:
            return jsonify({"success": False, "message": "未提供文件数据"}), 400

        # 验证文件格式
        validation_result = {
            "success": True,
            "message": "文件验证通过",
            "data": {
                "valid": True,
                "issues": []
            }
        }

        # 检查必要字段
        required_fields = ['version', 'accounts']
        missing_fields = [field for field in required_fields if field not in file_data]

        if missing_fields:
            validation_result["success"] = False
            validation_result["message"] = f"文件格式不正确，缺少必要字段: {', '.join(missing_fields)}"
            validation_result["data"]["valid"] = False
            validation_result["data"]["issues"].append({
                "type": "missing_fields",
                "message": f"缺少必要字段: {', '.join(missing_fields)}"
            })
            return jsonify(validation_result)

        # 验证版本
        version = file_data.get('version', '1.0')
        if not isinstance(version, str):
            validation_result["data"]["issues"].append({
                "type": "warning",
                "message": "版本号应为字符串格式"
            })

        # 验证账号数据
        accounts = file_data.get('accounts', [])
        if not isinstance(accounts, list):
            validation_result["success"] = False
            validation_result["message"] = "账号数据格式不正确，应为数组"
            validation_result["data"]["valid"] = False
            validation_result["data"]["issues"].append({
                "type": "invalid_format",
                "message": "账号数据格式不正确，应为数组"
            })
        else:
            invalid_accounts = []
            for i, account in enumerate(accounts):
                if not isinstance(account, dict):
                    invalid_accounts.append(f"索引 {i}: 不是有效的对象")
                    continue

                if 'type' not in account or 'account_id' not in account:
                    invalid_accounts.append(f"索引 {i}: 缺少必要字段 type 或 account_id")

            if invalid_accounts:
                validation_result["data"]["issues"].append({
                    "type": "warning",
                    "message": f"发现 {len(invalid_accounts)} 个无效账号数据，这些数据将被跳过",
                    "details": invalid_accounts
                })

        # 验证分析结果数据
        results = file_data.get('results', [])
        if results and not isinstance(results, list):
            validation_result["data"]["issues"].append({
                "type": "warning",
                "message": "分析结果数据格式不正确，应为数组，此部分将被跳过"
            })
        elif results:
            invalid_results = []
            for i, result in enumerate(results):
                if not isinstance(result, dict):
                    invalid_results.append(f"索引 {i}: 不是有效的对象")
                    continue

                if 'post_id' not in result or ('platform' not in result and 'social_network' not in result) or 'account_id' not in result:
                    invalid_results.append(f"索引 {i}: 缺少必要字段 post_id, platform/social_network 或 account_id")

            if invalid_results:
                validation_result["data"]["issues"].append({
                    "type": "warning",
                    "message": f"发现 {len(invalid_results)} 个无效分析结果数据，这些数据将被跳过",
                    "details": invalid_results[:10]  # 只返回前10个，避免响应过大
                })

        # 验证配置数据
        configs = file_data.get('configs', {})
        if configs and not isinstance(configs, dict):
            validation_result["data"]["issues"].append({
                "type": "warning",
                "message": "配置数据格式不正确，应为对象，此部分将被跳过"
            })

        # 统计数据
        validation_result["data"]["stats"] = {
            "account_count": len(accounts) if isinstance(accounts, list) else 0,
            "result_count": len(results) if isinstance(results, list) else 0,
            "config_count": len(configs) if isinstance(configs, dict) else 0
        }

        # 如果有警告但没有错误，仍然标记为有效
        if validation_result["data"]["issues"] and validation_result["data"]["valid"]:
            validation_result["message"] = "文件验证通过，但有一些警告"

        return jsonify(validation_result)

    except Exception as e:
        logger.error(f"验证导入文件时出错: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"验证文件失败: {str(e)}",
            "data": {
                "valid": False,
                "issues": [{
                    "type": "error",
                    "message": str(e)
                }]
            }
        }), 500

@test_api.route('/clean_database', methods=['POST'])
def clean_database():
    """清理数据库"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        try:
            data = request.get_json() or {}
            logger.debug(f"收到JSON数据: {data}")
        except Exception as e:
            logger.error(f"解析JSON数据时出错: {str(e)}")
            if request.content_type == 'application/x-www-form-urlencoded':
                data = request.form.to_dict()
                logger.debug(f"收到表单数据: {data}")
            else:
                logger.error(f"不支持的Content-Type: {request.content_type}")
                return jsonify({"success": False, "message": f"不支持的Content-Type: {request.content_type}"}), 415

        # 获取清理类型
        clean_type = data.get('type', 'all')
        days = int(data.get('days', 30))
        max_records = int(data.get('max_records', 0))
        account_id = data.get('account_id', '')

        # 记录操作开始
        if max_records > 0:
            logger.info(f"开始清理数据库，类型: {clean_type}, 保留最大记录数: {max_records}, 账号ID: {account_id or '所有账号'}")
        else:
            logger.info(f"开始清理数据库，类型: {clean_type}, 保留天数: {days}, 账号ID: {account_id or '所有账号'}")

        # 计算截止日期
        cutoff_date = datetime.datetime.now() - datetime.timedelta(days=days)

        # 根据类型执行不同的清理操作
        deleted_count = 0

        if clean_type == 'all':
            # 清理所有数据
            if max_records > 0:
                # 基于数量的清理
                if account_id:
                    # 针对特定账号
                    # 1. 获取该账号的所有记录，按时间降序排序
                    records = AnalysisResult.query.filter_by(account_id=account_id).order_by(AnalysisResult.post_time.desc()).all()
                    # 2. 如果记录数超过最大值，删除多余的记录
                    if len(records) > max_records:
                        # 获取要删除的记录ID
                        records_to_delete = records[max_records:]
                        delete_ids = [record.id for record in records_to_delete]
                        # 删除记录
                        deleted_count = AnalysisResult.query.filter(AnalysisResult.id.in_(delete_ids)).delete()
                        db.session.commit()
                        logger.info(f"已清理账号 {account_id} 的 {deleted_count} 条记录，保留最新的 {max_records} 条")
                else:
                    # 针对所有账号
                    # 获取所有不同的账号ID
                    account_ids = db.session.query(AnalysisResult.account_id).distinct().all()
                    account_ids = [account[0] for account in account_ids]

                    # 对每个账号分别处理
                    for acc_id in account_ids:
                        # 1. 获取该账号的所有记录，按时间降序排序
                        records = AnalysisResult.query.filter_by(account_id=acc_id).order_by(AnalysisResult.post_time.desc()).all()
                        # 2. 如果记录数超过最大值，删除多余的记录
                        if len(records) > max_records:
                            # 获取要删除的记录ID
                            records_to_delete = records[max_records:]
                            delete_ids = [record.id for record in records_to_delete]
                            # 删除记录
                            acc_deleted_count = AnalysisResult.query.filter(AnalysisResult.id.in_(delete_ids)).delete()
                            deleted_count += acc_deleted_count
                            logger.info(f"已清理账号 {acc_id} 的 {acc_deleted_count} 条记录，保留最新的 {max_records} 条")

                    db.session.commit()
                    logger.info(f"已清理所有账号的旧记录，共 {deleted_count} 条，每个账号保留最新的 {max_records} 条")
            else:
                # 基于时间的清理
                if account_id:
                    # 针对特定账号
                    deleted_count = AnalysisResult.query.filter(
                        AnalysisResult.account_id == account_id,
                        AnalysisResult.created_at < cutoff_date
                    ).delete()
                    db.session.commit()
                    logger.info(f"已清理账号 {account_id} 的 {deleted_count} 条超过 {days} 天的数据")
                else:
                    # 针对所有账号
                    deleted_count = AnalysisResult.query.filter(AnalysisResult.created_at < cutoff_date).delete()
                    db.session.commit()
                    logger.info(f"已清理所有 {deleted_count} 条超过 {days} 天的数据")

        elif clean_type == 'irrelevant':
            # 只清理不相关的数据
            if max_records > 0:
                # 基于数量的清理
                if account_id:
                    # 针对特定账号
                    # 1. 获取该账号的所有不相关记录，按时间降序排序
                    records = AnalysisResult.query.filter_by(account_id=account_id, is_relevant=False).order_by(AnalysisResult.post_time.desc()).all()
                    # 2. 如果记录数超过最大值，删除多余的记录
                    if len(records) > max_records:
                        # 获取要删除的记录ID
                        records_to_delete = records[max_records:]
                        delete_ids = [record.id for record in records_to_delete]
                        # 删除记录
                        deleted_count = AnalysisResult.query.filter(AnalysisResult.id.in_(delete_ids)).delete()
                        db.session.commit()
                        logger.info(f"已清理账号 {account_id} 的 {deleted_count} 条不相关记录，保留最新的 {max_records} 条")
                else:
                    # 针对所有账号
                    # 获取所有不同的账号ID
                    account_ids = db.session.query(AnalysisResult.account_id).distinct().all()
                    account_ids = [account[0] for account in account_ids]

                    # 对每个账号分别处理
                    for acc_id in account_ids:
                        # 1. 获取该账号的所有不相关记录，按时间降序排序
                        records = AnalysisResult.query.filter_by(account_id=acc_id, is_relevant=False).order_by(AnalysisResult.post_time.desc()).all()
                        # 2. 如果记录数超过最大值，删除多余的记录
                        if len(records) > max_records:
                            # 获取要删除的记录ID
                            records_to_delete = records[max_records:]
                            delete_ids = [record.id for record in records_to_delete]
                            # 删除记录
                            acc_deleted_count = AnalysisResult.query.filter(AnalysisResult.id.in_(delete_ids)).delete()
                            deleted_count += acc_deleted_count
                            logger.info(f"已清理账号 {acc_id} 的 {acc_deleted_count} 条不相关记录，保留最新的 {max_records} 条")

                    db.session.commit()
                    logger.info(f"已清理所有账号的旧不相关记录，共 {deleted_count} 条，每个账号保留最新的 {max_records} 条")
            else:
                # 基于时间的清理
                if account_id:
                    # 针对特定账号
                    deleted_count = AnalysisResult.query.filter(
                        AnalysisResult.account_id == account_id,
                        AnalysisResult.created_at < cutoff_date,
                        AnalysisResult.is_relevant == False
                    ).delete()
                    db.session.commit()
                    logger.info(f"已清理账号 {account_id} 的 {deleted_count} 条超过 {days} 天的不相关数据")
                else:
                    # 针对所有账号
                    deleted_count = AnalysisResult.query.filter(
                        AnalysisResult.created_at < cutoff_date,
                        AnalysisResult.is_relevant == False
                    ).delete()
                    db.session.commit()
                    logger.info(f"已清理 {deleted_count} 条超过 {days} 天的不相关数据")

        elif clean_type == 'all_irrelevant':
            # 清理所有不相关的数据，不考虑时间
            if account_id:
                # 针对特定账号
                deleted_count = AnalysisResult.query.filter(
                    AnalysisResult.account_id == account_id,
                    AnalysisResult.is_relevant == False
                ).delete()
                db.session.commit()
                logger.info(f"已清理账号 {account_id} 的所有 {deleted_count} 条不相关数据")
            else:
                # 针对所有账号
                deleted_count = AnalysisResult.query.filter(AnalysisResult.is_relevant == False).delete()
                db.session.commit()
                logger.info(f"已清理所有 {deleted_count} 条不相关数据")

        elif clean_type == 'truncate':
            # 清空整个表
            # 使用原生SQL执行TRUNCATE操作，但需要使用text()函数明确声明为文本SQL
            from sqlalchemy import text
            db.session.execute(text('DELETE FROM analysis_result'))
            db.session.commit()
            logger.warning("已清空整个分析结果表")
            deleted_count = -1  # 表示清空整个表

        else:
            return jsonify({"success": False, "message": f"不支持的清理类型: {clean_type}"}), 400

        # 返回结果
        result_data = {
            "type": clean_type,
            "deleted_count": deleted_count if deleted_count != -1 else "全部",
        }

        # 添加额外的参数
        if max_records > 0:
            result_data["max_records"] = max_records
        else:
            result_data["days"] = days
            if clean_type != 'truncate' and clean_type != 'all_irrelevant':
                result_data["cutoff_date"] = cutoff_date.isoformat()

        if account_id:
            result_data["account_id"] = account_id

        return jsonify({
            "success": True,
            "message": "数据库清理成功",
            "data": result_data
        })

    except Exception as e:
        logger.error(f"清理数据库时出错: {str(e)}")
        db.session.rollback()
        return jsonify({"success": False, "message": f"清理数据库失败: {str(e)}"}), 500

@test_api.route('/clean_logs', methods=['POST'])
def clean_logs():
    """清理日志文件"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        try:
            data = request.get_json() or {}
            logger.debug(f"收到JSON数据: {data}")
        except Exception as e:
            logger.error(f"解析JSON数据时出错: {str(e)}")
            if request.content_type == 'application/x-www-form-urlencoded':
                data = request.form.to_dict()
                logger.debug(f"收到表单数据: {data}")
            else:
                logger.error(f"不支持的Content-Type: {request.content_type}")
                return jsonify({"success": False, "message": f"不支持的Content-Type: {request.content_type}"}), 415

        # 获取清理类型
        clean_type = data.get('type', 'empty')

        # 获取日志目录
        logs_dir = os.path.join(os.getcwd(), 'logs')
        if not os.path.exists(logs_dir):
            return jsonify({"success": False, "message": "日志目录不存在"}), 404

        # 记录操作开始
        logger.info(f"开始清理日志文件，类型: {clean_type}")

        # 根据类型执行不同的清理操作
        cleaned_files = []

        if clean_type == 'empty':
            # 清空所有日志文件内容，但保留文件
            log_files = glob.glob(os.path.join(logs_dir, '*.log'))
            for file_path in log_files:
                try:
                    with open(file_path, 'w') as f:
                        f.write('')
                    cleaned_files.append(os.path.basename(file_path))
                except Exception as e:
                    logger.error(f"清空日志文件 {file_path} 时出错: {str(e)}")

            logger.info(f"已清空 {len(cleaned_files)} 个日志文件")

        elif clean_type == 'delete':
            # 删除所有日志文件
            log_files = glob.glob(os.path.join(logs_dir, '*.log'))
            for file_path in log_files:
                try:
                    os.remove(file_path)
                    cleaned_files.append(os.path.basename(file_path))
                except Exception as e:
                    logger.error(f"删除日志文件 {file_path} 时出错: {str(e)}")

            logger.info(f"已删除 {len(cleaned_files)} 个日志文件")

        elif clean_type == 'backup_and_empty':
            # 备份并清空日志文件
            backup_dir = os.path.join(logs_dir, f'backup_{datetime.datetime.now().strftime("%Y%m%d_%H%M%S")}')
            os.makedirs(backup_dir, exist_ok=True)

            log_files = glob.glob(os.path.join(logs_dir, '*.log'))
            for file_path in log_files:
                try:
                    # 备份文件
                    shutil.copy2(file_path, os.path.join(backup_dir, os.path.basename(file_path)))

                    # 清空文件
                    with open(file_path, 'w') as f:
                        f.write('')

                    cleaned_files.append(os.path.basename(file_path))
                except Exception as e:
                    logger.error(f"备份并清空日志文件 {file_path} 时出错: {str(e)}")

            logger.info(f"已备份并清空 {len(cleaned_files)} 个日志文件，备份目录: {backup_dir}")

        else:
            return jsonify({"success": False, "message": f"不支持的清理类型: {clean_type}"}), 400

        # 返回结果
        return jsonify({
            "success": True,
            "message": "日志清理成功",
            "data": {
                "type": clean_type,
                "cleaned_files": cleaned_files,
                "count": len(cleaned_files)
            }
        })

    except Exception as e:
        logger.error(f"清理日志文件时出错: {str(e)}")
        return jsonify({"success": False, "message": f"清理日志文件失败: {str(e)}"}), 500
