"""
测试API模块
处理所有测试相关的API请求
"""

import logging
import time
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
    data = request.get_json() or {}
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
    data = request.get_json() or {}
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
    data = request.get_json() or {}
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
        data = request.get_json() or {}
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
        for url in urls.splitlines():
            url = url.strip()
            if url:
                apobj.add(url)
        
        if not apobj.servers:
            return jsonify({"success": False, "message": "未添加有效的推送URL"}), 400
        
        # 发送测试消息
        start_time = time.time()
        result = apobj.notify(
            title="TweetAnalyst测试通知",
            body="这是一条测试通知，如果您收到此消息，说明推送设置正确。"
        )
        end_time = time.time()
        
        if result:
            logger.info("推送测试成功")
            return jsonify({
                "success": True,
                "message": "推送测试成功",
                "data": {
                    "sent_to": f"{len(apobj.servers)}个目标",
                    "response_time": f"{end_time - start_time:.2f}秒"
                }
            })
        else:
            logger.warning("推送测试失败")
            return jsonify({
                "success": False,
                "message": "推送发送失败，请检查URL格式是否正确",
                "data": {
                    "urls": urls
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
