"""
统一数据库迁移管理脚本

这个脚本整合了所有数据库迁移功能，提供了一个统一的接口来执行所有迁移操作。
使用方法：
1. 直接运行此脚本执行所有迁移: python migrations/db_migrations.py
2. 在其他模块中导入并调用run_all_migrations()函数

迁移操作包括：
1. 添加bypass_ai字段到SocialAccount表
2. 添加notification_services表
3. 添加AI提供商字段
4. 添加confidence和reason字段到AnalysisResult表
5. 添加社交账号详细信息字段
6. 添加唯一性约束到AnalysisResult表，防止重复记录
7. 添加代理配置表，支持多代理管理
"""

import os
import sys
import logging
import sqlite3
import importlib
from datetime import datetime
from typing import List, Dict, Any, Tuple, Optional

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 尝试导入项目依赖
try:
    from dotenv import load_dotenv
except ImportError as e:
    print(f"导入python-dotenv时出错: {str(e)}")
    print("正在尝试安装python-dotenv...")
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "python-dotenv"])
        from dotenv import load_dotenv
        print("成功安装并导入python-dotenv")
    except Exception as install_error:
        print(f"安装python-dotenv失败: {str(install_error)}")
        print("请手动安装: pip install python-dotenv")
        sys.exit(1)

try:
    from sqlalchemy import text, inspect
except ImportError as e:
    print(f"导入sqlalchemy时出错: {str(e)}")
    print("正在尝试安装sqlalchemy...")
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "sqlalchemy"])
        from sqlalchemy import text, inspect
        print("成功安装并导入sqlalchemy")
    except Exception as install_error:
        print(f"安装sqlalchemy失败: {str(install_error)}")
        print("请手动安装: pip install sqlalchemy")
        sys.exit(1)

try:
    from alembic import op
    import sqlalchemy as sa
except ImportError as e:
    print(f"导入alembic时出错: {str(e)}")
    print("正在尝试安装alembic...")
    try:
        import subprocess
        subprocess.check_call([sys.executable, "-m", "pip", "install", "alembic"])
        from alembic import op
        import sqlalchemy as sa
        print("成功安装并导入alembic")
    except Exception as install_error:
        print(f"安装alembic失败: {str(install_error)}")
        print("请手动安装: pip install alembic")
        sys.exit(1)

# 加载环境变量
load_dotenv()

# 使用统一的日志管理模块
try:
    from utils.logger import get_logger
    logger = get_logger('db_migrations')
except ImportError:
    # 如果无法导入自定义日志模块，使用标准日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    logger = logging.getLogger('db_migrations')
    logger.warning("无法导入utils.logger模块，使用标准日志配置")

# 迁移记录表名
MIGRATION_TABLE = 'db_migration_history'

class Migration:
    """迁移基类"""

    def __init__(self, id: str, name: str, description: str):
        self.id = id
        self.name = name
        self.description = description
        self.success = False
        self.error_message = None
        self.start_time = None
        self.end_time = None

    def run(self, conn: sqlite3.Connection) -> bool:
        """执行迁移"""
        self.start_time = datetime.now()
        try:
            logger.info(f"开始执行迁移 {self.id}: {self.name}")
            self.success = self._execute(conn)
            if self.success:
                logger.info(f"迁移 {self.id} 成功完成")
            else:
                logger.error(f"迁移 {self.id} 失败")
            return self.success
        except Exception as e:
            self.error_message = str(e)
            logger.error(f"迁移 {self.id} 执行时出错: {self.error_message}")
            return False
        finally:
            self.end_time = datetime.now()

    def _execute(self, conn: sqlite3.Connection) -> bool:
        """实际执行迁移的方法，子类需要重写此方法"""
        raise NotImplementedError("子类必须实现_execute方法")

    def get_duration(self) -> float:
        """获取迁移执行时间（秒）"""
        if self.start_time and self.end_time:
            return (self.end_time - self.start_time).total_seconds()
        return 0.0

