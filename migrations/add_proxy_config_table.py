"""
添加代理配置表迁移脚本

此脚本用于创建代理配置表，支持多代理管理功能。
"""

import os
import sys
import sqlite3
import logging
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 使用统一的日志管理模块
try:
    from utils.logger import get_logger
    logger = get_logger('db_migrations.proxy_config')
except ImportError:
    # 如果无法导入自定义日志模块，使用标准日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('db_migrations.proxy_config')
    logger.warning("无法导入utils.logger模块，使用标准日志配置")

def run_migration():
    """执行迁移"""
    # 获取数据库路径
    db_path = os.environ.get('DATABASE_PATH', 'instance/tweetAnalyst.db')

    # 确保目录存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    logger.info(f"开始执行代理配置表迁移，数据库路径: {db_path}")
    start_time = datetime.now()

    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()

        # 检查表是否已存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='proxy_config'")
        if cursor.fetchone():
            logger.info("proxy_config表已存在，跳过创建")
            conn.close()
            return True

        # 创建代理配置表
        logger.info("创建proxy_config表")
        cursor.execute('''
        CREATE TABLE proxy_config (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            host TEXT NOT NULL,
            port INTEGER NOT NULL,
            protocol TEXT NOT NULL DEFAULT 'http',
            username TEXT,
            password TEXT,
            priority INTEGER DEFAULT 0,
            is_active BOOLEAN DEFAULT 1,
            last_check_time TIMESTAMP,
            last_check_result BOOLEAN,
            response_time REAL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        # 创建索引
        cursor.execute("CREATE INDEX idx_proxy_priority ON proxy_config (priority)")
        cursor.execute("CREATE INDEX idx_proxy_is_active ON proxy_config (is_active)")
        cursor.execute("CREATE INDEX idx_proxy_last_check_result ON proxy_config (last_check_result)")

        # 从环境变量和配置中导入现有代理
        try:
            # 导入配置服务
            from services.config_service import get_config

            # 获取HTTP_PROXY环境变量
            http_proxy = get_config('HTTP_PROXY', '')
            if http_proxy:
                logger.info(f"从HTTP_PROXY配置导入代理: {http_proxy}")

                # 解析代理URL
                import re
                from urllib.parse import urlparse

                try:
                    # 解析代理URL
                    parsed = urlparse(http_proxy)
                    protocol = parsed.scheme
                    host = parsed.hostname
                    port = parsed.port
                    username = parsed.username
                    password = parsed.password

                    if host and port:
                        # 插入代理配置
                        cursor.execute('''
                        INSERT INTO proxy_config (name, host, port, protocol, username, password, priority, is_active)
                        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                        ''', (
                            f"导入的{protocol.upper()}代理",
                            host,
                            port,
                            protocol,
                            username,
                            password,
                            1,  # 优先级1
                            1   # 激活状态
                        ))
                        logger.info(f"成功导入代理: {protocol}://{host}:{port}")
                except Exception as e:
                    logger.error(f"解析代理URL时出错: {str(e)}")

            # 获取代理主机和端口配置
            proxy_host = get_config("PROXY_HOST", '')
            proxy_port_http = get_config("PROXY_PORT_HTTP", '')
            proxy_port_socks = get_config("PROXY_PORT_SOCKS", '')

            if proxy_host:
                # 添加HTTP代理
                if proxy_port_http:
                    try:
                        port = int(proxy_port_http)
                        cursor.execute('''
                        INSERT INTO proxy_config (name, host, port, protocol, priority, is_active)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            "配置的HTTP代理",
                            proxy_host,
                            port,
                            "http",
                            2,  # 优先级2
                            1   # 激活状态
                        ))
                        logger.info(f"成功导入HTTP代理: {proxy_host}:{port}")
                    except ValueError:
                        logger.warning(f"无效的HTTP代理端口: {proxy_port_http}")

                # 添加SOCKS5代理
                if proxy_port_socks:
                    try:
                        port = int(proxy_port_socks)
                        cursor.execute('''
                        INSERT INTO proxy_config (name, host, port, protocol, priority, is_active)
                        VALUES (?, ?, ?, ?, ?, ?)
                        ''', (
                            "配置的SOCKS5代理",
                            proxy_host,
                            port,
                            "socks5",
                            3,  # 优先级3
                            1   # 激活状态
                        ))
                        logger.info(f"成功导入SOCKS5代理: {proxy_host}:{port}")
                    except ValueError:
                        logger.warning(f"无效的SOCKS5代理端口: {proxy_port_socks}")
        except ImportError:
            logger.warning("无法导入配置服务，跳过导入现有代理")
        except Exception as e:
            logger.error(f"导入现有代理时出错: {str(e)}")

        # 不添加默认代理配置，完全由用户自定义
        logger.info("不添加默认代理配置，将由用户自定义添加代理")

        # 提交事务
        conn.commit()
        logger.info("代理配置表创建成功")

        # 关闭连接
        conn.close()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()
        logger.info(f"代理配置表迁移成功完成，耗时 {duration:.2f} 秒")

        return True
    except Exception as e:
        logger.error(f"执行代理配置表迁移时出错: {str(e)}")
        return False

if __name__ == "__main__":
    success = run_migration()
    sys.exit(0 if success else 1)
