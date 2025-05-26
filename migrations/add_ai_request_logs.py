"""
数据库迁移脚本：添加AI请求日志表
"""

import logging
import os
import sys
from datetime import datetime, timezone

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 导入Flask应用和数据库
from web_app import app, db
from models.ai_provider import AIProvider
from models.ai_request_log import AIRequestLog

# 创建日志记录器
logger = logging.getLogger('migrations.add_ai_request_logs')

def run_migration():
    """运行迁移脚本"""
    logger.info("开始运行AI请求日志表迁移脚本")

    with app.app_context():
        try:
            # 检查数据库连接
            from sqlalchemy import text
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1")).fetchall()
            logger.info("数据库连接正常")

            # 检查AI请求日志表是否存在
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()

            if 'ai_request_logs' not in existing_tables:
                logger.info("AI请求日志表不存在，创建表")
                # 创建AI请求日志表
                db.create_all()
                logger.info("AI请求日志表创建成功")
            else:
                logger.info("AI请求日志表已存在")

                # 检查外键是否正确
                columns = inspector.get_columns('ai_request_logs')
                foreign_keys = inspector.get_foreign_keys('ai_request_logs')
                
                # 检查provider_id字段是否存在
                provider_id_exists = any(col['name'] == 'provider_id' for col in columns)
                
                # 检查外键关系是否正确
                foreign_key_correct = any(
                    fk['constrained_columns'] == ['provider_id'] and 
                    fk['referred_table'] == 'ai_provider' and 
                    fk['referred_columns'] == ['id']
                    for fk in foreign_keys
                )
                
                if provider_id_exists and not foreign_key_correct:
                    logger.warning("AI请求日志表的外键关系不正确，尝试修复")
                    
                    # 删除旧表并重新创建
                    with db.engine.connect() as conn:
                        # 备份数据
                        conn.execute(text("CREATE TABLE ai_request_logs_backup AS SELECT * FROM ai_request_logs"))
                        
                        # 删除旧表
                        conn.execute(text("DROP TABLE ai_request_logs"))
                        
                        # 重新创建表
                        db.create_all()
                        
                        # 恢复数据（除了外键关系）
                        conn.execute(text("""
                            INSERT INTO ai_request_logs 
                            (id, request_type, request_content, response_content, is_success, 
                            error_message, response_time, token_count, is_cached, cache_key, 
                            meta_data, created_at, updated_at)
                            SELECT 
                            id, request_type, request_content, response_content, is_success, 
                            error_message, response_time, token_count, is_cached, cache_key, 
                            meta_data, created_at, updated_at
                            FROM ai_request_logs_backup
                        """))
                        
                        # 删除备份表
                        conn.execute(text("DROP TABLE ai_request_logs_backup"))
                        
                        conn.commit()
                    
                    logger.info("AI请求日志表外键关系修复成功")

            logger.info("AI请求日志表迁移脚本运行成功")
            return True
        except Exception as e:
            logger.error(f"迁移脚本运行失败: {str(e)}")
            return False

if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 运行迁移脚本
    success = run_migration()

    if success:
        print("迁移脚本运行成功")
        sys.exit(0)
    else:
        print("迁移脚本运行失败")
        sys.exit(1)
