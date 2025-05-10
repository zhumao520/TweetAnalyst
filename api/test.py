"""
测试API模块
处理所有测试相关的API请求
"""

import logging
import time
import datetime
import os
from flask import Blueprint, request, jsonify, session, current_app
from utils.test_utils import test_twitter_connection, test_llm_connection, test_proxy_connection, check_system_status

# 创建日志记录器
logger = logging.getLogger('api.test')

# 创建Blueprint
test_api = Blueprint('test_api', __name__, url_prefix='/test')

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
    """测试代理连接"""
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

    # 执行测试
    logger.info(f"开始测试代理连接，URL: {test_url}")
    result = test_proxy_connection(test_url)

    if result['success']:
        logger.info("代理连接测试成功")
    else:
        logger.warning(f"代理连接测试失败: {result['message']}")

    return jsonify(result)

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

        if not urls:
            return jsonify({"success": False, "message": "未提供推送URL"}), 400

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
                            "proxy_used": proxy if proxy else "未使用代理"
                        }
                    })
                else:
                    # 收集错误信息
                    for server in apobj.servers():
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
