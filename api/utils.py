"""
API工具模块
提供API响应格式化和错误处理功能
"""

import logging
import traceback
from functools import wraps
from flask import jsonify, session, request

# 创建日志记录器
logger = logging.getLogger('api.utils')

def api_response(success=True, message=None, data=None, status_code=200, **kwargs):
    """
    格式化API响应
    
    Args:
        success: 是否成功
        message: 消息
        data: 数据
        status_code: HTTP状态码
        **kwargs: 其他参数
        
    Returns:
        tuple: (response, status_code)
    """
    response = {
        "success": success,
    }
    
    if message:
        response["message"] = message
        
    if data is not None:
        response["data"] = data
        
    # 添加其他参数
    for key, value in kwargs.items():
        response[key] = value
        
    return jsonify(response), status_code

def handle_api_exception(func):
    """
    API异常处理装饰器
    
    Args:
        func: 被装饰的函数
        
    Returns:
        function: 装饰后的函数
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            # 记录详细错误信息
            logger.error(f"API错误: {str(e)}")
            logger.error(f"请求路径: {request.path}")
            logger.error(f"请求方法: {request.method}")
            logger.error(f"请求参数: {request.args}")
            logger.error(f"请求JSON: {request.get_json(silent=True)}")
            logger.error(f"堆栈跟踪: {traceback.format_exc()}")
            
            # 返回错误响应
            return api_response(
                success=False,
                message=f"服务器错误: {str(e)}",
                error_type=e.__class__.__name__,
                status_code=500
            )
    return wrapper

def login_required(func):
    """
    登录验证装饰器
    
    Args:
        func: 被装饰的函数
        
    Returns:
        function: 装饰后的函数
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        if 'user_id' not in session:
            logger.warning(f"未登录用户尝试访问: {request.path}")
            return api_response(
                success=False,
                message="未登录或会话已过期，请重新登录",
                status_code=401
            )
        return func(*args, **kwargs)
    return wrapper

def validate_json_request(required_fields=None):
    """
    验证JSON请求装饰器
    
    Args:
        required_fields: 必需的字段列表
        
    Returns:
        function: 装饰器函数
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # 检查Content-Type
            if not request.is_json:
                logger.warning(f"无效的Content-Type: {request.content_type}")
                return api_response(
                    success=False,
                    message="请求必须是JSON格式",
                    status_code=400
                )
            
            # 获取JSON数据
            data = request.get_json(silent=True)
            if data is None:
                logger.warning("无法解析JSON数据")
                return api_response(
                    success=False,
                    message="无法解析JSON数据",
                    status_code=400
                )
            
            # 验证必需字段
            if required_fields:
                missing_fields = [field for field in required_fields if field not in data]
                if missing_fields:
                    logger.warning(f"缺少必需字段: {missing_fields}")
                    return api_response(
                        success=False,
                        message=f"缺少必需字段: {', '.join(missing_fields)}",
                        status_code=400
                    )
            
            return func(*args, **kwargs)
        return wrapper
    return decorator
