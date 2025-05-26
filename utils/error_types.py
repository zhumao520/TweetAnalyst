"""
统一的错误类型定义
确保前后端错误处理的一致性
"""

# 错误类型常量
class ErrorTypes:
    """错误类型枚举"""
    NETWORK = 'network'
    TIMEOUT = 'timeout'
    SERVER = 'server'
    CLIENT = 'client'
    AUTH = 'auth'
    PARSE = 'parse'
    UNKNOWN = 'unknown'
    CONNECTION = 'connection'
    RATE_LIMIT = 'rate_limit'

# 错误类型映射（用于前后端一致性）
ERROR_TYPE_MAPPING = {
    # 后端异常类名到前端错误类型的映射
    'ConnectionAPIError': ErrorTypes.CONNECTION,
    'TimeoutAPIError': ErrorTypes.TIMEOUT,
    'AuthenticationAPIError': ErrorTypes.AUTH,
    'RateLimitAPIError': ErrorTypes.RATE_LIMIT,
    'ServerAPIError': ErrorTypes.SERVER,
    'ClientAPIError': ErrorTypes.CLIENT,
    'ResponseParseError': ErrorTypes.PARSE,
    'APIError': ErrorTypes.UNKNOWN,
    
    # HTTP状态码到错误类型的映射
    400: ErrorTypes.CLIENT,
    401: ErrorTypes.AUTH,
    403: ErrorTypes.AUTH,
    404: ErrorTypes.CLIENT,
    429: ErrorTypes.RATE_LIMIT,
    500: ErrorTypes.SERVER,
    502: ErrorTypes.SERVER,
    503: ErrorTypes.SERVER,
    504: ErrorTypes.TIMEOUT,
}

# 错误消息模板
ERROR_MESSAGES = {
    ErrorTypes.NETWORK: "网络连接错误，请检查您的网络连接",
    ErrorTypes.TIMEOUT: "请求超时，服务器响应时间过长",
    ErrorTypes.SERVER: "服务器错误，请稍后重试",
    ErrorTypes.CLIENT: "请求错误，请检查请求参数",
    ErrorTypes.AUTH: "认证失败，请重新登录",
    ErrorTypes.PARSE: "无法解析服务器响应",
    ErrorTypes.UNKNOWN: "未知错误",
    ErrorTypes.CONNECTION: "连接错误，无法连接到服务器",
    ErrorTypes.RATE_LIMIT: "请求过于频繁，请稍后再试",
}

# 可重试的错误类型
RETRYABLE_ERROR_TYPES = {
    ErrorTypes.NETWORK,
    ErrorTypes.TIMEOUT,
    ErrorTypes.SERVER,
    ErrorTypes.CONNECTION,
    ErrorTypes.RATE_LIMIT,
}

# 不可重试的错误类型
NON_RETRYABLE_ERROR_TYPES = {
    ErrorTypes.AUTH,
    ErrorTypes.CLIENT,
    ErrorTypes.PARSE,
}

def get_error_type_from_status_code(status_code):
    """
    根据HTTP状态码获取错误类型
    
    Args:
        status_code (int): HTTP状态码
        
    Returns:
        str: 错误类型
    """
    if status_code in ERROR_TYPE_MAPPING:
        return ERROR_TYPE_MAPPING[status_code]
    
    if 400 <= status_code < 500:
        if status_code in [401, 403]:
            return ErrorTypes.AUTH
        elif status_code == 429:
            return ErrorTypes.RATE_LIMIT
        else:
            return ErrorTypes.CLIENT
    elif 500 <= status_code < 600:
        if status_code == 504:
            return ErrorTypes.TIMEOUT
        else:
            return ErrorTypes.SERVER
    else:
        return ErrorTypes.UNKNOWN

def get_error_message(error_type, status_code=None, custom_message=None):
    """
    获取错误消息
    
    Args:
        error_type (str): 错误类型
        status_code (int, optional): HTTP状态码
        custom_message (str, optional): 自定义消息
        
    Returns:
        str: 错误消息
    """
    if custom_message:
        return custom_message
    
    base_message = ERROR_MESSAGES.get(error_type, ERROR_MESSAGES[ErrorTypes.UNKNOWN])
    
    if status_code:
        return f"{base_message} (状态码: {status_code})"
    
    return base_message

def is_retryable_error(error_type):
    """
    判断错误是否可重试
    
    Args:
        error_type (str): 错误类型
        
    Returns:
        bool: 是否可重试
    """
    return error_type in RETRYABLE_ERROR_TYPES

def classify_error_from_exception(exception, status_code=None):
    """
    从异常对象分类错误
    
    Args:
        exception (Exception): 异常对象
        status_code (int, optional): HTTP状态码
        
    Returns:
        tuple: (错误类型, 错误消息)
    """
    exception_name = exception.__class__.__name__
    
    # 首先检查异常类名映射
    if exception_name in ERROR_TYPE_MAPPING:
        error_type = ERROR_TYPE_MAPPING[exception_name]
        return error_type, get_error_message(error_type, status_code)
    
    # 检查异常消息中的关键词
    error_message = str(exception).lower()
    
    if 'timeout' in error_message:
        return ErrorTypes.TIMEOUT, get_error_message(ErrorTypes.TIMEOUT, status_code)
    elif 'connection' in error_message or 'network' in error_message:
        return ErrorTypes.CONNECTION, get_error_message(ErrorTypes.CONNECTION, status_code)
    elif 'json' in error_message and 'parse' in error_message:
        return ErrorTypes.PARSE, get_error_message(ErrorTypes.PARSE, status_code)
    
    # 如果有状态码，根据状态码分类
    if status_code:
        error_type = get_error_type_from_status_code(status_code)
        return error_type, get_error_message(error_type, status_code)
    
    # 默认返回未知错误
    return ErrorTypes.UNKNOWN, get_error_message(ErrorTypes.UNKNOWN, status_code, str(exception))

def create_error_response(error_type, message=None, status_code=None, data=None):
    """
    创建标准化的错误响应
    
    Args:
        error_type (str): 错误类型
        message (str, optional): 错误消息
        status_code (int, optional): HTTP状态码
        data (dict, optional): 额外数据
        
    Returns:
        dict: 标准化的错误响应
    """
    response = {
        'success': False,
        'error_type': error_type,
        'message': message or get_error_message(error_type, status_code),
        'retryable': is_retryable_error(error_type)
    }
    
    if status_code:
        response['status_code'] = status_code
    
    if data:
        response['data'] = data
    
    return response
