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
_config_refreshing = False  # 替代锁，使用简单的标志变量
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

def _refresh_config_cache(force=False):
    """
    刷新配置缓存

    Args:
        force (bool): 是否强制刷新缓存，忽略缓存有效期

    Returns:
        bool: 是否成功刷新缓存
    """
    global _config_cache, _config_cache_timestamp, _config_meta, _config_refreshing

    # 获取当前时间
    current_time = time.time()

    # 检查是否需要刷新缓存
    cache_valid = (current_time - _config_cache_timestamp < _config_cache_ttl) and _config_cache

    # 如果缓存有效且不强制刷新，直接返回
    if cache_valid and not force:
        logger.debug("使用配置缓存")
        return True

    # 检查刷新间隔
    last_attempt = _config_meta['last_refresh_attempt']
    failure_count = _config_meta['refresh_failure_count']
    min_interval = _config_meta['refresh_min_interval']

    # 计算当前应该使用的刷新间隔
    if failure_count > 0:
        # 使用指数退避策略
        backoff = min(_config_meta['refresh_max_interval'],
                      min_interval * (_config_meta['refresh_backoff_factor'] ** failure_count))
        if current_time - last_attempt < backoff and not force:
            logger.debug(f"刷新间隔过短 ({current_time - last_attempt:.1f}秒 < {backoff:.1f}秒)，跳过刷新")
            return False

    # 更新最后尝试刷新时间
    _config_meta['last_refresh_attempt'] = current_time

    # 如果已经在刷新中，直接返回
    if _config_refreshing:
        logger.debug("配置刷新已在进行中，跳过")
        return False

    # 使用标志变量代替线程锁
    _config_refreshing = True
    try:
        # 缓存过期或为空，重新加载
        logger.debug("刷新配置缓存")

        try:
            # 使用仓储模式获取所有配置
            config_repo = RepositoryFactory.get_system_config_repository()
            configs = config_repo.get_all()

            # 更新缓存
            _config_cache = {config.key: config.value for config in configs}
            _config_cache_timestamp = current_time
            logger.debug(f"配置缓存已更新，包含 {len(_config_cache)} 个配置项")

            # 重置失败计数
            _config_meta['refresh_failure_count'] = 0
            return True
        except Exception as db_error:
            # 如果使用仓储模式失败，尝试直接使用SQLite
            logger.debug(f"使用仓储模式获取配置失败: {str(db_error)}，尝试直接使用SQLite")

            # 获取数据库路径
            db_path = os.environ.get('DATABASE_PATH', '/data/tweetAnalyst.db')

            # 检查是否存在小写版本的数据库文件
            db_dir = os.path.dirname(db_path)
            db_name = os.path.basename(db_path)
            lowercase_db_name = db_name.lower()
            lowercase_db_path = os.path.join(db_dir, lowercase_db_name)

            if os.path.exists(lowercase_db_path) and not os.path.exists(db_path) and lowercase_db_path != db_path:
                logger.warning(f"检测到小写数据库文件: {lowercase_db_path}，但配置使用: {db_path}")
                logger.info(f"正在重命名数据库文件: {lowercase_db_path} -> {db_path}")
                try:
                    os.rename(lowercase_db_path, db_path)
                    logger.info(f"数据库文件重命名成功")
                except Exception as e:
                    logger.error(f"数据库文件重命名失败: {str(e)}")
                    # 如果重命名失败，使用小写版本的数据库文件
                    logger.warning(f"将使用小写版本的数据库文件: {lowercase_db_path}")
                    db_path = lowercase_db_path

            # 创建SQLite连接
            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 查询所有配置
            cursor.execute("SELECT key, value FROM system_config")
            configs = cursor.fetchall()

            # 更新缓存
            _config_cache = {key: value for key, value in configs}
            _config_cache_timestamp = current_time
            logger.debug(f"配置缓存已通过SQLite更新，包含 {len(_config_cache)} 个配置项")

            # 关闭连接
            cursor.close()
            conn.close()

            # 重置失败计数
            _config_meta['refresh_failure_count'] = 0
            return True
    except Exception as e:
        # 增加失败计数
        _config_meta['refresh_failure_count'] += 1

        logger.warning(f"刷新配置缓存时出错 (失败次数: {_config_meta['refresh_failure_count']}): {str(e)}")

        # 如果刷新失败，但缓存不为空，继续使用旧缓存
        if not _config_cache:
            # 如果缓存为空，创建一个空缓存
            _config_cache = {}

        return False
    finally:
        # 无论成功还是失败，都重置刷新标志
        _config_refreshing = False

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
        # 如果使用缓存，先检查缓存
        if use_cache:
            try:
                # 刷新缓存（如果需要）
                _refresh_config_cache()

                # 从缓存中获取配置
                if key in _config_cache:
                    return _config_cache[key]
            except Exception as cache_error:
                logger.warning(f"从缓存获取配置时出错: {str(cache_error)}")
                # 继续执行，尝试从数据库获取

        # 不使用缓存或缓存获取失败，直接从数据库查询
        try:
            # 使用仓储模式获取配置
            config_repo = RepositoryFactory.get_system_config_repository()
            value = config_repo.get_value(key)
            if value is not None:
                return value
        except Exception as db_error:
            logger.warning(f"从数据库获取配置时出错: {str(db_error)}")
            # 继续执行，尝试从环境变量获取

        # 缓存中没有或不使用缓存且数据库中没有，从环境变量获取
        env_value = os.getenv(key)
        if env_value is not None:
            return env_value
        return default
    except Exception as e:
        logger.warning(f"获取配置时出错: {str(e)}")
        # 出错时返回默认值
        return default

