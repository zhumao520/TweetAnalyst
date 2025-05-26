"""
分析结果模型
存储社交媒体内容分析结果
"""

from datetime import datetime, timezone
from . import db

class AnalysisResult(db.Model):
    """分析结果模型"""
    id = db.Column(db.Integer, primary_key=True)
    social_network = db.Column(db.String(50), nullable=False, index=True)
    account_id = db.Column(db.String(100), nullable=False, index=True)
    post_id = db.Column(db.String(100), nullable=False, index=True)
    post_time = db.Column(db.DateTime, nullable=False, index=True)
    content = db.Column(db.Text, nullable=False)
    analysis = db.Column(db.Text, nullable=False)
    is_relevant = db.Column(db.Boolean, nullable=False, index=True)
    confidence = db.Column(db.Integer, nullable=True)  # AI决策的置信度(0-100)
    reason = db.Column(db.Text, nullable=True)  # AI决策的理由
    poster_avatar_url = db.Column(db.String(500), nullable=True)  # 发布者头像URL
    poster_name = db.Column(db.String(200), nullable=True)  # 发布者真实用户名

    # 媒体内容字段
    has_media = db.Column(db.Boolean, default=False, index=True)  # 是否包含媒体内容
    media_content = db.Column(db.Text, nullable=True)  # 媒体内容JSON字符串

    # AI提供商信息
    ai_provider = db.Column(db.String(100), nullable=True, index=True)  # AI提供商ID或名称
    ai_model = db.Column(db.String(100), nullable=True, index=True)  # AI模型名称

    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # 添加复合索引和唯一约束
    __table_args__ = (
        db.UniqueConstraint('social_network', 'account_id', 'post_id', name='uix_post'),  # 添加唯一性约束
        db.Index('idx_account_relevant', 'account_id', 'is_relevant'),
        db.Index('idx_network_account', 'social_network', 'account_id'),
        db.Index('idx_time_relevant', 'post_time', 'is_relevant'),
        db.Index('idx_confidence', 'confidence'),  # 添加置信度索引
    )

    def to_dict(self):
        """转换为字典"""
        result = {
            'id': self.id,
            'social_network': self.social_network,
            'account_id': self.account_id,
            'post_id': self.post_id,
            'post_time': self.post_time.isoformat(),
            'content': self.content,
            'analysis': self.analysis,
            'is_relevant': self.is_relevant,
            'confidence': self.confidence,
            'reason': self.reason,
            'poster_avatar_url': self.poster_avatar_url,
            'poster_name': self.poster_name,
            'created_at': self.created_at.isoformat()
        }

        # 添加媒体内容信息（如果有）
        if hasattr(self, 'has_media') and self.has_media:
            result['has_media'] = True

            # 解析媒体内容JSON
            if hasattr(self, 'media_content') and self.media_content:
                try:
                    import json
                    media_content = json.loads(self.media_content)
                    result['media_content'] = media_content
                except Exception:
                    # 如果解析失败，返回原始字符串
                    result['media_content'] = self.media_content

        # 添加AI提供商信息（如果有）
        if hasattr(self, 'ai_provider') and self.ai_provider:
            result['ai_provider'] = self.ai_provider
        if hasattr(self, 'ai_model') and self.ai_model:
            result['ai_model'] = self.ai_model

        return result

    def __repr__(self):
        media_info = " with_media" if hasattr(self, 'has_media') and self.has_media else ""
        ai_info = f" {self.ai_provider}" if hasattr(self, 'ai_provider') and self.ai_provider else ""
        return f'<AnalysisResult {self.id} {self.social_network}:{self.account_id}{media_info}{ai_info}>'
