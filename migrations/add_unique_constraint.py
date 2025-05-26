"""
数据库迁移脚本
添加唯一性约束到AnalysisResult表并处理重复数据
"""

import os
import sys
import sqlite3
from datetime import datetime
import json
import logging

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 尝试导入日志模块
try:
    from utils.logger import get_logger
    logger = get_logger('migration')
except ImportError:
    # 如果无法导入自定义日志模块，使用标准日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('migration')

# 加载环境变量
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    logger.warning("无法导入dotenv模块，将使用默认环境变量")

def handle_duplicates(cursor, conn):
    """处理重复记录（使用公共数据库工具）"""
    try:
        # 导入公共数据库工具
        from utils.db_utils import handle_duplicate_records

        # 使用公共函数处理重复记录
        unique_columns = ['social_network', 'account_id', 'post_id']
        priority_columns = ['is_relevant DESC', 'confidence DESC', 'created_at DESC']

        total_removed = handle_duplicate_records(
            cursor, conn, 'analysis_result', unique_columns, priority_columns
        )

        return total_removed
    except ImportError:
        # 如果无法导入公共工具，使用原始实现
        logger.warning("无法导入公共数据库工具，使用原始实现")

        # 查找重复记录
        cursor.execute("""
        SELECT social_network, account_id, post_id, COUNT(*) as count
        FROM analysis_result
        GROUP BY social_network, account_id, post_id
        HAVING COUNT(*) > 1
        """)

        duplicates = cursor.fetchall()
        logger.info(f"找到 {len(duplicates)} 组重复记录")

        if not duplicates:
            logger.info("没有发现重复记录，无需处理")
            return 0

        total_removed = 0

        for dup in duplicates:
            social_network, account_id, post_id, count = dup
            logger.info(f"处理重复记录: {social_network}, {account_id}, {post_id}, 共 {count} 条")

            # 获取所有重复记录
            cursor.execute("""
            SELECT id, is_relevant, confidence, created_at
            FROM analysis_result
            WHERE social_network = ? AND account_id = ? AND post_id = ?
            ORDER BY
                is_relevant DESC,  -- 优先保留相关的记录
                confidence DESC,   -- 其次是置信度高的
                created_at DESC    -- 最后是最新创建的
            """, (social_network, account_id, post_id))

            records = cursor.fetchall()

            # 保留第一条记录，删除其余记录
            keep_id = records[0][0]
            delete_ids = [r[0] for r in records[1:]]

            if delete_ids:
                placeholders = ','.join(['?'] * len(delete_ids))
                cursor.execute(f"DELETE FROM analysis_result WHERE id IN ({placeholders})", delete_ids)
                removed = len(delete_ids)
                total_removed += removed
                logger.info(f"保留记录ID: {keep_id}, 删除 {removed} 条重复记录")

        conn.commit()
        logger.info(f"共删除 {total_removed} 条重复记录")
        return total_removed

def add_unique_constraint(cursor, conn):
    """添加唯一性约束"""
    logger.info("开始添加唯一性约束...")

    try:
        # SQLite不支持直接添加约束，需要创建新表并迁移数据

        # 1. 创建临时表
        cursor.execute("""
        CREATE TABLE analysis_result_temp (
            id INTEGER PRIMARY KEY,
            social_network TEXT NOT NULL,
            account_id TEXT NOT NULL,
            post_id TEXT NOT NULL,
            post_time TIMESTAMP NOT NULL,
            content TEXT NOT NULL,
            analysis TEXT NOT NULL,
            is_relevant BOOLEAN NOT NULL,
            confidence INTEGER,
            reason TEXT,
            has_media BOOLEAN DEFAULT 0,
            media_content TEXT,
            ai_provider TEXT,
            ai_model TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(social_network, account_id, post_id)
        )
        """)

        # 2. 创建索引
        cursor.execute("CREATE INDEX idx_account_relevant_temp ON analysis_result_temp (account_id, is_relevant)")
        cursor.execute("CREATE INDEX idx_network_account_temp ON analysis_result_temp (social_network, account_id)")
        cursor.execute("CREATE INDEX idx_time_relevant_temp ON analysis_result_temp (post_time, is_relevant)")
        cursor.execute("CREATE INDEX idx_confidence_temp ON analysis_result_temp (confidence)")
        cursor.execute("CREATE INDEX idx_social_network_temp ON analysis_result_temp (social_network)")
        cursor.execute("CREATE INDEX idx_account_id_temp ON analysis_result_temp (account_id)")
        cursor.execute("CREATE INDEX idx_post_id_temp ON analysis_result_temp (post_id)")
        cursor.execute("CREATE INDEX idx_post_time_temp ON analysis_result_temp (post_time)")
        cursor.execute("CREATE INDEX idx_is_relevant_temp ON analysis_result_temp (is_relevant)")
        cursor.execute("CREATE INDEX idx_has_media_temp ON analysis_result_temp (has_media)")
        cursor.execute("CREATE INDEX idx_ai_provider_temp ON analysis_result_temp (ai_provider)")
        cursor.execute("CREATE INDEX idx_ai_model_temp ON analysis_result_temp (ai_model)")
        cursor.execute("CREATE INDEX idx_created_at_temp ON analysis_result_temp (created_at)")

        # 3. 迁移数据
        cursor.execute("""
        INSERT INTO analysis_result_temp
        SELECT id, social_network, account_id, post_id, post_time, content, analysis,
               is_relevant, confidence, reason, has_media, media_content, ai_provider,
               ai_model, created_at
        FROM analysis_result
        """)

        # 4. 删除旧表
        cursor.execute("DROP TABLE analysis_result")

        # 5. 重命名新表
        cursor.execute("ALTER TABLE analysis_result_temp RENAME TO analysis_result")

        conn.commit()
        logger.info("成功添加唯一性约束")
        return True
    except Exception as e:
        conn.rollback()
        logger.error(f"添加唯一性约束时出错: {str(e)}")
        return False

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

        # 1. 处理重复记录
        handle_duplicates(cursor, conn)

        # 2. 添加唯一性约束
        success = add_unique_constraint(cursor, conn)

        # 关闭连接
        conn.close()

        if success:
            logger.info("数据库迁移成功")
            return True
        else:
            logger.error("数据库迁移失败")
            return False
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
