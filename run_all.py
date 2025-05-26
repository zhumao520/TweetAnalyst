"""
同时启动Web应用和定时任务
"""
import subprocess
import sys
import os
import time
from dotenv import load_dotenv

# 使用统一的日志管理模块
from utils.logger import get_logger, setup_third_party_logging

# 创建日志记录器
logger = get_logger('run_all')

# 设置第三方库的日志级别，减少不必要的日志输出
setup_third_party_logging()

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

    这个函数不再尝试初始化数据库或导入web_app模块，
    而是简单地设置一些基本的环境变量，避免循环导入问题。
    """
    try:
        logger.info("设置基本环境变量...")

        # 设置默认环境变量
        defaults = {
            'AUTO_FETCH_ENABLED': 'false',
            'SCHEDULER_INTERVAL_MINUTES': '30',
            'DB_AUTO_CLEAN_ENABLED': 'false',
            'DB_AUTO_CLEAN_TIME': '03:00',
            'DB_CLEAN_BY_COUNT': 'false',
            'DB_MAX_RECORDS_PER_ACCOUNT': '100',
            'DB_RETENTION_DAYS': '30',
            'DB_CLEAN_IRRELEVANT_ONLY': 'true',
            'ENABLE_AUTO_REPLY': 'false',
            'AUTO_REPLY_PROMPT': '',
            'FLASK_DEBUG': 'false'
        }

        # 设置环境变量（如果尚未设置）
        for key, value in defaults.items():
            if key not in os.environ:
                os.environ[key] = value
                logger.info(f"设置默认环境变量: {key}={value}")

        # 尝试从数据库加载配置（如果数据库已初始化）
        try:
            db_path = os.environ.get('DATABASE_PATH', '/data/tweetAnalyst.db')

            # 检查是否存在小写版本的数据库文件
            db_dir = os.path.dirname(db_path)
            db_name = os.path.basename(db_path)
            lowercase_db_name = db_name.lower()
            lowercase_db_path = os.path.join(db_dir, lowercase_db_name)

            if os.path.exists(lowercase_db_path) and not os.path.exists(db_path) and lowercase_db_path != db_path:
                logger.warning(f"检测到小写数据库文件: {lowercase_db_path}，但配置使用: {db_path}")
                logger.info(f"正在重命名数据库文件: {lowercase_db_path} -> {db_path}")
                try:
                    os.rename(lowercase_db_path, db_path)
                    logger.info(f"数据库文件重命名成功")
                except Exception as e:
                    logger.error(f"数据库文件重命名失败: {str(e)}")
                    # 如果重命名失败，使用小写版本的数据库文件
                    logger.warning(f"将使用小写版本的数据库文件: {lowercase_db_path}")
                    db_path = lowercase_db_path
            if os.path.exists(db_path):
                logger.info(f"尝试从数据库加载配置: {db_path}")

                # 使用SQLite直接查询，避免依赖Flask应用上下文
                import sqlite3
                conn = sqlite3.connect(db_path)
                cursor = conn.cursor()

                try:
                    # 检查system_config表是否存在
                    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='system_config'")
                    if cursor.fetchone():
                        # 查询所有配置
                        cursor.execute("SELECT key, value FROM system_config")
                        configs = cursor.fetchall()

                        # 加载到环境变量
                        for key, value in configs:
                            os.environ[key] = value
                            logger.debug(f"从数据库加载配置: {key}")

                        logger.info(f"从数据库加载了 {len(configs)} 个配置")
                except Exception as db_error:
                    logger.warning(f"从数据库加载配置时出错: {str(db_error)}")

                # 关闭连接
                cursor.close()
                conn.close()
        except Exception as db_error:
            logger.warning(f"尝试从数据库加载配置时出错: {str(db_error)}")

        logger.info("基本环境变量设置完成")
        return True
    except Exception as e:
        logger.error(f"设置环境变量时出错: {str(e)}")
        return False

def setup_proxy():
    """
    设置代理环境变量
    """
    # 尝试从数据库加载代理配置
    try:
        # 使用SQLite直接查询，避免依赖Flask应用上下文
        db_path = os.environ.get('DATABASE_PATH', '/data/tweetAnalyst.db')

        # 检查是否存在小写版本的数据库文件
        db_dir = os.path.dirname(db_path)
        db_name = os.path.basename(db_path)
        lowercase_db_name = db_name.lower()
        lowercase_db_path = os.path.join(db_dir, lowercase_db_name)

        # 检查文件名大小写问题（特别是在Windows上）
        if lowercase_db_path != db_path and os.path.exists(db_path):
            # 检查实际文件名的大小写
            try:
                actual_files = os.listdir(db_dir)
                actual_db_name = None
                for file in actual_files:
                    if file.lower() == lowercase_db_name:
                        actual_db_name = file
                        break

                if actual_db_name and actual_db_name != db_name:
                    logger.warning(f"检测到数据库文件名大小写不匹配: 实际={actual_db_name}, 期望={db_name}")
                    logger.info(f"正在修正数据库文件名大小写")

                    # 在Windows上，需要通过临时文件名来重命名
                    temp_db_path = os.path.join(db_dir, f"temp_{db_name}")
                    actual_db_path = os.path.join(db_dir, actual_db_name)

                    try:
                        # 先重命名为临时文件名
                        os.rename(actual_db_path, temp_db_path)
                        # 再重命名为正确的文件名
                        os.rename(temp_db_path, db_path)
                        logger.info(f"数据库文件名大小写修正成功: {actual_db_name} -> {db_name}")
                    except Exception as e:
                        logger.error(f"数据库文件名大小写修正失败: {str(e)}")
                        # 如果修正失败，恢复原文件名
                        try:
                            if os.path.exists(temp_db_path):
                                os.rename(temp_db_path, actual_db_path)
                        except:
                            pass
            except Exception as e:
                logger.error(f"检查数据库文件名大小写时出错: {str(e)}")

        elif os.path.exists(lowercase_db_path) and not os.path.exists(db_path) and lowercase_db_path != db_path:
            logger.warning(f"检测到小写数据库文件: {lowercase_db_path}，但配置使用: {db_path}")
            logger.info(f"正在重命名数据库文件: {lowercase_db_path} -> {db_path}")
            try:
                os.rename(lowercase_db_path, db_path)
                logger.info(f"数据库文件重命名成功")
            except Exception as e:
                logger.error(f"数据库文件重命名失败: {str(e)}")
                # 如果重命名失败，使用小写版本的数据库文件
                logger.warning(f"将使用小写版本的数据库文件: {lowercase_db_path}")
                db_path = lowercase_db_path
        if os.path.exists(db_path):
            logger.info(f"尝试从数据库加载代理配置: {db_path}")

            import sqlite3
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()

            try:
                # 检查proxy_config表是否存在
                cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='proxy_config'")
                if cursor.fetchone():
                    # 查询所有激活的代理配置，按优先级排序
                    cursor.execute("""
                        SELECT id, name, protocol, host, port, username, password, is_active, last_check_result
                        FROM proxy_config
                        WHERE is_active = 1
                        ORDER BY priority ASC
                    """)
                    proxies = cursor.fetchall()

                    if proxies:
                        logger.info(f"从数据库加载了 {len(proxies)} 个代理配置")

                        # 首先尝试使用最近测试成功的代理
                        cursor.execute("""
                            SELECT id, name, protocol, host, port, username, password
                            FROM proxy_config
                            WHERE is_active = 1 AND last_check_result = 1
                            ORDER BY priority ASC
                            LIMIT 1
                        """)
                        working_proxy = cursor.fetchone()

                        if working_proxy:
                            # 使用最近测试成功的代理
                            _, name, protocol, host, port, username, password = working_proxy

                            # 构建代理URL
                            auth_str = ""
                            if username and password:
                                auth_str = f"{username}:{password}@"
                            proxy_url = f"{protocol}://{auth_str}{host}:{port}"

                            logger.info(f"设置代理环境变量: {proxy_url} (使用最近测试成功的代理: {name})")
                            os.environ['HTTP_PROXY'] = proxy_url
                            os.environ['HTTPS_PROXY'] = proxy_url

                            # 如果是SOCKS代理，尝试安装支持
                            if protocol.startswith('socks'):
                                try:
                                    logger.info("检测到SOCKS代理，尝试安装支持...")
                                    import pip
                                    pip.main(['install', 'httpx[socks]', '--quiet'])
                                    logger.info("成功安装SOCKS代理支持")
                                except Exception as e:
                                    logger.warning(f"安装SOCKS代理支持失败: {str(e)}")

                            # 关闭连接并返回
                            cursor.close()
                            conn.close()
                            return

                        # 如果没有最近测试成功的代理，尝试测试所有代理
                        for proxy in proxies:
                            _, name, protocol, host, port, username, password, is_active, _ = proxy

                            # 构建代理URL
                            auth_str = ""
                            if username and password:
                                auth_str = f"{username}:{password}@"
                            proxy_url = f"{protocol}://{auth_str}{host}:{port}"

                            # 测试代理
                            logger.info(f"测试代理: {name} ({proxy_url})")
                            try:
                                import requests
                                start_time = time.time()
                                response = requests.get(
                                    "https://www.google.com/generate_204",
                                    proxies={
                                        'http': proxy_url,
                                        'https': proxy_url
                                    },
                                    timeout=10,
                                    verify=False
                                )
                                end_time = time.time()

                                if response.status_code in [200, 204]:
                                    # 更新代理测试结果
                                    cursor.execute(
                                        "UPDATE proxy_config SET last_check_time = datetime('now'), last_check_result = 1, response_time = ? WHERE id = ?",
                                        (end_time - start_time, proxy[0])
                                    )
                                    conn.commit()

                                    # 设置代理环境变量
                                    logger.info(f"设置代理环境变量: {proxy_url} (测试成功: {name})")
                                    os.environ['HTTP_PROXY'] = proxy_url
                                    os.environ['HTTPS_PROXY'] = proxy_url

                                    # 如果是SOCKS代理，尝试安装支持
                                    if protocol.startswith('socks'):
                                        try:
                                            logger.info("检测到SOCKS代理，尝试安装支持...")
                                            import pip
                                            pip.main(['install', 'httpx[socks]', '--quiet'])
                                            logger.info("成功安装SOCKS代理支持")
                                        except Exception as e:
                                            logger.warning(f"安装SOCKS代理支持失败: {str(e)}")

                                    # 关闭连接并返回
                                    cursor.close()
                                    conn.close()
                                    return
                                else:
                                    # 更新代理测试结果
                                    cursor.execute(
                                        "UPDATE proxy_config SET last_check_time = datetime('now'), last_check_result = 0 WHERE id = ?",
                                        (proxy[0],)
                                    )
                                    conn.commit()
                                    logger.warning(f"代理测试失败: {name}, 状态码: {response.status_code}")
                            except Exception as e:
                                # 更新代理测试结果
                                cursor.execute(
                                    "UPDATE proxy_config SET last_check_time = datetime('now'), last_check_result = 0 WHERE id = ?",
                                    (proxy[0],)
                                )
                                conn.commit()
                                logger.warning(f"代理测试失败: {name}, 错误: {str(e)}")
                    else:
                        logger.warning("数据库中没有激活的代理配置")
                else:
                    logger.warning("数据库中不存在proxy_config表")
            except Exception as db_error:
                logger.warning(f"从数据库加载代理配置时出错: {str(db_error)}")

            # 关闭连接
            cursor.close()
            conn.close()
    except Exception as e:
        logger.warning(f"尝试从数据库加载代理配置时出错: {str(e)}")

    # 如果从数据库加载代理失败，尝试使用代理管理器
    try:
        from utils.api_utils import get_proxy_manager

        # 获取代理管理器
        proxy_manager = get_proxy_manager()

        # 查找可用代理
        working_proxy = proxy_manager.find_working_proxy()

        if working_proxy:
            proxy_url = f"{working_proxy.protocol}://{working_proxy.host}:{working_proxy.port}"
            logger.info(f"设置代理环境变量: {proxy_url} (使用代理管理器)")
            os.environ['HTTP_PROXY'] = proxy_url
            os.environ['HTTPS_PROXY'] = proxy_url

            # 如果是SOCKS代理，尝试安装支持
            if working_proxy.protocol.startswith('socks'):
                try:
                    logger.info("检测到SOCKS代理，尝试安装支持...")
                    import pip
                    pip.main(['install', 'httpx[socks]', '--quiet'])
                    logger.info("成功安装SOCKS代理支持")
                except Exception as e:
                    logger.warning(f"安装SOCKS代理支持失败: {str(e)}")
            return
        else:
            logger.warning("代理管理器未找到可用的代理")
    except Exception as e:
        logger.warning(f"使用代理管理器设置代理失败: {str(e)}")

    # 如果以上方法都失败，回退到使用环境变量中的代理
    proxy = os.getenv('HTTP_PROXY', '')
    if proxy:
        logger.info(f"设置代理环境变量: {proxy} (使用环境变量)")
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
    else:
        logger.warning("未找到可用的代理")

if __name__ == "__main__":
    # 加载配置
    load_configs()

    # 设置代理
    setup_proxy()

    # 启动Web应用
    web_process = run_command("python run_web.py", "Web应用")

    # 等待Web应用启动
    time.sleep(3)

    # 检查是否启用自动抓取
    auto_fetch_enabled = os.getenv('AUTO_FETCH_ENABLED', 'false').lower() == 'true'

    # 启动定时任务（即使不自动抓取，也需要启动定时任务以处理日志清理等）
    scheduler_process = run_command("python run_scheduler.py", "定时任务")

    if auto_fetch_enabled:
        logger.info("已启用自动抓取，定时任务将自动执行抓取")
    else:
        logger.info("自动抓取已禁用，请通过Web界面手动启动抓取任务")

    # 检查是否启用推送队列
    push_queue_enabled = os.getenv('PUSH_QUEUE_ENABLED', 'true').lower() == 'true'

    # 启动推送队列处理器
    if push_queue_enabled:
        logger.info("启动推送队列处理器...")
        try:
            # 导入推送队列工作线程模块
            from services.push_queue_worker import start_push_queue_worker

            # 启动推送队列工作线程
            if start_push_queue_worker():
                logger.info("推送队列处理器已启动")
            else:
                logger.warning("推送队列处理器启动失败")
        except ImportError:
            logger.warning("无法导入推送队列工作线程模块，推送队列功能将不可用")
        except Exception as e:
            logger.error(f"启动推送队列处理器时出错: {str(e)}")
    else:
        logger.info("推送队列功能已禁用，将使用直接推送模式")

    try:
        # 等待进程结束
        web_process.wait()
        scheduler_process.wait()
    except KeyboardInterrupt:
        # 捕获Ctrl+C
        logger.info("正在关闭所有进程...")

        # 停止推送队列处理器
        if push_queue_enabled:
            try:
                from services.push_queue_worker import stop_push_queue_worker
                if stop_push_queue_worker():
                    logger.info("推送队列处理器已停止")
                else:
                    logger.warning("推送队列处理器停止失败")
            except Exception as e:
                logger.error(f"停止推送队列处理器时出错: {str(e)}")

        # 停止其他进程
        web_process.terminate()
        scheduler_process.terminate()
        sys.exit(0)
