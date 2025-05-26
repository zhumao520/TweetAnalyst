"""
添加推送通知表

Revision ID: add_push_notifications_table
Revises:
Create Date: 2023-12-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.sqlite import JSON


# revision identifiers, used by Alembic.
revision = 'add_push_notifications_table'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    """升级数据库"""
    # 创建推送通知表
    op.create_table(
        'push_notifications',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(length=255), nullable=True),
        sa.Column('message', sa.Text(), nullable=False),
        sa.Column('tag', sa.String(length=50), nullable=True),
        sa.Column('targets', sa.Text(), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=False, server_default='pending'),
        sa.Column('attempt_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('max_attempts', sa.Integer(), nullable=False, server_default='3'),
        sa.Column('error_message', sa.Text(), nullable=True),
        sa.Column('error_details', JSON(), nullable=True),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('updated_at', sa.DateTime(), nullable=False, server_default=sa.text('CURRENT_TIMESTAMP')),
        sa.Column('scheduled_for', sa.DateTime(), nullable=True),
        sa.Column('sent_at', sa.DateTime(), nullable=True),
        sa.Column('account_id', sa.String(length=100), nullable=True),
        sa.Column('post_id', sa.String(length=100), nullable=True),
        sa.Column('meta_data', JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id')
    )

    # 创建索引
    op.create_index(op.f('ix_push_notifications_status'), 'push_notifications', ['status'], unique=False)
    op.create_index(op.f('ix_push_notifications_created_at'), 'push_notifications', ['created_at'], unique=False)
    op.create_index(op.f('ix_push_notifications_account_id'), 'push_notifications', ['account_id'], unique=False)


def downgrade():
    """降级数据库"""
    # 删除索引
    op.drop_index(op.f('ix_push_notifications_account_id'), table_name='push_notifications')
    op.drop_index(op.f('ix_push_notifications_created_at'), table_name='push_notifications')
    op.drop_index(op.f('ix_push_notifications_status'), table_name='push_notifications')

    # 删除表
    op.drop_table('push_notifications')
