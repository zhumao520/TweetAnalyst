"""
系统配置模型
存储系统配置信息
"""

from datetime import datetime, timezone
from . import db

class SystemConfig(db.Model):
    """系统配置模型"""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(100), unique=True, nullable=False)  # 配置键
    value = db.Column(db.Text, nullable=True)  # 配置值
    is_secret = db.Column(db.Boolean, default=False)  # 是否为敏感信息
    description = db.Column(db.String(255), nullable=True)  # 配置描述
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    
    def to_dict(self, include_secret=False):
        """转换为字典"""
        result = {
            'id': self.id,
            'key': self.key,
            'is_secret': self.is_secret,
            'description': self.description,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
        
        # 处理敏感信息
        if self.is_secret and not include_secret:
            result['value'] = '******' if self.value else ''
            result['has_value'] = bool(self.value)
        else:
            result['value'] = self.value
        
        return result
    
    def __repr__(self):
        return f'<SystemConfig {self.key}>'
