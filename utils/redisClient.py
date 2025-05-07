import os
import logging
from datetime import datetime, timedelta

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 内存存储
memory_store = {}

class MemoryRedisClient:
    def __init__(self):
        self.store = memory_store
    
    def get(self, key):
        return self.store.get(key)
    
    def set(self, key, value, ex=None):
        self.store[key] = value
        logger.info(f"Set key: {key}, value: {value}, expiry: {ex}")
        return True
    
    def delete(self, key):
        if key in self.store:
            del self.store[key]
            return 1
        return 0
    
    def exists(self, key):
        return key in self.store
    
    def keys(self, pattern):
        # 简单实现，不支持复杂模式匹配
        if pattern.endswith('*'):
            prefix = pattern[:-1]
            return [k for k in self.store.keys() if k.startswith(prefix)]
        return [k for k in self.store.keys() if k == pattern]

# 创建内存 Redis 客户端
redis_client = MemoryRedisClient()

logger.info("Using in-memory storage instead of Redis")
