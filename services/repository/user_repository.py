"""
用户仓储
处理用户相关的数据库操作
"""

from typing import Optional, List, Dict, Any, Tuple
from models.user import User
from . import BaseRepository

class UserRepository(BaseRepository[User]):
    """用户仓储类"""

    def __init__(self):
        """初始化用户仓储"""
        super().__init__(User)

    def get_by_username(self, username: str) -> Optional[User]:
        """
        根据用户名获取用户

        Args:
            username: 用户名

        Returns:
            Optional[User]: 找到的用户，如果不存在则返回None
        """
        return self.find_one(username=username)

    def create_user(self, username: str, password: str, is_admin: bool = False) -> User:
        """
        创建新用户

        Args:
            username: 用户名
            password: 密码
            is_admin: 是否为管理员

        Returns:
            User: 创建的用户
        """
        user = User(username=username, is_admin=is_admin)
        user.set_password(password)
        return self.save(user)

    def authenticate(self, username: str, password: str) -> Optional[User]:
        """
        验证用户凭据

        Args:
            username: 用户名
            password: 密码

        Returns:
            Optional[User]: 验证成功的用户，如果验证失败则返回None
        """
        user = self.get_by_username(username)
        if user and user.check_password(password):
            return user
        return None

    def change_password(self, user_id: int, new_password: str) -> bool:
        """
        修改用户密码

        Args:
            user_id: 用户ID
            new_password: 新密码

        Returns:
            bool: 是否成功修改
        """
        user = self.get_by_id(user_id)
        if user:
            user.set_password(new_password)
            self.save(user)
            return True
        return False

    def get_all_admins(self) -> List[User]:
        """
        获取所有管理员用户

        Returns:
            List[User]: 管理员用户列表
        """
        return self.find(is_admin=True)
