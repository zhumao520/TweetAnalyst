"""
配置服务
处理系统配置的读写操作

提供统一的配置管理接口，包括配置的读取、写入、缓存和初始化。
"""

import os
import json
import logging
import time
import threading
import sqlite3
from sqlalchemy import text
from models import db
from functools import lru_cache
from services.repository.factory import RepositoryFactory

# 创建日志记录器
logger = logging.getLogger('services.config')

# 配置缓存
_config_cache = {}
_config_cache_timestamp = 0
_config_cache_ttl = 60  # 缓存有效期（秒）
_config_initialized = False
_config_refreshing = False
_config_lock = threading.Lock() # Thread lock for cache operations

_config_meta = {
    'last_refresh_attempt': 0,  # 上次尝试刷新缓存的时间
    'refresh_failure_count': 0,  # 刷新失败计数
    'refresh_min_interval': 5,   # 最小刷新间隔（秒）
    'refresh_backoff_factor': 2, # 失败后的退避因子
    'refresh_max_interval': 300  # 最大刷新间隔（秒）
}

# 需要同步到环境变量的配置键列表
ENV_SYNC_KEYS = {
    'SCHEDULER_INTERVAL_MINUTES',
    'AUTO_FETCH_ENABLED',
    'TIMELINE_INTERVAL_MINUTES',
    'TIMELINE_FETCH_ENABLED',
    'PUSH_QUEUE_INTERVAL_SECONDS',
    'PUSH_QUEUE_ENABLED',
    'DB_AUTO_CLEAN_ENABLED',
    'DB_AUTO_CLEAN_TIME',
    'DB_RETENTION_DAYS',
    'DB_CLEAN_IRRELEVANT_ONLY',
    'ENABLE_AUTO_REPLY',
    'AUTO_REPLY_PROMPT',
    'LLM_API_KEY',
    'LLM_API_MODEL',
    'LLM_API_BASE',
    'HTTP_PROXY',
    'HTTPS_PROXY',
    'APPRISE_URLS'
}

def _get_database_path():
    """
    Determines the database path.
    Prioritizes DATABASE_PATH env var, then defaults to 'data/tweetAnalyst.db'.
    Logs an error if the file is not found.
    """
    db_path_env = os.environ.get('DATABASE_PATH')
    if db_path_env:
        db_path = db_path_env
        logger.debug(f"Using DATABASE_PATH from environment: {db_path}")
    else:
        # Default path relative to the project root (assuming app runs from root)
        # Get current working directory, assuming it's the project root
        project_root = os.getcwd() 
        db_path = os.path.join(project_root, 'data', 'tweetAnalyst.db')
        logger.debug(f"DATABASE_PATH not set, using default: {db_path}")

    # Ensure the directory exists
    db_dir = os.path.dirname(db_path)
    if not os.path.exists(db_dir):
        try:
            os.makedirs(db_dir, exist_ok=True)
            logger.info(f"Created database directory: {db_dir}")
        except Exception as e:
            logger.error(f"Failed to create database directory {db_dir}: {str(e)}")
            return None # Cannot proceed if directory creation fails

    if not os.path.exists(db_path):
        logger.warning(f"Database file not found at resolved path: {db_path}. It might be created by SQLAlchemy.")
        # Allow to proceed, as SQLAlchemy might create it. 
        # The connection attempt will fail later if it's truly an issue.
    return db_path

