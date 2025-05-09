"""
用户模型
处理用户认证和权限
"""

from werkzeug.security import generate_password_hash, check_password_hash
from . import db

class User(db.Model):
    """用户模型"""
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128), nullable=False)
    is_admin = db.Column(db.Boolean, default=False)
    
    def __init__(self, username, is_admin=False):
        self.username = username
        self.is_admin = is_admin

    def set_password(self, password):
        """设置密码"""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        """验证密码"""
        return check_password_hash(self.password_hash, password)
    
    def to_dict(self):
        """转换为字典"""
        return {
            'id': self.id,
            'username': self.username,
            'is_admin': self.is_admin
        }
    
    def __repr__(self):
        return f'<User {self.username}>'
