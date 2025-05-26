"""
设置API模块
处理所有设置相关的API请求
"""

import os
import json
import logging
from flask import Blueprint, request, jsonify, session, current_app
from services.config_service import set_config, get_config, batch_set_configs
from models import db, User, AIProvider

# 创建日志记录器
logger = logging.getLogger('api.settings')

# 创建Blueprint
settings_api = Blueprint('settings_api', __name__, url_prefix='/settings')

@settings_api.route('/scheduler', methods=['POST'])
def update_scheduler_settings():
    """更新定时任务设置"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        try:
            data = request.get_json() or {}
            logger.debug(f"收到JSON数据: {data}")
        except Exception as e:
            logger.error(f"解析JSON数据时出错: {str(e)}")
            if request.content_type == 'application/x-www-form-urlencoded':
                data = request.form.to_dict()
                logger.debug(f"收到表单数据: {data}")
            else:
                logger.error(f"不支持的Content-Type: {request.content_type}")
                return jsonify({"success": False, "message": f"不支持的Content-Type: {request.content_type}"}), 415

        scheduler_interval = data.get('scheduler_interval')

        if scheduler_interval:
            # 验证参数
            try:
                interval = int(scheduler_interval)
                if interval < 1 or interval > 1440:
                    return jsonify({"success": False, "message": "执行间隔必须在1-1440分钟之间"}), 400
            except ValueError:
                return jsonify({"success": False, "message": "执行间隔必须是整数"}), 400

            # 保存设置
            set_config('SCHEDULER_INTERVAL_MINUTES', scheduler_interval, description='定时任务执行间隔（分钟）')
            logger.info(f"定时任务执行间隔已更新为 {scheduler_interval} 分钟")

            return jsonify({"success": True, "message": "定时任务设置已更新"})
        else:
            return jsonify({"success": False, "message": "缺少必要参数"}), 400
    except Exception as e:
        logger.error(f"更新定时任务设置时出错: {str(e)}")
        return jsonify({"success": False, "message": f"更新设置失败: {str(e)}"}), 500

@settings_api.route('/auto_reply', methods=['POST'])
def update_auto_reply_settings():
    """更新自动回复设置"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        try:
            data = request.get_json() or {}
            logger.debug(f"收到JSON数据: {data}")
        except Exception as e:
            logger.error(f"解析JSON数据时出错: {str(e)}")
            if request.content_type == 'application/x-www-form-urlencoded':
                data = request.form.to_dict()
                logger.debug(f"收到表单数据: {data}")
            else:
                logger.error(f"不支持的Content-Type: {request.content_type}")
                return jsonify({"success": False, "message": f"不支持的Content-Type: {request.content_type}"}), 415

        enable_auto_reply = data.get('enable_auto_reply', 'off')
        auto_reply_prompt = data.get('auto_reply_prompt', '')

        # 处理复选框值
        if isinstance(enable_auto_reply, str):
            enable_auto_reply = enable_auto_reply.lower() == 'on' or enable_auto_reply.lower() == 'true'

        # 保存设置
        set_config('ENABLE_AUTO_REPLY', 'true' if enable_auto_reply else 'false', description='是否启用自动回复')
        if auto_reply_prompt:
            set_config('AUTO_REPLY_PROMPT', auto_reply_prompt, description='自动回复提示词模板')

        logger.info(f"自动回复设置已更新，启用状态: {enable_auto_reply}")

        return jsonify({"success": True, "message": "自动回复设置已更新"})
    except Exception as e:
        logger.error(f"更新自动回复设置时出错: {str(e)}")
        return jsonify({"success": False, "message": f"更新设置失败: {str(e)}"}), 500