def _refresh_config_cache(force=False):
    """
    刷新配置缓存

    Args:
        force (bool): 是否强制刷新缓存，忽略缓存有效期

    Returns:
        bool: 是否成功刷新缓存
    """
    global _config_cache, _config_cache_timestamp, _config_meta, _config_refreshing

    current_time = time.time()

    with _config_lock:
        cache_valid = (current_time - _config_cache_timestamp < _config_cache_ttl) and _config_cache
        if cache_valid and not force:
            logger.debug("使用配置缓存")
            return True

        last_attempt = _config_meta['last_refresh_attempt']
        failure_count = _config_meta['refresh_failure_count']
        min_interval = _config_meta['refresh_min_interval']

        if failure_count > 0:
            backoff = min(_config_meta['refresh_max_interval'],
                          min_interval * (_config_meta['refresh_backoff_factor'] ** failure_count))
            if current_time - last_attempt < backoff and not force:
                logger.debug(f"刷新间隔过短 ({current_time - last_attempt:.1f}秒 < {backoff:.1f}秒)，跳过刷新")
                return False
        
        _config_meta['last_refresh_attempt'] = current_time

        if _config_refreshing:
            logger.debug("配置刷新已在进行中，跳过")
            return False # Another thread is already refreshing

        _config_refreshing = True

    # Actual refresh logic (outside the initial lock to allow other threads to check _config_refreshing)
    try:
        logger.debug("尝试刷新配置缓存")
        new_cache_data = {}
        timestamp_to_set = current_time # Default to current time

        try:
            config_repo = RepositoryFactory.get_system_config_repository()
            configs = config_repo.get_all()
            new_cache_data = {config.key: config.value for config in configs}
            logger.debug(f"配置缓存已通过 Repository 更新，包含 {len(new_cache_data)} 个配置项")
            
            with _config_lock:
                _config_meta['refresh_failure_count'] = 0
            
            success = True
        except Exception as db_error:
            logger.warning(f"使用仓储模式获取配置失败: {str(db_error)}，尝试直接使用SQLite")
            
            db_path = _get_database_path()
            if not db_path or not os.path.exists(db_path): # Re-check existence before connecting
                logger.error(f"SQLite数据库文件不存在于: {db_path}，无法刷新缓存")
                with _config_lock:
                    _config_meta['refresh_failure_count'] += 1
                success = False
            else:
                try:
                    conn = sqlite3.connect(db_path)
                    cursor = conn.cursor()
                    cursor.execute("SELECT key, value FROM system_config")
                    configs_sqlite = cursor.fetchall()
                    new_cache_data = {key: value for key, value in configs_sqlite}
                    logger.debug(f"配置缓存已通过SQLite更新，包含 {len(new_cache_data)} 个配置项")
                    cursor.close()
                    conn.close()
                    with _config_lock:
                        _config_meta['refresh_failure_count'] = 0
                    success = True
                except Exception as sqlite_error:
                    logger.error(f"通过SQLite刷新配置缓存时出错: {sqlite_error}")
                    with _config_lock:
                        _config_meta['refresh_failure_count'] += 1
                    success = False
        
        # Update cache only if refresh was successful or cache is currently empty
        with _config_lock:
            if success or not _config_cache: # if successful, or if cache is empty, update
                _config_cache = new_cache_data
                _config_cache_timestamp = timestamp_to_set
            elif not success and _config_cache: # if failed but old cache exists, log it
                 logger.warning("刷新配置失败，继续使用旧缓存（如果存在）")

            _config_refreshing = False # Reset refreshing flag under lock
        return success

    except Exception as e: # Catch any unexpected error during the broader try block
        with _config_lock:
            _config_meta['refresh_failure_count'] += 1
            logger.error(f"刷新配置缓存时发生意外错误 (失败次数: {_config_meta['refresh_failure_count']}): {str(e)}")
            if not _config_cache: # Ensure cache is at least an empty dict
                _config_cache = {}
            _config_refreshing = False
        return False


def get_config(key, default=None, use_cache=True):
    """
    获取系统配置

    Args:
        key: 配置键
        default: 默认值
        use_cache: 是否使用缓存

    Returns:
        str: 配置值
    """
    try:
        if use_cache:
            _refresh_config_cache() # Will use lock internally
            with _config_lock: # Protect reading from cache
                if key in _config_cache:
                    return _config_cache[key]
        
        # Fallback if not use_cache or key not in cache
        try:
            config_repo = RepositoryFactory.get_system_config_repository()
            value = config_repo.get_value(key)
            if value is not None:
                if use_cache: # Update cache if fetched from DB
                    with _config_lock:
                        _config_cache[key] = value
                return value
        except Exception as db_error:
            logger.warning(f"从数据库获取配置 '{key}' 时出错: {str(db_error)}")

        env_value = os.getenv(key)
        if env_value is not None:
            if use_cache: # Update cache if fetched from env
                 with _config_lock:
                    _config_cache[key] = env_value
            return env_value
        return default
    except Exception as e:
        logger.warning(f"获取配置 '{key}' 时出错: {str(e)}")
        return default

