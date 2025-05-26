"""
系统配置仓储
处理系统配置相关的数据库操作
"""

from typing import Optional, List, Dict, Any, Tuple
from models.system_config import SystemConfig
from . import BaseRepository

class SystemConfigRepository(BaseRepository[SystemConfig]):
    """系统配置仓储类"""

    def __init__(self):
        """初始化系统配置仓储"""
        super().__init__(SystemConfig)

    def get_by_key(self, key: str) -> Optional[SystemConfig]:
        """
        根据键获取配置

        Args:
            key: 配置键

        Returns:
            Optional[SystemConfig]: 找到的配置，如果不存在则返回None
        """
        return self.find_one(key=key)

    def get_value(self, key: str, default: Any = None) -> Any:
        """
        获取配置值

        Args:
            key: 配置键
            default: 默认值

        Returns:
            Any: 配置值，如果不存在则返回默认值
        """
        config = self.get_by_key(key)
        return config.value if config else default

    def set_value(self, key: str, value: str, is_secret: bool = False, description: str = None) -> SystemConfig:
        """
        设置配置值

        Args:
            key: 配置键
            value: 配置值
            is_secret: 是否为敏感信息
            description: 配置描述

        Returns:
            SystemConfig: 更新或创建的配置
        """
        config = self.get_by_key(key)

        if config:
            # 更新现有配置
            updated = False

            if config.value != value:
                config.value = value
                updated = True

            if is_secret is not None and config.is_secret != is_secret:
                config.is_secret = is_secret
                updated = True

            if description and config.description != description:
                config.description = description
                updated = True

            if updated:
                return self.save(config)
            return config
        else:
            # 创建新配置
            return self.create(
                key=key,
                value=value,
                is_secret=is_secret,
                description=description
            )

    def delete_by_key(self, key: str) -> bool:
        """
        根据键删除配置

        Args:
            key: 配置键

        Returns:
            bool: 是否成功删除
        """
        config = self.get_by_key(key)
        if config:
            return self.delete(config)
        return False

    def get_all_configs(self, include_secrets: bool = False) -> Dict[str, str]:
        """
        获取所有配置

        Args:
            include_secrets: 是否包含敏感信息

        Returns:
            Dict[str, str]: 配置字典
        """
        configs = self.get_all()
        result = {}

        for config in configs:
            if include_secrets or not config.is_secret:
                result[config.key] = config.value
            else:
                # 对于敏感信息，只返回是否已设置
                result[config.key] = '******' if config.value else ''

        return result

    def get_configs_by_prefix(self, prefix: str, include_secrets: bool = False) -> Dict[str, str]:
        """
        根据前缀获取配置

        Args:
            prefix: 配置键前缀
            include_secrets: 是否包含敏感信息

        Returns:
            Dict[str, str]: 配置字典
        """
        query = self.query().filter(SystemConfig.key.like(f'{prefix}%'))
        configs = query.all()
        result = {}

        for config in configs:
            if include_secrets or not config.is_secret:
                result[config.key] = config.value
            else:
                # 对于敏感信息，只返回是否已设置
                result[config.key] = '******' if config.value else ''

        return result

    def batch_set_configs(self, configs_dict: Dict[str, Dict[str, Any]]) -> Tuple[int, int]:
        """
        批量设置配置

        Args:
            configs_dict: 配置字典，格式为 {key: {value: value, is_secret: bool, description: str}}

        Returns:
            Tuple[int, int]: (更新的配置数量, 跳过的配置数量)
        """
        updated_count = 0
        skipped_count = 0

        for key, config_data in configs_dict.items():
            value = config_data.get('value', '')
            is_secret = config_data.get('is_secret', False)
            description = config_data.get('description', None)

            config = self.get_by_key(key)

            if config:
                # 检查值是否相同，如果相同则不更新
                if config.value == value:
                    # 如果描述或敏感标记需要更新，则更新这些字段
                    if (description and config.description != description) or \
                       (is_secret is not None and config.is_secret != is_secret):

                        if description:
                            config.description = description

                        if is_secret is not None:
                            config.is_secret = is_secret

                        self.save(config)
                        updated_count += 1
                    else:
                        # 完全没有变化，不需要更新
                        skipped_count += 1
                else:
                    # 值不同，需要更新
                    config.value = value

                    if description:
                        config.description = description

                    if is_secret is not None:
                        config.is_secret = is_secret

                    self.save(config)
                    updated_count += 1
            else:
                # 配置不存在，创建新配置
                self.create(
                    key=key,
                    value=value,
                    is_secret=is_secret,
                    description=description
                )
                updated_count += 1

        return updated_count, skipped_count
