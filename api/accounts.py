"""
账号管理API模块
处理所有账号相关的API请求
"""

import logging
from flask import Blueprint, request, jsonify, session, current_app
from models import db, SocialAccount
from services.config_service import get_default_prompt_template
from utils.yaml_utils import sync_accounts_to_yaml
from modules.socialmedia.twitter import check_account_status

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

@accounts_api.route('/list', methods=['GET'])
def list_accounts():
    """获取所有账号的简单列表"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        accounts = SocialAccount.query.all()
        return jsonify({
            "success": True,
            "accounts": [
                {
                    "id": account.id,
                    "type": account.type,
                    "account_id": account.account_id,
                    "tag": account.tag,
                    "avatar_url": account.avatar_url
                } for account in accounts
            ]
        })
    except Exception as e:
        logger.error(f"获取账号列表时出错: {str(e)}")
        return jsonify({"success": False, "message": f"获取账号列表失败: {str(e)}"}), 500

@accounts_api.route('/<account_id>', methods=['GET'])
def get_account(account_id):
    """获取特定账号"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 尝试将account_id转换为整数（兼容旧版本的路由）
        try:
            id_as_int = int(account_id)
            account = SocialAccount.query.get(id_as_int)
            if account:
                logger.info(f"通过ID查找账号: {id_as_int}")
            else:
                # 如果找不到，尝试通过account_id查找
                account = SocialAccount.query.filter_by(account_id=account_id).first()
                if account:
                    logger.info(f"通过account_id查找账号: {account_id}")
                else:
                    logger.error(f"未找到账号: {account_id}")
                    return jsonify({"success": False, "message": "账号不存在"}), 404
        except ValueError:
            # 如果不是整数，直接通过account_id查找
            account = SocialAccount.query.filter_by(account_id=account_id).first()
            if account:
                logger.info(f"通过account_id查找账号: {account_id}")
            else:
                logger.error(f"未找到账号: {account_id}")
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
        bypass_ai = data.get('bypass_ai', False)
        prompt_template = data.get('prompt_template')
        auto_reply_template = data.get('auto_reply_template')

        # AI提供商相关字段
        ai_provider_id = data.get('ai_provider_id')
        text_provider_id = data.get('text_provider_id')
        image_provider_id = data.get('image_provider_id')
        video_provider_id = data.get('video_provider_id')
        gif_provider_id = data.get('gif_provider_id')

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
            bypass_ai=bypass_ai,
            prompt_template=prompt_template,
            auto_reply_template=auto_reply_template,
            ai_provider_id=ai_provider_id,
            text_provider_id=text_provider_id,
            image_provider_id=image_provider_id,
            video_provider_id=video_provider_id,
            gif_provider_id=gif_provider_id
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

@accounts_api.route('/<account_id>', methods=['PUT'])
def update_account(account_id):
    """更新账号"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 尝试将account_id转换为整数（兼容旧版本的路由）
        try:
            id_as_int = int(account_id)
            account = SocialAccount.query.get(id_as_int)
            if account:
                logger.info(f"通过ID查找账号: {id_as_int}")
            else:
                # 如果找不到，尝试通过account_id查找
                account = SocialAccount.query.filter_by(account_id=account_id).first()
                if account:
                    logger.info(f"通过account_id查找账号: {account_id}")
                else:
                    logger.error(f"未找到账号: {account_id}")
                    return jsonify({"success": False, "message": "账号不存在"}), 404
        except ValueError:
            # 如果不是整数，直接通过account_id查找
            account = SocialAccount.query.filter_by(account_id=account_id).first()
            if account:
                logger.info(f"通过account_id查找账号: {account_id}")
            else:
                logger.error(f"未找到账号: {account_id}")
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
        if 'bypass_ai' in data:
            account.bypass_ai = data['bypass_ai']
        if 'prompt_template' in data:
            account.prompt_template = data['prompt_template']
        if 'auto_reply_template' in data:
            account.auto_reply_template = data['auto_reply_template']

        # 更新AI提供商相关字段
        if 'ai_provider_id' in data:
            account.ai_provider_id = data['ai_provider_id']
        if 'text_provider_id' in data:
            account.text_provider_id = data['text_provider_id']
        if 'image_provider_id' in data:
            account.image_provider_id = data['image_provider_id']
        if 'video_provider_id' in data:
            account.video_provider_id = data['video_provider_id']
        if 'gif_provider_id' in data:
            account.gif_provider_id = data['gif_provider_id']

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

@accounts_api.route('/<account_id>', methods=['DELETE'])
def delete_account(account_id):
    """删除账号"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 尝试将account_id转换为整数（兼容旧版本的路由）
        try:
            id_as_int = int(account_id)
            account = SocialAccount.query.get(id_as_int)
            if account:
                logger.info(f"通过ID查找账号: {id_as_int}")
            else:
                # 如果找不到，尝试通过account_id查找
                account = SocialAccount.query.filter_by(account_id=account_id).first()
                if account:
                    logger.info(f"通过account_id查找账号: {account_id}")
                else:
                    logger.error(f"未找到账号: {account_id}")
                    return jsonify({"success": False, "message": "账号不存在"}), 404
        except ValueError:
            # 如果不是整数，直接通过account_id查找
            account = SocialAccount.query.filter_by(account_id=account_id).first()
            if account:
                logger.info(f"通过account_id查找账号: {account_id}")
            else:
                logger.error(f"未找到账号: {account_id}")
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