def update_env_variable(key: str, value: str):
    """
    更新环境变量，同时更新配置缓存
    
    Args:
        key: 配置键
        value: 配置值
    """
    try:
        os.environ[key] = value
        with _config_lock:
            _config_cache[key] = value
        logger.debug(f"已更新环境变量和配置缓存: {key}={value}")
    except Exception as e:
        logger.error(f"更新环境变量失败: {key}={value}, 错误: {str(e)}")

def set_config(key: str, value: str, description: str = None, is_secret: bool = False, update_env: bool = True):
    """
    设置配置值
    
    Args:
        key: 配置键
        value: 配置值
        description: 配置描述
        is_secret: 是否为敏感信息
        update_env: 是否同步更新环境变量
    """
    try:
        config_repo = RepositoryFactory.get_system_config_repository()
        config = config_repo.get_by_key(key)
        
        if config:
            config.value = value
            if description:
                config.description = description
            config.is_secret = is_secret
            config_repo.update(config)
        else:
            config_repo.create({
                'key': key,
                'value': value,
                'description': description,
                'is_secret': is_secret
            })
        
        with _config_lock:
            _config_cache[key] = value
        
        if update_env and key in ENV_SYNC_KEYS:
            update_env_variable(key, value)
        
        logger.info(f"配置已更新: {key}={'******' if is_secret and value else value}")
        return True
    except Exception as e:
        logger.error(f"设置配置失败: {key}={'******' if is_secret and value else value}, 错误: {str(e)}")
        return False

def get_system_config(use_cache=True):
    """
    获取所有系统配置

    Args:
        use_cache: 是否使用缓存

    Returns:
        dict: 配置字典
    """
    result = {}
    
    if use_cache:
        _refresh_config_cache() # Will use lock internally
        with _config_lock: # Protect reading from cache
            # Make a copy to avoid issues if the cache is modified elsewhere
            # though with the lock this should be safer.
            configs_dict_cache_copy = dict(_config_cache) 
        
        config_repo = RepositoryFactory.get_system_config_repository()
        secret_configs = config_repo.query().filter_by(is_secret=True).all()
        secret_keys = set(config.key for config in secret_configs)

        for key, value in configs_dict_cache_copy.items():
            if key in secret_keys:
                result[key] = '******' if value else ''
            else:
                result[key] = value
    else:
        config_repo = RepositoryFactory.get_system_config_repository()
        configs = config_repo.get_all()
        for config in configs:
            if config.is_secret:
                result[config.key] = '******' if config.value else ''
            else:
                result[config.key] = config.value

    env_keys = [
        'LLM_API_KEY', 'LLM_API_MODEL', 'LLM_API_BASE',
        'TWITTER_USERNAME', 'TWITTER_EMAIL', 'TWITTER_PASSWORD', 'TWITTER_SESSION',
        'SCHEDULER_INTERVAL_MINUTES', 'HTTP_PROXY', 'APPRISE_URLS'
    ]
    for key in env_keys:
        if key not in result:
            value = os.getenv(key, '')
            if key in ['LLM_API_KEY', 'TWITTER_PASSWORD', 'TWITTER_SESSION'] and value:
                result[key] = '******'
            else:
                result[key] = value
    return result

