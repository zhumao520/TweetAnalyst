"""
数据库迁移脚本：添加bypass_ai字段到SocialAccount表
"""

import os
import sys
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 导入应用和模型
from web_app import app, db
from models.social_account import SocialAccount
from sqlalchemy import text

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('migration')

def run_migration():
    """
    执行迁移：添加bypass_ai字段到SocialAccount表
    """
    try:
        with app.app_context():
            # 检查字段是否已存在
            inspector = db.inspect(db.engine)
            columns = [column['name'] for column in inspector.get_columns('social_account')]

            if 'bypass_ai' not in columns:
                logger.info("开始添加bypass_ai字段到SocialAccount表")

                # 添加字段 - 使用SQLAlchemy 2.0兼容的方式
                with db.engine.connect() as conn:
                    conn.execute(text('ALTER TABLE social_account ADD COLUMN bypass_ai BOOLEAN DEFAULT FALSE'))
                    # 创建索引
                    conn.execute(text('CREATE INDEX idx_bypass_ai ON social_account (bypass_ai)'))
                    conn.commit()

                logger.info("成功添加bypass_ai字段和索引")
            else:
                logger.info("bypass_ai字段已存在，无需迁移")

            # 同步到配置文件
            from utils.yaml_utils import sync_accounts_to_yaml
            sync_accounts_to_yaml()
            logger.info("已同步账号配置到YAML文件")

            return True
    except Exception as e:
        logger.error(f"迁移失败: {str(e)}")
        return False

if __name__ == "__main__":
    logger.info("开始执行数据库迁移")
    start_time = datetime.now()

    success = run_migration()

    end_time = datetime.now()
    duration = (end_time - start_time).total_seconds()

    if success:
        logger.info(f"迁移成功完成，耗时 {duration:.2f} 秒")
    else:
        logger.error(f"迁移失败，耗时 {duration:.2f} 秒")
        sys.exit(1)
