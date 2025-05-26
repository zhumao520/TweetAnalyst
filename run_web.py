#!/usr/bin/env python3
"""
Web应用启动脚本
"""
import os
from web_app import app, init_db
from services.config_service import init_config
from utils.logger import setup_third_party_logging

# 设置第三方库的日志级别，减少不必要的日志输出
setup_third_party_logging()

if __name__ == "__main__":
    # 初始化数据库和配置
    with app.app_context():
        # 初始化数据库
        try:
            init_db()
            print("数据库初始化成功")
        except Exception as e:
            print(f"数据库初始化失败: {str(e)}")

        # 使用统一的配置初始化函数，并传递应用上下文
        try:
            # 获取当前应用上下文
            ctx = app.app_context()
            if init_config(app_context=ctx):
                print("配置初始化成功")
            else:
                print("配置初始化失败，将使用环境变量中的配置")
        except Exception as e:
            print(f"配置初始化失败: {str(e)}")

    # 根据环境变量设置调试模式
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'
    print(f"调试模式: {'启用' if debug_mode else '禁用'}")

    # 启动Web应用
    print("启动Web服务器...")
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