@settings_api.route('/twitter', methods=['POST'])
def update_twitter_settings():
    """更新Twitter设置"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        try:
            data = request.get_json() or {}
            logger.debug(f"收到JSON数据: {data}")
        except Exception as e:
            logger.error(f"解析JSON数据时出错: {str(e)}")
            if request.content_type == 'application/x-www-form-urlencoded':
                data = request.form.to_dict()
                logger.debug(f"收到表单数据: {data}")
            else:
                logger.error(f"不支持的Content-Type: {request.content_type}")
                return jsonify({"success": False, "message": f"不支持的Content-Type: {request.content_type}"}), 415

        twitter_username = data.get('twitter_username', '')
        twitter_password = data.get('twitter_password', '')
        twitter_session = data.get('twitter_session', '')

        # 保存设置
        if twitter_username:
            set_config('TWITTER_USERNAME', twitter_username, description='Twitter用户名')

        # 如果提供了新的密码（不是占位符），则更新
        if twitter_password and not twitter_password.startswith('******'):
            set_config('TWITTER_PASSWORD', twitter_password, is_secret=True, description='Twitter密码')

        # 如果提供了新的会话数据（不是占位符），则更新
        if twitter_session and not twitter_session.startswith('******'):
            set_config('TWITTER_SESSION', twitter_session, is_secret=True, description='Twitter会话数据')

        logger.info(f"Twitter设置已更新，用户名: {twitter_username}")

        # 重新初始化Twitter客户端以使用新配置
        try:
            from modules.socialmedia.twitter_client_manager import get_twitter_manager
            twitter_manager = get_twitter_manager()

            # 重置客户端状态
            twitter_manager.tweety_client = None
            twitter_manager.tweety_async_client = None
            twitter_manager.twikit_client = None
            twitter_manager.current_library = None
            twitter_manager.initialized = False

            # 获取库偏好设置
            library_preference = get_config('TWITTER_LIBRARY', 'auto')

            # 重新初始化
            if library_preference == 'auto':
                success = twitter_manager.auto_initialize()
            else:
                success = twitter_manager.switch_library(library_preference)

            if success:
                logger.info(f"Twitter客户端已重新初始化，使用库: {twitter_manager.current_library}")
            else:
                logger.warning("Twitter客户端重新初始化失败，但配置已保存")

        except Exception as e:
            logger.warning(f"重新初始化Twitter客户端时出错: {str(e)}，但配置已保存")

        return jsonify({"success": True, "message": "Twitter设置已更新"})
    except Exception as e:
        logger.error(f"更新Twitter设置时出错: {str(e)}")
        return jsonify({"success": False, "message": f"更新设置失败: {str(e)}"}), 500

@settings_api.route('/twitter/current_library', methods=['GET'])
def get_current_twitter_library():
    """获取当前使用的Twitter库信息"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取Twitter客户端管理器
        from modules.socialmedia.twitter_client_manager import get_twitter_manager
        twitter_manager = get_twitter_manager()

        # 获取当前库和可用库信息
        current_library = twitter_manager.current_library if twitter_manager.initialized else 'none'
        available_libraries = twitter_manager.get_available_libraries()

        # 获取配置的偏好设置
        from services.config_service import get_config
        library_preference = get_config('TWITTER_LIBRARY', 'auto')

        return jsonify({
            "success": True,
            "current_library": current_library,
            "available_libraries": available_libraries,
            "library_preference": library_preference,
            "initialized": twitter_manager.initialized
        })
    except Exception as e:
        logger.error(f"获取Twitter库信息时出错: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"获取Twitter库信息失败: {str(e)}"
        }), 500

