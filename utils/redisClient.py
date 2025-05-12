import os
import logging
import time
from datetime import datetime, timedelta

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 内存存储
memory_store = {}
# 过期时间存储
expiry_store = {}

class MemoryRedisClient:
    def __init__(self):
        self.store = memory_store
        self.expiry = expiry_store

        # 清理过期键的方法
        self._clean_expired_keys()

    def _clean_expired_keys(self):
        """清理已过期的键"""
        current_time = int(time.time())
        expired_keys = [k for k, v in self.expiry.items() if v <= current_time]
        for key in expired_keys:
            if key in self.store:
                logger.debug(f"自动清理过期键: {key}")
                del self.store[key]
            del self.expiry[key]

    def get(self, key):
        """获取键值，如果键已过期则返回None"""
        self._clean_expired_keys()
        return self.store.get(key)

    def set(self, key, value, ex=None):
        """设置键值，可选过期时间（秒）"""
        self.store[key] = value

        # 如果设置了过期时间，记录过期时间戳
        if ex is not None:
            self.expiry[key] = int(time.time()) + int(ex)
            logger.debug(f"设置键 {key} 的过期时间为 {ex} 秒")
        elif key in self.expiry:
            # 如果之前设置了过期时间，但现在没有设置，则移除过期设置
            del self.expiry[key]

        logger.debug(f"设置键: {key}, 值长度: {len(str(value)) if value else 0}, 过期时间: {ex if ex else '无'}")
        return True

    def expire(self, key, seconds):
        """设置键的过期时间"""
        if key in self.store:
            self.expiry[key] = int(time.time()) + int(seconds)
            logger.debug(f"设置键 {key} 的过期时间为 {seconds} 秒")
            return True
        return False

    def ttl(self, key):
        """获取键的剩余生存时间"""
        if key not in self.store:
            return -2  # 键不存在
        if key not in self.expiry:
            return -1  # 键存在但没有设置过期时间

        remaining = self.expiry[key] - int(time.time())
        return max(0, remaining)  # 不返回负值

    def delete(self, key):
        """删除键"""
        count = 0
        if key in self.store:
            del self.store[key]
            count += 1
        if key in self.expiry:
            del self.expiry[key]
        return count

    def exists(self, key):
        """检查键是否存在"""
        self._clean_expired_keys()
        return key in self.store

    def keys(self, pattern):
        """查找匹配模式的键"""
        self._clean_expired_keys()
        # 简单实现，不支持复杂模式匹配
        if pattern.endswith('*'):
            prefix = pattern[:-1]
            return [k for k in self.store.keys() if k.startswith(prefix)]
        return [k for k in self.store.keys() if k == pattern]

# 创建内存 Redis 客户端
redis_client = MemoryRedisClient()

logger.info("使用内存存储代替Redis")
