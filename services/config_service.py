"""
配置服务
处理系统配置的读写操作
"""

import os
import logging
import time
from models import db, SystemConfig
from functools import lru_cache

# 创建日志记录器
logger = logging.getLogger('services.config')

# 配置缓存
_config_cache = {}
_config_cache_timestamp = 0
_config_cache_ttl = 60  # 缓存有效期（秒）

def _refresh_config_cache():
    """
    刷新配置缓存
    """
    global _config_cache, _config_cache_timestamp

    # 检查缓存是否过期
    current_time = time.time()
    if current_time - _config_cache_timestamp < _config_cache_ttl and _config_cache:
        logger.debug("使用配置缓存")
        return

    # 缓存过期或为空，重新加载
    logger.debug("刷新配置缓存")
    configs = SystemConfig.query.all()

    # 更新缓存
    _config_cache = {config.key: config.value for config in configs}
    _config_cache_timestamp = current_time
    logger.debug(f"配置缓存已更新，包含 {len(_config_cache)} 个配置项")

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
    # 如果使用缓存，先检查缓存
    if use_cache:
        # 刷新缓存（如果需要）
        _refresh_config_cache()

        # 从缓存中获取配置
        if key in _config_cache:
            return _config_cache[key]
    else:
        # 不使用缓存，直接从数据库查询
        config = SystemConfig.query.filter_by(key=key).first()
        if config:
            return config.value

    # 缓存中没有或不使用缓存且数据库中没有，从环境变量获取
    return os.getenv(key, default)

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
        tuple: (SystemConfig, bool) - 配置对象和是否进行了更新
    """
    config = SystemConfig.query.filter_by(key=key).first()
    updated = False

    # 记录操作开始
    if is_secret:
        # 对于敏感信息，不记录实际值
        logger.debug(f"尝试设置配置 {key}，值为 ******")
    else:
        logger.debug(f"尝试设置配置 {key}，值为 {value}")

    if config:
        # 检查值是否相同，如果相同则不更新
        if config.value == value:
            # 如果描述或敏感标记需要更新，则更新这些字段
            if (description and config.description != description) or \
               (is_secret is not None and config.is_secret != is_secret):

                old_description = config.description
                old_is_secret = config.is_secret

                if description:
                    config.description = description
                    logger.debug(f"更新配置 {key} 的描述：'{old_description}' -> '{description}'")

                if is_secret is not None:
                    config.is_secret = is_secret
                    logger.debug(f"更新配置 {key} 的敏感标记：{old_is_secret} -> {is_secret}")

                db.session.commit()
                logger.info(f"配置 {key} 的元数据已更新，值保持不变")
                updated = True
            else:
                # 完全没有变化，不需要更新
                logger.debug(f"配置 {key} 已存在且所有属性相同，跳过更新")
                return config, False
        else:
            # 值不同，需要更新
            old_value = config.value if not config.is_secret else "******"
            new_value = value if not is_secret else "******"

            config.value = value
            if description:
                old_description = config.description
                config.description = description
                logger.debug(f"更新配置 {key} 的描述：'{old_description}' -> '{description}'")

            if is_secret is not None:
                old_is_secret = config.is_secret
                config.is_secret = is_secret
                logger.debug(f"更新配置 {key} 的敏感标记：{old_is_secret} -> {is_secret}")

            updated = True
            logger.info(f"配置 {key} 的值已更新：{old_value} -> {new_value}")
    else:
        # 配置不存在，创建新配置
        config = SystemConfig(
            key=key,
            value=value,
            is_secret=is_secret,
            description=description
        )
        db.session.add(config)
        updated = True

        # 记录创建信息
        if is_secret:
            logger.info(f"创建新配置 {key}，值为 ******，描述：{description}")
        else:
            logger.info(f"创建新配置 {key}，值为 {value}，描述：{description}")

    # 只有在有更新时才提交事务
    if updated:
        try:
            db.session.commit()
            logger.debug(f"配置 {key} 的更改已提交到数据库")

            # 更新缓存
            global _config_cache
            _config_cache[key] = value
            logger.debug(f"配置 {key} 已更新到缓存")
        except Exception as e:
            db.session.rollback()
            logger.error(f"提交配置 {key} 的更改时出错: {str(e)}")
            raise

    # 更新环境变量
    if update_env and updated:
        os.environ[key] = value
        logger.debug(f"环境变量 {key} 已更新")

        # 更新.env文件
        try:
            env_file = os.path.join(os.path.dirname(os.environ.get('DATABASE_PATH', '.')), '.env')
            env_lines = []

            # 读取现有.env文件
            if os.path.exists(env_file):
                with open(env_file, 'r') as f:
                    env_lines = f.readlines()

            # 更新或添加环境变量
            key_found = False
            for i, line in enumerate(env_lines):
                if line.startswith(f"{key}="):
                    env_lines[i] = f"{key}={value}\n"
                    key_found = True
                    break

            if not key_found:
                env_lines.append(f"{key}={value}\n")

            # 写回.env文件
            with open(env_file, 'w') as f:
                f.writelines(env_lines)
            logger.debug(f".env文件中的 {key} 已更新")
        except Exception as e:
            logger.error(f"更新环境变量文件时出错: {str(e)}")

    return config, updated

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

        # 获取敏感配置标记
        secret_keys = set()
        for config in SystemConfig.query.filter_by(is_secret=True).all():
            secret_keys.add(config.key)

        # 处理配置值
        for key, value in configs_dict.items():
            if key in secret_keys:
                # 对于敏感信息，只返回是否已设置
                result[key] = '******' if value else ''
            else:
                result[key] = value
    else:
        # 不使用缓存，直接从数据库查询
        configs = SystemConfig.query.all()

        for config in configs:
            if config.is_secret:
                # 对于敏感信息，只返回是否已设置
                result[config.key] = '******' if config.value else ''
            else:
                result[config.key] = config.value

    # 添加环境变量中的配置
    env_keys = [
        'LLM_API_KEY', 'LLM_API_MODEL', 'LLM_API_BASE',
        'TWITTER_USERNAME', 'TWITTER_PASSWORD', 'TWITTER_SESSION',
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
    updated_count = 0
    skipped_count = 0
    updated_keys = []

    try:
        # 开始事务
        for key, config_data in configs_dict.items():
            value = config_data.get('value', '')
            is_secret = config_data.get('is_secret', False)
            description = config_data.get('description', None)

            # 查找现有配置
            config = SystemConfig.query.filter_by(key=key).first()

            if config:
                # 检查值是否相同，如果相同则不更新
                if config.value == value:
                    # 如果描述或敏感标记需要更新，则更新这些字段
                    if (description and config.description != description) or \
                       (is_secret is not None and config.is_secret != is_secret):

                        if description:
                            config.description = description
                        if is_secret is not None:
                            config.is_secret = is_secret

                        updated_keys.append(key)
                        updated_count += 1
                    else:
                        # 完全没有变化，不需要更新
                        skipped_count += 1
                else:
                    # 值不同，需要更新
                    config.value = value
                    if description:
                        config.description = description
                    if is_secret is not None:
                        config.is_secret = is_secret

                    updated_keys.append(key)
                    updated_count += 1
            else:
                # 配置不存在，创建新配置
                config = SystemConfig(
                    key=key,
                    value=value,
                    is_secret=is_secret,
                    description=description
                )
                db.session.add(config)
                updated_keys.append(key)
                updated_count += 1

        # 提交事务
        if updated_count > 0:
            db.session.commit()
            logger.info(f"批量更新了 {updated_count} 个配置项，跳过了 {skipped_count} 个配置项")

            # 更新环境变量
            if update_env:
                for key in updated_keys:
                    config = SystemConfig.query.filter_by(key=key).first()
                    if config:
                        os.environ[key] = config.value
                        logger.debug(f"已更新环境变量 {key}")

        return updated_count, skipped_count

    except Exception as e:
        db.session.rollback()
        logger.error(f"批量更新配置时出错: {str(e)}")
        raise

def load_configs_to_env():
    """
    将数据库中的配置加载到环境变量中

    Returns:
        bool: 是否成功
    """
    try:
        # 使用更安全的方式加载配置，避免应用上下文问题
        # 直接从数据库加载配置，不依赖Flask应用上下文
        from models import db, SystemConfig

        # 获取数据库中的所有配置
        try:
            # 使用SQLAlchemy直接执行SQL查询
            from sqlalchemy import text
            from flask import current_app

            # 尝试使用当前应用上下文
            try:
                if current_app:
                    # 已经在应用上下文中
                    configs = SystemConfig.query.all()
                    for config in configs:
                        os.environ[config.key] = config.value
                        logger.debug(f"已加载配置 {config.key} 到环境变量")
                    logger.info(f"已加载 {len(configs)} 个配置到环境变量")
                else:
                    # 不在应用上下文中，使用直接SQL查询
                    raise RuntimeError("不在应用上下文中")
            except Exception:
                # 如果不在应用上下文中，使用直接SQL查询
                # 获取数据库路径
                db_path = os.environ.get('DATABASE_PATH', '/data/tweetAnalyst.db')

                # 创建SQLite连接
                import sqlite3
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
        except Exception as e:
            logger.error(f"加载配置到环境变量时出错: {str(e)}")
            return False

        # 检查代理设置
        proxy = os.getenv('HTTP_PROXY', '')
        if proxy and proxy.startswith('socks'):
            logger.info(f"检测到SOCKS代理: {proxy}")
            try:
                import socksio
                logger.info("SOCKS代理支持已安装")
            except ImportError:
                logger.warning("未安装SOCKS代理支持，尝试安装...")
                try:
                    import pip
                    pip.main(['install', 'httpx[socks]', '--quiet'])
                    logger.info("成功安装SOCKS代理支持")
                except Exception as e:
                    logger.error(f"安装SOCKS代理支持失败: {str(e)}")

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
    # 避免循环导入 - 使用更安全的方式
    # 不再尝试动态导入模块，而是直接使用内置模板

    # 根据账号类型选择合适的模板
    if account_type == 'twitter':
        return """你现在是一名专业分析师，请对以下社交媒体内容进行分析，并给按我指定的格式返回分析结果。

