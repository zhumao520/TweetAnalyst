"""
TweetAnalyst API包
提供统一的API接口，包括设置、测试、账号管理、数据分析等功能
"""

from flask import Blueprint

# 创建主API蓝图
api_blueprint = Blueprint('api', __name__, url_prefix='/api')

# 导入各模块API
from .settings import settings_api
from .test import test_api
from .accounts import accounts_api
from .analytics import analytics_api
from .tasks import tasks_api
from .logs import logs_api

# 注册子蓝图
api_blueprint.register_blueprint(settings_api)
api_blueprint.register_blueprint(test_api)
api_blueprint.register_blueprint(accounts_api)
api_blueprint.register_blueprint(analytics_api)
api_blueprint.register_blueprint(tasks_api)
api_blueprint.register_blueprint(logs_api)

# 版本信息
__version__ = '1.0.0'
