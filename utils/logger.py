"""
日志模块 - 提供统一的日志记录功能

此模块提供了统一的日志管理接口，包括：
1. 全局日志配置
2. 日志记录器创建
3. 日志文件管理
4. 日志清理

所有模块应使用此模块中的get_logger()函数创建日志记录器，
而不是直接使用logging.getLogger()或logging.basicConfig()。

此模块支持监控以下组件的日志：
- AI相关组件（llm.log）
- 推送相关组件（apprise_adapter.log）
- 社交媒体组件（twitter.log）
- Web应用组件（web_app.log）
- 主程序组件（main.log）
- 系统组件（app.log）
"""
import os
import logging
import sys
import glob
import time
import re
import threading
from logging.handlers import RotatingFileHandler, TimedRotatingFileHandler
from dotenv import load_dotenv

# 加载环境变量
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
LOG_FILE_MAX_SIZE = int(os.getenv('LOG_FILE_MAX_SIZE', 5 * 1024 * 1024))  # 默认5MB
LOG_FILE_BACKUP_COUNT = int(os.getenv('LOG_FILE_BACKUP_COUNT', 3))  # 默认保留3个备份
LOG_TO_CONSOLE = os.getenv('LOG_TO_CONSOLE', 'true').lower() == 'true'
LOG_ROTATION_TYPE = os.getenv('LOG_ROTATION_TYPE', 'size').lower()  # size或time

# 日志文件列表 - 用于清理旧日志
CORE_LOG_FILES = ['app.log', 'main.log', 'web_app.log', 'twitter.log', 'llm.log', 'apprise_adapter.log']

# 日志格式
LOG_FORMAT = '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
DATE_FORMAT = '%Y-%m-%d %H:%M:%S'

# 组件日志格式 - 为不同组件提供特定的日志格式
COMPONENT_FORMATS = {
    'llm': '%(asctime)s - [AI] - %(levelname)s - %(message)s',
    'apprise_adapter': '%(asctime)s - [推送] - %(levelname)s - %(message)s',
    'twitter': '%(asctime)s - [Twitter] - %(levelname)s - %(message)s',
    'web_app': '%(asctime)s - [Web] - %(levelname)s - %(message)s',
    'main': '%(asctime)s - [主程序] - %(levelname)s - %(message)s',
    'app': '%(asctime)s - [系统] - %(levelname)s - %(message)s'
}

# 全局锁，用于线程安全的日志初始化
_logger_lock = threading.Lock()

# 全局标志，表示是否已初始化根日志记录器
_root_logger_initialized = False

# 模块级别的日志配置
_module_log_levels = {}

# 确保日志目录存在并设置正确的权限
def ensure_log_dir():
    """
    确保日志目录存在并设置正确的权限

    Returns:
        bool: 是否成功创建或设置日志目录
    """
    if not os.path.exists(LOG_DIR):
        try:
            os.makedirs(LOG_DIR, exist_ok=True)
            # 设置权限为755，确保所有用户都可以读取日志
            os.chmod(LOG_DIR, 0o755)
            return True
        except Exception as e:
            print(f"创建日志目录时出错: {str(e)}")
            return False
    else:
        # 如果目录已存在，也设置权限为755
        try:
            os.chmod(LOG_DIR, 0o755)
            return True
        except Exception as e:
            print(f"设置日志目录权限时出错: {str(e)}")
            return False

# 初始化日志目录
ensure_log_dir()

def configure_root_logger():
    """
    配置根日志记录器

    这个函数替代了直接使用logging.basicConfig()的方式，
    确保所有日志都使用统一的格式和配置。

    Returns:
        bool: 是否成功配置根日志记录器
    """
    global _root_logger_initialized

    # 使用线程锁确保线程安全
    with _logger_lock:
        # 如果已经初始化过，直接返回
        if _root_logger_initialized:
            return True

        try:
            # 获取根日志记录器
            root_logger = logging.getLogger()

            # 设置日志级别
            root_logger.setLevel(LOG_LEVELS.get(LOG_LEVEL, logging.INFO))

            # 创建格式化器
            formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

            # 添加主应用日志文件处理器
            app_log_file = os.path.join(LOG_DIR, 'app.log')

            # 确保日志文件存在并有正确的权限
            ensure_log_file(app_log_file)

            if LOG_ROTATION_TYPE == 'time':
                # 按时间轮转，每天一个文件
                file_handler = TimedRotatingFileHandler(
                    app_log_file,
                    when='midnight',
                    interval=1,
                    backupCount=LOG_FILE_BACKUP_COUNT
                )
            else:
                # 按大小轮转
                file_handler = RotatingFileHandler(
                    app_log_file,
                    maxBytes=LOG_FILE_MAX_SIZE,
                    backupCount=LOG_FILE_BACKUP_COUNT
                )

            # 设置文件处理器在文件不存在时自动创建
            file_handler.delay = False

            file_handler.setFormatter(formatter)
            root_logger.addHandler(file_handler)

            # 添加控制台处理器
            if LOG_TO_CONSOLE:
                console_handler = logging.StreamHandler(sys.stdout)
                console_handler.setFormatter(formatter)
                root_logger.addHandler(console_handler)

            # 标记为已初始化
            _root_logger_initialized = True

            return True
        except Exception as e:
            print(f"配置根日志记录器时出错: {str(e)}")
            return False

