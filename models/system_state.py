"""
系统状态模型
存储系统运行状态信息，用于替代Redis存储状态信息
"""

import logging
from datetime import datetime, timezone
from . import db

# 创建日志记录器
logger = logging.getLogger('models.system_state')

class SystemState(db.Model):
    """系统状态模型，用于替代Redis存储状态信息"""
    id = db.Column(db.Integer, primary_key=True)
    key = db.Column(db.String(255), unique=True, nullable=False, index=True)  # 状态键
    value = db.Column(db.Text, nullable=True)  # 状态值
    expires_at = db.Column(db.DateTime, nullable=True, index=True)  # 过期时间
    created_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = db.Column(db.DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    @classmethod
    def cleanup_expired(cls):
        """清理过期的状态数据"""
        try:
            now = datetime.now(timezone.utc)
            expired = cls.query.filter(cls.expires_at < now).all()
            for item in expired:
                db.session.delete(item)
            db.session.commit()
            return len(expired)
        except Exception as e:
            logger.error(f"清理过期状态数据时出错: {str(e)}")
            db.session.rollback()
            return 0
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'key': self.key,
            'value': self.value,
            'expires_at': self.expires_at.isoformat() if self.expires_at else None,
            'created_at': self.created_at.isoformat(),
            'updated_at': self.updated_at.isoformat()
        }
    
    def __repr__(self):
        return f'<SystemState {self.key}>'
