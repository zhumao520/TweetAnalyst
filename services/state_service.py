"""
状态存储服务
提供类似Redis的状态存储功能
"""

import logging
from datetime import datetime, timedelta, timezone
from services.repository.factory import RepositoryFactory

# 创建日志记录器
logger = logging.getLogger('services.state')

class DBStateStore:
    """数据库状态存储，替代Redis"""

    def __init__(self, auto_cleanup=True, cleanup_interval=3600):
        """
        初始化状态存储

        Args:
            auto_cleanup: 是否自动清理过期数据
            cleanup_interval: 清理间隔（秒）
        """
        self.auto_cleanup = auto_cleanup
        self.cleanup_interval = cleanup_interval
        self.last_cleanup = datetime.now(timezone.utc)
        self.repository = RepositoryFactory.get_system_state_repository()

    def get(self, key):
        """
        获取状态值

        Args:
            key: 状态键

        Returns:
            str: 状态值
        """
        # 尝试自动清理
        self._try_cleanup()

        return self.repository.get_value(key)

    def set(self, key, value, expire=None):
        """
        设置状态值

        Args:
            key: 状态键
            value: 状态值
            expire: 过期时间（秒）

        Returns:
            bool: 是否成功
        """
        # 尝试自动清理
        self._try_cleanup()

        try:
            self.repository.set_value(key, value, expire)
            return True
        except Exception as e:
            logger.error(f"设置状态值时出错: {str(e)}")
            return False

    def expire(self, key, seconds):
        """
        设置过期时间

        Args:
            key: 状态键
            seconds: 过期时间（秒）

        Returns:
            bool: 是否成功
        """
        state = self.repository.get_by_key(key)
        if state:
            try:
                expires_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
                self.repository.update(state, expires_at=expires_at)
                return True
            except Exception as e:
                logger.error(f"设置过期时间时出错: {str(e)}")
        return False

    def delete(self, key):
        """
        删除状态值

        Args:
            key: 状态键

        Returns:
            bool: 是否成功
        """
        return self.repository.delete_by_key(key)

    def cleanup(self):
        """
        清理过期数据

        Returns:
            int: 清理的数据数量
        """
        count = self.repository.cleanup_expired()
        self.last_cleanup = datetime.now(timezone.utc)
        return count

    def _try_cleanup(self):
        """尝试自动清理"""
        if not self.auto_cleanup:
            return

        now = datetime.now(timezone.utc)
        if (now - self.last_cleanup).total_seconds() > self.cleanup_interval:
            self.cleanup()
