"""
同时启动Web应用和定时任务
"""
import subprocess
import sys
import os
import time

def run_command(command, name):
    """
    运行命令
    """
    print(f"启动 {name}...")
    process = subprocess.Popen(command, shell=True)
    return process

if __name__ == "__main__":
    # 启动Web应用
    web_process = run_command("python run_web.py", "Web应用")
    
    # 等待Web应用启动
    time.sleep(3)
    
    # 启动定时任务
    scheduler_process = run_command("python run_scheduler.py", "定时任务")
    
    try:
        # 等待进程结束
        web_process.wait()
        scheduler_process.wait()
    except KeyboardInterrupt:
        # 捕获Ctrl+C
        print("正在关闭所有进程...")
        web_process.terminate()
        scheduler_process.terminate()
        sys.exit(0)
