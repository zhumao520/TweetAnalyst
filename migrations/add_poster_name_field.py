"""
添加 poster_name 字段到 analysis_result 表
用于存储推文发布者的真实用户名
"""

import sqlite3
import os
import sys

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

try:
    from utils.logger import get_logger
    logger = get_logger('migration_poster_name')
except ImportError:
    import logging
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger('migration_poster_name')

def add_poster_name_field():
    """添加 poster_name 字段到 analysis_result 表"""
    try:
        # 获取数据库路径
        db_path = os.getenv('DATABASE_PATH', '/data/tweetAnalyst.db')

        # 确保数据库文件存在
        if not os.path.exists(db_path):
            logger.warning(f"数据库文件不存在: {db_path}")
            return False

        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(analysis_result)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'poster_name' in columns:
            logger.info("poster_name 字段已存在，跳过迁移")
            conn.close()
            return True

        # 添加 poster_name 字段
        logger.info("开始添加 poster_name 字段...")
        cursor.execute("""
            ALTER TABLE analysis_result
            ADD COLUMN poster_name VARCHAR(200)
        """)

        # 提交更改
        conn.commit()
        logger.info("成功添加 poster_name 字段")

        # 验证字段是否添加成功
        cursor.execute("PRAGMA table_info(analysis_result)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'poster_name' in columns:
            logger.info("poster_name 字段添加验证成功")

            # 尝试从现有数据中提取用户名信息
            # 对于时间线推文，account_id 通常就是用户名
            logger.info("开始更新现有数据的 poster_name 字段...")

            # 查询所有没有 poster_name 的记录
            cursor.execute("""
                SELECT id, account_id, social_network
                FROM analysis_result
                WHERE poster_name IS NULL
            """)

            records = cursor.fetchall()
            updated_count = 0

            for record_id, account_id, social_network in records:
                # 对于时间线推文，account_id 通常就是真实用户名
                # 这里我们将 account_id 作为 poster_name 的初始值
                cursor.execute("""
                    UPDATE analysis_result
                    SET poster_name = ?
                    WHERE id = ?
                """, (account_id, record_id))
                updated_count += 1

            if updated_count > 0:
                conn.commit()
                logger.info(f"成功更新了 {updated_count} 条记录的 poster_name 字段")
            else:
                logger.info("没有需要更新的记录")

            conn.close()
            return True
        else:
            logger.error("poster_name 字段添加失败")
            conn.close()
            return False

    except Exception as e:
        logger.error(f"添加 poster_name 字段时出错: {str(e)}")
        if 'conn' in locals():
            conn.close()
        return False

def run_migration():
    """运行迁移"""
    logger.info("开始运行 poster_name 字段迁移...")

    if add_poster_name_field():
        logger.info("poster_name 字段迁移完成")
        return True
    else:
        logger.error("poster_name 字段迁移失败")
        return False

if __name__ == "__main__":
    run_migration()
