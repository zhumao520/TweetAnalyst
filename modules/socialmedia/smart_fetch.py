"""
智能抓取模块
提供统一的社交媒体数据抓取接口，自动选择最佳的抓取方式
"""

import os
from typing import List, Optional, Dict, Any
from modules.socialmedia.post import Post
from modules.socialmedia.async_utils import safe_asyncio_run
from modules.socialmedia.twitter_client_manager import get_twitter_manager
from utils.logger import get_logger

logger = get_logger('smart_fetch')


class SmartFetcher:
    """智能抓取器 - 自动选择最佳的抓取方式"""
    
    def __init__(self):
        self.twitter_manager = get_twitter_manager()
        self.fallback_strategies = ['tweety', 'twikit']
        self.last_successful_library = None
    
    def initialize(self, prefer_library: str = None) -> bool:
        """初始化智能抓取器"""
        if prefer_library:
            self.fallback_strategies = [prefer_library] + [lib for lib in self.fallback_strategies if lib != prefer_library]
        
        # 尝试初始化Twitter管理器
        for library in self.fallback_strategies:
            logger.info(f"尝试使用 {library} 库初始化...")
            if self.twitter_manager.auto_initialize(prefer_library=library):
                self.last_successful_library = library
                logger.info(f"成功使用 {library} 库初始化")
                return True
        
        logger.error("所有Twitter库初始化都失败了")
        return False
    
    def fetch_user_posts(self, user_id: str, limit: int = 10, retry_with_fallback: bool = True) -> List[Post]:
        """
        智能获取用户推文
        
        Args:
            user_id: 用户ID
            limit: 限制数量
            retry_with_fallback: 是否在失败时尝试备选方案
            
        Returns:
            List[Post]: 推文列表
        """
        if not self.twitter_manager.initialized:
            logger.warning("Twitter管理器未初始化，尝试自动初始化...")
            if not self.initialize():
                return []
        
        # 首先尝试当前库
        posts = self._try_fetch_user_posts(user_id, limit)
        
        # 如果失败且允许备选方案，尝试其他库
        if not posts and retry_with_fallback:
            posts = self._try_fallback_fetch_user_posts(user_id, limit)
        
        return posts
    
    def fetch_timeline_posts(self, limit: int = 20, retry_with_fallback: bool = True) -> List[Post]:
        """
        智能获取时间线推文
        
        Args:
            limit: 限制数量
            retry_with_fallback: 是否在失败时尝试备选方案
            
        Returns:
            List[Post]: 推文列表
        """
        if not self.twitter_manager.initialized:
            logger.warning("Twitter管理器未初始化，尝试自动初始化...")
            if not self.initialize():
                return []
        
        # 首先尝试当前库
        posts = self._try_fetch_timeline_posts(limit)
        
        # 如果失败且允许备选方案，尝试其他库
        if not posts and retry_with_fallback:
            posts = self._try_fallback_fetch_timeline_posts(limit)
        
        return posts
    
    def _try_fetch_user_posts(self, user_id: str, limit: int) -> List[Post]:
        """尝试获取用户推文"""
        try:
            posts = self.twitter_manager.fetch_user_tweets(user_id, limit)
            if posts:
                logger.info(f"成功使用 {self.twitter_manager.current_library} 获取 {len(posts)} 条用户推文")
                self.last_successful_library = self.twitter_manager.current_library
            return posts
        except Exception as e:
            logger.error(f"使用 {self.twitter_manager.current_library} 获取用户推文失败: {str(e)}")
            return []
    
    def _try_fetch_timeline_posts(self, limit: int) -> List[Post]:
        """尝试获取时间线推文"""
        try:
            posts = self.twitter_manager.fetch_timeline_tweets(limit)
            if posts:
                logger.info(f"成功使用 {self.twitter_manager.current_library} 获取 {len(posts)} 条时间线推文")
                self.last_successful_library = self.twitter_manager.current_library
            return posts
        except Exception as e:
            logger.error(f"使用 {self.twitter_manager.current_library} 获取时间线推文失败: {str(e)}")
            return []
    
    def _try_fallback_fetch_user_posts(self, user_id: str, limit: int) -> List[Post]:
        """尝试备选方案获取用户推文"""
        current_lib = self.twitter_manager.current_library
        
        for library in self.fallback_strategies:
            if library == current_lib:
                continue
            
            logger.info(f"尝试使用备选方案 {library} 获取用户推文...")
            
            if self.twitter_manager.switch_library(library):
                posts = self._try_fetch_user_posts(user_id, limit)
                if posts:
                    return posts
        
        logger.error("所有备选方案都失败了")
        return []
    
    def _try_fallback_fetch_timeline_posts(self, limit: int) -> List[Post]:
        """尝试备选方案获取时间线推文"""
        current_lib = self.twitter_manager.current_library
        
        for library in self.fallback_strategies:
            if library == current_lib:
                continue
            
            logger.info(f"尝试使用备选方案 {library} 获取时间线推文...")
            
            if self.twitter_manager.switch_library(library):
                posts = self._try_fetch_timeline_posts(limit)
                if posts:
                    return posts
        
        logger.error("所有备选方案都失败了")
        return []
    
    def get_status(self) -> Dict[str, Any]:
        """获取智能抓取器状态"""
        return {
            'initialized': self.twitter_manager.initialized,
            'current_library': self.twitter_manager.current_library,
            'last_successful_library': self.last_successful_library,
            'available_libraries': self.twitter_manager.get_available_libraries(),
            'fallback_strategies': self.fallback_strategies,
            'twitter_manager_status': self.twitter_manager.get_status()
        }


# 全局智能抓取器实例
smart_fetcher = SmartFetcher()


# 兼容性接口函数
async def fetch_twitter_posts_smart(user_id: Optional[str], limit: int = 10, fetch_type: str = "user") -> List[Post]:
    """
    智能抓取Twitter推文 - 与现有系统兼容的异步接口
    
    Args:
        user_id: 用户ID（时间线抓取时可为None）
        limit: 限制数量
        fetch_type: 抓取类型 ("user" 或 "timeline")
        
    Returns:
        List[Post]: 推文列表
    """
    try:
        # 确保智能抓取器已初始化
        if not smart_fetcher.twitter_manager.initialized:
            prefer_library = os.getenv('PREFERRED_TWITTER_LIBRARY', 'tweety')
            if not smart_fetcher.initialize(prefer_library):
                logger.error("智能抓取器初始化失败")
                return []
        
        if fetch_type == "timeline":
            return smart_fetcher.fetch_timeline_posts(limit)
        else:
            if not user_id:
                logger.error("用户推文抓取需要提供user_id")
                return []
            return smart_fetcher.fetch_user_posts(user_id, limit)
    
    except Exception as e:
        logger.error(f"智能抓取失败: {str(e)}")
        return []


def get_smart_fetcher() -> SmartFetcher:
    """获取智能抓取器实例"""
    return smart_fetcher


def initialize_smart_fetcher(prefer_library: str = 'tweety') -> bool:
    """初始化智能抓取器"""
    return smart_fetcher.initialize(prefer_library)


# 导出主要类和函数
__all__ = [
    'SmartFetcher',
    'smart_fetcher',
    'fetch_twitter_posts_smart',
    'get_smart_fetcher',
    'initialize_smart_fetcher'
]
