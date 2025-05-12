"""
定时任务启动脚本
"""
import time
import schedule
import main
import os
import datetime
from dotenv import load_dotenv
import sys

# 添加当前目录到路径，确保能导入web_app模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 导入配置加载函数
try:
    from web_app import load_configs_to_env, init_db
    from models import db, AnalysisResult
    # 初始化数据库并加载配置
    init_db()
    load_configs_to_env()
except ImportError:
    print("警告: 无法导入web_app模块，将使用环境变量中的配置")

load_dotenv()

def job():
    """
    执行主程序
    """
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始执行社交媒体监控任务...")
    try:
        main.main()
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 社交媒体监控任务执行完成")
    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 社交媒体监控任务执行出错: {e}")

def auto_clean_database():
    """
    自动清理数据库
    根据配置清理旧数据或保持每个账号的记录数在限制范围内
    """
    print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 开始执行数据库自动清理任务...")

    try:
        # 从环境变量获取配置
        clean_by_count = os.getenv('DB_CLEAN_BY_COUNT', 'false').lower() == 'true'
        max_records = int(os.getenv('DB_MAX_RECORDS_PER_ACCOUNT', '100'))
        retention_days = int(os.getenv('DB_RETENTION_DAYS', '30'))
        clean_irrelevant_only = os.getenv('DB_CLEAN_IRRELEVANT_ONLY', 'true').lower() == 'true'

        # 根据配置选择清理方式
        if clean_by_count:
            # 基于数量的清理
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 使用基于数量的清理方式，每个账号保留最新的 {max_records} 条{'不相关' if clean_irrelevant_only else ''}记录")

            # 获取所有不同的账号ID
            with db.app.app_context():
                account_ids = db.session.query(AnalysisResult.account_id).distinct().all()
                account_ids = [account[0] for account in account_ids]

                total_deleted = 0

                # 对每个账号分别处理
                for account_id in account_ids:
                    # 构建查询
                    if clean_irrelevant_only:
                        # 只清理不相关的记录
                        query = AnalysisResult.query.filter_by(account_id=account_id, is_relevant=False)
                    else:
                        # 清理所有记录
                        query = AnalysisResult.query.filter_by(account_id=account_id)

                    # 获取该账号的记录，按时间降序排序
                    records = query.order_by(AnalysisResult.post_time.desc()).all()

                    # 如果记录数超过最大值，删除多余的记录
                    if len(records) > max_records:
                        # 获取要删除的记录ID
                        records_to_delete = records[max_records:]
                        delete_ids = [record.id for record in records_to_delete]

                        # 删除记录
                        deleted_count = AnalysisResult.query.filter(AnalysisResult.id.in_(delete_ids)).delete()
                        total_deleted += deleted_count

                        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 已清理账号 {account_id} 的 {deleted_count} 条{'不相关' if clean_irrelevant_only else ''}记录")

                # 提交事务
                db.session.commit()
                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 数据库自动清理完成，共清理 {total_deleted} 条记录")
        else:
            # 基于时间的清理
            print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 使用基于时间的清理方式，清理超过 {retention_days} 天的{'不相关' if clean_irrelevant_only else ''}数据")

            # 计算截止日期
            cutoff_date = datetime.datetime.now() - datetime.timedelta(days=retention_days)

            with db.app.app_context():
                # 构建查询
                query = AnalysisResult.query.filter(AnalysisResult.created_at < cutoff_date)

                if clean_irrelevant_only:
                    # 只清理不相关的记录
                    query = query.filter(AnalysisResult.is_relevant == False)

                # 执行删除
                deleted_count = query.delete()

                # 提交事务
                db.session.commit()

                print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 数据库自动清理完成，共清理 {deleted_count} 条超过 {retention_days} 天的{'不相关' if clean_irrelevant_only else ''}数据")

    except Exception as e:
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 数据库自动清理任务执行出错: {e}")
        try:
            db.session.rollback()
        except:
            pass

if __name__ == "__main__":
    # 获取执行间隔（分钟）
    interval_minutes = int(os.getenv("SCHEDULER_INTERVAL_MINUTES", "30"))

    # 设置定时任务
    schedule.every(interval_minutes).minutes.do(job)

    # 设置数据库自动清理任务
    # 默认每天凌晨3点执行一次
    auto_clean_enabled = os.getenv('DB_AUTO_CLEAN_ENABLED', 'false').lower() == 'true'
    if auto_clean_enabled:
        auto_clean_time = os.getenv('DB_AUTO_CLEAN_TIME', '03:00')
        print(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] 已启用数据库自动清理，将在每天 {auto_clean_time} 执行")
        schedule.every().day.at(auto_clean_time).do(auto_clean_database)

    print(f"定时任务已启动，每 {interval_minutes} 分钟执行一次")

    # 立即执行一次
    job()

    # 循环执行定时任务
    while True:
        schedule.run_pending()
        time.sleep(1)
