"""
数据库迁移脚本：添加AI提供商相关字段
"""

import logging
import os
import sys
from datetime import datetime, timezone

# 添加项目根目录到Python路径
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# 导入Flask应用和数据库
from web_app import app, db
from models.ai_provider import AIProvider
from models.social_account import SocialAccount
from services.config_service import get_config

# 创建日志记录器
logger = logging.getLogger('migrations.add_ai_provider_fields')

def run_migration():
    """运行迁移脚本"""
    logger.info("开始运行AI提供商字段迁移脚本")

    with app.app_context():
        try:
            # 检查数据库连接
            from sqlalchemy import text
            with db.engine.connect() as conn:
                conn.execute(text("SELECT 1")).fetchall()
            logger.info("数据库连接正常")

            # 检查AI提供商表是否存在
            from sqlalchemy import inspect
            inspector = inspect(db.engine)
            existing_tables = inspector.get_table_names()

            if 'ai_provider' not in existing_tables:
                logger.info("AI提供商表不存在，创建表")
                # 创建AI提供商表
                db.create_all()
                logger.info("AI提供商表创建成功")

                # 创建默认AI提供商
                create_default_ai_providers()
            else:
                logger.info("AI提供商表已存在")

            # 检查社交账号表中是否存在AI提供商相关字段
            social_account_columns = [column['name'] for column in inspector.get_columns('social_account')]

            # 需要添加的字段
            fields_to_add = []
            if 'ai_provider_id' not in social_account_columns:
                fields_to_add.append(('ai_provider_id', 'INTEGER'))
            if 'text_provider_id' not in social_account_columns:
                fields_to_add.append(('text_provider_id', 'INTEGER'))
            if 'image_provider_id' not in social_account_columns:
                fields_to_add.append(('image_provider_id', 'INTEGER'))
            if 'video_provider_id' not in social_account_columns:
                fields_to_add.append(('video_provider_id', 'INTEGER'))
            if 'gif_provider_id' not in social_account_columns:
                fields_to_add.append(('gif_provider_id', 'INTEGER'))

            # 添加字段
            if fields_to_add:
                logger.info(f"需要添加的字段: {fields_to_add}")

                with db.engine.connect() as conn:
                    for field_name, field_type in fields_to_add:
                        logger.info(f"添加字段: {field_name} ({field_type})")
                        conn.execute(text(f"ALTER TABLE social_account ADD COLUMN {field_name} {field_type}"))

                    # 添加外键约束
                    for field_name, _ in fields_to_add:
                        if field_name.endswith('_id'):
                            logger.info(f"添加外键约束: {field_name} -> ai_provider.id")
                            conn.execute(text(f"CREATE INDEX idx_{field_name} ON social_account ({field_name})"))

                    conn.commit()

                logger.info("字段添加成功")
            else:
                logger.info("所有字段已存在，无需添加")

            # 检查分析结果表中是否存在AI提供商相关字段
            analysis_result_columns = [column['name'] for column in inspector.get_columns('analysis_result')]

            # 需要添加的字段
            fields_to_add = []
            if 'ai_provider' not in analysis_result_columns:
                fields_to_add.append(('ai_provider', 'VARCHAR(100)'))
            if 'ai_model' not in analysis_result_columns:
                fields_to_add.append(('ai_model', 'VARCHAR(100)'))
            if 'has_media' not in analysis_result_columns:
                fields_to_add.append(('has_media', 'BOOLEAN DEFAULT FALSE'))
            if 'media_content' not in analysis_result_columns:
                fields_to_add.append(('media_content', 'TEXT'))

            # 添加字段
            if fields_to_add:
                logger.info(f"需要添加的字段: {fields_to_add}")

                with db.engine.connect() as conn:
                    for field_name, field_type in fields_to_add:
                        logger.info(f"添加字段: {field_name} ({field_type})")
                        conn.execute(text(f"ALTER TABLE analysis_result ADD COLUMN {field_name} {field_type}"))

                    # 添加索引
                    if 'ai_provider' in [f[0] for f in fields_to_add]:
                        logger.info("添加索引: idx_ai_provider")
                        conn.execute(text("CREATE INDEX idx_ai_provider ON analysis_result (ai_provider)"))

                    if 'ai_model' in [f[0] for f in fields_to_add]:
                        logger.info("添加索引: idx_ai_model")
                        conn.execute(text("CREATE INDEX idx_ai_model ON analysis_result (ai_model)"))

                    if 'has_media' in [f[0] for f in fields_to_add]:
                        logger.info("添加索引: idx_has_media")
                        conn.execute(text("CREATE INDEX idx_has_media ON analysis_result (has_media)"))

                    conn.commit()

                logger.info("字段添加成功")
            else:
                logger.info("所有字段已存在，无需添加")

            logger.info("AI提供商字段迁移脚本运行成功")
            return True
        except Exception as e:
            logger.error(f"迁移脚本运行失败: {str(e)}")
            return False

def create_default_ai_providers():
    """创建默认AI提供商"""
    try:
        # 确保在应用上下文中运行
        with app.app_context():
            # 检查是否已存在AI提供商
            if AIProvider.query.first() is not None:
                logger.debug("已存在AI提供商，不创建默认提供商")
                return False

            # 从配置中获取API密钥和基础URL
            # 直接从环境变量获取，避免循环依赖
            api_key = os.environ.get('LLM_API_KEY', '')
            api_base = os.environ.get('LLM_API_BASE', 'https://api.openai.com/v1')
            api_model = os.environ.get('LLM_API_MODEL', 'gpt-4')

            # 创建默认AI提供商
            default_provider = AIProvider(
                name="默认提供商",
                model=api_model,
                api_key=api_key,
                api_base=api_base,
                priority=0,
                is_active=True,
                supports_text=True,
                supports_image=False,
                supports_video=False,
                supports_gif=False
            )

            # 创建多模态AI提供商
            multimodal_provider = AIProvider(
                name="多模态提供商",
                model="gpt-4-vision-preview",
                api_key=api_key,
                api_base=api_base,
                priority=1,
                is_active=True,
                supports_text=True,
                supports_image=True,
                supports_video=False,
                supports_gif=True
            )

            db.session.add(default_provider)
            db.session.add(multimodal_provider)
            db.session.commit()

            logger.info("已创建默认AI提供商")
            return True
    except Exception as e:
        logger.error(f"创建默认AI提供商时出错: {str(e)}")
        try:
            db.session.rollback()
        except:
            pass
        return False

if __name__ == '__main__':
    # 配置日志
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )

    # 运行迁移脚本
    success = run_migration()

    if success:
        print("迁移脚本运行成功")
        sys.exit(0)
    else:
        print("迁移脚本运行失败")
        sys.exit(1)
