#!/usr/bin/env python3
"""
依赖检查脚本 - 检查并安装必要的依赖
"""
import os
import sys
import importlib.util
import subprocess
import logging
from typing import List, Dict, Tuple, Optional

# 配置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('check_dependencies')

# 必要的依赖列表
REQUIRED_PACKAGES = [
    # 核心依赖
    ("flask", "Flask"),
    ("flask_sqlalchemy", "Flask-SQLAlchemy"),
    ("langchain_openai", "langchain-openai"),
    ("langchain_core", "langchain-core"),
    ("tweety", "tweety-ns"),
    ("apprise", "apprise"),
    ("schedule", "schedule"),
    ("pytz", "pytz"),
    ("pyyaml", "PyYAML"),
    ("python-dotenv", "python-dotenv"),
    
    # 可选依赖
    ("socksio", "httpx[socks]", False),  # 用于SOCKS代理支持
]

def check_package(module_name: str) -> bool:
    """
    检查包是否已安装
    
    Args:
        module_name: 模块名称
        
    Returns:
        bool: 是否已安装
    """
    return importlib.util.find_spec(module_name) is not None

def install_package(package_name: str) -> bool:
    """
    安装包
    
    Args:
        package_name: 包名称
        
    Returns:
        bool: 是否安装成功
    """
    try:
        logger.info(f"安装 {package_name}...")
        subprocess.check_call([sys.executable, "-m", "pip", "install", package_name, "--quiet"])
        logger.info(f"{package_name} 安装成功")
        return True
    except subprocess.CalledProcessError as e:
        logger.error(f"安装 {package_name} 失败: {str(e)}")
        return False

def check_and_install_dependencies() -> Tuple[int, int]:
    """
    检查并安装所有依赖
    
    Returns:
        Tuple[int, int]: (已安装的依赖数量, 安装失败的依赖数量)
    """
    installed = 0
    failed = 0
    
    for package_info in REQUIRED_PACKAGES:
        if len(package_info) == 2:
            module_name, package_name = package_info
            required = True
        else:
            module_name, package_name, required = package_info
        
        if check_package(module_name):
            logger.info(f"{module_name} 已安装")
            installed += 1
        else:
            if install_package(package_name):
                installed += 1
            else:
                if required:
                    failed += 1
                    logger.error(f"必要依赖 {package_name} 安装失败")
                else:
                    logger.warning(f"可选依赖 {package_name} 安装失败")
    
    return installed, failed

def check_proxy_support() -> bool:
    """
    检查代理支持
    
    Returns:
        bool: 是否支持SOCKS代理
    """
    proxy = os.getenv('HTTP_PROXY', '')
    if proxy and proxy.startswith('socks'):
        logger.info(f"检测到SOCKS代理: {proxy}")
        if check_package('socksio'):
            logger.info("SOCKS代理支持已安装")
            return True
        else:
            logger.warning("未安装SOCKS代理支持，尝试安装...")
            return install_package('httpx[socks]')
    return True

def main():
    """主函数"""
    logger.info("开始检查并安装依赖...")
    
    # 检查Python版本
    python_version = sys.version.split()[0]
    logger.info(f"Python版本: {python_version}")
    
    # 检查pip版本
    try:
        pip_version = subprocess.check_output([sys.executable, "-m", "pip", "--version"]).decode().split()[1]
        logger.info(f"pip版本: {pip_version}")
    except:
        logger.warning("无法获取pip版本")
    
    # 检查并安装依赖
    installed, failed = check_and_install_dependencies()
    
    # 检查代理支持
    proxy_support = check_proxy_support()
    
    # 输出结果
    logger.info(f"依赖检查完成: {installed} 个已安装, {failed} 个安装失败")
    if failed > 0:
        logger.warning("有依赖安装失败，可能会影响系统功能")
    
    if not proxy_support:
        logger.warning("SOCKS代理支持安装失败，如果您使用SOCKS代理，可能会影响网络连接")
    
    return failed == 0 and proxy_support

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
