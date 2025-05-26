"""
代理API模块
处理所有代理相关的API请求
"""

import logging
from flask import Blueprint, request, jsonify, session
from services.proxy_service import (
    get_all_proxies, get_proxy_by_id, create_proxy, update_proxy,
    delete_proxy, test_proxy, test_all_proxies, find_working_proxy
)
from api.utils import api_response, handle_api_exception, login_required
from utils.api_utils import get_proxy_manager
# 移除CSRF导入，避免循环导入

# 创建日志记录器
logger = logging.getLogger('api.proxy')

# 创建Blueprint
proxy_api = Blueprint('proxy_api', __name__, url_prefix='/proxy')

@proxy_api.route('/list', methods=['GET'])
@login_required
@handle_api_exception
def list_proxies():
    """获取所有代理配置"""
    logger.info("获取所有代理配置")
    proxies = get_all_proxies()
    return api_response(
        success=True,
        data=proxies
    )

@proxy_api.route('/<int:proxy_id>', methods=['GET'])
@login_required
@handle_api_exception
def get_proxy(proxy_id):
    """获取特定代理配置"""
    logger.info(f"获取代理配置: {proxy_id}")
    proxy = get_proxy_by_id(proxy_id)
    if not proxy:
        return api_response(
            success=False,
            message="代理配置不存在"
        ), 404
    return api_response(
        success=True,
        data=proxy
    )

@proxy_api.route('/', methods=['POST'])
@login_required
@handle_api_exception
def add_proxy():
    """添加代理配置"""
    data = request.get_json()
    logger.info(f"添加代理配置: {data}")

    # 验证必填字段
    required_fields = ['name', 'host', 'port', 'protocol']
    for field in required_fields:
        if field not in data:
            return api_response(
                success=False,
                message=f"缺少必填字段: {field}"
            ), 400

    # 创建代理配置
    proxy = create_proxy(
        name=data['name'],
        host=data['host'],
        port=int(data['port']),
        protocol=data['protocol'],
        username=data.get('username'),
        password=data.get('password'),
        priority=int(data.get('priority', 0)),
        is_active=bool(data.get('is_active', True))
    )

    if not proxy:
        return api_response(
            success=False,
            message="创建代理配置失败"
        ), 500

    # 重新初始化代理管理器
    get_proxy_manager(force_new=True)

    return api_response(
        success=True,
        message="代理配置已添加",
        data=proxy
    )

@proxy_api.route('/<int:proxy_id>', methods=['PUT'])
@login_required
@handle_api_exception
def update_proxy_config(proxy_id):
    """更新代理配置"""
    data = request.get_json()
    logger.info(f"更新代理配置: {proxy_id}, {data}")

    # 更新代理配置
    proxy = update_proxy(proxy_id, **data)

    if not proxy:
        return api_response(
            success=False,
            message="更新代理配置失败，代理可能不存在"
        ), 404

    # 重新初始化代理管理器
    get_proxy_manager(force_new=True)

    return api_response(
        success=True,
        message="代理配置已更新",
        data=proxy
    )

@proxy_api.route('/<int:proxy_id>', methods=['DELETE'])
@login_required
@handle_api_exception
def remove_proxy(proxy_id):
    """删除代理配置"""
    logger.info(f"删除代理配置: {proxy_id}")

    # 删除代理配置
    success = delete_proxy(proxy_id)

    if not success:
        return api_response(
            success=False,
            message="删除代理配置失败，代理可能不存在"
        ), 404

    # 重新初始化代理管理器
    get_proxy_manager(force_new=True)

    return api_response(
        success=True,
        message="代理配置已删除"
    )

@proxy_api.route('/<int:proxy_id>/test', methods=['POST'])
@login_required
@handle_api_exception
def test_proxy_connection(proxy_id):
    """测试代理连接"""
    data = request.get_json() or {}
    test_url = data.get('url')

    logger.info(f"测试代理连接: {proxy_id}, URL: {test_url}")

    # 测试代理连接
    result = test_proxy(proxy_id, test_url)

    return api_response(
        success=result.get('success', False),
        message=result.get('message', ''),
        data=result.get('data')
    )

@proxy_api.route('/test_all', methods=['POST'])
@login_required
@handle_api_exception
def test_all_proxy_connections():
    """测试所有代理连接"""
    data = request.get_json() or {}
    test_url = data.get('url')

    logger.info(f"测试所有代理连接, URL: {test_url}")

    # 测试所有代理连接
    results = test_all_proxies(test_url)

    return api_response(
        success=True,
        data=results
    )

@proxy_api.route('/working', methods=['GET'])
@login_required
@handle_api_exception
def get_working_proxy():
    """获取可用的代理"""
    logger.info("获取可用的代理")

    # 获取可用的代理
    proxy = find_working_proxy()

    if not proxy:
        return api_response(
            success=False,
            message="未找到可用的代理"
        ), 404

    return api_response(
        success=True,
        data=proxy
    )
