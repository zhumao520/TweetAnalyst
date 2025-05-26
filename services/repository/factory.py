"""
仓储工厂
提供获取各种仓储实例的工厂方法
"""

from typing import Dict, Any, Type, TypeVar, Optional

from .user_repository import UserRepository
from .social_account_repository import SocialAccountRepository
from .analysis_result_repository import AnalysisResultRepository
from .system_config_repository import SystemConfigRepository
from .system_state_repository import SystemStateRepository
from .ai_provider_repository import AIProviderRepository
from .notification_service_repository import NotificationServiceRepository
from . import BaseRepository

# 定义泛型类型变量，表示任何仓储类
R = TypeVar('R', bound=BaseRepository)

class RepositoryFactory:
    """仓储工厂类，用于获取各种仓储实例"""
    
    # 仓储实例缓存
    _instances: Dict[str, BaseRepository] = {}
    
    @classmethod
    def get_user_repository(cls) -> UserRepository:
        """
        获取用户仓储
        
        Returns:
            UserRepository: 用户仓储实例
        """
        return cls._get_repository(UserRepository)
    
    @classmethod
    def get_social_account_repository(cls) -> SocialAccountRepository:
        """
        获取社交账号仓储
        
        Returns:
            SocialAccountRepository: 社交账号仓储实例
        """
        return cls._get_repository(SocialAccountRepository)
    
    @classmethod
    def get_analysis_result_repository(cls) -> AnalysisResultRepository:
        """
        获取分析结果仓储
        
        Returns:
            AnalysisResultRepository: 分析结果仓储实例
        """
        return cls._get_repository(AnalysisResultRepository)
    
    @classmethod
    def get_system_config_repository(cls) -> SystemConfigRepository:
        """
        获取系统配置仓储
        
        Returns:
            SystemConfigRepository: 系统配置仓储实例
        """
        return cls._get_repository(SystemConfigRepository)
    
    @classmethod
    def get_system_state_repository(cls) -> SystemStateRepository:
        """
        获取系统状态仓储
        
        Returns:
            SystemStateRepository: 系统状态仓储实例
        """
        return cls._get_repository(SystemStateRepository)
    
    @classmethod
    def get_ai_provider_repository(cls) -> AIProviderRepository:
        """
        获取AI提供商仓储
        
        Returns:
            AIProviderRepository: AI提供商仓储实例
        """
        return cls._get_repository(AIProviderRepository)
    
    @classmethod
    def get_notification_service_repository(cls) -> NotificationServiceRepository:
        """
        获取通知服务仓储
        
        Returns:
            NotificationServiceRepository: 通知服务仓储实例
        """
        return cls._get_repository(NotificationServiceRepository)
    
    @classmethod
    def _get_repository(cls, repository_class: Type[R]) -> R:
        """
        获取仓储实例
        
        Args:
            repository_class: 仓储类
            
        Returns:
            R: 仓储实例
        """
        class_name = repository_class.__name__
        
        if class_name not in cls._instances:
            cls._instances[class_name] = repository_class()
            
        return cls._instances[class_name]
    
    @classmethod
    def clear_cache(cls) -> None:
        """
        清除仓储实例缓存
        """
        cls._instances.clear()
