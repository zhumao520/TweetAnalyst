"""
AI提供商管理API
"""

from flask import Blueprint, request, jsonify
from flask_login import login_required
from models.ai_provider import AIProvider
from flask import current_app
import logging

# 创建蓝图
ai_provider_bp = Blueprint('ai_provider', __name__)

# 获取日志记录器
logger = logging.getLogger(__name__)

@ai_provider_bp.route('/ai_providers', methods=['GET'])
@login_required
def get_ai_providers():
    """获取所有AI提供商"""
    try:
        providers = AIProvider.query.order_by(AIProvider.priority).all()
        return jsonify({
            'success': True,
            'providers': [provider.to_dict() for provider in providers]
        })
    except Exception as e:
        logger.error(f"获取AI提供商列表时出错: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"获取AI提供商列表时出错: {str(e)}"
        }), 500

@ai_provider_bp.route('/ai_provider/<int:provider_id>', methods=['GET'])
@login_required
def get_ai_provider(provider_id):
    """获取指定AI提供商"""
    try:
        provider = AIProvider.query.get(provider_id)
        if not provider:
            return jsonify({
                'success': False,
                'message': f"未找到ID为{provider_id}的AI提供商"
            }), 404

        return jsonify({
            'success': True,
            'provider': provider.to_dict()
        })
    except Exception as e:
        logger.error(f"获取AI提供商时出错: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"获取AI提供商时出错: {str(e)}"
        }), 500

@ai_provider_bp.route('/ai_provider', methods=['POST'])
@login_required
def create_ai_provider():
    """创建AI提供商"""
    try:
        data = request.json

        # 验证必要字段
        required_fields = ['name', 'api_key', 'api_base', 'model']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({
                    'success': False,
                    'message': f"缺少必要字段: {field}"
                }), 400

        # 检查名称是否已存在
        existing = AIProvider.query.filter_by(name=data['name']).first()
        if existing:
            return jsonify({
                'success': False,
                'message': f"名称 '{data['name']}' 已存在"
            }), 400

        # 创建新提供商
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

        current_app.extensions['sqlalchemy'].session.add(provider)
        current_app.extensions['sqlalchemy'].session.commit()

        logger.info(f"创建AI提供商成功: {provider.name}")
        return jsonify({
            'success': True,
            'message': f"创建AI提供商成功: {provider.name}",
            'provider': provider.to_dict()
        })
    except Exception as e:
        current_app.extensions['sqlalchemy'].session.rollback()
        logger.error(f"创建AI提供商时出错: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"创建AI提供商时出错: {str(e)}"
        }), 500

@ai_provider_bp.route('/ai_provider/<int:provider_id>', methods=['PUT'])
@login_required
def update_ai_provider(provider_id):
    """更新AI提供商"""
    try:
        provider = AIProvider.query.get(provider_id)
        if not provider:
            return jsonify({
                'success': False,
                'message': f"未找到ID为{provider_id}的AI提供商"
            }), 404

        data = request.json

        # 检查名称是否已存在（排除当前提供商）
        if 'name' in data and data['name'] != provider.name:
            existing = AIProvider.query.filter_by(name=data['name']).first()
            if existing and existing.id != provider_id:
                return jsonify({
                    'success': False,
                    'message': f"名称 '{data['name']}' 已存在"
                }), 400

        # 更新字段
        if 'name' in data:
            provider.name = data['name']
        if 'api_key' in data and data['api_key']:
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

        current_app.extensions['sqlalchemy'].session.commit()

        logger.info(f"更新AI提供商成功: {provider.name}")
        return jsonify({
            'success': True,
            'message': f"更新AI提供商成功: {provider.name}",
            'provider': provider.to_dict()
        })
    except Exception as e:
        current_app.extensions['sqlalchemy'].session.rollback()
        logger.error(f"更新AI提供商时出错: {str(e)}")
        return jsonify({
            'success': False,
            'message': f"更新AI提供商时出错: {str(e)}"
        }), 500

@ai_provider_bp.route('/ai_provider/<int:provider_id>', methods=['DELETE'])
@login_required
def delete_ai_provider(provider_id):
    """删除AI提供商"""
    try:
        provider = AIProvider.query.get(provider_id)
        if not provider:
            return jsonify({
                'success': False,
                'message': f"未找到ID为{provider_id}的AI提供商"
            }), 404

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
                'success': False,
                'message': f"无法删除此AI提供商，因为它正在被以下账号使用: {', '.join(account_names)}"
            }), 400

        name = provider.name
        current_app.extensions['sqlalchemy'].session.delete(provider)
        current_app.extensions['sqlalchemy'].session.commit()

        logger.info(f"删除AI提供商成功: {name}")
        return jsonify({
            'success': True,
            'message': f"删除AI提供商成功: {name}"
        })
    except Exception as e:
        current_app.extensions['sqlalchemy'].session.rollback()
        logger.error(f"删除AI提供商时出错: {str(e)}")
        # 确保返回的是有效的JSON响应
        return jsonify({
            'success': False,
            'message': f"删除AI提供商时出错: {str(e)}"
        }), 500
