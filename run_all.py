"""
同时启动Web应用和定时任务
"""
import subprocess
import sys
import os
import time
from dotenv import load_dotenv
import logging

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('run_all')

# 加载环境变量
load_dotenv()

def run_command(command, name):
    """
    运行命令
    """
    logger.info(f"启动 {name}...")
    process = subprocess.Popen(command, shell=True)
    return process

def load_configs():
    """
    加载配置并设置环境变量
    """
    # 尝试从web_app模块加载配置
    try:
        logger.info("尝试从web_app模块加载配置...")
        sys.path.append(os.path.dirname(os.path.abspath(__file__)))
        from web_app import load_configs_to_env, init_db

        # 初始化数据库
        init_db()

        # 加载配置到环境变量
        load_configs_to_env()
        logger.info("成功从web_app模块加载配置")
        return True
    except ImportError as e:
        logger.warning(f"无法导入web_app模块: {str(e)}")
        return False
    except Exception as e:
        logger.error(f"加载配置时出错: {str(e)}")
        return False

def setup_proxy():
    """
    设置代理环境变量
    """
    proxy = os.getenv('HTTP_PROXY', '')
    if proxy:
        logger.info(f"设置代理环境变量: {proxy}")
        os.environ['HTTP_PROXY'] = proxy
        os.environ['HTTPS_PROXY'] = proxy

        # 如果是SOCKS代理，尝试安装支持
        if proxy.startswith('socks'):
            try:
                logger.info("检测到SOCKS代理，尝试安装支持...")
                import pip
                pip.main(['install', 'httpx[socks]', '--quiet'])
                logger.info("成功安装SOCKS代理支持")
            except Exception as e:
                logger.warning(f"安装SOCKS代理支持失败: {str(e)}")

if __name__ == "__main__":
    # 加载配置
    load_configs()

    # 设置代理
    setup_proxy()

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
        logger.info("正在关闭所有进程...")
        web_process.terminate()
        scheduler_process.terminate()
        sys.exit(0)