class AddBypassAIField(Migration):
    """添加bypass_ai字段到SocialAccount表"""

    def __init__(self):
        super().__init__(
            id="001_add_bypass_ai_field",
            name="添加bypass_ai字段到SocialAccount表",
            description="为SocialAccount表添加bypass_ai布尔字段，用于控制是否绕过AI判断直接推送"
        )

    def _execute(self, conn: sqlite3.Connection) -> bool:
        cursor = conn.cursor()

        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(social_account)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'bypass_ai' not in columns:
            logger.info("添加bypass_ai字段到social_account表")
            cursor.execute('ALTER TABLE social_account ADD COLUMN bypass_ai BOOLEAN DEFAULT FALSE')
            cursor.execute('CREATE INDEX idx_bypass_ai ON social_account (bypass_ai)')
            conn.commit()
            logger.info("成功添加bypass_ai字段和索引")
        else:
            logger.info("bypass_ai字段已存在，无需迁移")

        return True

class AddNotificationServicesTable(Migration):
    """添加notification_services表"""

    def __init__(self):
        super().__init__(
            id="002_add_notification_services_table",
            name="添加notification_services表",
            description="创建notification_services表，用于存储通知服务配置"
        )

    def _execute(self, conn: sqlite3.Connection) -> bool:
        cursor = conn.cursor()

        # 检查表是否已存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='notification_services'")
        if cursor.fetchone():
            logger.info("notification_services表已存在，跳过创建")
            return True

        # 创建表
        cursor.execute('''
        CREATE TABLE notification_services (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            service_type TEXT NOT NULL,
            config_url TEXT NOT NULL,
            is_active BOOLEAN DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        ''')

        conn.commit()
        logger.info("成功创建notification_services表")
        return True

class AddAvatarUrlField(Migration):
    """添加avatar_url字段到SocialAccount表"""

    def __init__(self):
        super().__init__(
            id="003_add_avatar_url_field",
            name="添加avatar_url字段到SocialAccount表",
            description="为SocialAccount表添加avatar_url字段，用于存储用户头像URL"
        )

    def _execute(self, conn: sqlite3.Connection) -> bool:
        cursor = conn.cursor()

        # 检查字段是否已存在
        cursor.execute("PRAGMA table_info(social_account)")
        columns = [column[1] for column in cursor.fetchall()]

        if 'avatar_url' not in columns:
            logger.info("添加avatar_url字段到social_account表")
            cursor.execute('ALTER TABLE social_account ADD COLUMN avatar_url TEXT')
            conn.commit()
            logger.info("成功添加avatar_url字段")
        else:
            logger.info("avatar_url字段已存在，无需迁移")

        return True

class AddAccountDetailsFields(Migration):
    """添加社交账号详细信息字段"""

    def __init__(self):
        super().__init__(
            id="004_add_account_details_fields",
            name="添加社交账号详细信息字段",
            description="为SocialAccount表添加display_name, bio, verified等详细信息字段"
        )

    def _execute(self, conn: sqlite3.Connection) -> bool:
        cursor = conn.cursor()

        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='social_account'")
        if not cursor.fetchone():
            logger.warning("social_account表不存在，跳过添加详细信息字段")
            return True

        # 获取现有字段
        cursor.execute("PRAGMA table_info(social_account)")
        existing_columns = [column[1] for column in cursor.fetchall()]

        # 定义需要添加的字段（与models/social_account.py保持一致）
        fields_to_add = [
            ('display_name', 'TEXT'),
            ('bio', 'TEXT'),
            ('verified', 'BOOLEAN DEFAULT 0'),
            ('followers_count', 'INTEGER DEFAULT 0'),
            ('following_count', 'INTEGER DEFAULT 0'),
            ('posts_count', 'INTEGER DEFAULT 0'),  # 帖子数
            ('join_date', 'TIMESTAMP'),  # 与模型保持一致，使用join_date而不是joined_date
            ('location', 'TEXT'),
            ('website', 'TEXT'),
            ('profession', 'TEXT')  # 添加模型中存在的profession字段
        ]

        # 添加缺失的字段
        added_fields = []
        for field_name, field_type in fields_to_add:
            if field_name not in existing_columns:
                try:
                    logger.info(f"添加字段 {field_name} 到 social_account 表")
                    cursor.execute(f'ALTER TABLE social_account ADD COLUMN {field_name} {field_type}')
                    added_fields.append(field_name)
                except sqlite3.OperationalError as e:
                    if "duplicate column name" in str(e).lower():
                        logger.info(f"字段 {field_name} 已存在，跳过")
                    else:
                        logger.error(f"添加字段 {field_name} 时出错: {str(e)}")
                        return False
            else:
                logger.info(f"字段 {field_name} 已存在，跳过")

        if added_fields:
            conn.commit()
            logger.info(f"成功添加字段: {', '.join(added_fields)}")
        else:
            logger.info("所有字段都已存在，无需添加")

        return True

