"""
社交账号模型
处理社交媒体账号信息
"""

from datetime import datetime, timezone
from . import db

class SocialAccount(db.Model):
    """社交媒体账号模型"""
    id = db.Column(db.Integer, primary_key=True)
    type = db.Column(db.String(50), nullable=False, index=True)  # 平台类型，如twitter
    account_id = db.Column(db.String(100), nullable=False, index=True)  # 账号ID
    tag = db.Column(db.String(50), default='all', index=True)  # 标签，用于分组
    enable_auto_reply = db.Column(db.Boolean, default=False, index=True)  # 是否启用自动回复
    prompt_template = db.Column(db.Text)  # 分析提示词模板
    auto_reply_template = db.Column(db.Text)  # 自动回复提示词模板
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 添加唯一约束和复合索引
    __table_args__ = (
        db.UniqueConstraint('type', 'account_id', name='uix_type_account'),
        db.Index('idx_type_tag', 'type', 'tag'),
    )

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'type': self.type,
            'account_id': self.account_id,
            'tag': self.tag,
            'enable_auto_reply': self.enable_auto_reply,
            'prompt_template': self.prompt_template,
            'auto_reply_template': self.auto_reply_template,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f'<SocialAccount {self.type}:{self.account_id}>'