@settings_api.route('/llm', methods=['POST'])
def update_llm_settings():
    """更新LLM设置"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        try:
            data = request.get_json() or {}
            logger.debug(f"收到JSON数据: {data}")
        except Exception as e:
            logger.error(f"解析JSON数据时出错: {str(e)}")
            if request.content_type == 'application/x-www-form-urlencoded':
                data = request.form.to_dict()
                logger.debug(f"收到表单数据: {data}")
            else:
                logger.error(f"不支持的Content-Type: {request.content_type}")
                return jsonify({"success": False, "message": f"不支持的Content-Type: {request.content_type}"}), 415

        llm_api_key = data.get('llm_api_key', '')
        llm_api_model = data.get('llm_api_model', '')
        llm_api_base = data.get('llm_api_base', '')

        # 保存设置
        # 如果提供了新的API密钥（不是占位符），则更新
        if llm_api_key and not llm_api_key.startswith('******'):
            set_config('LLM_API_KEY', llm_api_key, is_secret=True, description='LLM API密钥')

        if llm_api_model:
            set_config('LLM_API_MODEL', llm_api_model, description='LLM API模型')

        if llm_api_base:
            set_config('LLM_API_BASE', llm_api_base, description='LLM API基础URL')

        logger.info(f"LLM设置已更新，模型: {llm_api_model}")

        return jsonify({"success": True, "message": "LLM设置已更新"})
    except Exception as e:
        logger.error(f"更新LLM设置时出错: {str(e)}")
        return jsonify({"success": False, "message": f"更新设置失败: {str(e)}"}), 500

@settings_api.route('/proxy', methods=['POST'])
def update_proxy_settings():
    """更新代理设置（向后兼容）"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        try:
            data = request.get_json() or {}
            logger.debug(f"收到JSON数据: {data}")
        except Exception as e:
            logger.error(f"解析JSON数据时出错: {str(e)}")
            if request.content_type == 'application/x-www-form-urlencoded':
                data = request.form.to_dict()
                logger.debug(f"收到表单数据: {data}")
            else:
                logger.error(f"不支持的Content-Type: {request.content_type}")
                return jsonify({"success": False, "message": f"不支持的Content-Type: {request.content_type}"}), 415

        http_proxy = data.get('http_proxy', '')

        # 保存设置
        set_config('HTTP_PROXY', http_proxy, description='HTTP代理')

        # 如果提供了代理URL，尝试将其添加到代理配置表中
        if http_proxy:
            try:
                # 导入代理服务
                from services.proxy_service import create_proxy, get_all_proxies
                from urllib.parse import urlparse

                # 解析代理URL
                parsed = urlparse(http_proxy)
                protocol = parsed.scheme
                host = parsed.hostname
                port = parsed.port
                username = parsed.username
                password = parsed.password

                if host and port and protocol:
                    # 检查是否已存在相同的代理配置
                    existing_proxies = get_all_proxies()
                    exists = False

                    for proxy in existing_proxies:
                        if (proxy['host'] == host and
                            proxy['port'] == port and
                            proxy['protocol'] == protocol):
                            exists = True
                            break

                    # 如果不存在，则创建新的代理配置
                    if not exists:
                        create_proxy(
                            name=f"从HTTP_PROXY导入的{protocol.upper()}代理",
                            host=host,
                            port=port,
                            protocol=protocol,
                            username=username,
                            password=password,
                            priority=0,  # 最高优先级
                            is_active=True
                        )
                        logger.info(f"已将代理URL添加到代理配置表: {protocol}://{host}:{port}")
            except ImportError:
                logger.warning("无法导入代理服务，跳过添加到代理配置表")
            except Exception as e:
                logger.warning(f"将代理URL添加到代理配置表时出错: {str(e)}")

        # 重新初始化代理管理器
        try:
            from utils.api_utils import get_proxy_manager
            get_proxy_manager(force_new=True)
            logger.info("代理管理器已重新初始化")
        except Exception as e:
            logger.warning(f"重新初始化代理管理器时出错: {str(e)}")

        logger.info(f"代理设置已更新: {http_proxy}")

        return jsonify({"success": True, "message": "代理设置已更新"})
    except Exception as e:
        logger.error(f"更新代理设置时出错: {str(e)}")
        return jsonify({"success": False, "message": f"更新设置失败: {str(e)}"}), 500



