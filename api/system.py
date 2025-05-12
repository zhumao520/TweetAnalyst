"""
系统API模块
处理所有系统相关的API请求，包括系统状态检查
"""

import logging
import time
import datetime
import os
import platform
from flask import Blueprint, request, jsonify, session, current_app
from utils.test_utils import check_system_status
from models import db
from services.test_service import check_system_status as service_check_system_status
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
    # 获取系统状态
    logger.info("获取系统状态")

    # 检查数据库连接
    database_status = "normal"  # 默认为正常状态
    try:
        # 直接使用Flask应用上下文检查数据库连接
        # 避免循环导入main模块
        try:
            from web_app import AnalysisResult, db, app
            with app.app_context():
                db_count = AnalysisResult.query.count()
                logger.info(f"数据库连接正常，已有 {db_count} 条分析结果记录")
        except Exception as db_error:
            database_status = "error"
            logger.error(f"测试数据库连接时出错: {str(db_error)}")
    except ImportError as import_error:
        database_status = "error"
        logger.error(f"导入数据库模块时出错: {str(import_error)}")
    except Exception as e:
        database_status = "error"
        logger.error(f"检查数据库连接时出错: {str(e)}")

    # 检查AI服务状态
    ai_status = "normal"  # 默认为正常状态
    try:
        # 检查LLM API密钥是否存在
        from services.config_service import get_config
        llm_api_key = get_config('LLM_API_KEY')
        if not llm_api_key:
            ai_status = "error"
            logger.warning("LLM API密钥未配置")
        else:
            # 尝试进行简单的API调用测试
            try:
                # 导入但不执行，避免每次检查都调用API
                from modules.langchain.llm import get_llm_response_with_cache
                logger.info("AI模块加载正常")
            except Exception as e:
                ai_status = "warning"
                logger.warning(f"AI模块加载异常: {str(e)}")
    except Exception as e:
        ai_status = "error"
        logger.error(f"检查AI服务状态时出错: {str(e)}")

    # 检查推送服务状态
    notification_status = "normal"  # 默认为正常状态
    try:
        # 检查推送URL是否配置
        from services.config_service import get_config
        apprise_urls = get_config('APPRISE_URLS')
        if not apprise_urls:
            notification_status = "warning"
            logger.warning("推送服务URL未配置")
        else:
            # 尝试加载推送模块
            try:
                from modules.bots.apprise_adapter import send_notification
                logger.info("推送模块加载正常")
            except Exception as e:
                notification_status = "warning"
                logger.warning(f"推送模块加载异常: {str(e)}")
    except Exception as e:
        notification_status = "error"
        logger.error(f"检查推送服务状态时出错: {str(e)}")

    # 返回状态信息
    return api_response(
        success=True,
        database_status=database_status,
        ai_status=ai_status,
        notification_status=notification_status,
        timestamp=datetime.datetime.now().timestamp()
    )

@system_api.route('/info', methods=['GET'])
@login_required
@handle_api_exception
def get_system_info():
    """获取系统详细信息"""
    # 获取系统详细信息
    logger.info("获取系统详细信息")
    system_status = service_check_system_status()

    return api_response(
        success=True,
        data=system_status
    )