@accounts_api.route('/<account_id>/refresh', methods=['POST'])
def refresh_account_info(account_id):
    """刷新账号信息"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 查找账号
        account = SocialAccount.query.filter_by(account_id=account_id).first()
        if not account:
            logger.error(f"未找到账号: {account_id}")
            return jsonify({"success": False, "message": "账号不存在"}), 404

        # 只支持Twitter账号
        if account.type != 'twitter':
            logger.error(f"不支持的账号类型: {account.type}")
            return jsonify({"success": False, "message": f"不支持的账号类型: {account.type}"}), 400

        # 调用Twitter API获取最新账号信息
        logger.info(f"开始刷新账号信息: {account_id}")

        # 强制刷新，不使用缓存
        try:
            # 使用系统的Redis客户端删除缓存
            from utils.redisClient import redis_client

            cache_key = f"twitter:account_status:{account_id}"
            redis_client.delete(cache_key)
            logger.info(f"已删除账号状态缓存: {cache_key}")
        except Exception as e:
            logger.warning(f"删除缓存时出错: {str(e)}")

        # 获取最新账号信息
        try:
            account_status = check_account_status(account_id)

            if account_status.get("error"):
                error_msg = account_status['error']
                logger.error(f"获取账号信息时出错: {error_msg}")

                # 根据错误类型提供更友好的错误信息
                if "Twitter客户端初始化失败" in error_msg or "未找到任何Twitter登录凭据" in error_msg:
                    return jsonify({
                        "success": False,
                        "message": "Twitter配置缺失，请先在设置页面配置Twitter登录凭据",
                        "action": "configure_twitter",
                        "config_url": f"http://{request.host}/unified_settings#twitter"
                    }), 400
                elif "账号不存在" in error_msg:
                    return jsonify({
                        "success": False,
                        "message": "该Twitter账号不存在或已被删除"
                    }), 404
                elif "账号受保护" in error_msg:
                    return jsonify({
                        "success": False,
                        "message": "该Twitter账号受保护，无法获取详细信息"
                    }), 403
                elif "账号已被暂停" in error_msg:
                    return jsonify({
                        "success": False,
                        "message": "该Twitter账号已被暂停"
                    }), 403
                else:
                    return jsonify({
                        "success": False,
                        "message": f"获取账号信息失败: {error_msg}"
                    }), 500

            # 如果没有错误，检查是否成功获取到账号信息
            if not account_status.get("exists"):
                return jsonify({
                    "success": False,
                    "message": "无法验证账号存在性，可能是网络问题"
                }), 500

        except Exception as status_error:
            logger.error(f"调用check_account_status时出错: {str(status_error)}")
            return jsonify({
                "success": False,
                "message": f"检查账号状态时出错: {str(status_error)}"
            }), 500

        # 获取更新后的账号信息
        updated_account = SocialAccount.query.filter_by(account_id=account_id).first()

        if not updated_account:
            logger.error(f"刷新后未找到账号: {account_id}")
            return jsonify({
                "success": False,
                "message": "账号信息刷新后未找到对应记录"
            }), 404

        logger.info(f"成功刷新账号信息: {account_id}")
        return jsonify({
            "success": True,
            "message": "账号信息已成功刷新",
            "data": updated_account.to_dict()
        })
    except Exception as e:
        logger.error(f"刷新账号信息时出错: {str(e)}")
        return jsonify({"success": False, "message": f"刷新账号信息失败: {str(e)}"}), 500

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