def ensure_log_file(file_path):
    """
    确保日志文件存在并有正确的权限

    Args:
        file_path (str): 日志文件路径

    Returns:
        bool: 是否成功创建或设置日志文件
    """
    try:
        # 确保日志目录存在
        ensure_log_dir()

        # 如果文件不存在，创建一个空文件
        if not os.path.exists(file_path):
            with open(file_path, 'w') as f:
                pass
            # 设置权限为644，确保所有用户都可以读取
            os.chmod(file_path, 0o644)
        else:
            # 如果文件已存在，也设置权限为644
            os.chmod(file_path, 0o644)
        return True
    except Exception as e:
        print(f"设置日志文件权限时出错: {str(e)}")
        return False

def set_module_log_level(module_name, level):
    """
    设置指定模块的日志级别

    Args:
        module_name (str): 模块名称
        level (str or int): 日志级别，可以是字符串('debug', 'info'等)或整数(logging.DEBUG等)

    Returns:
        bool: 是否成功设置日志级别
    """
    try:
        # 如果level是字符串，转换为整数
        if isinstance(level, str):
            level = LOG_LEVELS.get(level.lower(), logging.INFO)

        # 存储模块日志级别
        _module_log_levels[module_name] = level

        # 如果已经创建了该模块的日志记录器，更新其级别
        logger = logging.getLogger(module_name)
        logger.setLevel(level)

        return True
    except Exception as e:
        print(f"设置模块日志级别时出错: {str(e)}")
        return False

def clean_old_logs():
    """
    清理旧的日志文件，保留必要的核心日志

    Returns:
        dict: 清理结果统计，包括总文件数、删除文件数等
    """
    result = {
        "total_files": 0,
        "deleted_files": 0,
        "error_count": 0
    }

    try:
        # 确保日志目录存在
        if not os.path.exists(LOG_DIR):
            os.makedirs(LOG_DIR)
            return result

        # 获取所有日志文件
        all_log_files = glob.glob(os.path.join(LOG_DIR, '*.log*'))
        result["total_files"] = len(all_log_files)

        if not all_log_files:
            return result

        # 当前时间
        current_time = time.time()
        # 30天的秒数
        thirty_days_in_seconds = 30 * 24 * 60 * 60
        # 7天的秒数
        seven_days_in_seconds = 7 * 24 * 60 * 60

        # 遍历所有日志文件
        for log_file in all_log_files:
            file_name = os.path.basename(log_file)

            # 检查是否是核心日志文件
            is_core_log = False
            for core_log in CORE_LOG_FILES:
                if file_name == core_log or re.match(f"{core_log}\\.\\d+$", file_name):
                    is_core_log = True
                    break

            # 如果不是核心日志文件，或者是旧的轮转文件
            if not is_core_log or re.search(r'\.\d+$', file_name):
                # 获取文件修改时间
                file_mod_time = os.path.getmtime(log_file)
                file_age = current_time - file_mod_time

                # 如果文件超过30天未修改，或者不是核心日志文件且超过7天未修改
                if (file_age > thirty_days_in_seconds) or \
                   (not is_core_log and file_age > seven_days_in_seconds):
                    try:
                        os.remove(log_file)
                        result["deleted_files"] += 1
                    except Exception:
                        result["error_count"] += 1

        return result
    except Exception:
        return result

def get_logger(name):
    """
    获取指定名称的日志记录器

    这是创建日志记录器的统一接口，所有模块都应使用此函数创建日志记录器，
    而不是直接使用logging.getLogger()。

    Args:
        name (str): 日志记录器名称，通常使用模块名

    Returns:
        logging.Logger: 日志记录器实例
    """
    # 确保根日志记录器已配置
    if not _root_logger_initialized:
        configure_root_logger()

    # 获取日志记录器
    logger = logging.getLogger(name)

    # 如果已经配置过，检查日志文件是否存在，如果不存在则重新配置
    if logger.handlers:
        # 检查模块日志文件是否存在
        module_log_file = os.path.join(LOG_DIR, f'{name}.log')

        # 如果日志文件不存在，则移除所有处理器并重新配置
        if not os.path.exists(module_log_file):
            # 移除所有处理器
            for handler in logger.handlers[:]:
                logger.removeHandler(handler)
        else:
            # 日志文件存在，检查是否需要更新日志级别
            if name in _module_log_levels:
                logger.setLevel(_module_log_levels[name])
            return logger

    # 设置日志级别
    if name in _module_log_levels:
        logger.setLevel(_module_log_levels[name])
    else:
        logger.setLevel(LOG_LEVELS.get(LOG_LEVEL, logging.INFO))

    # 创建格式化器 - 使用组件特定的格式（如果有）
    if name in COMPONENT_FORMATS:
        formatter = logging.Formatter(COMPONENT_FORMATS[name], DATE_FORMAT)
    else:
        formatter = logging.Formatter(LOG_FORMAT, DATE_FORMAT)

    # 添加模块特定的文件处理器
    module_log_file = os.path.join(LOG_DIR, f'{name}.log')

    # 确保日志文件存在并有正确的权限
    ensure_log_file(module_log_file)

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

    return logger

