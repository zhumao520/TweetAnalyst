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
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), index=True)

    # 添加复合索引
    __table_args__ = (
        db.Index('idx_account_relevant', 'account_id', 'is_relevant'),
        db.Index('idx_network_account', 'social_network', 'account_id'),
        db.Index('idx_time_relevant', 'post_time', 'is_relevant'),
    )

    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'social_network': self.social_network,
            'account_id': self.account_id,
            'post_id': self.post_id,
            'post_time': self.post_time.isoformat(),
            'content': self.content,
            'analysis': self.analysis,
            'is_relevant': self.is_relevant,
            'created_at': self.created_at.isoformat()
        }
    
    def __repr__(self):
        return f'<AnalysisResult {self.id} {self.social_network}:{self.account_id}>'