def update_env_variable(key: str, value: str):
    """
    更新环境变量，同时更新配置缓存
    
    Args:
        key: 配置键
        value: 配置值
    """
    try:
        # 更新环境变量
        os.environ[key] = value
        
        # 更新配置缓存
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
        # 使用仓储模式保存配置
        config_repo = RepositoryFactory.get_system_config_repository()
        config = config_repo.get_by_key(key)
        
        if config:
            # 更新现有配置
            config.value = value
            if description:
                config.description = description
            config.is_secret = is_secret
            config_repo.update(config)
        else:
            # 创建新配置
            config_repo.create({
                'key': key,
                'value': value,
                'description': description,
                'is_secret': is_secret
            })
        
        # 更新配置缓存
        _config_cache[key] = value
        
        # 如果需要，同步更新环境变量
        if update_env and key in ENV_SYNC_KEYS:
            update_env_variable(key, value)
        
        logger.info(f"配置已更新: {key}={value}")
        return True
    except Exception as e:
        logger.error(f"设置配置失败: {key}={value}, 错误: {str(e)}")
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
        # 刷新缓存（如果需要）
        _refresh_config_cache()

        # 从缓存中获取所有配置
        configs_dict = _config_cache

        # 使用仓储模式获取敏感配置标记
        config_repo = RepositoryFactory.get_system_config_repository()
        secret_configs = config_repo.query().filter_by(is_secret=True).all()
        secret_keys = set(config.key for config in secret_configs)

        # 处理配置值
        for key, value in configs_dict.items():
            if key in secret_keys:
                # 对于敏感信息，只返回是否已设置
                result[key] = '******' if value else ''
            else:
                result[key] = value
    else:
        # 不使用缓存，直接从数据库查询
        config_repo = RepositoryFactory.get_system_config_repository()
        configs = config_repo.get_all()

        for config in configs:
            if config.is_secret:
                # 对于敏感信息，只返回是否已设置
                result[config.key] = '******' if config.value else ''
            else:
                result[config.key] = config.value

    # 添加环境变量中的配置
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
    # 使用仓储模式批量设置配置
    config_repo = RepositoryFactory.get_system_config_repository()

    try:
        # 调用仓储的批量设置方法
        updated_count, skipped_count = config_repo.batch_set_configs(configs_dict)

        logger.info(f"批量更新了 {updated_count} 个配置项，跳过了 {skipped_count} 个配置项")

        # 更新环境变量
        if update_env and updated_count > 0:
            for key, config_data in configs_dict.items():
                value = config_data.get('value', '')
                config = config_repo.get_by_key(key)
                if config:
                    os.environ[key] = config.value
                    logger.debug(f"已更新环境变量 {key}")

                    # 更新缓存
                    global _config_cache
                    _config_cache[key] = value

        return updated_count, skipped_count

    except Exception as e:
        logger.error(f"批量更新配置时出错: {str(e)}")
        raise

