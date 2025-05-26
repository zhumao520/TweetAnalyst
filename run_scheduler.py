#!/usr/bin/env python3
"""
定时任务启动脚本
"""
import time
import schedule
import os
import subprocess
import threading
from dotenv import load_dotenv
import sys

# 添加当前目录到路径，确保能导入web_app模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入日志设置函数
from utils.logger import setup_third_party_logging

# 设置第三方库的日志级别，减少不必要的日志输出
setup_third_party_logging()

# 导入配置和数据库初始化函数
try:
    from web_app import init_db
    from services.config_service import init_config

    # 初始化数据库
    init_db()

    # 使用统一的配置初始化函数
    # 创建应用上下文
    from web_app import app
    with app.app_context() as ctx:
        if init_config(app_context=ctx):
            print("配置初始化成功")
        else:
            print("配置初始化失败，将使用环境变量中的配置")
except ImportError:
    print("警告: 无法导入必要模块，将使用环境变量中的配置")

load_dotenv()

# 全局变量跟踪正在运行的任务
running_tasks = {}
task_lock = threading.Lock()

def job():
    """
    执行主程序（使用独立进程，避免阻塞调度器）
    """
    task_id = f"social_media_task_{int(time.time())}"

    with task_lock:
        # 检查是否有任务正在运行
        if running_tasks:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 社交媒体监控任务已在运行中，跳过本次执行")
            # 清理已完成的任务
            completed_tasks = [tid for tid, process in running_tasks.items() if process.poll() is not None]
            for tid in completed_tasks:
                process = running_tasks.pop(tid)
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 任务 {tid} 已完成，返回码: {process.returncode}")
            return

    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始执行社交媒体监控任务 {task_id}...")

    try:
        # 使用独立进程执行主程序
        python_executable = sys.executable
        script_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "main.py")

        # 启动独立进程
        process = subprocess.Popen(
            [python_executable, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=os.path.dirname(os.path.abspath(__file__))
        )

        with task_lock:
            running_tasks[task_id] = process

        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 社交媒体监控任务 {task_id} 已启动，PID: {process.pid}")

        # 启动线程监控任务完成
        monitor_thread = threading.Thread(target=monitor_task, args=(task_id, process))
        monitor_thread.daemon = True
        monitor_thread.start()

    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 启动社交媒体监控任务时出错: {e}")
        with task_lock:
            if task_id in running_tasks:
                del running_tasks[task_id]

def monitor_task(task_id, process):
    """
    监控任务执行状态
    """
    try:
        # 等待进程完成
        stdout, stderr = process.communicate()

        with task_lock:
            if task_id in running_tasks:
                del running_tasks[task_id]

        if process.returncode == 0:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 社交媒体监控任务 {task_id} 执行完成")
            if stdout:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 任务输出: {stdout.strip()}")
        else:
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 社交媒体监控任务 {task_id} 执行失败，返回码: {process.returncode}")
            if stderr:
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 错误信息: {stderr.strip()}")
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 监控任务 {task_id} 时出错: {e}")
        with task_lock:
            if task_id in running_tasks:
                del running_tasks[task_id]

if __name__ == "__main__":
    # 获取执行间隔（分钟）
    interval_minutes = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "30"))

    # 检查是否启用自动抓取
    auto_fetch_enabled = os.getenv('AUTO_FETCH_ENABLED', 'false').lower() == 'true'

    if auto_fetch_enabled:
        # 设置定时任务
        schedule.every(interval_minutes).minutes.do(job)
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 已启用自动抓取，每 {interval_minutes} 分钟执行一次")
    else:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 自动抓取已禁用，请通过Web界面手动启动抓取任务")

    # 如果启用了自动抓取，立即执行一次
    if auto_fetch_enabled:
        print(f"定时任务已启动，每 {interval_minutes} 分钟执行一次")
        job()

    # 循环执行定时任务
    while True:
        schedule.run_pending()
        time.sleep(1)
