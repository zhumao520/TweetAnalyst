"""
账号管理API模块
处理所有账号相关的API请求
"""

import logging
from flask import Blueprint, request, jsonify, session, current_app
from models import db, SocialAccount
from utils.config import get_default_prompt_template
from utils.yaml_utils import sync_accounts_to_yaml

# 创建日志记录器
logger = logging.getLogger('api.accounts')

# 创建Blueprint
accounts_api = Blueprint('accounts_api', __name__, url_prefix='/accounts')

@accounts_api.route('/', methods=['GET'])
def get_accounts():
    """获取所有账号"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        accounts = SocialAccount.query.all()
        return jsonify({
            "success": True,
            "data": [account.to_dict() for account in accounts]
        })
    except Exception as e:
        logger.error(f"获取账号列表时出错: {str(e)}")
        return jsonify({"success": False, "message": f"获取账号列表失败: {str(e)}"}), 500

@accounts_api.route('/<int:account_id>', methods=['GET'])
def get_account(account_id):
    """获取特定账号"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        account = SocialAccount.query.get(account_id)
        if not account:
            return jsonify({"success": False, "message": "账号不存在"}), 404
        
        return jsonify({
            "success": True,
            "data": account.to_dict()
        })
    except Exception as e:
        logger.error(f"获取账号信息时出错: {str(e)}")
        return jsonify({"success": False, "message": f"获取账号信息失败: {str(e)}"}), 500

@accounts_api.route('/', methods=['POST'])
def create_account():
    """创建新账号"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        data = request.get_json() or {}
        
        account_type = data.get('type')
        account_id = data.get('account_id')
        tag = data.get('tag', 'all')
        enable_auto_reply = data.get('enable_auto_reply', False)
        prompt_template = data.get('prompt_template')
        auto_reply_template = data.get('auto_reply_template')
        
        # 验证必要参数
        if not account_type or not account_id:
            return jsonify({"success": False, "message": "平台类型和账号ID不能为空"}), 400
        
        # 检查账号是否已存在
        existing = SocialAccount.query.filter_by(
            type=account_type,
            account_id=account_id
        ).first()
        
        if existing:
            return jsonify({"success": False, "message": "该账号已存在"}), 400
        
        # 创建新账号
        new_account = SocialAccount(
            type=account_type,
            account_id=account_id,
            tag=tag,
            enable_auto_reply=enable_auto_reply,
            prompt_template=prompt_template,
            auto_reply_template=auto_reply_template
        )
        
        db.session.add(new_account)
        db.session.commit()
        
        # 同步到配置文件
        sync_accounts_to_yaml()
        
        logger.info(f"已添加新账号: {account_type}:{account_id}")
        
        return jsonify({
            "success": True,
            "message": "账号已成功添加",
            "data": new_account.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"创建账号时出错: {str(e)}")
        return jsonify({"success": False, "message": f"创建账号失败: {str(e)}"}), 500

@accounts_api.route('/<int:account_id>', methods=['PUT'])
def update_account(account_id):
    """更新账号"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取账号
        account = SocialAccount.query.get(account_id)
        if not account:
            return jsonify({"success": False, "message": "账号不存在"}), 404
        
        # 获取请求参数
        data = request.get_json() or {}
        
        # 更新账号信息
        if 'type' in data:
            account.type = data['type']
        if 'account_id' in data:
            account.account_id = data['account_id']
        if 'tag' in data:
            account.tag = data['tag']
        if 'enable_auto_reply' in data:
            account.enable_auto_reply = data['enable_auto_reply']
        if 'prompt_template' in data:
            account.prompt_template = data['prompt_template']
        if 'auto_reply_template' in data:
            account.auto_reply_template = data['auto_reply_template']
        
        db.session.commit()
        
        # 同步到配置文件
        sync_accounts_to_yaml()
        
        logger.info(f"已更新账号: {account.type}:{account.account_id}")
        
        return jsonify({
            "success": True,
            "message": "账号已成功更新",
            "data": account.to_dict()
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新账号时出错: {str(e)}")
        return jsonify({"success": False, "message": f"更新账号失败: {str(e)}"}), 500

@accounts_api.route('/<int:account_id>', methods=['DELETE'])
def delete_account(account_id):
    """删除账号"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取账号
        account = SocialAccount.query.get(account_id)
        if not account:
            return jsonify({"success": False, "message": "账号不存在"}), 404
        
        # 记录账号信息，用于日志
        account_info = f"{account.type}:{account.account_id}"
        
        # 删除账号
        db.session.delete(account)
        db.session.commit()
        
        # 同步到配置文件
        sync_accounts_to_yaml()
        
        logger.info(f"已删除账号: {account_info}")
        
        return jsonify({
            "success": True,
            "message": "账号已成功删除"
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除账号时出错: {str(e)}")
        return jsonify({"success": False, "message": f"删除账号失败: {str(e)}"}), 500

@accounts_api.route('/default_prompt/<account_type>', methods=['GET'])
def get_default_prompt(account_type):
    """获取默认提示词模板"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        prompt = get_default_prompt_template(account_type)
        return jsonify({
            "success": True,
            "data": {
                "prompt": prompt
            }
        })
    except Exception as e:
        logger.error(f"获取默认提示词模板时出错: {str(e)}")
        return jsonify({"success": False, "message": f"获取默认提示词模板失败: {str(e)}"}), 500
