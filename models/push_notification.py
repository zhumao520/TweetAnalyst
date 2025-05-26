"""
推送通知模型
用于记录推送通知的状态和历史
"""

from datetime import datetime, timezone
from web_app import db
from sqlalchemy.dialects.sqlite import JSON

class PushNotification(db.Model):
    """推送通知模型"""
    __tablename__ = 'push_notifications'

    id = db.Column(db.Integer, primary_key=True)

    # 推送内容
    title = db.Column(db.String(255), nullable=True)
    message = db.Column(db.Text, nullable=False)
    tag = db.Column(db.String(50), nullable=True)

    # 推送目标
    targets = db.Column(db.Text, nullable=True)  # 逗号分隔的URL列表或描述

    # 推送状态
    status = db.Column(db.String(20), nullable=False, default='pending')  # pending, success, failed, retrying
    attempt_count = db.Column(db.Integer, nullable=False, default=0)
    max_attempts = db.Column(db.Integer, nullable=False, default=3)

    # 错误信息
    error_message = db.Column(db.Text, nullable=True)
    error_details = db.Column(JSON, nullable=True)  # 存储详细错误信息的JSON

    # 时间戳
    created_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, nullable=False, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))
    scheduled_for = db.Column(db.DateTime, nullable=True)  # 计划发送时间
    sent_at = db.Column(db.DateTime, nullable=True)  # 实际发送时间

    # 关联信息
    account_id = db.Column(db.String(100), nullable=True)  # 关联的账号ID
    post_id = db.Column(db.String(100), nullable=True)  # 关联的帖子ID

    # 附加数据
    meta_data = db.Column(JSON, nullable=True)  # 存储额外元数据的JSON

    def __repr__(self):
        return f'<PushNotification {self.id} {self.status}>'

    def to_dict(self):
        """转换为字典"""
        # 计算总URL数和成功URL数
        total_urls = 0
        success_urls = 0

        # 解析targets字段获取总URL数
        if self.targets:
            # 尝试按换行符分割
            if '\n' in self.targets:
                urls = [u.strip() for u in self.targets.splitlines() if u.strip()]
                total_urls = len(urls)
            # 尝试按逗号分割
            elif ',' in self.targets:
                urls = [u.strip() for u in self.targets.split(',') if u.strip()]
                total_urls = len(urls)
            # 单个URL
            elif self.targets.strip():
                total_urls = 1

        # 如果没有targets或解析失败，使用默认值
        if total_urls == 0:
            total_urls = 3  # 默认值

        # 根据状态确定成功URL数
        if self.status == 'success':
            # 如果状态是成功，则所有URL都成功
            success_urls = total_urls
        elif self.status == 'failed':
            # 如果状态是失败，则根据错误信息判断
            if self.error_message and '成功发送到' in self.error_message:
                # 尝试从错误信息中提取成功URL数
                import re
                match = re.search(r'成功发送到 (\d+)\/(\d+) 个URL', self.error_message)
                if match:
                    success_urls = int(match.group(1))
                    # 如果错误信息中也有总URL数，使用它
                    total_urls = int(match.group(2))

        return {
            'id': self.id,
            'title': self.title,
            'message': self.message[:100] + '...' if self.message and len(self.message) > 100 else self.message,
            'tag': self.tag,
            'targets': self.targets,
            'status': self.status,
            'attempt_count': self.attempt_count,
            'max_attempts': self.max_attempts,
            'error_message': self.error_message,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
            'scheduled_for': self.scheduled_for.isoformat() if self.scheduled_for else None,
            'sent_at': self.sent_at.isoformat() if self.sent_at else None,
            'account_id': self.account_id,
            'post_id': self.post_id,
            'success_urls': success_urls,
            'total_urls': total_urls
        }

    @classmethod
    def create(cls, **kwargs):
        """创建新的推送通知记录"""
        notification = cls(**kwargs)
        db.session.add(notification)
        db.session.commit()
        return notification

    def update(self, **kwargs):
        """更新推送通知记录"""
        for key, value in kwargs.items():
            if hasattr(self, key):
                setattr(self, key, value)
        self.updated_at = datetime.now(timezone.utc)
        db.session.commit()
        return self

    def mark_as_success(self):
        """标记为成功"""
        self.status = 'success'
        self.sent_at = datetime.now(timezone.utc)
        db.session.commit()
        return self

    def mark_as_failed(self, error_message=None, error_details=None):
        """标记为失败"""
        self.status = 'failed'
        if error_message:
            self.error_message = error_message
        if error_details:
            self.error_details = error_details
        db.session.commit()
        return self

    def increment_attempt(self):
        """增加尝试次数"""
        self.attempt_count += 1
        if self.attempt_count >= self.max_attempts:
            self.status = 'failed'
        else:
            self.status = 'retrying'
        db.session.commit()
        return self

    @classmethod
    def get_pending(cls, limit=10):
        """获取待处理的推送通知"""
        return cls.query.filter(
            (cls.status == 'pending') | (cls.status == 'retrying')
        ).order_by(cls.created_at).limit(limit).all()

    @classmethod
    def get_failed(cls, limit=10):
        """获取失败的推送通知"""
        return cls.query.filter_by(status='failed').order_by(cls.updated_at.desc()).limit(limit).all()

    @classmethod
    def get_recent(cls, limit=10):
        """获取最近的推送通知"""
        return cls.query.order_by(cls.created_at.desc()).limit(limit).all()
