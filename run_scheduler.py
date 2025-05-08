"""
定时任务启动脚本
"""
import time
import schedule
import main
import os
from dotenv import load_dotenv
import sys

# 添加当前目录到路径，确保能导入web_app模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入配置加载函数
try:
    from web_app import load_configs_to_env, init_db
    # 初始化数据库并加载配置
    init_db()
    load_configs_to_env()
except ImportError:
    print("警告: 无法导入web_app模块，将使用环境变量中的配置")

load_dotenv()

def job():
    """
    执行主程序
    """
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始执行社交媒体监控任务...")
    try:
        main.main()
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 社交媒体监控任务执行完成")
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 社交媒体监控任务执行出错: {e}")

if __name__ == "__main__":
    # 获取执行间隔（分钟）
    interval_minutes = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "30"))

    # 设置定时任务
    schedule.every(interval_minutes).minutes.do(job)

    print(f"定时任务已启动，每 {interval_minutes} 分钟执行一次")

    # 立即执行一次
    job()

    # 循环执行定时任务
    while True:
        schedule.run_pending()
        time.sleep(1)