def batch_set_configs(configs_dict, update_env=True):
    """
    批量设置系统配置

    Args:
        configs_dict: 配置字典，格式为 {key: {value: value, is_secret: bool, description: str}}
        update_env: 是否更新环境变量

    Returns:
        tuple: (updated_count, skipped_count) - 更新的配置数量和跳过的配置数量
    """
    config_repo = RepositoryFactory.get_system_config_repository()
    try:
        updated_count, skipped_count = config_repo.batch_set_configs(configs_dict)
        logger.info(f"批量更新了 {updated_count} 个配置项，跳过了 {skipped_count} 个配置项")

        if updated_count > 0:
            with _config_lock: # Acquire lock before updating cache and env
                for key, config_data in configs_dict.items():
                    # Check if this key was actually updated (not skipped)
                    # This might require more info from batch_set_configs or re-fetching
                    # For simplicity, we update all provided keys in cache/env if any update happened.
                    # A more precise way would be to get the list of successfully updated keys.
                    value = config_data.get('value', '')
                    _config_cache[key] = value
                    if update_env and key in ENV_SYNC_KEYS:
                        os.environ[key] = value
                        logger.debug(f"已更新环境变量 {key}")
        return updated_count, skipped_count
    except Exception as e:
        logger.error(f"批量更新配置时出错: {str(e)}")
        raise

def init_config(force=False, validate=True, app_context=None):
    """
    初始化配置：从数据库加载最新配置到环境变量和缓存
    """
    global _config_initialized
    result = {'success': False, 'message': '', 'missing_configs': [], 'configs': {}}

    with _config_lock:
        if _config_initialized and not force:
            logger.debug("配置已初始化，跳过初始化过程")
            result['success'] = True
            result['message'] = "配置已初始化，跳过初始化过程"
            result['configs'] = get_system_config(use_cache=False) # get fresh data
            return result
        
        # If another thread is initializing, wait or return.
        # For simplicity, we'll let it proceed if force=True or not initialized.
        # A more robust solution might involve a separate init_lock or event.

    logger.info("开始初始化配置")
    
    # Load configs to environment
    if app_context:
        with app_context:
            load_success = load_configs_to_env()
    else:
        load_success = load_configs_to_env()

    if load_success:
        # Refresh cache after loading to env
        _refresh_config_cache(force=True) # This will use the lock internally
        logger.info("配置缓存已刷新")
        
        current_configs = get_system_config(use_cache=False) # Get fresh after refresh
        result['configs'] = current_configs

        if validate:
            critical_configs = ['LLM_API_KEY', 'LLM_API_MODEL', 'LLM_API_BASE']
            for key in critical_configs:
                value = os.getenv(key, '') # Check env var directly as it's most up-to-date
                if not value:
                    result['missing_configs'].append(key)
            
            if result['missing_configs']:
                msg = f"配置初始化成功，但缺少 {len(result['missing_configs'])} 个关键配置: {', '.join(result['missing_configs'])}"
                logger.warning(msg)
                result['message'] = msg
            else:
                msg = "配置初始化成功，所有关键配置都已设置"
                logger.info(msg)
                result['message'] = msg
        else:
            result['message'] = "配置初始化成功，跳过配置验证"

        logger.info("当前环境变量配置 (部分):")
        for key in ['LLM_API_MODEL', 'LLM_API_BASE', 'SCHEDULER_INTERVAL_MINUTES']:
            logger.info(f"{key}: {os.getenv(key, '未设置')}")
        for key in ['LLM_API_KEY', 'TWITTER_PASSWORD', 'TWITTER_SESSION']:
            value = os.getenv(key, '')
            logger.info(f"{key}: {'已设置' if value else '未设置'}")
        
        with _config_lock:
            _config_initialized = True
        result['success'] = True
        logger.info("配置初始化成功")
    else:
        result['message'] = "配置初始化失败，无法加载配置到环境变量"
        logger.error("配置初始化失败，无法加载配置到环境变量")
    
    return result

