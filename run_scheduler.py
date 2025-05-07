"""
定时任务启动脚本
"""
import time
import schedule
import main
import os
from dotenv import load_dotenv

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
