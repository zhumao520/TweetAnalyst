"""
日志模块 - 提供统一的日志记录功能
"""
import os
import logging
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
import sys
from dotenv import load_dotenv

load_dotenv()

# 日志级别映射
LOG_LEVELS = {
    'debug': logging.DEBUG,
    'info': logging.INFO,
    'warning': logging.WARNING,
    'error': logging.ERROR,
    'critical': logging.CRITICAL
}

# 从环境变量获取日志配置
LOG_LEVEL = os.getenv('LOG_LEVEL', 'info').lower()
LOG_DIR = os.getenv('LOG_DIR', 'logs')
LOG_FILE_MAX_SIZE = int(os.getenv('LOG_FILE_MAX_SIZE', 10 * 1024 * 1024))  # 默认10MB
LOG_FILE_BACKUP_COUNT = int(os.getenv('LOG_FILE_BACKUP_COUNT', 5))  # 默认保留5个备份
LOG_TO_CONSOLE = os.getenv('LOG_TO_CONSOLE', 'true').lower() == 'true'
LOG_ROTATION_TYPE = os.getenv('LOG_ROTATION_TYPE', 'size').lower()  # size或time

# 确保日志目录存在
if not os.path.exists(LOG_DIR):
    os.makedirs(LOG_DIR)

# 日志格式
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

def get_logger(name):
    """
    获取指定名称的日志记录器
    
    Args:
        name (str): 日志记录器名称，通常使用模块名
        
    Returns:
        logging.Logger: 日志记录器实例
    """
    logger = logging.getLogger(name)
    
    # 如果已经配置过，直接返回
    if logger.handlers:
        return logger
    
    # 设置日志级别
    logger.setLevel(LOG_LEVELS.get(LOG_LEVEL, logging.INFO))
    
    # 创建格式化器
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)
    
    # 添加文件处理器
    log_file = os.path.join(LOG_DIR, f'{name}.log')
    
    if LOG_ROTATION_TYPE == 'time':
        # 按时间轮转，每天一个文件
        file_handler = TimedRotatingFileHandler(
            log_file, 
            when='midnight',
            interval=1,
            backupCount=LOG_FILE_BACKUP_COUNT
        )
    else:
        # 按大小轮转
        file_handler = RotatingFileHandler(
            log_file, 
            maxBytes=LOG_FILE_MAX_SIZE, 
            backupCount=LOG_FILE_BACKUP_COUNT
        )
    
    file_handler.setFormatter(formatter)
    logger.addHandler(file_handler)
    
    # 添加控制台处理器
    if LOG_TO_CONSOLE:
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)
    
    return logger

# 创建主日志记录器
main_logger = get_logger('secretary')

# 导出日志级别常量，方便其他模块使用
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL
