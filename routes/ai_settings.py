"""
AI设置路由模块
提供AI设置页面和相关API
"""

import os
import json
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import login_required, current_user
from sqlalchemy import desc, or_

from models.ai_provider import AIProvider
from models.ai_request_log import AIRequestLog
from web_app import db
from services.config_service import get_config, set_config
from services.ai_polling_service import ai_polling_service
from utils.logger import get_logger

# 创建日志记录器
logger = get_logger('web_app')

# 创建蓝图
ai_settings_bp = Blueprint('ai_settings', __name__)

@ai_settings_bp.route('/ai_settings')
@login_required
def ai_settings_page():
    """AI设置页面"""
    # 获取AI配置
    llm_api_key = get_config('LLM_API_KEY', '')
    llm_api_model = get_config('LLM_API_MODEL', '')
    llm_api_base = get_config('LLM_API_BASE', '')

    # 获取AI轮询配置
    ai_polling_enabled = get_config('AI_POLLING_ENABLED', 'true').lower() == 'true'
    ai_auto_health_check_enabled = get_config('AI_AUTO_HEALTH_CHECK_ENABLED', 'true').lower() == 'true'
    ai_health_check_interval = int(get_config('AI_HEALTH_CHECK_INTERVAL', '30'))
    ai_cache_enabled = get_config('AI_CACHE_ENABLED', 'true').lower() == 'true'
    ai_cache_ttl = int(get_config('AI_CACHE_TTL', '3600'))
    ai_batch_enabled = get_config('AI_BATCH_ENABLED', 'false').lower() == 'true'

    # 获取当前时间
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return render_template('ai_settings.html',
                          llm_api_key=llm_api_key,
                          llm_api_model=llm_api_model,
                          llm_api_base=llm_api_base,
                          ai_polling_enabled=ai_polling_enabled,
                          ai_auto_health_check_enabled=ai_auto_health_check_enabled,
                          ai_health_check_interval=ai_health_check_interval,
                          ai_cache_enabled=ai_cache_enabled,
                          ai_cache_ttl=ai_cache_ttl,
                          ai_batch_enabled=ai_batch_enabled,
                          now=now)

@ai_settings_bp.route('/api/ai_settings/providers')
@login_required
def get_ai_providers():
    """获取AI提供商列表"""
    try:
        providers = AIProvider.query.order_by(AIProvider.priority).all()

        # 转换为字典列表
        providers_list = []
        for provider in providers:
            # 获取提供商的请求统计
            stats = get_provider_stats(provider.id)

            providers_list.append({
                'id': provider.id,
                'name': provider.name,
                'api_base': provider.api_base,
                'model': provider.model,
                'priority': provider.priority,
                'is_active': provider.is_active,
                'supports_text': provider.supports_text,
                'supports_image': provider.supports_image,
                'supports_video': provider.supports_video,
                'supports_gif': provider.supports_gif,
                'request_count': stats['request_count'],
                'success_count': stats['success_count'],
                'error_count': stats['error_count'],
                'avg_response_time': stats['avg_response_time'],
                'health_status': stats['health_status'],
                'last_check_time': stats['last_check_time']
            })

        return jsonify({
            'success': True,
            'providers': providers_list
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取AI提供商列表失败: {str(e)}'
        }), 500

@ai_settings_bp.route('/api/ai_settings/providers', methods=['POST'])
@login_required
def add_ai_provider():
    """添加AI提供商"""
    try:
        data = request.json

        # 记录添加AI提供商请求
        logger.info(f"用户 {current_user.username} 请求添加AI提供商: {data.get('name')}")

        # 创建新提供商
        provider = AIProvider(
            name=data.get('name'),
            api_key=data.get('api_key'),
            api_base=data.get('api_base'),
            model=data.get('model'),
            priority=data.get('priority', 0),
            is_active=data.get('is_active', True),
            supports_text=data.get('supports_text', True),
            supports_image=data.get('supports_image', False),
            supports_video=data.get('supports_video', False),
            supports_gif=data.get('supports_gif', False)
        )

        db.session.add(provider)
        db.session.commit()

        # 记录添加成功
        logger.info(f"AI提供商添加成功: ID={provider.id}, 名称={provider.name}, 模型={provider.model}")

        return jsonify({
            'success': True,
            'message': 'AI提供商添加成功',
            'provider_id': provider.id
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"添加AI提供商失败: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'添加AI提供商失败: {str(e)}'
        }), 500

@ai_settings_bp.route('/api/ai_settings/providers/<int:provider_id>', methods=['GET'])
@login_required
def get_ai_provider(provider_id):
    """获取AI提供商详情"""
    try:
        provider = AIProvider.query.get(provider_id)
        if not provider:
            return jsonify({
                'success': False,
                'message': f'未找到ID为{provider_id}的AI提供商'
            }), 404

        # 获取提供商的请求统计
        stats = get_provider_stats(provider_id)

        return jsonify({
            'success': True,
            'provider': {
                'id': provider.id,
                'name': provider.name,
                'api_base': provider.api_base,
                'model': provider.model,
                'priority': provider.priority,
                'is_active': provider.is_active,
                'supports_text': provider.supports_text,
                'supports_image': provider.supports_image,
                'supports_video': provider.supports_video,
                'supports_gif': provider.supports_gif,
                'request_count': stats['request_count'],
                'success_count': stats['success_count'],
                'error_count': stats['error_count'],
                'avg_response_time': stats['avg_response_time'],
                'health_status': stats['health_status'],
                'last_check_time': stats['last_check_time']
            }
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'获取AI提供商详情失败: {str(e)}'
        }), 500

def get_provider_stats(provider_id):
    """获取提供商的请求统计"""
    try:
        # 获取最近24小时的请求日志
        cutoff_time = datetime.now(timezone.utc) - timedelta(hours=24)
        logs = AIRequestLog.query.filter_by(provider_id=provider_id).filter(
            AIRequestLog.created_at >= cutoff_time
        ).all()

        request_count = len(logs)
        success_count = sum(1 for log in logs if log.is_success)
        error_count = request_count - success_count

        # 计算平均响应时间
        if success_count > 0:
            avg_response_time = sum(log.response_time for log in logs if log.is_success) / success_count
        else:
            avg_response_time = 0

        # 简化健康状态计算，只有可用和不可用两种状态
        if request_count == 0:
            health_status = 'unknown'
        elif success_count / request_count >= 0.5:  # 成功率超过50%即视为可用
            health_status = 'available'
        else:
            health_status = 'unavailable'

        # 获取最后检查时间
        last_check = AIRequestLog.query.filter_by(
            provider_id=provider_id,
            request_type='health_check'
        ).order_by(desc(AIRequestLog.created_at)).first()

        last_check_time = last_check.created_at.isoformat() if last_check else None

        return {
            'request_count': request_count,
            'success_count': success_count,
            'error_count': error_count,
            'avg_response_time': round(avg_response_time, 2),
            'health_status': health_status,
            'last_check_time': last_check_time
        }
    except Exception as e:
        current_app.logger.error(f"获取提供商统计信息出错: {str(e)}")
        return {
            'request_count': 0,
            'success_count': 0,
            'error_count': 0,
            'avg_response_time': 0,
            'health_status': 'unknown',
            'last_check_time': None
        }

@ai_settings_bp.route('/api/ai_settings/polling_status')
@login_required
def get_polling_status():
    """获取AI轮询状态"""
    try:
        # 使用AI轮询服务获取状态
        status = ai_polling_service.get_status()

        return jsonify({
            'success': True,
            'status': status
        })
    except Exception as e:
        current_app.logger.error(f"获取AI轮询状态出错: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取AI轮询状态失败: {str(e)}'
        }), 500

@ai_settings_bp.route('/api/ai_settings/cache_stats')
@login_required
def get_cache_stats():
    """获取缓存统计信息"""
    try:
        # 使用AI轮询服务获取缓存统计
        stats = ai_polling_service.get_cache_stats()

        return jsonify({
            'success': True,
            'stats': stats
        })
    except Exception as e:
        current_app.logger.error(f"获取缓存统计信息出错: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'获取缓存统计信息失败: {str(e)}'
        }), 500

