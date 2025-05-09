"""
状态存储服务
提供类似Redis的状态存储功能
"""

import logging
from datetime import datetime, timedelta, timezone
from models import db, SystemState

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

        state = SystemState.query.filter_by(key=key).first()
        if state and (state.expires_at is None or state.expires_at > datetime.now(timezone.utc)):
            return state.value
        return None

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

        state = SystemState.query.filter_by(key=key).first()
        expires_at = None
        if expire:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expire)

        if state:
            state.value = value
            state.expires_at = expires_at
            state.updated_at = datetime.now(timezone.utc)
        else:
            state = SystemState(key=key, value=value, expires_at=expires_at)
            db.session.add(state)

        try:
            db.session.commit()
            return True
        except Exception as e:
            logger.error(f"设置状态值时出错: {str(e)}")
            db.session.rollback()
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
        state = SystemState.query.filter_by(key=key).first()
        if state:
            state.expires_at = datetime.now(timezone.utc) + timedelta(seconds=seconds)
            try:
                db.session.commit()
                return True
            except Exception as e:
                logger.error(f"设置过期时间时出错: {str(e)}")
                db.session.rollback()
        return False

    def delete(self, key):
        """
        删除状态值
        
        Args:
            key: 状态键
            
        Returns:
            bool: 是否成功
        """
        state = SystemState.query.filter_by(key=key).first()
        if state:
            try:
                db.session.delete(state)
                db.session.commit()
                return True
            except Exception as e:
                logger.error(f"删除状态值时出错: {str(e)}")
                db.session.rollback()
        return False

    def cleanup(self):
        """
        清理过期数据
        
        Returns:
            int: 清理的数据数量
        """
        count = SystemState.cleanup_expired()
        self.last_cleanup = datetime.now(timezone.utc)
        return count

    def _try_cleanup(self):
        """尝试自动清理"""
        if not self.auto_cleanup:
            return

        now = datetime.now(timezone.utc)
        if (now - self.last_cleanup).total_seconds() > self.cleanup_interval:
            self.cleanup()
