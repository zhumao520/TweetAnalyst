"""
Web应用启动脚本
"""
import os
from web_app import app, init_db, load_configs_to_env

if __name__ == "__main__":
    # 初始化数据库
    with app.app_context():
        init_db()
        # 加载数据库中的配置到环境变量
        load_configs_to_env()

    # 根据环境变量设置调试模式
    debug_mode = os.getenv('FLASK_DEBUG', 'false').lower() == 'true'

    # 启动Web应用
    app.run(host='0.0.0.0', port=5000, debug=debug_mode)
