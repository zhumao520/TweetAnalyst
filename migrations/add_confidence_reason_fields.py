"""
数据库迁移脚本
添加confidence和reason字段到AnalysisResult表
"""

import os
import sys
import sqlite3
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.logger import get_logger
from dotenv import load_dotenv

# 创建日志记录器
logger = get_logger('migration')

# 加载环境变量
load_dotenv()

def migrate():
    """执行数据库迁移"""
    # 获取数据库路径
    db_path = os.getenv('DATABASE_PATH', 'instance/tweetAnalyst.db')
    # 确保路径是绝对路径
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.getcwd(), db_path)

    logger.info(f"开始迁移数据库: {db_path}")

    # 检查数据库文件是否存在
    if not os.path.exists(db_path):
        logger.error(f"数据库文件不存在: {db_path}")
        return False

    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_result'")
        if not cursor.fetchone():
            logger.error("analysis_result表不存在")
            conn.close()
            return False

        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(analysis_result)")
        columns = [column[1] for column in cursor.fetchall()]

        # 添加confidence字段
        if 'confidence' not in columns:
            logger.info("添加confidence字段")
            cursor.execute("ALTER TABLE analysis_result ADD COLUMN confidence INTEGER")
        else:
            logger.info("confidence字段已存在")

        # 添加reason字段
        if 'reason' not in columns:
            logger.info("添加reason字段")
            cursor.execute("ALTER TABLE analysis_result ADD COLUMN reason TEXT")
        else:
            logger.info("reason字段已存在")

        # 提交更改
        conn.commit()

        # 更新现有记录的confidence和reason字段
        logger.info("更新现有记录的confidence和reason字段")

        # 为相关内容设置100%置信度，为不相关内容设置0%置信度
        cursor.execute("UPDATE analysis_result SET confidence = 100 WHERE is_relevant = 1 AND confidence IS NULL")
        cursor.execute("UPDATE analysis_result SET confidence = 0 WHERE is_relevant = 0 AND confidence IS NULL")

        # 设置默认理由
        cursor.execute("UPDATE analysis_result SET reason = '符合预设主题' WHERE is_relevant = 1 AND reason IS NULL")
        cursor.execute("UPDATE analysis_result SET reason = '不符合预设主题' WHERE is_relevant = 0 AND reason IS NULL")

        # 提交更改
        conn.commit()

        # 创建索引
        logger.info("创建confidence字段索引")
        try:
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_confidence ON analysis_result (confidence)")
            conn.commit()
        except sqlite3.OperationalError as e:
            logger.warning(f"创建索引时出错: {str(e)}")

        # 关闭连接
        conn.close()

        logger.info("数据库迁移成功")
        return True
    except Exception as e:
        logger.error(f"数据库迁移失败: {str(e)}")
        return False

if __name__ == "__main__":
    # 执行迁移
    success = migrate()
    if success:
        print("数据库迁移成功")
        sys.exit(0)
    else:
        print("数据库迁移失败")
        sys.exit(1)