这是你需要分析的内容：{content}

这是输出格式的说明：
{
    "is_relevant": "是否与相关主题相关，只需要返回1或0这两个值之一即可",
    "analytical_briefing": "分析简报"
}

其中analytical_briefing的值是一个字符串，它是针对内容所做的分析简报，仅在is_relevant为1时会返回这个值。

analytical_briefing的内容是markdown格式的，它需要符合下面的规范：

原始正文，仅当需要分析的内容不是为中文时，这部分内容才会保留，否则这部分的内容为原始的正文

翻译后的内容，仅当需要分析的内容为英文时，才会有这部分的内容。

## Summarize

这部分需要用非常简明扼要的文字对内容进行总结。"""
    elif account_type == 'finance':
        return """你是一个专业的财经内容分析助手，请分析以下财经相关的社交媒体内容，并决定是否值得向关注财经的用户推送通知。

这是你需要分析的内容：{content}

请考虑以下因素：
1. 内容的财经价值和重要性
2. 市场影响和时效性
3. 分析的深度和独特视角
4. 是否包含有用的投资见解或市场预测

特别关注以下领域的内容：
- 美股市场动态
- 美债市场变化
- 科技股和半导体股分析
- 中国和香港股票市场
- 人民币兑美元汇率
- 中美经济关系
- 重要的财经政策变化
- 有影响力的财经人物观点

