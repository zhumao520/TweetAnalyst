#!/usr/bin/env python3
"""
执行数据库迁移脚本

这个脚本是数据库迁移的入口点，它调用统一的数据库迁移管理脚本执行所有迁移操作。
"""

import sys
from datetime import datetime

# 使用统一的日志管理模块
from utils.logger import get_logger

# 创建日志记录器
logger = get_logger('migration_runner')

def main():
    """
    主函数
    """
    logger.info("开始执行数据库迁移")
    start_time = datetime.now()

    try:
        # 导入统一迁移脚本
        from migrations.db_migrations import run_all_migrations

        # 执行所有迁移
        success = run_all_migrations()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        if success:
            logger.info(f"所有迁移成功完成，耗时 {duration:.2f} 秒")
        else:
            logger.error(f"迁移过程中出现错误，耗时 {duration:.2f} 秒")
            sys.exit(1)
    except Exception as e:
        logger.error(f"执行迁移时出错: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()
