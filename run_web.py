"""
Web应用启动脚本
"""
from web_app import app, init_db

if __name__ == "__main__":
    # 初始化数据库
    init_db()
    # 启动Web应用
    app.run(host='0.0.0.0', port=5000, debug=True)