@settings_api.route('/batch', methods=['POST'])
def batch_update_settings():
    """批量更新设置"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        try:
            data = request.get_json() or {}
            logger.debug(f"收到JSON数据: {data}")
        except Exception as e:
            logger.error(f"解析JSON数据时出错: {str(e)}")
            if request.content_type == 'application/x-www-form-urlencoded':
                data = request.form.to_dict()
                logger.debug(f"收到表单数据: {data}")
            else:
                logger.error(f"不支持的Content-Type: {request.content_type}")
                return jsonify({"success": False, "message": f"不支持的Content-Type: {request.content_type}"}), 415

        configs = data.get('configs', {})
        update_env = data.get('update_env', True)

        if not configs:
            return jsonify({"success": False, "message": "未提供配置数据"}), 400

        # 批量更新配置
        updated_count, skipped_count = batch_set_configs(configs, update_env)

        logger.info(f"批量更新配置完成，更新了 {updated_count} 个配置项，跳过了 {skipped_count} 个配置项")

        return jsonify({
            "success": True,
            "message": f"批量更新配置完成，更新了 {updated_count} 个配置项，跳过了 {skipped_count} 个配置项",
            "updated_count": updated_count,
            "skipped_count": skipped_count
        })
    except Exception as e:
        logger.error(f"批量更新配置时出错: {str(e)}")
        return jsonify({"success": False, "message": f"批量更新配置失败: {str(e)}"}), 500

@settings_api.route('/db_clean', methods=['POST'])
def update_db_clean_settings():
    """更新数据库自动清理配置"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        try:
            data = request.get_json() or {}
            logger.debug(f"收到JSON数据: {data}")
        except Exception as e:
            logger.error(f"解析JSON数据时出错: {str(e)}")
            if request.content_type == 'application/x-www-form-urlencoded':
                data = request.form.to_dict()
                logger.debug(f"收到表单数据: {data}")
            else:
                logger.error(f"不支持的Content-Type: {request.content_type}")
                return jsonify({"success": False, "message": f"不支持的Content-Type: {request.content_type}"}), 415

        # 获取配置参数
        db_auto_clean_enabled = data.get('db_auto_clean_enabled', 'false')
        db_auto_clean_time = data.get('db_auto_clean_time', '03:00')
        db_clean_by_count = data.get('db_clean_by_count', 'false')
        db_max_records = data.get('db_max_records', '100')
        db_retention_days = data.get('db_retention_days', '30')
        db_clean_irrelevant_only = data.get('db_clean_irrelevant_only', 'true')

        # 处理布尔值
        if isinstance(db_auto_clean_enabled, str):
            db_auto_clean_enabled = db_auto_clean_enabled.lower() == 'on' or db_auto_clean_enabled.lower() == 'true'

        if isinstance(db_clean_by_count, str):
            db_clean_by_count = db_clean_by_count.lower() == 'on' or db_clean_by_count.lower() == 'true'

        if isinstance(db_clean_irrelevant_only, str):
            db_clean_irrelevant_only = db_clean_irrelevant_only.lower() == 'on' or db_clean_irrelevant_only.lower() == 'true'

        # 验证参数
        try:
            # 验证时间格式
            if not db_auto_clean_time or len(db_auto_clean_time.split(':')) != 2:
                return jsonify({"success": False, "message": "自动清理时间格式不正确，应为HH:MM格式"}), 400

            # 验证最大记录数
            max_records = int(db_max_records)
            if max_records < 10 or max_records > 10000:
                return jsonify({"success": False, "message": "每个账号保留的最大记录数必须在10-10000之间"}), 400

            # 验证保留天数
            retention_days = int(db_retention_days)
            if retention_days < 1 or retention_days > 365:
                return jsonify({"success": False, "message": "数据保留天数必须在1-365之间"}), 400
        except ValueError:
            return jsonify({"success": False, "message": "参数格式不正确，请检查输入"}), 400

        # 保存设置
        set_config('DB_AUTO_CLEAN_ENABLED', 'true' if db_auto_clean_enabled else 'false', description='是否启用数据库自动清理')
        set_config('DB_AUTO_CLEAN_TIME', db_auto_clean_time, description='数据库自动清理时间')
        set_config('DB_CLEAN_BY_COUNT', 'true' if db_clean_by_count else 'false', description='是否基于数量清理')
        set_config('DB_MAX_RECORDS_PER_ACCOUNT', db_max_records, description='每个账号保留的最大记录数')
        set_config('DB_RETENTION_DAYS', db_retention_days, description='数据保留天数')
        set_config('DB_CLEAN_IRRELEVANT_ONLY', 'true' if db_clean_irrelevant_only else 'false', description='是否只清理不相关数据')

        logger.info(f"数据库自动清理配置已更新，启用状态: {db_auto_clean_enabled}, 清理方式: {'基于数量' if db_clean_by_count else '基于时间'}")

        return jsonify({
            "success": True,
            "message": "数据库自动清理配置已更新",
            "data": {
                "db_auto_clean_enabled": db_auto_clean_enabled,
                "db_auto_clean_time": db_auto_clean_time,
                "db_clean_by_count": db_clean_by_count,
                "db_max_records": db_max_records,
                "db_retention_days": db_retention_days,
                "db_clean_irrelevant_only": db_clean_irrelevant_only
            }
        })
    except Exception as e:
        logger.error(f"更新数据库自动清理配置时出错: {str(e)}")
        return jsonify({"success": False, "message": f"更新配置失败: {str(e)}"}), 500

