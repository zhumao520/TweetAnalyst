"""
系统API模块
处理所有系统相关的API请求，包括系统状态检查
"""

import logging
from flask import Blueprint
from api.utils import api_response, handle_api_exception, login_required

# 创建日志记录器
logger = logging.getLogger('api.system')

# 创建Blueprint
system_api = Blueprint('system_api', __name__, url_prefix='/system')

@system_api.route('/status', methods=['GET'])
@login_required
@handle_api_exception
def get_system_status():
    """获取系统状态"""
    logger.info("获取系统状态")

    try:
        # 使用系统状态服务获取详细状态
        from services.system_status_service import get_system_status
        status_data = get_system_status()

        # 转换为API响应格式
        response_data = {
            "database_status": status_data['database']['status'],
            "database_message": status_data['database']['message'],
            "database_details": status_data['database']['details'],

            "ai_status": status_data['ai_service']['status'],
            "ai_message": status_data['ai_service']['message'],
            "ai_details": status_data['ai_service']['details'],

            "notification_status": status_data['notification']['status'],
            "notification_message": status_data['notification']['message'],
            "notification_details": status_data['notification']['details'],

            "proxy_status": status_data['proxy']['status'],
            "proxy_message": status_data['proxy']['message'],
            "proxy_details": status_data['proxy']['details'],

            "twitter_status": status_data['twitter']['status'],
            "twitter_message": status_data['twitter']['message'],
            "twitter_details": status_data['twitter']['details'],

            "core_scraping_status": status_data['core_scraping']['status'],
            "core_scraping_message": status_data['core_scraping']['message'],
            "core_scraping_details": status_data['core_scraping']['details'],

            "timestamp": status_data['timestamp']
        }

        return api_response(
            success=True,
            message="系统状态检查完成",
            **response_data
        )

    except Exception as e:
        logger.error(f"获取系统状态时出错: {str(e)}")
        return api_response(
            success=False,
            message=f"获取系统状态失败: {str(e)}"
        ), 500

# 系统详细信息接口已移除，相关功能已集成到状态检查中
