"""
代理配置模型
用于存储多个代理服务器配置
"""

from datetime import datetime
from . import db

class ProxyConfig(db.Model):
    """代理配置模型"""
    __tablename__ = 'proxy_config'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    host = db.Column(db.String(255), nullable=False)
    port = db.Column(db.Integer, nullable=False)
    protocol = db.Column(db.String(20), nullable=False, default='http')
    username = db.Column(db.String(100))
    password = db.Column(db.String(100))
    priority = db.Column(db.Integer, default=0)
    is_active = db.Column(db.Boolean, default=True)
    last_check_time = db.Column(db.DateTime)
    last_check_result = db.Column(db.Boolean)
    response_time = db.Column(db.Float)  # 响应时间（秒）
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)

    def __init__(self, name, host, port, protocol='http', username=None, password=None, 
                 priority=0, is_active=True):
        self.name = name
        self.host = host
        self.port = port
        self.protocol = protocol.lower()
        self.username = username
        self.password = password
        self.priority = priority
        self.is_active = is_active

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'host': self.host,
            'port': self.port,
            'protocol': self.protocol,
            'username': self.username,
            'password': '******' if self.password else None,
            'priority': self.priority,
            'is_active': self.is_active,
            'last_check_time': self.last_check_time.isoformat() if self.last_check_time else None,
            'last_check_result': self.last_check_result,
            'response_time': self.response_time,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

    def get_proxy_url(self):
        """获取代理URL"""
        auth_str = ""
        if self.username and self.password:
            auth_str = f"{self.username}:{self.password}@"
        return f"{self.protocol}://{auth_str}{self.host}:{self.port}"

    def get_proxy_dict(self):
        """获取代理字典，用于requests库"""
        proxy_url = self.get_proxy_url()
        return {
            'http': proxy_url,
            'https': proxy_url
        }

    def __repr__(self):
        return f"<ProxyConfig {self.name} ({self.protocol}://{self.host}:{self.port})>"