@settings_api.route('/account', methods=['POST'])
def update_account_settings():
    """更新账号设置"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        try:
            data = request.get_json() or {}
            logger.debug(f"收到JSON数据: {data}")
        except Exception as e:
            logger.error(f"解析JSON数据时出错: {str(e)}")
            if request.content_type == 'application/x-www-form-urlencoded':
                data = request.form.to_dict()
                logger.debug(f"收到表单数据: {data}")
            else:
                logger.error(f"不支持的Content-Type: {request.content_type}")
                return jsonify({"success": False, "message": f"不支持的Content-Type: {request.content_type}"}), 415

        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')
        new_username = data.get('username', '').strip()

        # 验证参数
        if not current_password:
            return jsonify({"success": False, "message": "当前密码不能为空"}), 400

        # 验证当前密码
        user = User.query.get(session['user_id'])
        if not user.check_password(current_password):
            return jsonify({"success": False, "message": "当前密码不正确"}), 400

        # 跟踪是否有更改
        password_changed = False
        username_changed = False

        # 处理密码更改
        if new_password:
            if new_password != confirm_password:
                return jsonify({"success": False, "message": "新密码和确认密码不匹配"}), 400

            if len(new_password) < 6:
                return jsonify({"success": False, "message": "新密码长度不能少于6个字符"}), 400

            # 更新密码
            user.set_password(new_password)
            password_changed = True
            logger.info(f"用户 {user.username} 已更新密码")

        # 处理用户名更改
        if new_username and new_username != user.username:
            # 检查用户名是否已存在
            existing_user = User.query.filter_by(username=new_username).first()
            if existing_user:
                return jsonify({"success": False, "message": "该用户名已被使用"}), 400

            # 更新用户名
            old_username = user.username
            user.username = new_username
            username_changed = True
            logger.info(f"用户 {old_username} 已更改用户名为 {new_username}")

        # 如果有任何更改，提交到数据库
        if password_changed or username_changed:
            db.session.commit()

            # 如果用户名已更改，更新会话
            if username_changed:
                session['username'] = new_username

            return jsonify({
                "success": True,
                "message": "账号设置已更新",
                "password_changed": password_changed,
                "username_changed": username_changed
            })
        else:
            return jsonify({"success": True, "message": "没有进行任何更改"})
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新账号设置时出错: {str(e)}")
        return jsonify({"success": False, "message": f"更新设置失败: {str(e)}"}), 500

@settings_api.route('/ai_providers', methods=['GET'])
def get_ai_providers():
    """获取AI提供商列表"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取所有AI提供商
        providers = AIProvider.query.all()

        return jsonify({
            "success": True,
            "providers": [provider.to_dict() for provider in providers]
        })
    except Exception as e:
        logger.error(f"获取AI提供商列表时出错: {str(e)}")
        return jsonify({"success": False, "message": f"获取AI提供商列表失败: {str(e)}"}), 500

