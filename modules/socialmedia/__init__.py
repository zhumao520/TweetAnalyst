"""
社交媒体模块初始化
提供统一的社交媒体数据抓取接口
"""

import os
from typing import List, Optional
from utils.logger import get_logger

logger = get_logger('socialmedia')

# 版本信息
__version__ = "2.0.0"
__author__ = "TweetAnalyst Team"

# 导入主要组件
try:
    from .post import Post
    from .async_utils import safe_asyncio_run, safe_call_async_method
    from .twitter_utils import (
        extract_media_info,
        extract_author_info, 
        create_post_from_tweet,
        set_timeline_metadata,
        batch_create_posts
    )
    from .twitter_client_manager import (
        TwitterClientManager,
        twitter_manager,
        get_twitter_manager,
        initialize_twitter_manager
    )
    from .smart_fetch import (
        SmartFetcher,
        smart_fetcher,
        fetch_twitter_posts_smart,
        get_smart_fetcher,
        initialize_smart_fetcher
    )
    
    # 尝试导入具体的Twitter实现
    try:
        from . import twitter
        TWITTER_AVAILABLE = True
        logger.info("Twitter (tweety) 模块加载成功")
    except ImportError as e:
        TWITTER_AVAILABLE = False
        logger.warning(f"Twitter (tweety) 模块加载失败: {str(e)}")
    
    try:
        from . import twitter_twikit
        TWITTER_TWIKIT_AVAILABLE = True
        logger.info("Twitter (twikit) 模块加载成功")
    except ImportError as e:
        TWITTER_TWIKIT_AVAILABLE = False
        logger.warning(f"Twitter (twikit) 模块加载失败: {str(e)}")
    
    logger.info(f"社交媒体模块初始化完成 v{__version__}")
    
except ImportError as e:
    logger.error(f"社交媒体模块初始化失败: {str(e)}")
    raise


def get_available_platforms() -> List[str]:
    """获取可用的社交媒体平台"""
    platforms = []
    
    if TWITTER_AVAILABLE or TWITTER_TWIKIT_AVAILABLE:
        platforms.append('twitter')
    
    return platforms


def get_module_status() -> dict:
    """获取模块状态"""
    return {
        'version': __version__,
        'twitter_tweety_available': TWITTER_AVAILABLE,
        'twitter_twikit_available': TWITTER_TWIKIT_AVAILABLE,
        'available_platforms': get_available_platforms(),
        'smart_fetcher_status': smart_fetcher.get_status() if 'smart_fetcher' in globals() else None,
        'twitter_manager_status': twitter_manager.get_status() if 'twitter_manager' in globals() else None
    }


def initialize_all(prefer_twitter_library: str = None) -> bool:
    """
    初始化所有社交媒体组件
    
    Args:
        prefer_twitter_library: 首选的Twitter库 ('tweety' 或 'twikit')
        
    Returns:
        bool: 是否成功初始化
    """
    logger.info("开始初始化社交媒体组件...")
    
    # 从环境变量获取首选库
    if not prefer_twitter_library:
        prefer_twitter_library = os.getenv('PREFERRED_TWITTER_LIBRARY', 'tweety')
    
    success = False
    
    # 初始化Twitter管理器
    if TWITTER_AVAILABLE or TWITTER_TWIKIT_AVAILABLE:
        try:
            if initialize_twitter_manager(prefer_twitter_library):
                logger.info("Twitter管理器初始化成功")
                success = True
            else:
                logger.error("Twitter管理器初始化失败")
        except Exception as e:
            logger.error(f"Twitter管理器初始化异常: {str(e)}")
    
    # 初始化智能抓取器
    if success:
        try:
            if initialize_smart_fetcher(prefer_twitter_library):
                logger.info("智能抓取器初始化成功")
            else:
                logger.warning("智能抓取器初始化失败，但Twitter管理器已可用")
        except Exception as e:
            logger.error(f"智能抓取器初始化异常: {str(e)}")
    
    if success:
        logger.info("社交媒体组件初始化完成")
    else:
        logger.error("社交媒体组件初始化失败")
    
    return success


# 兼容性接口 - 保持与现有代码的兼容性
def fetch_posts(platform: str, user_id: str, limit: int = 10) -> List[Post]:
    """
    获取社交媒体帖子 - 兼容性接口
    
    Args:
        platform: 平台名称 ('twitter')
        user_id: 用户ID
        limit: 限制数量
        
    Returns:
        List[Post]: 帖子列表
    """
    if platform.lower() == 'twitter':
        return smart_fetcher.fetch_user_posts(user_id, limit)
    else:
        logger.error(f"不支持的平台: {platform}")
        return []


def fetch_timeline(platform: str, limit: int = 50) -> List[Post]:
    """
    获取时间线帖子 - 兼容性接口
    
    Args:
        platform: 平台名称 ('twitter')
        limit: 限制数量
        
    Returns:
        List[Post]: 帖子列表
    """
    if platform.lower() == 'twitter':
        return smart_fetcher.fetch_timeline_posts(limit)
    else:
        logger.error(f"不支持的平台: {platform}")
        return []


# 导出主要接口
__all__ = [
    # 版本信息
    '__version__',
    '__author__',
    
    # 核心类
    'Post',
    'TwitterClientManager',
    'SmartFetcher',
    
    # 实例
    'twitter_manager',
    'smart_fetcher',
    
    # 工具函数
    'safe_asyncio_run',
    'safe_call_async_method',
    'extract_media_info',
    'extract_author_info',
    'create_post_from_tweet',
    'set_timeline_metadata',
    'batch_create_posts',
    
    # 管理函数
    'get_twitter_manager',
    'get_smart_fetcher',
    'initialize_twitter_manager',
    'initialize_smart_fetcher',
    'initialize_all',
    
    # 状态函数
    'get_available_platforms',
    'get_module_status',
    
    # 兼容性接口
    'fetch_posts',
    'fetch_timeline',
    'fetch_twitter_posts_smart',
    
    # 可用性标志
    'TWITTER_AVAILABLE',
    'TWITTER_TWIKIT_AVAILABLE'
]