def init_config(force=False, validate=True, app_context=None):
    """
    初始化配置：从数据库加载最新配置到环境变量和缓存

    这是一个统一的配置初始化函数，应在应用启动时调用。
    它确保配置只被初始化一次，除非指定force=True。

    Args:
        force (bool): 是否强制重新初始化配置，即使已经初始化过
        validate (bool): 是否验证关键配置
        app_context: Flask应用上下文，如果提供则在此上下文中执行

    Returns:
        dict: 包含初始化结果的字典，格式为：
            {
                'success': bool,  # 是否成功初始化
                'message': str,   # 初始化结果消息
                'missing_configs': list,  # 缺失的关键配置列表
                'configs': dict   # 当前配置字典（敏感信息已隐藏）
            }
    """
    global _config_initialized, _config_cache, _config_cache_timestamp

    # 初始化结果字典
    result = {
        'success': False,
        'message': '',
        'missing_configs': [],
        'configs': {}
    }

    # 使用标志变量代替线程锁
    # 如果已经初始化过且不强制重新初始化，则直接返回
    if _config_initialized and not force:
        logger.debug("配置已初始化，跳过初始化过程")
        result['success'] = True
        result['message'] = "配置已初始化，跳过初始化过程"
        result['configs'] = get_system_config()
        return result

    # 如果已经在初始化中，避免重复初始化
    global _config_refreshing
    if _config_refreshing:
        logger.debug("配置初始化已在进行中，跳过")
        result['success'] = False
        result['message'] = "配置初始化已在进行中，跳过"
        return result

    # 标记为正在初始化
    _config_refreshing = True
    try:
        logger.info("开始初始化配置")

        # 清空配置缓存
        _config_cache = {}
        _config_cache_timestamp = 0

        # 如果提供了应用上下文，则在此上下文中执行
        if app_context:
            with app_context:
                # 加载配置到环境变量
                success = load_configs_to_env()
        else:
            # 加载配置到环境变量
            success = load_configs_to_env()

        if success:
            # 刷新配置缓存
            try:
                _refresh_config_cache(force=True)
                logger.info("配置缓存已刷新")
            except Exception as e:
                logger.warning(f"刷新配置缓存时出错: {str(e)}")

            # 获取当前配置
            current_configs = get_system_config()
            result['configs'] = current_configs

            # 验证关键配置
            if validate:
                # 定义关键配置列表
                critical_configs = [
                    'LLM_API_KEY',  # AI模型API密钥
                    'LLM_API_MODEL',  # AI模型名称
                    'LLM_API_BASE'  # AI模型API基础URL
                ]

                # 检查关键配置是否存在
                for key in critical_configs:
                    value = os.getenv(key, '')
                    if not value:
                        result['missing_configs'].append(key)
                        logger.warning(f"缺少关键配置: {key}")

                # 如果有缺失的关键配置，记录警告但仍然继续
                if result['missing_configs']:
                    logger.warning(f"缺少 {len(result['missing_configs'])} 个关键配置: {', '.join(result['missing_configs'])}")
                    result['message'] = f"配置初始化成功，但缺少 {len(result['missing_configs'])} 个关键配置"
                else:
                    logger.info("所有关键配置都已设置")
                    result['message'] = "配置初始化成功，所有关键配置都已设置"
            else:
                result['message'] = "配置初始化成功，跳过配置验证"

            # 打印关键配置（隐藏敏感信息）
            logger.info("当前环境变量配置:")
            for key in ['LLM_API_MODEL', 'LLM_API_BASE', 'SCHEDULER_INTERVAL_MINUTES']:
                logger.info(f"{key}: {os.getenv(key, '未设置')}")

            # 对于敏感信息，只显示是否已设置
            for key in ['LLM_API_KEY', 'TWITTER_PASSWORD', 'TWITTER_SESSION']:
                value = os.getenv(key, '')
                logger.info(f"{key}: {'已设置' if value else '未设置'}")

            # 标记为已初始化
            _config_initialized = True
            result['success'] = True
            logger.info("配置初始化成功")
        else:
            result['message'] = "配置初始化失败，无法加载配置到环境变量"
            logger.error("配置初始化失败，无法加载配置到环境变量")

        return result
    finally:
        # 无论成功还是失败，都重置刷新标志
        _config_refreshing = False

