"""
添加通知服务表的迁移脚本
"""

import sqlite3
import os
import logging

# 创建日志记录器
logger = logging.getLogger('migrations.notification_services')

def run_migration():
    """运行迁移脚本，添加notification_services表"""
    try:
        # 获取数据库路径
        db_path = os.environ.get('DATABASE_PATH', 'instance/tweetanalyst.db')
        
        # 确保目录存在
        os.makedirs(os.path.dirname(db_path), exist_ok=True)
        
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 检查表是否已存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notification_services'")
        if cursor.fetchone():
            logger.info("notification_services表已存在，跳过创建")
            conn.close()
            return True
        
        # 创建表
        cursor.execute('''
        CREATE TABLE notification_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            service_type TEXT NOT NULL,
            config_url TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')
        
        # 提交更改
        conn.commit()
        logger.info("成功创建notification_services表")
        
        # 关闭连接
        conn.close()
        return True
    except Exception as e:
        logger.error(f"创建notification_services表时出错: {str(e)}")
        return False

if __name__ == "__main__":
    # 设置日志
    logging.basicConfig(level=logging.INFO)
    
    # 运行迁移
    success = run_migration()
    if success:
        print("迁移成功完成")
    else:
        print("迁移失败")
