"""
通知服务模型
用于存储通知服务配置
"""

from . import db
from datetime import datetime

class NotificationService(db.Model):
    """通知服务模型"""
    __tablename__ = 'notification_services'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    service_type = db.Column(db.String(50), nullable=False)
    config_url = db.Column(db.Text, nullable=False)
    is_active = db.Column(db.Boolean, default=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __init__(self, name, service_type, config_url, is_active=True):
        self.name = name
        self.service_type = service_type
        self.config_url = config_url
        self.is_active = is_active

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'service_type': self.service_type,
            'config_url': self.config_url,
            'is_active': self.is_active,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None
        }

    def __repr__(self):
        return f'<NotificationService {self.name}>'

    @classmethod
    def get_active_services(cls):
        """获取所有活跃的通知服务"""
        return cls.query.filter_by(is_active=True).all()

    @classmethod
    def get_service_by_name(cls, name):
        """根据名称获取通知服务"""
        return cls.query.filter_by(name=name).first()

    @classmethod
    def get_service_by_type(cls, service_type):
        """根据类型获取通知服务"""
        return cls.query.filter_by(service_type=service_type).all()
