"""
系统状态仓储
处理系统状态相关的数据库操作
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta, timezone
from models.system_state import SystemState
from . import BaseRepository

class SystemStateRepository(BaseRepository[SystemState]):
    """系统状态仓储类"""

    def __init__(self):
        """初始化系统状态仓储"""
        super().__init__(SystemState)

    def get_by_key(self, key: str) -> Optional[SystemState]:
        """
        根据键获取状态

        Args:
            key: 状态键

        Returns:
            Optional[SystemState]: 找到的状态，如果不存在则返回None
        """
        state = self.find_one(key=key)

        # 检查是否过期
        if state and state.expires_at and state.expires_at < datetime.now(timezone.utc):
            # 状态已过期，删除并返回None
            self.delete(state)
            return None

        return state

    def get_value(self, key: str, default: Any = None) -> Any:
        """
        获取状态值

        Args:
            key: 状态键
            default: 默认值

        Returns:
            Any: 状态值，如果不存在或已过期则返回默认值
        """
        state = self.get_by_key(key)
        return state.value if state else default

    def set_value(self, key: str, value: str, expire: int = None) -> SystemState:
        """
        设置状态值

        Args:
            key: 状态键
            value: 状态值
            expire: 过期时间（秒）

        Returns:
            SystemState: 更新或创建的状态
        """
        state = self.find_one(key=key)
        expires_at = None

        if expire:
            expires_at = datetime.now(timezone.utc) + timedelta(seconds=expire)

        if state:
            # 更新现有状态
            state.value = value
            state.expires_at = expires_at
            state.updated_at = datetime.now(timezone.utc)
            return self.save(state)
        else:
            # 创建新状态
            return self.create(
                key=key,
                value=value,
                expires_at=expires_at
            )

    def delete_by_key(self, key: str) -> bool:
        """
        根据键删除状态

        Args:
            key: 状态键

        Returns:
            bool: 是否成功删除
        """
        state = self.find_one(key=key)
        if state:
            return self.delete(state)
        return False

    def cleanup_expired(self) -> int:
        """
        清理过期状态

        Returns:
            int: 清理的状态数量
        """
        now = datetime.now(timezone.utc)
        expired_states = self.query().filter(
            SystemState.expires_at.isnot(None),
            SystemState.expires_at < now
        ).all()

        count = len(expired_states)

        for state in expired_states:
            self.delete(state)

        return count

    def get_all_by_prefix(self, prefix: str) -> Dict[str, str]:
        """
        根据前缀获取所有状态

        Args:
            prefix: 状态键前缀

        Returns:
            Dict[str, str]: 状态字典
        """
        now = datetime.now(timezone.utc)
        query = self.query().filter(SystemState.key.like(f'{prefix}%'))

        # 排除已过期的状态
        query = query.filter(
            (SystemState.expires_at.is_(None)) |
            (SystemState.expires_at >= now)
        )

        states = query.all()
        result = {}

        for state in states:
            result[state.key] = state.value

        return result
