"""
数据模型包
包含所有数据库模型定义
"""

from flask_sqlalchemy import SQLAlchemy

# 创建数据库实例
db = SQLAlchemy()

# 导入所有模型
from .user import User
from .social_account import SocialAccount
from .analysis_result import AnalysisResult
from .system_config import SystemConfig
from .system_state import SystemState

# 版本信息
__version__ = '1.0.0'
