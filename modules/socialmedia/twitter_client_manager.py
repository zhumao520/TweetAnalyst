"""
Twitter客户端管理器
统一管理tweety和twikit客户端，提供一致的接口
"""

import os
from typing import Optional, List, Dict, Any
from modules.socialmedia.post import Post
from modules.socialmedia.async_utils import safe_asyncio_run, safe_call_async_method
from utils.logger import get_logger

logger = get_logger('twitter_client_manager')


class TwitterClientManager:
    """Twitter客户端管理器 - 统一管理不同的Twitter库"""

    def __init__(self):
        self.tweety_client = None
        self.tweety_async_client = None
        self.twikit_client = None
        self.current_library = None  # 'tweety' 或 'twikit'
        self.initialized = False

    def get_available_libraries(self) -> List[str]:
        """获取可用的Twitter库"""
        available = []

        # 检查tweety
        try:
            import tweety
            available.append('tweety')
        except ImportError:
            pass

        # 检查twikit
        try:
            import twikit
            available.append('twikit')
        except ImportError:
            pass

        return available

    def initialize_tweety(self, use_async: bool = False) -> bool:
        """初始化tweety客户端"""
        try:
            # 先清除全局变量缓存和会话文件
            from modules.socialmedia import twitter
            twitter.app = None
            twitter.async_app = None

            # 清除会话文件缓存
            import os
            session_files = ['session.tw_session', 'session', '.tw_session']
            for session_file in session_files:
                if os.path.exists(session_file):
                    try:
                        os.remove(session_file)
                        logger.info(f"已删除旧的会话文件: {session_file}")
                    except Exception as e:
                        logger.warning(f"删除会话文件 {session_file} 失败: {str(e)}")

            from modules.socialmedia.twitter import init_twitter_client

            if use_async:
                self.tweety_async_client = init_twitter_client(use_async=True)
                success = self.tweety_async_client is not None
            else:
                self.tweety_client = init_twitter_client(use_async=False)
                success = self.tweety_client is not None

            if success:
                self.current_library = 'tweety'
                logger.info(f"Tweety客户端初始化成功 ({'异步' if use_async else '同步'})")

            return success

        except Exception as e:
            logger.error(f"初始化tweety客户端失败: {str(e)}")
            return False

    def initialize_twikit(self) -> bool:
        """初始化twikit客户端"""
        try:
            from modules.socialmedia import twitter_twikit

            # 使用异步初始化
            success = safe_asyncio_run(twitter_twikit.initialize())

            if success:
                self.twikit_client = twitter_twikit.twikit_handler
                self.current_library = 'twikit'
                logger.info("Twikit客户端初始化成功")

            return success

        except Exception as e:
            logger.error(f"初始化twikit客户端失败: {str(e)}")
            return False

    def auto_initialize(self, prefer_library: str = 'tweety') -> bool:
        """自动初始化可用的客户端"""
        available_libraries = self.get_available_libraries()

        if not available_libraries:
            logger.error("没有可用的Twitter库")
            return False

        # 按优先级尝试初始化
        libraries_to_try = []
        if prefer_library in available_libraries:
            libraries_to_try.append(prefer_library)

        for lib in available_libraries:
            if lib not in libraries_to_try:
                libraries_to_try.append(lib)

        for library in libraries_to_try:
            logger.info(f"尝试初始化 {library} 客户端...")

            if library == 'tweety':
                if self.initialize_tweety():
                    self.initialized = True
                    return True
            elif library == 'twikit':
                if self.initialize_twikit():
                    self.initialized = True
                    return True

        logger.error("所有Twitter库初始化都失败了")
        return False

    def fetch_user_tweets(self, user_id: str, limit: int = 10) -> List[Post]:
        """获取用户推文 - 统一接口"""
        if not self.initialized:
            logger.error("Twitter客户端未初始化")
            return []

        try:
            if self.current_library == 'tweety':
                from modules.socialmedia.twitter import fetch
                return fetch(user_id, limit, use_async=False)

            elif self.current_library == 'twikit':
                from modules.socialmedia import twitter_twikit
                return safe_asyncio_run(twitter_twikit.fetch_tweets(user_id, limit))

            else:
                logger.error(f"未知的Twitter库: {self.current_library}")
                return []

        except Exception as e:
            logger.error(f"获取用户推文失败: {str(e)}")
            return []

    def fetch_timeline_tweets(self, limit: int = 50) -> List[Post]:
        """获取时间线推文 - 统一接口"""
        if not self.initialized:
            logger.error("Twitter客户端未初始化")
            return []

        try:
            if self.current_library == 'tweety':
                from modules.socialmedia.twitter import fetch_timeline
                return fetch_timeline(limit)

            elif self.current_library == 'twikit':
                from modules.socialmedia import twitter_twikit
                return safe_asyncio_run(twitter_twikit.fetch_timeline_tweets(limit))

            else:
                logger.error(f"未知的Twitter库: {self.current_library}")
                return []

        except Exception as e:
            logger.error(f"获取时间线推文失败: {str(e)}")
            return []

    def reply_to_post(self, post_id: str, content: str) -> bool:
        """回复推文 - 统一接口"""
        if not self.initialized:
            logger.error("Twitter客户端未初始化")
            return False

        try:
            if self.current_library == 'tweety':
                from modules.socialmedia.twitter import reply_to_post
                return reply_to_post(post_id, content)

            elif self.current_library == 'twikit':
                logger.warning("Twikit暂不支持回复功能")
                return False

            else:
                logger.error(f"未知的Twitter库: {self.current_library}")
                return False

        except Exception as e:
            logger.error(f"回复推文失败: {str(e)}")
            return False

    def get_status(self) -> Dict[str, Any]:
        """获取客户端状态"""
        status = {
            'initialized': self.initialized,
            'current_library': self.current_library,
            'available_libraries': self.get_available_libraries()
        }

        if self.current_library == 'tweety':
            status['tweety_client'] = self.tweety_client is not None
            status['tweety_async_client'] = self.tweety_async_client is not None

        elif self.current_library == 'twikit':
            if self.twikit_client:
                from modules.socialmedia import twitter_twikit
                status['twikit_status'] = twitter_twikit.get_status()

        return status

    def switch_library(self, library: str) -> bool:
        """切换Twitter库"""
        if library not in self.get_available_libraries():
            logger.error(f"Twitter库 {library} 不可用")
            return False

        logger.info(f"切换到 {library} 库...")

        if library == 'tweety':
            return self.initialize_tweety()
        elif library == 'twikit':
            return self.initialize_twikit()
        else:
            logger.error(f"不支持的Twitter库: {library}")
            return False


# 全局客户端管理器实例
twitter_manager = TwitterClientManager()


# 兼容性接口函数
def get_twitter_manager() -> TwitterClientManager:
    """获取Twitter客户端管理器实例"""
    return twitter_manager


def initialize_twitter_manager(prefer_library: str = 'tweety') -> bool:
    """初始化Twitter客户端管理器"""
    return twitter_manager.auto_initialize(prefer_library)


# 导出主要类和函数
__all__ = [
    'TwitterClientManager',
    'twitter_manager',
    'get_twitter_manager',
    'initialize_twitter_manager'
]
