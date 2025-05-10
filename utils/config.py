"""
配置工具函数
提供配置读写功能
"""

import os
import logging
from services.config_service import get_config as get_config_service
from services.config_service import set_config as set_config_service
from services.config_service import get_default_prompt_template as get_default_prompt_template_service

# 创建日志记录器
logger = logging.getLogger('utils.config')

def get_config(key, default=None):
    """
    获取系统配置
    
    Args:
        key: 配置键
        default: 默认值
        
    Returns:
        str: 配置值
    """
    return get_config_service(key, default)

def set_config(key, value, is_secret=False, description=None, update_env=True):
    """
    设置系统配置
    
    Args:
        key: 配置键
        value: 配置值
        is_secret: 是否为敏感信息
        description: 配置描述
        update_env: 是否更新环境变量
        
    Returns:
        SystemConfig: 配置对象
    """
    return set_config_service(key, value, is_secret, description, update_env)

def get_default_prompt_template(account_type):
    """
    获取默认提示词模板
    
    Args:
        account_type: 账号类型
        
    Returns:
        str: 提示词模板
    """
    return get_default_prompt_template_service(account_type)
