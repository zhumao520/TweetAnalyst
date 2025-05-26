"""
代理配置服务

提供代理配置的增删改查功能
"""

import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
import requests
import time

from models import db, ProxyConfig
from utils.logger import get_logger

logger = get_logger('proxy_service')

def get_all_proxies() -> List[Dict[str, Any]]:
    """
    获取所有代理配置

    Returns:
        List[Dict[str, Any]]: 代理配置列表
    """
    try:
        proxies = ProxyConfig.query.order_by(ProxyConfig.priority).all()
        return [proxy.to_dict() for proxy in proxies]
    except Exception as e:
        logger.error(f"获取代理配置列表时出错: {str(e)}")
        return []

def get_proxy_by_id(proxy_id: int) -> Optional[Dict[str, Any]]:
    """
    根据ID获取代理配置

    Args:
        proxy_id (int): 代理配置ID

    Returns:
        Optional[Dict[str, Any]]: 代理配置，如果不存在则返回None
    """
    try:
        proxy = ProxyConfig.query.get(proxy_id)
        if proxy:
            return proxy.to_dict()
        return None
    except Exception as e:
        logger.error(f"获取代理配置时出错: {str(e)}")
        return None

def create_proxy(name: str, host: str, port: int, protocol: str = 'http',
                username: str = None, password: str = None, priority: int = 0,
                is_active: bool = True) -> Optional[Dict[str, Any]]:
    """
    创建代理配置

    Args:
        name (str): 代理名称
        host (str): 代理主机
        port (int): 代理端口
        protocol (str, optional): 代理协议. 默认为 'http'.
        username (str, optional): 用户名. 默认为 None.
        password (str, optional): 密码. 默认为 None.
        priority (int, optional): 优先级. 默认为 0.
        is_active (bool, optional): 是否激活. 默认为 True.

    Returns:
        Optional[Dict[str, Any]]: 创建的代理配置，如果失败则返回None
    """
    try:
        proxy = ProxyConfig(
            name=name,
            host=host,
            port=port,
            protocol=protocol.lower(),
            username=username,
            password=password,
            priority=priority,
            is_active=is_active
        )
        db.session.add(proxy)
        db.session.commit()
        logger.info(f"创建代理配置成功: {name}")
        return proxy.to_dict()
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建代理配置时出错: {str(e)}")
        return None

def update_proxy(proxy_id: int, **kwargs) -> Optional[Dict[str, Any]]:
    """
    更新代理配置

    Args:
        proxy_id (int): 代理配置ID
        **kwargs: 要更新的字段

    Returns:
        Optional[Dict[str, Any]]: 更新后的代理配置，如果失败则返回None
    """
    try:
        proxy = ProxyConfig.query.get(proxy_id)
        if not proxy:
            logger.warning(f"代理配置不存在: {proxy_id}")
            return None

        # 更新字段
        for key, value in kwargs.items():
            if hasattr(proxy, key):
                setattr(proxy, key, value)

        db.session.commit()
        logger.info(f"更新代理配置成功: {proxy.name}")
        return proxy.to_dict()
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新代理配置时出错: {str(e)}")
        return None

def delete_proxy(proxy_id: int) -> bool:
    """
    删除代理配置

    Args:
        proxy_id (int): 代理配置ID

    Returns:
        bool: 是否删除成功
    """
    try:
        proxy = ProxyConfig.query.get(proxy_id)
        if not proxy:
            logger.warning(f"代理配置不存在: {proxy_id}")
            return False

        db.session.delete(proxy)
        db.session.commit()
        logger.info(f"删除代理配置成功: {proxy.name}")
        return True
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除代理配置时出错: {str(e)}")
        return False

def test_proxy(proxy_id: int, test_url: str = None) -> Dict[str, Any]:
    """
    测试代理连接

    Args:
        proxy_id (int): 代理配置ID
        test_url (str, optional): 测试URL. 默认为 None.

    Returns:
        Dict[str, Any]: 测试结果
    """
    try:
        proxy = ProxyConfig.query.get(proxy_id)
        if not proxy:
            return {
                "success": False,
                "message": f"代理配置不存在: {proxy_id}"
            }

        # 如果没有提供测试URL，使用默认测试URL
        if not test_url:
            test_url = "https://www.google.com/generate_204"

        # 获取代理字典
        proxies = proxy.get_proxy_dict()

        # 测试连接
        start_time = time.time()
        try:
            response = requests.get(test_url, proxies=proxies, timeout=10, verify=False)
            end_time = time.time()
            response_time = end_time - start_time

            # 更新代理测试结果
            proxy.last_check_time = datetime.now()
            proxy.last_check_result = response.status_code in [200, 204]
            proxy.response_time = response_time
            db.session.commit()

            if response.status_code in [200, 204]:
                return {
                    "success": True,
                    "message": "代理连接测试成功",
                    "data": {
                        "proxy": proxy.to_dict(),
                        "status_code": response.status_code,
                        "response_time": f"{response_time:.2f}秒"
                    }
                }
            else:
                return {
                    "success": False,
                    "message": f"代理连接测试失败，状态码: {response.status_code}",
                    "data": {
                        "proxy": proxy.to_dict(),
                        "status_code": response.status_code,
                        "response_time": f"{response_time:.2f}秒"
                    }
                }
        except Exception as e:
            # 更新代理测试结果
            proxy.last_check_time = datetime.now()
            proxy.last_check_result = False
            db.session.commit()

            return {
                "success": False,
                "message": f"代理连接测试失败: {str(e)}",
                "data": {
                    "proxy": proxy.to_dict(),
                    "error": str(e)
                }
            }
    except Exception as e:
        logger.error(f"测试代理连接时出错: {str(e)}")
        return {
            "success": False,
            "message": f"测试代理连接时出错: {str(e)}"
        }

def test_all_proxies(test_url: str = None) -> List[Dict[str, Any]]:
    """
    测试所有代理连接

    Args:
        test_url (str, optional): 测试URL. 默认为 None.

    Returns:
        List[Dict[str, Any]]: 测试结果列表
    """
    results = []
    proxies = ProxyConfig.query.filter_by(is_active=True).order_by(ProxyConfig.priority).all()

    for proxy in proxies:
        result = test_proxy(proxy.id, test_url)
        results.append(result)

    return results

def find_working_proxy() -> Optional[Dict[str, Any]]:
    """
    查找可用的代理

    Returns:
        Optional[Dict[str, Any]]: 可用的代理配置，如果没有则返回None
    """
    try:
        # 先查找最近测试成功的代理，按优先级降序排序（数字越大优先级越高）
        proxy = ProxyConfig.query.filter_by(
            is_active=True,
            last_check_result=True
        ).order_by(ProxyConfig.priority.desc()).first()

        if proxy:
            return proxy.to_dict()

        # 如果没有最近测试成功的代理，测试所有代理
        results = test_all_proxies()
        for result in results:
            if result.get("success"):
                return result.get("data", {}).get("proxy")

        return None
    except Exception as e:
        logger.error(f"查找可用代理时出错: {str(e)}")
        return None
