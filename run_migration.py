"""
执行数据库迁移脚本
"""

import os
import sys
import logging
from datetime import datetime

# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger('migration_runner')

def main():
    """
    主函数
    """
    logger.info("开始执行数据库迁移")
    start_time = datetime.now()

    try:
        # 导入迁移脚本
        from migrations.add_bypass_ai_field import run_migration
        
        # 执行迁移
        success = run_migration()
        
        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        
        if success:
            logger.info(f"迁移成功完成，耗时 {duration:.2f} 秒")
        else:
            logger.error(f"迁移失败，耗时 {duration:.2f} 秒")
            sys.exit(1)
    except Exception as e:
        logger.error(f"执行迁移时出错: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
