"""
TweetAnalyst API包
提供统一的API接口，包括设置、测试、账号管理、数据分析等功能
"""

from flask import Blueprint, jsonify, redirect, url_for, request

# 导入统一的API工具类
from utils.api_utils import (
    api_request, get, post, put, delete,
    APIError, ConnectionAPIError, TimeoutAPIError,
    AuthenticationAPIError, RateLimitAPIError, ServerAPIError, ClientAPIError
)
from utils.api_decorators import handle_api_errors, retry_on_error, cache_result

# 创建主API蓝图
api_blueprint = Blueprint('api', __name__, url_prefix='/api')

# 导入系统API
from .system import system_api

# 导入各模块API
from .settings import settings_api
from .test import test_api
from .accounts import accounts_api
from .analytics import analytics_api
from .logs import logs_api
from .notifications import notifications_api
from .tasks import tasks_api
from .ai_provider import ai_provider_bp
from .proxy import proxy_api
from .twitter import twitter_api

# 注册子蓝图
api_blueprint.register_blueprint(system_api)
api_blueprint.register_blueprint(settings_api)
api_blueprint.register_blueprint(test_api)
api_blueprint.register_blueprint(accounts_api)
api_blueprint.register_blueprint(analytics_api)
api_blueprint.register_blueprint(tasks_api)
api_blueprint.register_blueprint(logs_api)
api_blueprint.register_blueprint(notifications_api)
api_blueprint.register_blueprint(ai_provider_bp)
api_blueprint.register_blueprint(proxy_api)
api_blueprint.register_blueprint(twitter_api)

# 版本信息
__version__ = '1.0.0'