@ai_settings_bp.route('/api/ai_settings/polling_settings', methods=['POST'])
@login_required
def update_polling_settings():
    """更新AI轮询设置"""
    try:
        data = request.json

        # 更新配置
        set_config('AI_POLLING_ENABLED', data.get('ai_polling_enabled', 'true'))
        set_config('AI_AUTO_HEALTH_CHECK_ENABLED', data.get('ai_auto_health_check_enabled', 'true'))
        set_config('AI_HEALTH_CHECK_INTERVAL', data.get('ai_health_check_interval', '30'))
        set_config('AI_CACHE_ENABLED', data.get('ai_cache_enabled', 'true'))
        set_config('AI_CACHE_TTL', data.get('ai_cache_ttl', '3600'))
        set_config('AI_BATCH_ENABLED', data.get('ai_batch_enabled', 'false'))

        # 如果启用了轮询，启动轮询服务
        if data.get('ai_polling_enabled') == 'true':
            ai_polling_service.start()
        else:
            ai_polling_service.stop()

        return jsonify({
            'success': True,
            'message': 'AI轮询设置已更新'
        })
    except Exception as e:
        current_app.logger.error(f"更新AI轮询设置出错: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'更新AI轮询设置失败: {str(e)}'
        }), 500

@ai_settings_bp.route('/api/ai_settings/run_health_check', methods=['POST'])
@login_required
def run_health_check():
    """运行健康检查"""
    try:
        # 记录开始运行健康检查
        logger.info(f"用户 {current_user.username} 手动触发健康检查")

        # 使用AI轮询服务运行健康检查
        results = ai_polling_service.run_health_check()

        # 记录健康检查结果
        success_count = sum(1 for r in results.values() if isinstance(r, dict) and r.get('is_success', False))
        total_count = len(results)
        logger.info(f"健康检查完成: 成功 {success_count}/{total_count}")

        return jsonify({
            'success': True,
            'results': results
        })
    except Exception as e:
        logger.error(f"运行健康检查出错: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'运行健康检查失败: {str(e)}'
        }), 500

@ai_settings_bp.route('/api/ai_settings/clear_cache', methods=['POST'])
@login_required
def clear_cache():
    """清空缓存"""
    try:
        # 记录开始清空缓存
        logger.info(f"用户 {current_user.username} 请求清空AI缓存")

        # 使用AI轮询服务清空缓存
        count = ai_polling_service.clear_cache()

        # 记录清空缓存结果
        logger.info(f"AI缓存已清空: {count} 项")

        return jsonify({
            'success': True,
            'count': count,
            'message': f'已清空 {count} 项缓存'
        })
    except Exception as e:
        logger.error(f"清空缓存出错: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'清空缓存失败: {str(e)}'
        }), 500

@ai_settings_bp.route('/api/ai_settings/providers/<int:provider_id>', methods=['PUT'])
@login_required
def update_ai_provider(provider_id):
    """更新AI提供商"""
    try:
        provider = AIProvider.query.get(provider_id)
        if not provider:
            logger.warning(f"用户 {current_user.username} 尝试更新不存在的AI提供商: ID={provider_id}")
            return jsonify({
                'success': False,
                'message': f'未找到ID为{provider_id}的AI提供商'
            }), 404

        data = request.json

        # 记录更新AI提供商请求
        logger.info(f"用户 {current_user.username} 请求更新AI提供商: ID={provider_id}, 名称={provider.name}")

        # 更新提供商信息
        old_name = provider.name
        old_model = provider.model

        provider.name = data.get('name', provider.name)
        provider.api_base = data.get('api_base', provider.api_base)
        provider.model = data.get('model', provider.model)
        provider.priority = data.get('priority', provider.priority)
        provider.is_active = data.get('is_active', provider.is_active)
        provider.supports_text = data.get('supports_text', provider.supports_text)
        provider.supports_image = data.get('supports_image', provider.supports_image)
        provider.supports_video = data.get('supports_video', provider.supports_video)
        provider.supports_gif = data.get('supports_gif', provider.supports_gif)

        # 如果提供了API密钥，则更新
        api_key_updated = False
        if data.get('api_key'):
            provider.api_key = data.get('api_key')
            api_key_updated = True

        db.session.commit()

        # 记录更新成功
        changes = []
        if old_name != provider.name:
            changes.append(f"名称: {old_name} -> {provider.name}")
        if old_model != provider.model:
            changes.append(f"模型: {old_model} -> {provider.model}")
        if api_key_updated:
            changes.append("API密钥已更新")

        logger.info(f"AI提供商更新成功: ID={provider_id}, {', '.join(changes) if changes else '无变更'}")

        return jsonify({
            'success': True,
            'message': 'AI提供商更新成功'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"更新AI提供商出错: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'更新AI提供商失败: {str(e)}'
        }), 500

