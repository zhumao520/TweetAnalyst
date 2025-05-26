"""
AI请求日志模型
记录AI请求的详细信息和健康检查结果
"""

from datetime import datetime, timezone
from web_app import db
import json

class AIRequestLog(db.Model):
    """AI请求日志模型"""
    __tablename__ = 'ai_request_logs'

    id = db.Column(db.Integer, primary_key=True)
    provider_id = db.Column(db.Integer, db.ForeignKey('ai_provider.id'), nullable=True)
    request_type = db.Column(db.String(50), nullable=False, default='content_analysis')  # content_analysis, health_check, etc.
    request_content = db.Column(db.Text, nullable=True)  # 请求内容
    response_content = db.Column(db.Text, nullable=True)  # 响应内容
    is_success = db.Column(db.Boolean, default=False)  # 请求是否成功
    error_message = db.Column(db.Text, nullable=True)  # 错误信息
    response_time = db.Column(db.Float, nullable=True)  # 响应时间（毫秒）
    token_count = db.Column(db.Integer, nullable=True)  # 使用的token数量
    is_cached = db.Column(db.Boolean, default=False)  # 是否使用了缓存
    cache_key = db.Column(db.String(255), nullable=True)  # 缓存键
    meta_data = db.Column(db.Text, nullable=True)  # 元数据，JSON格式
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc),
                          onupdate=lambda: datetime.now(timezone.utc))

    # 关联关系
    provider = db.relationship('AIProvider', backref=db.backref('request_logs', lazy=True))

    def __repr__(self):
        return f'<AIRequestLog {self.id}: {self.request_type} - {self.is_success}>'

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'provider_id': self.provider_id,
            'request_type': self.request_type,
            'is_success': self.is_success,
            'error_message': self.error_message,
            'response_time': self.response_time,
            'token_count': self.token_count,
            'is_cached': self.is_cached,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'meta_data': json.loads(self.meta_data) if self.meta_data else None
        }

    def set_meta_data(self, data):
        """设置元数据"""
        if data:
            self.meta_data = json.dumps(data)

    def get_meta_data(self):
        """获取元数据"""
        if self.meta_data:
            try:
                return json.loads(self.meta_data)
            except:
                return {}
        return {}

    @classmethod
    def create_log(cls, provider_id=None, request_type='content_analysis', request_content=None,
                  response_content=None, is_success=False, error_message=None, response_time=None,
                  token_count=None, is_cached=False, cache_key=None, meta_data=None):
        """创建日志记录"""
        log = cls(
            provider_id=provider_id,
            request_type=request_type,
            request_content=request_content,
            response_content=response_content,
            is_success=is_success,
            error_message=error_message,
            response_time=response_time,
            token_count=token_count,
            is_cached=is_cached,
            cache_key=cache_key
        )

        if meta_data:
            log.set_meta_data(meta_data)

        db.session.add(log)
        db.session.commit()

        return log