def load_configs_to_env():
    """
    将数据库中的配置加载到环境变量中

    Returns:
        bool: 是否成功
    """
    logger.info("尝试从数据库加载配置到环境变量...")
    try:
        config_repo = RepositoryFactory.get_system_config_repository()
        configs = config_repo.get_all()
        
        if not configs: # Try SQLite if repository returns nothing (e.g. DB not fully up)
            logger.info("仓储未返回配置，尝试直接SQLite查询以加载到环境变量")
            db_path = _get_database_path()
            if not db_path or not os.path.exists(db_path):
                logger.error(f"数据库文件不存在于: {db_path}，无法加载配置到环境变量。")
                return False
            try:
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()
                cursor.execute("SELECT key, value FROM system_config")
                configs_sqlite = cursor.fetchall()
                cursor.close()
                conn.close()
                
                # Convert to list of objects similar to what repository returns, for consistent processing
                configs = [{'key': row[0], 'value': row[1]} for row in configs_sqlite]
                logger.info(f"已从SQLite查询到 {len(configs)} 个配置项")
            except Exception as sqlite_e:
                logger.error(f"直接SQLite查询配置失败: {sqlite_e}")
                return False # Critical if we can't even read from SQLite here

        # Load to environment variables
        count = 0
        for config_item in configs:
            key = config_item.key if hasattr(config_item, 'key') else config_item['key']
            value = config_item.value if hasattr(config_item, 'value') else config_item['value']
            os.environ[key] = value
            # logger.debug(f"已加载配置 {key} 到环境变量") # Too verbose for init
            count +=1
        
        logger.info(f"已成功加载 {count} 个配置到环境变量")

        proxy = os.getenv('HTTP_PROXY', '')
        if proxy:
            logger.info(f"检测到HTTP代理配置: {proxy}")
            os.environ['HTTPS_PROXY'] = proxy # Ensure HTTPS_PROXY is also set if HTTP_PROXY is

        return True
    except Exception as e:
        logger.error(f"加载配置到环境变量时出错: {str(e)}")
        return False


def get_default_prompt_template(account_type):
    """
    获取默认提示词模板

    Args:
        account_type: 账号类型

    Returns:
        str: 提示词模板
    """
    templates_path = 'config/prompt-templates.yml'
    try:
        if os.path.exists(templates_path):
            import yaml
            with open(templates_path, 'r', encoding='utf-8') as f:
                templates_data = yaml.safe_load(f)
                templates = templates_data.get('templates', {})
                if account_type == 'finance' and 'finance' in templates: return templates['finance']
                if (account_type == 'ai' or account_type == 'tech') and 'tech' in templates: return templates['tech']
                if account_type in ['general', 'twitter', 'news'] and 'general' in templates: return templates['general']
    except Exception as e:
        logger.warning(f"从配置文件读取模板失败: {str(e)}，使用内置模板")

    if account_type == 'finance':
        return """你是一个专业的财经内容分析助手，请分析以下财经相关的社交媒体内容，并决定是否值得向关注财经的用户推送通知。

这是你需要分析的内容：{content}

返回格式：
{
  "is_relevant": 1或0,  // 是否相关，只返回1或0
  "analytical_briefing": "分析简报，简明扼要地总结内容要点"
}"""
    elif account_type == 'ai' or account_type == 'tech':
        return """你是一个专业的AI和技术内容分析助手，请分析以下AI/技术相关的社交媒体内容，并决定是否值得向关注AI和技术的用户推送通知。

这是你需要分析的内容：{content}

返回格式：
{
  "is_relevant": 1或0,  // 是否相关，只返回1或0
  "analytical_briefing": "分析简报，简明扼要地总结内容要点"
}"""
    else: # general
        return """你现在是一名专业分析师，请对以下内容进行分析，并给按我指定的格式返回分析结果。

这是你需要分析的内容：{content}

这是输出格式的说明：
{
    "is_relevant": "是否与相关主题相关，只需要返回1或0这两个值之一即可",
    "analytical_briefing": "分析简报"
}

其中analytical_briefing的值是一个字符串，它是针对内容所做的分析简报，仅在is_relevant为1时会返回这个值。"""