@ai_settings_bp.route('/api/ai_settings/providers/<int:provider_id>', methods=['DELETE'])
@login_required
def delete_ai_provider(provider_id):
    """删除AI提供商"""
    try:
        provider = AIProvider.query.get(provider_id)
        if not provider:
            logger.warning(f"用户 {current_user.username} 尝试删除不存在的AI提供商: ID={provider_id}")
            return jsonify({
                'success': False,
                'message': f'未找到ID为{provider_id}的AI提供商'
            }), 404

        # 记录删除AI提供商请求
        logger.info(f"用户 {current_user.username} 请求删除AI提供商: ID={provider_id}, 名称={provider.name}")

        # 保存提供商信息用于日志记录
        provider_name = provider.name
        provider_model = provider.model

        db.session.delete(provider)
        db.session.commit()

        # 记录删除成功
        logger.info(f"AI提供商删除成功: ID={provider_id}, 名称={provider_name}, 模型={provider_model}")

        return jsonify({
            'success': True,
            'message': 'AI提供商删除成功'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"删除AI提供商出错: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'删除AI提供商失败: {str(e)}'
        }), 500

@ai_settings_bp.route('/api/ai_settings/providers/<int:provider_id>/toggle', methods=['POST'])
@login_required
def toggle_ai_provider(provider_id):
    """切换AI提供商状态"""
    try:
        provider = AIProvider.query.get(provider_id)
        if not provider:
            logger.warning(f"用户 {current_user.username} 尝试切换不存在的AI提供商状态: ID={provider_id}")
            return jsonify({
                'success': False,
                'message': f'未找到ID为{provider_id}的AI提供商'
            }), 404

        data = request.json
        is_active = data.get('is_active', not provider.is_active)

        # 记录切换AI提供商状态请求
        old_status = "启用" if provider.is_active else "禁用"
        new_status = "启用" if is_active else "禁用"
        logger.info(f"用户 {current_user.username} 请求切换AI提供商状态: ID={provider_id}, 名称={provider.name}, {old_status} -> {new_status}")

        provider.is_active = is_active
        db.session.commit()

        # 记录切换成功
        logger.info(f"AI提供商状态已切换: ID={provider_id}, 名称={provider.name}, 当前状态={new_status}")

        return jsonify({
            'success': True,
            'message': f'AI提供商已{is_active and "启用" or "禁用"}'
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"切换AI提供商状态出错: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'切换AI提供商状态失败: {str(e)}'
        }), 500

@ai_settings_bp.route('/api/ai_settings/reset_stats', methods=['POST'])
@login_required
def reset_stats():
    """重置统计数据"""
    try:
        # 记录重置统计数据请求
        logger.info(f"用户 {current_user.username} 请求重置AI统计数据")

        # 获取请求参数
        data = request.json
        provider_id = data.get('provider_id')

        # 如果提供了provider_id，只重置该提供商的统计数据
        if provider_id:
            provider = AIProvider.query.get(provider_id)
            if not provider:
                return jsonify({
                    'success': False,
                    'message': f'未找到ID为{provider_id}的AI提供商'
                }), 404

            # 删除该提供商的请求日志
            AIRequestLog.query.filter_by(provider_id=provider_id).delete()
            db.session.commit()

            logger.info(f"已重置AI提供商 {provider.name} (ID={provider_id}) 的统计数据")
            message = f"已重置 {provider.name} 的统计数据"
        else:
            # 重置所有统计数据
            AIRequestLog.query.delete()
            db.session.commit()

            # 重置提供商可用性状态
            ai_polling_service.reset_provider_availability()

            # 重置计数器 - 通过直接修改ai_polling_service模块中的变量
            import services.ai_polling_service as aps
            aps._health_check_count = 0
            aps._cache_hit_count = 0
            aps._cache_miss_count = 0
            aps._batch_processed_count = 0

            logger.info("已重置所有AI统计数据")
            message = "已重置所有AI统计数据"

        return jsonify({
            'success': True,
            'message': message
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"重置统计数据出错: {str(e)}")
        return jsonify({
            'success': False,
            'message': f'重置统计数据失败: {str(e)}'
        }), 500
