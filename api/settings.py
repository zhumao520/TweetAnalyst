"""
设置API模块
处理所有设置相关的API请求
"""

import os
import json
import logging
from flask import Blueprint, request, jsonify, session, current_app
from utils.config import set_config, get_config
from models import db, User

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
        data = request.get_json() or {}
        if request.content_type == 'application/x-www-form-urlencoded':
            data = request.form.to_dict()

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
        data = request.get_json() or {}
        if request.content_type == 'application/x-www-form-urlencoded':
            data = request.form.to_dict()

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
        data = request.get_json() or {}
        if request.content_type == 'application/x-www-form-urlencoded':
            data = request.form.to_dict()

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
        
        return jsonify({"success": True, "message": "Twitter设置已更新"})
    except Exception as e:
        logger.error(f"更新Twitter设置时出错: {str(e)}")
        return jsonify({"success": False, "message": f"更新设置失败: {str(e)}"}), 500

@settings_api.route('/llm', methods=['POST'])
def update_llm_settings():
    """更新LLM设置"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        data = request.get_json() or {}
        if request.content_type == 'application/x-www-form-urlencoded':
            data = request.form.to_dict()

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
    """更新代理设置"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        data = request.get_json() or {}
        if request.content_type == 'application/x-www-form-urlencoded':
            data = request.form.to_dict()

        http_proxy = data.get('http_proxy', '')
        
        # 保存设置
        set_config('HTTP_PROXY', http_proxy, description='HTTP代理')
        
        logger.info(f"代理设置已更新: {http_proxy}")
        
        return jsonify({"success": True, "message": "代理设置已更新"})
    except Exception as e:
        logger.error(f"更新代理设置时出错: {str(e)}")
        return jsonify({"success": False, "message": f"更新设置失败: {str(e)}"}), 500

@settings_api.route('/notification', methods=['POST'])
def update_notification_settings():
    """更新推送设置"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        data = request.get_json() or {}
        if request.content_type == 'application/x-www-form-urlencoded':
            data = request.form.to_dict()

        apprise_urls = data.get('apprise_urls', '')
        
        # 保存设置
        set_config('APPRISE_URLS', apprise_urls, description='Apprise推送URLs')
        
        logger.info("Apprise URLs已更新")
        
        return jsonify({"success": True, "message": "推送设置已更新"})
    except Exception as e:
        logger.error(f"更新推送设置时出错: {str(e)}")
        return jsonify({"success": False, "message": f"更新设置失败: {str(e)}"}), 500

@settings_api.route('/account', methods=['POST'])
def update_account_settings():
    """更新账号设置"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        data = request.get_json() or {}
        if request.content_type == 'application/x-www-form-urlencoded':
            data = request.form.to_dict()

        current_password = data.get('current_password', '')
        new_password = data.get('new_password', '')
        confirm_password = data.get('confirm_password', '')
        
        # 验证参数
        if not current_password:
            return jsonify({"success": False, "message": "当前密码不能为空"}), 400
        
        if not new_password:
            return jsonify({"success": False, "message": "新密码不能为空"}), 400
        
        if new_password != confirm_password:
            return jsonify({"success": False, "message": "新密码和确认密码不匹配"}), 400
        
        if len(new_password) < 6:
            return jsonify({"success": False, "message": "新密码长度不能少于6个字符"}), 400
        
        # 验证当前密码
        user = User.query.get(session['user_id'])
        if not user.check_password(current_password):
            return jsonify({"success": False, "message": "当前密码不正确"}), 400
        
        # 更新密码
        user.set_password(new_password)
        db.session.commit()
        
        logger.info(f"用户 {user.username} 已更新密码")
        
        return jsonify({"success": True, "message": "密码已成功更新"})
    except Exception as e:
        logger.error(f"更新账号设置时出错: {str(e)}")
        return jsonify({"success": False, "message": f"更新设置失败: {str(e)}"}), 500