def load_configs_to_env():
    """
    将数据库中的配置加载到环境变量中

    Returns:
        bool: 是否成功
    """
    try:
        # 使用仓储模式获取所有配置
        try:
            config_repo = RepositoryFactory.get_system_config_repository()
            configs = config_repo.get_all()

            # 加载到环境变量
            for config in configs:
                os.environ[config.key] = config.value
                logger.debug(f"已加载配置 {config.key} 到环境变量")

            logger.info(f"已加载 {len(configs)} 个配置到环境变量")
        except Exception as e:
            logger.warning(f"使用仓储模式获取配置失败: {str(e)}，尝试使用直接SQL查询")

            # 如果仓储模式失败，使用直接SQL查询
            # 获取数据库路径
            db_path = os.environ.get('DATABASE_PATH', '/data/tweetAnalyst.db')

            # 检查是否存在小写版本的数据库文件
            db_dir = os.path.dirname(db_path)
            db_name = os.path.basename(db_path)
            lowercase_db_name = db_name.lower()
            lowercase_db_path = os.path.join(db_dir, lowercase_db_name)

            # 检查文件名大小写问题（特别是在Windows上）
            if lowercase_db_path != db_path and os.path.exists(db_path):
                # 检查实际文件名的大小写
                try:
                    actual_files = os.listdir(db_dir)
                    actual_db_name = None
                    for file in actual_files:
                        if file.lower() == lowercase_db_name:
                            actual_db_name = file
                            break

                    if actual_db_name and actual_db_name != db_name:
                        logger.warning(f"检测到数据库文件名大小写不匹配: 实际={actual_db_name}, 期望={db_name}")
                        logger.info(f"正在修正数据库文件名大小写")

                        # 在Windows上，需要通过临时文件名来重命名
                        temp_db_path = os.path.join(db_dir, f"temp_{db_name}")
                        actual_db_path = os.path.join(db_dir, actual_db_name)

                        try:
                            # 先重命名为临时文件名
                            os.rename(actual_db_path, temp_db_path)
                            # 再重命名为正确的文件名
                            os.rename(temp_db_path, db_path)
                            logger.info(f"数据库文件名大小写修正成功: {actual_db_name} -> {db_name}")
                        except Exception as e:
                            logger.error(f"数据库文件名大小写修正失败: {str(e)}")
                            # 如果修正失败，恢复原文件名
                            try:
                                if os.path.exists(temp_db_path):
                                    os.rename(temp_db_path, actual_db_path)
                            except:
                                pass
                except Exception as e:
                    logger.error(f"检查数据库文件名大小写时出错: {str(e)}")

            elif os.path.exists(lowercase_db_path) and not os.path.exists(db_path) and lowercase_db_path != db_path:
                logger.warning(f"检测到小写数据库文件: {lowercase_db_path}，但配置使用: {db_path}")
                logger.info(f"正在重命名数据库文件: {lowercase_db_path} -> {db_path}")
                try:
                    os.rename(lowercase_db_path, db_path)
                    logger.info(f"数据库文件重命名成功")
                except Exception as e:
                    logger.error(f"数据库文件重命名失败: {str(e)}")
                    # 如果重命名失败，使用小写版本的数据库文件
                    logger.warning(f"将使用小写版本的数据库文件: {lowercase_db_path}")
                    db_path = lowercase_db_path

            # 确保数据库路径存在
            if not os.path.exists(db_path):
                logger.warning(f"数据库文件不存在: {db_path}")
                # 尝试在当前目录下查找
                alt_db_path = os.path.join(os.getcwd(), 'instance/tweetAnalyst.db')

                # 检查替代路径的小写版本
                alt_db_dir = os.path.dirname(alt_db_path)
                alt_db_name = os.path.basename(alt_db_path)
                alt_lowercase_db_name = alt_db_name.lower()
                alt_lowercase_db_path = os.path.join(alt_db_dir, alt_lowercase_db_name)

                # 检查替代路径的文件名大小写问题
                if os.path.exists(alt_db_path):
                    # 检查实际文件名的大小写
                    try:
                        actual_files = os.listdir(alt_db_dir)
                        actual_db_name = None
                        for file in actual_files:
                            if file.lower() == alt_lowercase_db_name:
                                actual_db_name = file
                                break

                        if actual_db_name and actual_db_name != alt_db_name:
                            logger.warning(f"检测到替代数据库文件名大小写不匹配: 实际={actual_db_name}, 期望={alt_db_name}")
                            logger.info(f"正在修正替代数据库文件名大小写")

                            # 在Windows上，需要通过临时文件名来重命名
                            temp_alt_db_path = os.path.join(alt_db_dir, f"temp_{alt_db_name}")
                            actual_alt_db_path = os.path.join(alt_db_dir, actual_db_name)

                            try:
                                # 先重命名为临时文件名
                                os.rename(actual_alt_db_path, temp_alt_db_path)
                                # 再重命名为正确的文件名
                                os.rename(temp_alt_db_path, alt_db_path)
                                logger.info(f"替代数据库文件名大小写修正成功: {actual_db_name} -> {alt_db_name}")
                            except Exception as e:
                                logger.error(f"替代数据库文件名大小写修正失败: {str(e)}")
                                # 如果修正失败，恢复原文件名
                                try:
                                    if os.path.exists(temp_alt_db_path):
                                        os.rename(temp_alt_db_path, actual_alt_db_path)
                                except:
                                    pass
                    except Exception as e:
                        logger.error(f"检查替代数据库文件名大小写时出错: {str(e)}")

                elif os.path.exists(alt_lowercase_db_path) and not os.path.exists(alt_db_path):
                    logger.warning(f"检测到小写替代数据库文件: {alt_lowercase_db_path}")
                    try:
                        os.rename(alt_lowercase_db_path, alt_db_path)
                        logger.info(f"替代数据库文件重命名成功")
                    except Exception as e:
                        logger.error(f"替代数据库文件重命名失败: {str(e)}")
                        alt_db_path = alt_lowercase_db_path

                if os.path.exists(alt_db_path):
                    db_path = alt_db_path
                    logger.info(f"找到替代数据库文件: {db_path}")
                else:
                    logger.error("无法找到数据库文件")
                    return False

            # 创建SQLite连接
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            # 查询所有配置
            cursor.execute("SELECT key, value FROM system_config")
            configs = cursor.fetchall()

            # 加载到环境变量
            for key, value in configs:
                os.environ[key] = value
                logger.debug(f"已加载配置 {key} 到环境变量")

            logger.info(f"已加载 {len(configs)} 个配置到环境变量")

            # 关闭连接
            cursor.close()
            conn.close()

        # 检查代理设置
        proxy = os.getenv('HTTP_PROXY', '')
        if proxy:
            logger.info(f"检测到HTTP代理配置: {proxy}")

            # 设置代理环境变量
            os.environ['HTTP_PROXY'] = proxy
            os.environ['HTTPS_PROXY'] = proxy

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
    # 尝试从配置文件中读取模板
    templates_path = 'config/prompt-templates.yml'

    try:
        if os.path.exists(templates_path):
            import yaml
            with open(templates_path, 'r', encoding='utf-8') as f:
                templates_data = yaml.safe_load(f)
                templates = templates_data.get('templates', {})

                # 根据账号类型选择合适的模板
                if account_type == 'finance' and 'finance' in templates:
                    return templates['finance']
                elif (account_type == 'ai' or account_type == 'tech') and 'tech' in templates:
                    return templates['tech']
                elif account_type in ['general', 'twitter', 'news'] and 'general' in templates:
                    return templates['general']
    except Exception as e:
        logger.warning(f"从配置文件读取模板失败: {str(e)}，使用内置模板")

    # 如果从配置文件读取失败，使用内置模板
    # 这些是最基本的默认模板，只在配置文件不存在或读取失败时使用
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
    else:
        return """你现在是一名专业分析师，请对以下内容进行分析，并给按我指定的格式返回分析结果。

这是你需要分析的内容：{content}

这是输出格式的说明：
{
    "is_relevant": "是否与相关主题相关，只需要返回1或0这两个值之一即可",
    "analytical_briefing": "分析简报"
}

其中analytical_briefing的值是一个字符串，它是针对内容所做的分析简报，仅在is_relevant为1时会返回这个值。"""
