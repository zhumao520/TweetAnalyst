"""
配置服务
处理系统配置的读写操作
"""

import os
import logging
from models import db, SystemConfig

# 创建日志记录器
logger = logging.getLogger('services.config')

def get_config(key, default=None):
    """
    获取系统配置
    
    Args:
        key: 配置键
        default: 默认值
        
    Returns:
        str: 配置值
    """
    config = SystemConfig.query.filter_by(key=key).first()
    if config:
        return config.value
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
        SystemConfig: 配置对象
    """
    config = SystemConfig.query.filter_by(key=key).first()

    if config:
        config.value = value
        if description:
            config.description = description
        if is_secret is not None:
            config.is_secret = is_secret
    else:
        config = SystemConfig(
            key=key,
            value=value,
            is_secret=is_secret,
            description=description
        )
        db.session.add(config)

    db.session.commit()

    # 更新环境变量
    if update_env:
        os.environ[key] = value

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
        except Exception as e:
            logger.error(f"更新环境变量文件时出错: {str(e)}")

    return config

def get_system_config():
    """
    获取所有系统配置
    
    Returns:
        dict: 配置字典
    """
    configs = SystemConfig.query.all()
    result = {}

    for config in configs:
        if config.is_secret:
            # 对于敏感信息，只返回是否已设置
            result[config.key] = '******' if config.value else ''
        else:
            result[config.key] = config.value

    # 添加环境变量中的配置
    for key in ['LLM_API_KEY', 'LLM_API_MODEL', 'LLM_API_BASE',
                'TWITTER_USERNAME', 'TWITTER_PASSWORD', 'TWITTER_SESSION',
                'SCHEDULER_INTERVAL_MINUTES', 'HTTP_PROXY', 'APPRISE_URLS']:
        if key not in result:
            value = os.getenv(key, '')
            if key in ['LLM_API_KEY', 'TWITTER_PASSWORD', 'TWITTER_SESSION'] and value:
                result[key] = '******'
            else:
                result[key] = value

    return result

def load_configs_to_env():
    """
    将数据库中的配置加载到环境变量中
    
    Returns:
        bool: 是否成功
    """
    try:
        configs = SystemConfig.query.all()
        for config in configs:
            os.environ[config.key] = config.value
            logger.info(f"已加载配置 {config.key} 到环境变量")

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
    else:
        return """你现在是一名专业分析师，请对以下内容进行分析，并给按我指定的格式返回分析结果。

这是你需要分析的内容：{content}

这是输出格式的说明：
{
    "is_relevant": "是否与相关主题相关，只需要返回1或0这两个值之一即可",
    "analytical_briefing": "分析简报"
}

其中analytical_briefing的值是一个字符串，它是针对内容所做的分析简报，仅在is_relevant为1时会返回这个值。"""