返回格式：
{
  "is_relevant": 1或0,  // 是否相关，只返回1或0
  "analytical_briefing": "分析简报，简明扼要地总结内容要点"
}"""
    elif account_type == 'ai' or account_type == 'tech':
        return """你是一个专业的AI和技术内容分析助手，请分析以下AI/技术相关的社交媒体内容，并决定是否值得向关注AI和技术的用户推送通知。

这是你需要分析的内容：{content}

请考虑以下因素：
1. 内容的技术价值和创新性
2. 行业影响和时效性
3. 技术见解的深度和独特视角
4. 是否包含重要的AI发展动态或突破

特别关注以下领域的内容：
- 大型语言模型(LLM)和生成式AI
- AI研究突破和新技术
- 重要的AI产品发布或更新
- AI伦理和监管动态
- 行业领袖的重要观点
- AI应用的创新案例
- 技术趋势和前沿发展

返回格式：
{
  "is_relevant": 1或0,  // 是否相关，只返回1或0
  "analytical_briefing": "分析简报，简明扼要地总结内容要点"
}"""
    elif account_type == 'news':
        return """你是一个专业的新闻内容分析助手，请分析以下新闻相关的社交媒体内容，并决定是否值得向关注新闻的用户推送通知。

这是你需要分析的内容：{content}

请考虑以下因素：
1. 新闻的重要性和影响力
2. 信息的时效性和准确性
3. 内容的客观性和公正性
4. 是否包含重要的社会、政治或经济事件

特别关注以下领域的内容：
- 重大国际事件
- 国内政策变化
- 社会热点事件
- 重要人物动态
- 突发事件和灾害
- 具有广泛社会影响的新闻

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
