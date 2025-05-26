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
    bypass_ai = db.Column(db.Boolean, default=False, index=True)  # 是否绕过AI判断直接推送
    prompt_template = db.Column(db.Text)  # 分析提示词模板
    auto_reply_template = db.Column(db.Text)  # 自动回复提示词模板
    avatar_url = db.Column(db.String(500))  # 用户头像URL
    display_name = db.Column(db.String(100))  # 显示名称（如"老蛮频道"）
    bio = db.Column(db.Text)  # 用户简介
    verified = db.Column(db.Boolean, default=False)  # 是否已验证
    followers_count = db.Column(db.Integer, default=0)  # 粉丝数
    following_count = db.Column(db.Integer, default=0)  # 关注数
    posts_count = db.Column(db.Integer, default=0)  # 帖子数
    join_date = db.Column(db.DateTime)  # 加入日期
    location = db.Column(db.String(100))  # 位置
    website = db.Column(db.String(200))  # 网站链接
    profession = db.Column(db.String(100))  # 职业
    ai_provider_id = db.Column(db.Integer, db.ForeignKey('ai_provider.id'), nullable=True)  # 默认AI提供商ID
    text_provider_id = db.Column(db.Integer, db.ForeignKey('ai_provider.id'), nullable=True)  # 文本内容AI提供商ID
    image_provider_id = db.Column(db.Integer, db.ForeignKey('ai_provider.id'), nullable=True)  # 图片内容AI提供商ID
    video_provider_id = db.Column(db.Integer, db.ForeignKey('ai_provider.id'), nullable=True)  # 视频内容AI提供商ID
    gif_provider_id = db.Column(db.Integer, db.ForeignKey('ai_provider.id'), nullable=True)  # GIF内容AI提供商ID
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    # 添加唯一约束和复合索引
    __table_args__ = (
        db.UniqueConstraint('type', 'account_id', name='uix_type_account'),
        db.Index('idx_type_tag', 'type', 'tag'),
    )

    def to_dict(self):
        """转换为字典"""
        result = {
            'id': self.id,
            'type': self.type,
            'account_id': self.account_id,
            'tag': self.tag,
            'enable_auto_reply': self.enable_auto_reply,
            'bypass_ai': self.bypass_ai,
            'prompt_template': self.prompt_template,
            'auto_reply_template': self.auto_reply_template,
            'avatar_url': self.avatar_url,
            'display_name': self.display_name,
            'bio': self.bio,
            'verified': self.verified,
            'followers_count': self.followers_count,
            'following_count': self.following_count,
            'posts_count': self.posts_count,
            'location': self.location,
            'website': self.website,
            'profession': self.profession,
            'ai_provider_id': self.ai_provider_id,
            'text_provider_id': self.text_provider_id,
            'image_provider_id': self.image_provider_id,
            'video_provider_id': self.video_provider_id,
            'gif_provider_id': self.gif_provider_id,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }

        # 处理可能为None的join_date
        if self.join_date:
            result['join_date'] = self.join_date.isoformat()
        else:
            result['join_date'] = None

        return result

    def __repr__(self):
        return f'<SocialAccount {self.type}:{self.account_id}>'