@settings_api.route('/ai_providers/<int:provider_id>', methods=['GET'])
def get_ai_provider(provider_id):
    """获取特定AI提供商"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取特定AI提供商
        provider = AIProvider.query.get(provider_id)

        if not provider:
            return jsonify({"success": False, "message": "AI提供商不存在"}), 404

        return jsonify({
            "success": True,
            "provider": provider.to_dict()
        })
    except Exception as e:
        logger.error(f"获取AI提供商时出错: {str(e)}")
        return jsonify({"success": False, "message": f"获取AI提供商失败: {str(e)}"}), 500

@settings_api.route('/ai_providers', methods=['POST'])
def create_ai_provider():
    """创建AI提供商"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求数据
        data = request.get_json() or {}

        # 验证必要字段
        required_fields = ['name', 'api_key', 'api_base', 'model']
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "message": f"缺少必要字段: {field}"}), 400

        # 检查名称是否已存在
        existing = AIProvider.query.filter_by(name=data['name']).first()
        if existing:
            return jsonify({"success": False, "message": "该名称已存在"}), 400

        # 创建新的AI提供商
        provider = AIProvider(
            name=data['name'],
            api_key=data['api_key'],
            api_base=data['api_base'],
            model=data['model'],
            priority=data.get('priority', 0),
            is_active=data.get('is_active', True),
            supports_text=data.get('supports_text', True),
            supports_image=data.get('supports_image', False),
            supports_video=data.get('supports_video', False),
            supports_gif=data.get('supports_gif', False)
        )

        db.session.add(provider)
        db.session.commit()

        logger.info(f"AI提供商已创建: {provider.name}")
        return jsonify({
            "success": True,
            "message": "AI提供商已创建",
            "provider": provider.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建AI提供商时出错: {str(e)}")
        return jsonify({"success": False, "message": f"创建AI提供商失败: {str(e)}"}), 500

@settings_api.route('/ai_providers/<int:provider_id>', methods=['PUT'])
def update_ai_provider(provider_id):
    """更新AI提供商"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取特定AI提供商
        provider = AIProvider.query.get(provider_id)

        if not provider:
            return jsonify({"success": False, "message": "AI提供商不存在"}), 404

        # 获取请求数据
        data = request.get_json() or {}

        # 更新字段
        if 'name' in data:
            # 检查名称是否已存在
            existing = AIProvider.query.filter(AIProvider.name == data['name'], AIProvider.id != provider_id).first()
            if existing:
                return jsonify({"success": False, "message": "该名称已存在"}), 400
            provider.name = data['name']

        if 'api_key' in data and data['api_key'] and not data['api_key'].startswith('******'):
            provider.api_key = data['api_key']

        if 'api_base' in data:
            provider.api_base = data['api_base']

        if 'model' in data:
            provider.model = data['model']

        if 'priority' in data:
            provider.priority = data['priority']

        if 'is_active' in data:
            provider.is_active = data['is_active']

        if 'supports_text' in data:
            provider.supports_text = data['supports_text']

        if 'supports_image' in data:
            provider.supports_image = data['supports_image']

        if 'supports_video' in data:
            provider.supports_video = data['supports_video']

        if 'supports_gif' in data:
            provider.supports_gif = data['supports_gif']

        db.session.commit()

        logger.info(f"AI提供商已更新: {provider.name}")
        return jsonify({
            "success": True,
            "message": "AI提供商已更新",
            "provider": provider.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新AI提供商时出错: {str(e)}")
        return jsonify({"success": False, "message": f"更新AI提供商失败: {str(e)}"}), 500

@settings_api.route('/ai_providers/<int:provider_id>', methods=['DELETE'])
def delete_ai_provider(provider_id):
    """删除AI提供商"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取特定AI提供商
        provider = AIProvider.query.get(provider_id)

        if not provider:
            return jsonify({"success": False, "message": "AI提供商不存在"}), 404

        # 检查是否有社交账号引用了此提供商
        from models.social_account import SocialAccount
        accounts_using_provider = SocialAccount.query.filter(
            (SocialAccount.ai_provider_id == provider_id) |
            (SocialAccount.text_provider_id == provider_id) |
            (SocialAccount.image_provider_id == provider_id) |
            (SocialAccount.video_provider_id == provider_id) |
            (SocialAccount.gif_provider_id == provider_id)
        ).all()

        if accounts_using_provider:
            account_names = [f"@{account.account_id}" for account in accounts_using_provider]
            return jsonify({
                "success": False,
                "message": f"无法删除此AI提供商，因为它正在被以下账号使用: {', '.join(account_names)}"
            }), 400

        # 删除AI提供商
        name = provider.name
        db.session.delete(provider)
        db.session.commit()

        logger.info(f"AI提供商已删除: {name}")
        return jsonify({
            "success": True,
            "message": f"AI提供商 {name} 已成功删除"
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除AI提供商时出错: {str(e)}")
        return jsonify({
            "success": False,
            "message": f"删除AI提供商失败: {str(e)}"
        }), 500