class AddUniqueConstraintToAnalysisResult(Migration):
    """添加唯一性约束到AnalysisResult表"""

    def __init__(self):
        super().__init__(
            id="005_add_unique_constraint_to_analysis_result",
            name="添加唯一性约束到AnalysisResult表",
            description="为AnalysisResult表添加social_network, account_id, post_id的唯一性约束，防止重复记录"
        )

    def _execute(self, conn: sqlite3.Connection) -> bool:
        cursor = conn.cursor()

        # 检查表是否存在
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='analysis_result'")
        if not cursor.fetchone():
            logger.warning("analysis_result表不存在，跳过添加唯一性约束")
            return True

        # 处理重复记录（使用公共数据库工具）
        logger.info("检查并处理重复记录...")
        try:
            # 导入公共数据库工具
            from utils.db_utils import handle_duplicate_records

            # 使用公共函数处理重复记录
            unique_columns = ['social_network', 'account_id', 'post_id']
            priority_columns = ['is_relevant DESC', 'confidence DESC', 'created_at DESC']

            total_removed = handle_duplicate_records(
                cursor, conn, 'analysis_result', unique_columns, priority_columns
            )
        except ImportError:
            # 如果无法导入公共工具，使用原始实现
            logger.warning("无法导入公共数据库工具，使用原始实现")

            cursor.execute("""
            SELECT social_network, account_id, post_id, COUNT(*) as count
            FROM analysis_result
            GROUP BY social_network, account_id, post_id
            HAVING COUNT(*) > 1
            """)

            duplicates = cursor.fetchall()
            logger.info(f"找到 {len(duplicates)} 组重复记录")

            total_removed = 0
            for dup in duplicates:
                social_network, account_id, post_id, count = dup
                logger.info(f"处理重复记录: {social_network}, {account_id}, {post_id}, 共 {count} 条")

                # 获取所有重复记录
                cursor.execute("""
                SELECT id, is_relevant, confidence, created_at
                FROM analysis_result
                WHERE social_network = ? AND account_id = ? AND post_id = ?
                ORDER BY
                    is_relevant DESC,  -- 优先保留相关的记录
                    confidence DESC,   -- 其次是置信度高的
                    created_at DESC    -- 最后是最新创建的
                """, (social_network, account_id, post_id))

                records = cursor.fetchall()

                # 保留第一条记录，删除其余记录
                keep_id = records[0][0]
                delete_ids = [r[0] for r in records[1:]]

                if delete_ids:
                    placeholders = ','.join(['?'] * len(delete_ids))
                    cursor.execute(f"DELETE FROM analysis_result WHERE id IN ({placeholders})", delete_ids)
                    removed = len(delete_ids)
                    total_removed += removed
                    logger.info(f"保留记录ID: {keep_id}, 删除 {removed} 条重复记录")

            if total_removed > 0:
                conn.commit()
                logger.info(f"共删除 {total_removed} 条重复记录")

        # 添加唯一性约束
        # SQLite不支持直接添加约束，需要创建新表并迁移数据
        logger.info("开始添加唯一性约束...")

        try:
            # 1. 创建临时表
            cursor.execute("""
            CREATE TABLE analysis_result_temp (
                id INTEGER PRIMARY KEY,
                social_network TEXT NOT NULL,
                account_id TEXT NOT NULL,
                post_id TEXT NOT NULL,
                post_time TIMESTAMP NOT NULL,
                content TEXT NOT NULL,
                analysis TEXT NOT NULL,
                is_relevant BOOLEAN NOT NULL,
                confidence INTEGER,
                reason TEXT,
                poster_avatar_url TEXT,
                has_media BOOLEAN DEFAULT 0,
                media_content TEXT,
                ai_provider TEXT,
                ai_model TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(social_network, account_id, post_id)
            )
            """)

            # 2. 创建索引
            cursor.execute("CREATE INDEX idx_account_relevant_temp ON analysis_result_temp (account_id, is_relevant)")
            cursor.execute("CREATE INDEX idx_network_account_temp ON analysis_result_temp (social_network, account_id)")
            cursor.execute("CREATE INDEX idx_time_relevant_temp ON analysis_result_temp (post_time, is_relevant)")
            cursor.execute("CREATE INDEX idx_confidence_temp ON analysis_result_temp (confidence)")
            cursor.execute("CREATE INDEX idx_social_network_temp ON analysis_result_temp (social_network)")
            cursor.execute("CREATE INDEX idx_account_id_temp ON analysis_result_temp (account_id)")
            cursor.execute("CREATE INDEX idx_post_id_temp ON analysis_result_temp (post_id)")
            cursor.execute("CREATE INDEX idx_post_time_temp ON analysis_result_temp (post_time)")
            cursor.execute("CREATE INDEX idx_is_relevant_temp ON analysis_result_temp (is_relevant)")
            cursor.execute("CREATE INDEX idx_has_media_temp ON analysis_result_temp (has_media)")
            cursor.execute("CREATE INDEX idx_ai_provider_temp ON analysis_result_temp (ai_provider)")
            cursor.execute("CREATE INDEX idx_ai_model_temp ON analysis_result_temp (ai_model)")
            cursor.execute("CREATE INDEX idx_created_at_temp ON analysis_result_temp (created_at)")

            # 3. 迁移数据
            cursor.execute("""
            INSERT INTO analysis_result_temp
            SELECT id, social_network, account_id, post_id, post_time, content, analysis,
                   is_relevant, confidence, reason,
                   CASE WHEN EXISTS(SELECT 1 FROM pragma_table_info('analysis_result') WHERE name='poster_avatar_url')
                        THEN poster_avatar_url ELSE NULL END as poster_avatar_url,
                   has_media, media_content, ai_provider,
                   ai_model, created_at
            FROM analysis_result
            """)

            # 4. 删除旧表
            cursor.execute("DROP TABLE analysis_result")

            # 5. 重命名新表
            cursor.execute("ALTER TABLE analysis_result_temp RENAME TO analysis_result")

            conn.commit()
            logger.info("成功添加唯一性约束")
            return True
        except Exception as e:
            conn.rollback()
            logger.error(f"添加唯一性约束时出错: {str(e)}")
            return False


