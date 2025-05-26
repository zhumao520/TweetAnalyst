"""
社交账号仓储
处理社交账号相关的数据库操作
"""

from typing import Optional, List, Dict, Any, Tuple
from models.social_account import SocialAccount
from . import BaseRepository

class SocialAccountRepository(BaseRepository[SocialAccount]):
    """社交账号仓储类"""

    def __init__(self):
        """初始化社交账号仓储"""
        super().__init__(SocialAccount)

    def get_by_account_id(self, account_type: str, account_id: str) -> Optional[SocialAccount]:
        """
        根据账号类型和ID获取账号

        Args:
            account_type: 账号类型
            account_id: 账号ID

        Returns:
            Optional[SocialAccount]: 找到的账号，如果不存在则返回None
        """
        return self.find_one(type=account_type, account_id=account_id)

    def get_by_type(self, account_type: str) -> List[SocialAccount]:
        """
        根据账号类型获取所有账号

        Args:
            account_type: 账号类型

        Returns:
            List[SocialAccount]: 账号列表
        """
        return self.find(type=account_type)

    def get_by_tag(self, tag: str) -> List[SocialAccount]:
        """
        根据标签获取所有账号

        Args:
            tag: 标签

        Returns:
            List[SocialAccount]: 账号列表
        """
        return self.find(tag=tag)

    def get_by_type_and_tag(self, account_type: str, tag: str) -> List[SocialAccount]:
        """
        根据账号类型和标签获取所有账号

        Args:
            account_type: 账号类型
            tag: 标签

        Returns:
            List[SocialAccount]: 账号列表
        """
        return self.find(type=account_type, tag=tag)

    def create_account(self, account_data: Dict[str, Any]) -> SocialAccount:
        """
        创建新账号

        Args:
            account_data: 账号数据

        Returns:
            SocialAccount: 创建的账号
        """
        return self.create(**account_data)

    def update_account_details(self, account_id: int, details: Dict[str, Any]) -> Optional[SocialAccount]:
        """
        更新账号详细信息

        Args:
            account_id: 账号ID
            details: 详细信息

        Returns:
            Optional[SocialAccount]: 更新后的账号，如果不存在则返回None
        """
        account = self.get_by_id(account_id)
        if account:
            return self.update(account, **details)
        return None

    def toggle_auto_reply(self, account_id: int, enable: bool) -> bool:
        """
        切换自动回复功能

        Args:
            account_id: 账号ID
            enable: 是否启用

        Returns:
            bool: 是否成功切换
        """
        account = self.get_by_id(account_id)
        if account:
            account.enable_auto_reply = enable
            self.save(account)
            return True
        return False

    def toggle_bypass_ai(self, account_id: int, enable: bool) -> bool:
        """
        切换绕过AI功能

        Args:
            account_id: 账号ID
            enable: 是否启用

        Returns:
            bool: 是否成功切换
        """
        account = self.get_by_id(account_id)
        if account:
            account.bypass_ai = enable
            self.save(account)
            return True
        return False

    def update_prompt_template(self, account_id: int, template: str) -> bool:
        """
        更新提示词模板

        Args:
            account_id: 账号ID
            template: 提示词模板

        Returns:
            bool: 是否成功更新
        """
        account = self.get_by_id(account_id)
        if account:
            account.prompt_template = template
            self.save(account)
            return True
        return False

    def update_auto_reply_template(self, account_id: int, template: str) -> bool:
        """
        更新自动回复模板

        Args:
            account_id: 账号ID
            template: 自动回复模板

        Returns:
            bool: 是否成功更新
        """
        account = self.get_by_id(account_id)
        if account:
            account.auto_reply_template = template
            self.save(account)
            return True
        return False

    def update_ai_provider(self, account_id: int, provider_id: int, content_type: str = None) -> bool:
        """
        更新AI提供商

        Args:
            account_id: 账号ID
            provider_id: AI提供商ID
            content_type: 内容类型，如text, image, video, gif，如果为None则更新默认提供商

        Returns:
            bool: 是否成功更新
        """
        account = self.get_by_id(account_id)
        if not account:
            return False

        if content_type == 'text':
            account.text_provider_id = provider_id
        elif content_type == 'image':
            account.image_provider_id = provider_id
        elif content_type == 'video':
            account.video_provider_id = provider_id
        elif content_type == 'gif':
            account.gif_provider_id = provider_id
        else:
            account.ai_provider_id = provider_id

        self.save(account)
        return True
