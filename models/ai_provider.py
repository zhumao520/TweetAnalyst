"""
AI提供商模型
用于存储和管理多个AI提供商的配置信息
"""

from datetime import datetime, timezone
from . import db

class AIProvider(db.Model):
    """AI提供商模型"""
    __tablename__ = 'ai_provider'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False, unique=True)
    api_key = db.Column(db.String(255), nullable=False)
    api_base = db.Column(db.String(255), nullable=False)
    model = db.Column(db.String(100), nullable=False)
    priority = db.Column(db.Integer, default=0)  # 优先级，数字越小优先级越高
    is_active = db.Column(db.Boolean, default=True)  # 是否激活

    # 使用统计
    request_count = db.Column(db.Integer, default=0)  # 请求次数
    success_count = db.Column(db.Integer, default=0)  # 成功次数
    error_count = db.Column(db.Integer, default=0)  # 错误次数
    last_error = db.Column(db.Text, nullable=True)  # 最后一次错误信息

    # 媒体类型支持
    supports_text = db.Column(db.Boolean, default=True)  # 是否支持文本
    supports_image = db.Column(db.Boolean, default=False)  # 是否支持图片
    supports_video = db.Column(db.Boolean, default=False)  # 是否支持视频
    supports_gif = db.Column(db.Boolean, default=False)  # 是否支持GIF

    # 时间戳
    created_at = db.Column(db.DateTime, default=datetime.now)
    updated_at = db.Column(db.DateTime, default=datetime.now, onupdate=datetime.now)
    last_used_at = db.Column(db.DateTime, nullable=True)  # 最后使用时间
    last_error_at = db.Column(db.DateTime, nullable=True)  # 最后错误时间

    def __repr__(self):
        return f'<AIProvider {self.id} {self.name}>'

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'name': self.name,
            'api_base': self.api_base,
            'model': self.model,
            'priority': self.priority,
            'is_active': self.is_active,
            'request_count': self.request_count,
            'success_count': self.success_count,
            'error_count': self.error_count,
            'last_error': self.last_error,
            'supports_text': self.supports_text,
            'supports_image': self.supports_image,
            'supports_video': self.supports_video,
            'supports_gif': self.supports_gif,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'last_used_at': self.last_used_at.isoformat() if self.last_used_at else None,
            'last_error_at': self.last_error_at.isoformat() if self.last_error_at else None
        }

    def record_success(self):
        """记录成功使用"""
        self.request_count += 1
        self.success_count += 1
        self.last_used_at = datetime.now()
        db.session.commit()

    def record_error(self, error_message=None):
        """记录使用错误"""
        self.request_count += 1
        self.error_count += 1
        self.last_error = error_message
        self.last_error_at = datetime.now()
        self.last_used_at = datetime.now()
        db.session.commit()

    @classmethod
    def get_by_media_type(cls, media_type):
        """
        根据媒体类型获取支持的AI提供商

        Args:
            media_type: 媒体类型，可选值：text, image, video, gif

        Returns:
            AIProvider: 支持该媒体类型的AI提供商，按优先级排序
        """
        query = cls.query.filter_by(is_active=True)

        if media_type == 'text':
            query = query.filter_by(supports_text=True)
        elif media_type == 'image':
            query = query.filter_by(supports_image=True)
        elif media_type == 'video':
            query = query.filter_by(supports_video=True)
        elif media_type == 'gif':
            query = query.filter_by(supports_gif=True)

        return query.order_by(cls.priority).all()
