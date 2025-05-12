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
LOG_DIR = os.path.join(os.getcwd(), 'logs')  # 固定日志目录在应用程序目录下
LOG_FILE_MAX_SIZE = int(os.getenv('LOG_FILE_MAX_SIZE', 10 * 1024 * 1024))  # 默认10MB
LOG_FILE_BACKUP_COUNT = int(os.getenv('LOG_FILE_BACKUP_COUNT', 5))  # 默认保留5个备份
LOG_TO_CONSOLE = os.getenv('LOG_TO_CONSOLE', 'true').lower() == 'true'
LOG_ROTATION_TYPE = os.getenv('LOG_ROTATION_TYPE', 'size').lower()  # size或time

# 确保日志目录存在
if not os.path.exists(LOG_DIR):
    try:
        os.makedirs(LOG_DIR, exist_ok=True)
        # 设置权限为755，确保所有用户都可以读取日志
        os.chmod(LOG_DIR, 0o755)
        print(f"已创建日志目录: {LOG_DIR}，并设置权限为755")
    except Exception as e:
        print(f"创建日志目录时出错: {str(e)}")
else:
    # 如果目录已存在，也设置权限为755
    try:
        os.chmod(LOG_DIR, 0o755)
        print(f"已设置日志目录权限为755: {LOG_DIR}")
    except Exception as e:
        print(f"设置日志目录权限时出错: {str(e)}")

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

    # 如果已经配置过，检查日志文件是否存在，如果不存在则重新配置
    if logger.handlers:
        # 检查日志文件是否存在
        module_log_file = os.path.join(LOG_DIR, f'{name}.log')
        app_log_file = os.path.join(LOG_DIR, 'app.log')

        # 如果任一日志文件不存在，则移除所有处理器并重新配置
        if not os.path.exists(module_log_file) or not os.path.exists(app_log_file):
            print(f"日志文件不存在，重新配置日志处理器: {name}")
            # 移除所有处理器
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
        else:
            # 日志文件存在，直接返回
            return logger

    # 设置日志级别
    logger.setLevel(LOG_LEVELS.get(LOG_LEVEL, logging.INFO))

    # 创建格式化器
    formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    # 添加模块特定的文件处理器
    module_log_file = os.path.join(LOG_DIR, f'{name}.log')

    # 确保日志文件存在并有正确的权限
    try:
        # 如果文件不存在，创建一个空文件
        if not os.path.exists(module_log_file):
            with open(module_log_file, 'w') as f:
                pass
            # 设置权限为644，确保所有用户都可以读取
            os.chmod(module_log_file, 0o644)
            print(f"已创建日志文件: {module_log_file}，并设置权限为644")
        else:
            # 如果文件已存在，也设置权限为644
            os.chmod(module_log_file, 0o644)
    except Exception as e:
        print(f"设置日志文件权限时出错: {str(e)}")

    if LOG_ROTATION_TYPE == 'time':
        # 按时间轮转，每天一个文件
        module_file_handler = TimedRotatingFileHandler(
            module_log_file,
            when='midnight',
            interval=1,
            backupCount=LOG_FILE_BACKUP_COUNT
        )
    else:
        # 按大小轮转
        module_file_handler = RotatingFileHandler(
            module_log_file,
            maxBytes=LOG_FILE_MAX_SIZE,
            backupCount=LOG_FILE_BACKUP_COUNT
        )

    # 设置文件处理器在文件不存在时自动创建
    module_file_handler.delay = False

    module_file_handler.setFormatter(formatter)
    logger.addHandler(module_file_handler)

    # 添加主应用日志文件处理器，所有日志都会写入这个文件
    app_log_file = os.path.join(LOG_DIR, 'app.log')

    # 确保主应用日志文件存在并有正确的权限
    try:
        # 如果文件不存在，创建一个空文件
        if not os.path.exists(app_log_file):
            with open(app_log_file, 'w') as f:
                pass
            # 设置权限为644，确保所有用户都可以读取
            os.chmod(app_log_file, 0o644)
            print(f"已创建主应用日志文件: {app_log_file}，并设置权限为644")
        else:
            # 如果文件已存在，也设置权限为644
            os.chmod(app_log_file, 0o644)
    except Exception as e:
        print(f"设置主应用日志文件权限时出错: {str(e)}")

    if LOG_ROTATION_TYPE == 'time':
        # 按时间轮转，每天一个文件
        app_file_handler = TimedRotatingFileHandler(
            app_log_file,
            when='midnight',
            interval=1,
            backupCount=LOG_FILE_BACKUP_COUNT
        )
    else:
        # 按大小轮转
        app_file_handler = RotatingFileHandler(
            app_log_file,
            maxBytes=LOG_FILE_MAX_SIZE,
            backupCount=LOG_FILE_BACKUP_COUNT
        )

    # 设置文件处理器在文件不存在时自动创建
    app_file_handler.delay = False

    # 为主应用日志添加模块名前缀
    app_formatter = logging.Formatter(f'%(asctime)s - {name} - %(levelname)s - %(message)s', DATE_FORMAT)
    app_file_handler.setFormatter(app_formatter)
    logger.addHandler(app_file_handler)

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
