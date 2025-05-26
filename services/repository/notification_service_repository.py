"""
通知服务仓储
处理通知服务相关的数据库操作
"""

from typing import Optional, List, Dict, Any, Tuple
from models.notification_service import NotificationService
from . import BaseRepository

class NotificationServiceRepository(BaseRepository[NotificationService]):
    """通知服务仓储类"""

    def __init__(self):
        """初始化通知服务仓储"""
        super().__init__(NotificationService)

    def get_by_name(self, name: str) -> Optional[NotificationService]:
        """
        根据名称获取通知服务

        Args:
            name: 服务名称

        Returns:
            Optional[NotificationService]: 找到的服务，如果不存在则返回None
        """
        return self.find_one(name=name)

    def get_active_services(self) -> List[NotificationService]:
        """
        获取所有激活的通知服务

        Returns:
            List[NotificationService]: 激活的服务列表
        """
        return self.find(is_active=True)

    def create_service(self, service_data: Dict[str, Any]) -> NotificationService:
        """
        创建新的通知服务

        Args:
            service_data: 服务数据

        Returns:
            NotificationService: 创建的服务
        """
        return self.create(**service_data)

    def update_service(self, service_id: int, service_data: Dict[str, Any]) -> Optional[NotificationService]:
        """
        更新通知服务

        Args:
            service_id: 服务ID
            service_data: 服务数据

        Returns:
            Optional[NotificationService]: 更新后的服务，如果不存在则返回None
        """
        service = self.get_by_id(service_id)
        if service:
            return self.update(service, **service_data)
        return None

    def toggle_active(self, service_id: int, is_active: bool) -> bool:
        """
        切换服务激活状态

        Args:
            service_id: 服务ID
            is_active: 是否激活

        Returns:
            bool: 是否成功切换
        """
        service = self.get_by_id(service_id)
        if service:
            service.is_active = is_active
            self.save(service)
            return True
        return False

    def get_service_url(self, service_id: int) -> Optional[str]:
        """
        获取服务URL

        Args:
            service_id: 服务ID

        Returns:
            Optional[str]: 服务URL，如果不存在则返回None
        """
        service = self.get_by_id(service_id)
        return service.url if service else None

    def get_all_urls(self, active_only: bool = True) -> List[str]:
        """
        获取所有服务URL

        Args:
            active_only: 是否只获取激活的服务

        Returns:
            List[str]: 服务URL列表
        """
        if active_only:
            services = self.get_active_services()
        else:
            services = self.get_all()

        return [service.url for service in services if service.url]