def setup_component_logging(component, level='info'):
    """
    设置特定组件的日志级别

    此函数用于设置特定组件的日志级别，方便监控不同组件的日志。
    支持的组件包括：ai, push, twitter, web, main, system

    Args:
        component (str): 组件名称，可以是'ai', 'push', 'twitter', 'web', 'main', 'system'
        level (str or int): 日志级别，可以是字符串('debug', 'info'等)或整数(logging.DEBUG等)

    Returns:
        bool: 是否成功设置组件日志级别
    """
    # 组件名称到日志记录器名称的映射
    component_map = {
        'ai': 'llm',
        'push': 'apprise_adapter',
        'twitter': 'twitter',
        'web': 'web_app',
        'main': 'main',
        'system': 'app'
    }

    # 检查组件名称是否有效
    if component not in component_map:
        print(f"无效的组件名称: {component}，有效的组件名称包括: {', '.join(component_map.keys())}")
        return False

    # 获取日志记录器名称
    logger_name = component_map[component]

    # 设置日志级别
    return set_module_log_level(logger_name, level)

def setup_logging(level=None, log_dir=None, to_console=None, rotation_type=None):
    """
    设置全局日志配置

    这个函数替代了logging.basicConfig()，提供了更多的配置选项。
    它会配置根日志记录器，并影响所有未显式配置的日志记录器。

    Args:
        level (str or int, optional): 日志级别，可以是字符串('debug', 'info'等)或整数(logging.DEBUG等)
        log_dir (str, optional): 日志目录路径
        to_console (bool, optional): 是否输出到控制台
        rotation_type (str, optional): 日志轮转类型，'size'或'time'

    Returns:
        bool: 是否成功设置日志配置
    """
    global LOG_LEVEL, LOG_DIR, LOG_TO_CONSOLE, LOG_ROTATION_TYPE, _root_logger_initialized

    # 更新全局配置
    if level is not None:
        if isinstance(level, str):
            LOG_LEVEL = level.lower()
        else:
            # 如果是整数，找到对应的字符串表示
            for k, v in LOG_LEVELS.items():
                if v == level:
                    LOG_LEVEL = k
                    break

    if log_dir is not None:
        LOG_DIR = log_dir

    if to_console is not None:
        LOG_TO_CONSOLE = to_console

    if rotation_type is not None:
        LOG_ROTATION_TYPE = rotation_type.lower()

    # 重置根日志记录器初始化标志
    _root_logger_initialized = False

    # 配置根日志记录器
    return configure_root_logger()

def basic_config(**kwargs):
    """
    基本日志配置，兼容logging.basicConfig()的接口

    这个函数是对logging.basicConfig()的替代，确保所有日志都使用统一的格式和配置。

    Args:
        **kwargs: 支持与logging.basicConfig()相同的参数

    Returns:
        bool: 是否成功配置日志
    """
    # 从kwargs中提取参数
    level = kwargs.get('level')
    format = kwargs.get('format')
    datefmt = kwargs.get('datefmt')

    # 更新全局配置
    global LOG_FORMAT, DATE_FORMAT

    if format is not None:
        LOG_FORMAT = format

    if datefmt is not None:
        DATE_FORMAT = datefmt

    # 设置日志配置
    return setup_logging(level=level)

# 创建主日志记录器
main_logger = get_logger('secretary')

# 导出日志级别常量，方便其他模块使用
DEBUG = logging.DEBUG
INFO = logging.INFO
WARNING = logging.WARNING
ERROR = logging.ERROR
CRITICAL = logging.CRITICAL

# 导出函数，替代logging模块中的同名函数
basicConfig = basic_config

# 导出组件日志级别设置函数，方便监控特定组件
setup_ai_logging = lambda level='debug': setup_component_logging('ai', level)
setup_push_logging = lambda level='debug': setup_component_logging('push', level)
setup_twitter_logging = lambda level='debug': setup_component_logging('twitter', level)
setup_web_logging = lambda level='debug': setup_component_logging('web', level)
setup_main_logging = lambda level='debug': setup_component_logging('main', level)
setup_system_logging = lambda level='debug': setup_component_logging('system', level)

# 设置第三方库的日志级别
def setup_third_party_logging():
    """
    设置第三方库的日志级别，减少不必要的日志输出
    """
    # 设置hpack.hpack模块的日志级别为WARNING，减少HTTP/2头部解码的调试日志
    logging.getLogger('hpack.hpack').setLevel(logging.WARNING)

    # 设置其他可能产生大量日志的第三方库
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)

    main_logger.info("已设置第三方库的日志级别")

# 在模块加载时自动设置第三方库的日志级别
setup_third_party_logging()

# 初始化根日志记录器
configure_root_logger()
