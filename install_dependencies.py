#!/usr/bin/env python
"""
依赖安装脚本

此脚本用于安装项目所需的依赖，包括基本依赖和可选依赖。
"""
import os
import sys
import subprocess
import argparse
import importlib.util
from typing import List, Dict, Tuple, Optional

def install_package(package):
    """
    安装指定的包

    Args:
        package (str): 包名
    """
    print(f"正在安装 {package}...")
    try:
        subprocess.check_call([sys.executable, "-m", "pip", "install", package])
        print(f"✓ {package} 安装成功")
        return True
    except subprocess.CalledProcessError:
        print(f"✗ {package} 安装失败")
        return False

def install_from_requirements(requirements_file, optional=False):
    """
    从requirements.txt文件安装依赖

    Args:
        requirements_file (str): requirements.txt文件路径
        optional (bool): 是否安装可选依赖
    """
    if not os.path.exists(requirements_file):
        print(f"错误: 找不到文件 {requirements_file}")
        return False

    print(f"正在从 {requirements_file} 安装{'可选' if optional else '基本'}依赖...")

    with open(requirements_file, 'r') as f:
        lines = f.readlines()

    installed_count = 0
    failed_count = 0

    for line in lines:
        line = line.strip()

        # 跳过空行和注释
        if not line or line.startswith('#'):
            continue

        # 处理可选依赖
        if optional and not line.startswith('#'):
            continue

        if optional and line.startswith('# '):
            # 去掉注释符号和说明文字
            package = line[2:].split('#')[0].strip()
        else:
            package = line

        if install_package(package):
            installed_count += 1
        else:
            failed_count += 1

    print(f"\n安装完成: {installed_count} 个包安装成功, {failed_count} 个包安装失败")
    return failed_count == 0

def check_package(module_name: str) -> bool:
    """
    检查包是否已安装

    Args:
        module_name: 模块名称

    Returns:
        bool: 是否已安装
    """
    return importlib.util.find_spec(module_name) is not None

def check_proxy_support() -> bool:
    """
    检查代理支持

    Returns:
        bool: 是否支持SOCKS代理
    """
    proxy = os.getenv('HTTP_PROXY', '')
    if proxy and proxy.startswith('socks'):
        print(f"检测到SOCKS代理: {proxy}")
        if check_package('socksio'):
            print("✓ SOCKS代理支持已安装")
            return True
        else:
            print("! 未安装SOCKS代理支持，尝试安装...")
            return install_package('httpx[socks]')
    return True

def main():
    parser = argparse.ArgumentParser(description='安装项目依赖')
    parser.add_argument('--all', action='store_true', help='安装所有依赖，包括可选依赖')
    parser.add_argument('--optional', action='store_true', help='只安装可选依赖')
    parser.add_argument('--proxy', action='store_true', help='检查并安装代理支持')
    args = parser.parse_args()

    # 检查代理支持
    if args.proxy or os.getenv('HTTP_PROXY', '').startswith('socks'):
        check_proxy_support()

    requirements_file = 'requirements.txt'

    if args.optional:
        # 只安装可选依赖
        install_from_requirements(requirements_file, optional=True)
    elif args.all:
        # 安装所有依赖
        install_from_requirements(requirements_file, optional=False)
        # 取消注释可选依赖并安装
        with open(requirements_file, 'r') as f:
            content = f.read()

        temp_file = 'temp_requirements.txt'
        with open(temp_file, 'w') as f:
            # 去掉可选依赖前的注释符号
            modified_content = content.replace('# psutil', 'psutil')
            modified_content = modified_content.replace('# redis', 'redis')
            modified_content = modified_content.replace('# beautifulsoup4', 'beautifulsoup4')
            modified_content = modified_content.replace('# gunicorn', 'gunicorn')
            modified_content = modified_content.replace('# httpx[socks]', 'httpx[socks]')
            f.write(modified_content)

        install_from_requirements(temp_file, optional=False)

        # 删除临时文件
        if os.path.exists(temp_file):
            os.remove(temp_file)
    else:
        # 安装基本依赖
        install_from_requirements(requirements_file, optional=False)

    print("\n依赖安装完成！")

    # 检查是否使用SOCKS代理
    proxy = os.getenv('HTTP_PROXY', '')
    if proxy and proxy.startswith('socks'):
        if not check_package('socksio'):
            print("\n警告: 您正在使用SOCKS代理，但未安装SOCKS代理支持。")
            print("请运行以下命令安装SOCKS代理支持:")
            print("    pip install httpx[socks]")
            print("或者使用此脚本的--proxy参数:")
            print("    python install_dependencies.py --proxy")

    print("\n您可以通过以下命令运行应用:")
    print("1. 运行Web应用: python run_web.py")
    print("2. 运行定时任务: python run_scheduler.py")
    print("3. 同时运行Web应用和定时任务: python run_all.py")

if __name__ == "__main__":
    main()