class AddPosterAvatarUrlField(Migration):
    """确保analysis_result表包含poster_avatar_url字段"""

    def __init__(self):
        super().__init__(
            id="006_add_poster_avatar_url_field",
            name="确保analysis_result表包含poster_avatar_url字段",
            description="检查并添加poster_avatar_url字段到analysis_result表，用于存储发布者头像URL"
        )

    def _execute(self, conn: sqlite3.Connection) -> bool:
        cursor = conn.cursor()

        try:
            # 检查字段是否已存在
            cursor.execute("PRAGMA table_info(analysis_result)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'poster_avatar_url' not in columns:
                logger.info("添加poster_avatar_url字段到analysis_result表")
                cursor.execute('ALTER TABLE analysis_result ADD COLUMN poster_avatar_url TEXT')
                conn.commit()
                logger.info("成功添加poster_avatar_url字段")
            else:
                logger.info("poster_avatar_url字段已存在，无需添加")

            return True
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                logger.info("poster_avatar_url字段已存在，无需添加")
                return True
            else:
                logger.error(f"添加poster_avatar_url字段时出错: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"执行poster_avatar_url字段迁移时出错: {str(e)}")
            return False


class AddPosterNameField(Migration):
    """添加poster_name字段到analysis_result表"""

    def __init__(self):
        super().__init__(
            id="007_add_poster_name_field",
            name="添加poster_name字段到analysis_result表",
            description="为analysis_result表添加poster_name字段，用于存储推文发布者的真实用户名"
        )

    def _execute(self, conn: sqlite3.Connection) -> bool:
        cursor = conn.cursor()

        try:
            # 检查字段是否已存在
            cursor.execute("PRAGMA table_info(analysis_result)")
            columns = [column[1] for column in cursor.fetchall()]

            if 'poster_name' not in columns:
                logger.info("添加poster_name字段到analysis_result表")
                cursor.execute('ALTER TABLE analysis_result ADD COLUMN poster_name VARCHAR(200)')
                conn.commit()
                logger.info("成功添加poster_name字段")

                # 尝试从现有数据中提取用户名信息
                logger.info("开始更新现有数据的poster_name字段...")

                # 查询所有没有poster_name的记录
                cursor.execute("""
                    SELECT id, account_id, social_network
                    FROM analysis_result
                    WHERE poster_name IS NULL
                """)

                records = cursor.fetchall()
                updated_count = 0

                for record_id, account_id, social_network in records:
                    # 对于时间线推文，account_id通常就是真实用户名
                    cursor.execute("""
                        UPDATE analysis_result
                        SET poster_name = ?
                        WHERE id = ?
                    """, (account_id, record_id))
                    updated_count += 1

                if updated_count > 0:
                    conn.commit()
                    logger.info(f"成功更新了{updated_count}条记录的poster_name字段")
                else:
                    logger.info("没有需要更新的记录")
            else:
                logger.info("poster_name字段已存在，无需添加")

            return True
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e).lower():
                logger.info("poster_name字段已存在，无需添加")
                return True
            else:
                logger.error(f"添加poster_name字段时出错: {str(e)}")
                return False
        except Exception as e:
            logger.error(f"执行poster_name字段迁移时出错: {str(e)}")
            return False


def init_migration_table(conn: sqlite3.Connection) -> None:
    """初始化迁移记录表"""
    cursor = conn.cursor()

    # 检查迁移记录表是否存在
    cursor.execute(f"SELECT name FROM sqlite_master WHERE type='table' AND name='{MIGRATION_TABLE}'")
    if not cursor.fetchone():
        logger.info(f"创建{MIGRATION_TABLE}表")
        cursor.execute(f'''
        CREATE TABLE {MIGRATION_TABLE} (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            description TEXT,
            executed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            success BOOLEAN NOT NULL,
            error_message TEXT,
            duration REAL
        )
        ''')
        conn.commit()
        logger.info(f"{MIGRATION_TABLE}表创建成功")

def get_executed_migrations(conn: sqlite3.Connection) -> List[str]:
    """获取已执行的迁移ID列表"""
    cursor = conn.cursor()
    cursor.execute(f"SELECT id FROM {MIGRATION_TABLE} WHERE success = 1")
    return [row[0] for row in cursor.fetchall()]

def record_migration(conn: sqlite3.Connection, migration: Migration) -> None:
    """记录迁移执行结果"""
    cursor = conn.cursor()

    # 检查是否已有记录
    cursor.execute(f"SELECT id FROM {MIGRATION_TABLE} WHERE id = ?", (migration.id,))
    if cursor.fetchone():
        # 更新现有记录
        cursor.execute(f'''
        UPDATE {MIGRATION_TABLE}
        SET executed_at = ?, success = ?, error_message = ?, duration = ?
        WHERE id = ?
        ''', (
            datetime.now(),
            migration.success,
            migration.error_message,
            migration.get_duration(),
            migration.id
        ))
    else:
        # 插入新记录
        cursor.execute(f'''
        INSERT INTO {MIGRATION_TABLE} (id, name, description, executed_at, success, error_message, duration)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            migration.id,
            migration.name,
            migration.description,
            datetime.now(),
            migration.success,
            migration.error_message,
            migration.get_duration()
        ))

    conn.commit()

def run_all_migrations() -> bool:
    """执行所有迁移"""
    # 获取数据库路径
    db_path = os.environ.get('DATABASE_PATH', '/data/tweetAnalyst.db')

    # 确保目录存在
    os.makedirs(os.path.dirname(db_path), exist_ok=True)

    logger.info(f"开始执行数据库迁移，数据库路径: {db_path}")
    start_time = datetime.now()

    try:
        # 连接数据库
        conn = sqlite3.connect(db_path)

        # 初始化迁移记录表
        init_migration_table(conn)

        # 获取已执行的迁移
        executed_migrations = get_executed_migrations(conn)
        logger.info(f"已执行的迁移: {executed_migrations}")

        # 定义所有迁移
        migrations = [
            AddBypassAIField(),
            AddNotificationServicesTable(),
            AddAvatarUrlField(),
            AddAccountDetailsFields(),
            AddUniqueConstraintToAnalysisResult(),
            AddPosterAvatarUrlField(),  # 确保poster_avatar_url字段存在
            AddPosterNameField()  # 添加poster_name字段
        ]

        # 运行AI提供商和AI请求日志表迁移
        try:
            from migrations.add_ai_provider_fields import run_migration as run_ai_provider_migration
            from migrations.add_ai_request_logs import run_migration as run_ai_request_logs_migration

            logger.info("运行AI提供商字段迁移")
            if run_ai_provider_migration():
                logger.info("AI提供商字段迁移成功")
            else:
                logger.warning("AI提供商字段迁移失败")

            logger.info("运行AI请求日志表迁移")
            if run_ai_request_logs_migration():
                logger.info("AI请求日志表迁移成功")
            else:
                logger.warning("AI请求日志表迁移失败")
        except Exception as e:
            logger.error(f"运行AI相关迁移时出错: {str(e)}")

        # 运行代理配置表迁移
        try:
            from migrations.add_proxy_config_table import run_migration as run_proxy_config_migration

            logger.info("运行代理配置表迁移")
            if run_proxy_config_migration():
                logger.info("代理配置表迁移成功")
            else:
                logger.warning("代理配置表迁移失败")
        except Exception as e:
            logger.error(f"运行代理配置表迁移时出错: {str(e)}")

        # 执行未执行的迁移
        all_success = True
        for migration in migrations:
            if migration.id in executed_migrations:
                logger.info(f"迁移 {migration.id} 已执行，跳过")
                continue

            success = migration.run(conn)
            record_migration(conn, migration)

            if not success:
                all_success = False
                logger.error(f"迁移 {migration.id} 失败，中止后续迁移")
                break

        # 关闭连接
        conn.close()

        end_time = datetime.now()
        duration = (end_time - start_time).total_seconds()

        if all_success:
            logger.info(f"所有迁移成功完成，总耗时 {duration:.2f} 秒")
        else:
            logger.error(f"迁移过程中出现错误，总耗时 {duration:.2f} 秒")

        return all_success
    except Exception as e:
        logger.error(f"执行迁移时出错: {str(e)}")
        return False

if __name__ == "__main__":
    success = run_all_migrations()
    sys.exit(0 if success else 1)
