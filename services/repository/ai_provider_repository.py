"""
AI提供商仓储
处理AI提供商相关的数据库操作
"""

from typing import Optional, List, Dict, Any, Tuple
from models.ai_provider import AIProvider
from . import BaseRepository

class AIProviderRepository(BaseRepository[AIProvider]):
    """AI提供商仓储类"""

    def __init__(self):
        """初始化AI提供商仓储"""
        super().__init__(AIProvider)

    def get_by_name(self, name: str) -> Optional[AIProvider]:
        """
        根据名称获取AI提供商

        Args:
            name: 提供商名称

        Returns:
            Optional[AIProvider]: 找到的提供商，如果不存在则返回None
        """
        return self.find_one(name=name)

    def get_active_providers(self) -> List[AIProvider]:
        """
        获取所有激活的AI提供商

        Returns:
            List[AIProvider]: 激活的提供商列表
        """
        return self.find(is_active=True)

    def get_by_priority(self, is_active: bool = True) -> List[AIProvider]:
        """
        根据优先级获取AI提供商

        Args:
            is_active: 是否只获取激活的提供商

        Returns:
            List[AIProvider]: 提供商列表，按优先级排序
        """
        query = self.query()

        if is_active:
            query = query.filter(AIProvider.is_active == True)

        return query.order_by(AIProvider.priority).all()

    def create_provider(self, provider_data: Dict[str, Any]) -> AIProvider:
        """
        创建新的AI提供商

        Args:
            provider_data: 提供商数据

        Returns:
            AIProvider: 创建的提供商
        """
        return self.create(**provider_data)

    def update_provider(self, provider_id: int, provider_data: Dict[str, Any]) -> Optional[AIProvider]:
        """
        更新AI提供商

        Args:
            provider_id: 提供商ID
            provider_data: 提供商数据

        Returns:
            Optional[AIProvider]: 更新后的提供商，如果不存在则返回None
        """
        provider = self.get_by_id(provider_id)
        if provider:
            return self.update(provider, **provider_data)
        return None

    def toggle_active(self, provider_id: int, is_active: bool) -> bool:
        """
        切换提供商激活状态

        Args:
            provider_id: 提供商ID
            is_active: 是否激活

        Returns:
            bool: 是否成功切换
        """
        provider = self.get_by_id(provider_id)
        if provider:
            provider.is_active = is_active
            self.save(provider)
            return True
        return False

    def update_stats(self, provider_id: int, success: bool, error_message: str = None) -> bool:
        """
        更新提供商使用统计

        Args:
            provider_id: 提供商ID
            success: 是否成功
            error_message: 错误信息

        Returns:
            bool: 是否成功更新
        """
        provider = self.get_by_id(provider_id)
        if not provider:
            return False

        # 更新请求计数
        provider.request_count += 1

        if success:
            # 更新成功计数
            provider.success_count += 1
        else:
            # 更新错误计数和最后错误信息
            provider.error_count += 1
            if error_message:
                provider.last_error = error_message

        self.save(provider)
        return True

    def get_best_provider(self) -> Optional[AIProvider]:
        """
        获取最佳AI提供商（优先级最高且激活的）

        Returns:
            Optional[AIProvider]: 最佳提供商，如果不存在则返回None
        """
        providers = self.get_by_priority(is_active=True)
        return providers[0] if providers else None
