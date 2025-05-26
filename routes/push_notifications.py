"""
推送通知路由
处理推送通知相关的Web请求
"""

import os
import logging
from datetime import datetime, timedelta, timezone
from flask import Blueprint, render_template, jsonify, request, current_app
from flask_login import login_required, current_user
from sqlalchemy import desc, or_

from models.push_notification import PushNotification
from web_app import db

# 获取日志记录器
logger = logging.getLogger(__name__)

# 创建蓝图
push_notifications_bp = Blueprint('push_notifications', __name__)

@push_notifications_bp.route('/push_notifications')
@login_required
def push_notifications_page():
    """推送通知页面"""
    # 获取推送配置
    from services.config_service import get_config
    apprise_urls = get_config('APPRISE_URLS', '')
    push_queue_enabled = get_config('PUSH_QUEUE_ENABLED', 'true').lower() == 'true'
    push_queue_interval = int(get_config('PUSH_QUEUE_INTERVAL_SECONDS', '30'))
    push_max_attempts = int(get_config('PUSH_MAX_ATTEMPTS', '3'))

    # 获取当前时间
    now = datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    return render_template('push_notifications.html',
                          apprise_urls=apprise_urls,
                          push_queue_enabled=push_queue_enabled,
                          push_queue_interval=push_queue_interval,
                          push_max_attempts=push_max_attempts,
                          now=now)

@push_notifications_bp.route('/api/push_notifications')
@login_required
def get_push_notifications():
    """获取推送通知列表"""
    # 获取查询参数
    page = request.args.get('page', 1, type=int)
    per_page = request.args.get('per_page', 10, type=int)
    status = request.args.get('status', None)

    # 构建查询
    query = PushNotification.query

    # 根据状态筛选
    if status:
        if status == 'pending':
            query = query.filter(PushNotification.status == 'pending')
        elif status == 'success':
            query = query.filter(PushNotification.status == 'success')
        elif status == 'failed':
            query = query.filter(PushNotification.status == 'failed')
        elif status == 'retrying':
            query = query.filter(PushNotification.status == 'retrying')
        elif status == 'active':
            query = query.filter(or_(
                PushNotification.status == 'pending',
                PushNotification.status == 'retrying'
            ))

    # 按创建时间降序排序
    query = query.order_by(desc(PushNotification.created_at))

    # 分页
    pagination = query.paginate(page=page, per_page=per_page, error_out=False)

    # 转换为字典列表
    notifications = [notification.to_dict() for notification in pagination.items]

    # 返回结果
    return jsonify({
        'notifications': notifications,
        'total': pagination.total,
        'pages': pagination.pages,
        'current_page': pagination.page
    })

@push_notifications_bp.route('/api/push_notifications/stats')
@login_required
def get_push_notifications_stats():
    """获取推送通知统计信息"""
    # 获取总数
    total_count = PushNotification.query.count()

    # 获取各状态数量
    pending_count = PushNotification.query.filter_by(status='pending').count()
    success_count = PushNotification.query.filter_by(status='success').count()
    failed_count = PushNotification.query.filter_by(status='failed').count()
    retrying_count = PushNotification.query.filter_by(status='retrying').count()

    # 获取最近24小时的数量
    recent_time = datetime.now(timezone.utc) - timedelta(hours=24)
    recent_count = PushNotification.query.filter(PushNotification.created_at >= recent_time).count()

    # 获取工作线程状态
    worker_status = {}
    try:
        from services.push_queue_worker import get_worker_status
        worker_status = get_worker_status()
    except ImportError:
        worker_status = {"running": False, "error": "无法导入工作线程模块"}
    except Exception as e:
        worker_status = {"running": False, "error": str(e)}

    # 返回结果
    return jsonify({
        'total_count': total_count,
        'pending_count': pending_count,
        'success_count': success_count,
        'failed_count': failed_count,
        'retrying_count': retrying_count,
        'recent_count': recent_count,
        'worker_status': worker_status
    })

@push_notifications_bp.route('/api/push_notifications/<int:notification_id>/retry', methods=['POST'])
@login_required
def retry_push_notification(notification_id):
    """重试推送通知"""
    notification = PushNotification.query.get_or_404(notification_id)

    # 只有失败的通知才能重试
    if notification.status != 'failed':
        return jsonify({
            'success': False,
            'message': '只有失败的通知才能重试'
        }), 400

    # 重置状态
    notification.status = 'pending'
    notification.attempt_count = 0
    notification.updated_at = datetime.now(timezone.utc)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '通知已加入重试队列'
    })

@push_notifications_bp.route('/api/push_notifications/<int:notification_id>/delete', methods=['POST'])
@login_required
def delete_push_notification(notification_id):
    """删除推送通知"""
    notification = PushNotification.query.get_or_404(notification_id)

    # 删除通知
    db.session.delete(notification)
    db.session.commit()

    return jsonify({
        'success': True,
        'message': '通知已删除'
    })

@push_notifications_bp.route('/api/push_notifications/clean', methods=['POST'])
@login_required
def clean_push_notifications():
    """清理推送通知"""
    # 获取参数
    status = request.json.get('status', 'all')
    days = request.json.get('days', 30)

    # 计算截止时间
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=days)

    # 构建查询
    query = PushNotification.query.filter(PushNotification.created_at < cutoff_time)

    # 根据状态筛选
    if status != 'all':
        query = query.filter_by(status=status)

    # 删除记录
    count = query.delete()
    db.session.commit()

    return jsonify({
        'success': True,
        'message': f'已清理 {count} 条通知记录'
    })

@push_notifications_bp.route('/api/push_notifications/config', methods=['POST'])
@login_required
def save_push_config():
    """保存推送配置"""
    try:
        # 获取参数
        apprise_urls = request.json.get('apprise_urls', '')
        push_queue_enabled = request.json.get('push_queue_enabled', True)
        push_queue_interval = request.json.get('push_queue_interval', 30)
        push_max_attempts = request.json.get('push_max_attempts', 3)

        # 导入配置服务
        from services.config_service import set_config

        # 保存配置
        set_config('APPRISE_URLS', apprise_urls, description='Apprise推送URLs')
        set_config('PUSH_QUEUE_ENABLED', 'true' if push_queue_enabled else 'false', description='是否启用推送队列')
        set_config('PUSH_QUEUE_INTERVAL_SECONDS', str(push_queue_interval), description='推送队列处理间隔（秒）')
        set_config('PUSH_MAX_ATTEMPTS', str(push_max_attempts), description='推送最大重试次数')

        # 更新环境变量
        os.environ['PUSH_QUEUE_ENABLED'] = 'true' if push_queue_enabled else 'false'
        os.environ['PUSH_QUEUE_INTERVAL_SECONDS'] = str(push_queue_interval)
        os.environ['PUSH_MAX_ATTEMPTS'] = str(push_max_attempts)

        # 重启推送队列处理器（如果需要）
        try:
            from services.push_queue_worker import stop_push_queue_worker, start_push_queue_worker

            # 停止当前处理器
            stop_push_queue_worker()

            # 如果启用了队列，启动处理器
            if push_queue_enabled:
                start_push_queue_worker()
        except ImportError:
            pass  # 忽略导入错误

        return jsonify({
            'success': True,
            'message': '推送配置已保存'
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'保存推送配置失败: {str(e)}'
        }), 500

@push_notifications_bp.route('/api/push_notifications/test', methods=['POST'])
@login_required
def test_push_notification():
    """测试推送通知"""
    try:
        # 获取参数
        title = request.json.get('title', '测试通知')
        message = request.json.get('message', '这是一条测试通知')
        tag = request.json.get('tag', '')
        url = request.json.get('url', '')
        use_queue = request.json.get('use_queue', True)

        # 根据是否使用队列选择不同的发送方式
        if use_queue:
            # 使用队列发送
            try:
                from services.push_queue_service import queue_notification

                notification = queue_notification(
                    message=message,
                    title=title,
                    tag=tag,
                    targets=url,
                    metadata={'test': True}
                )

                return jsonify({
                    'success': True,
                    'message': f'测试通知已加入队列，ID: {notification.id}',
                    'notification_id': notification.id
                })
            except ImportError:
                return jsonify({
                    'success': False,
                    'message': '推送队列服务不可用'
                }), 500
        else:
            # 直接发送
            if url:
                # 发送到特定URL
                from modules.bots.apprise_adapter import send_to_specific_url

                # 检查是否有多个URL（逗号或换行符分隔）
                # 先尝试按换行符分割
                if '\n' in url:
                    urls = [u.strip() for u in url.splitlines() if u.strip()]
                    logger.info(f"检测到多个URL(换行符分隔): {len(urls)}个，将逐个发送")
                # 再尝试按逗号分割
                elif ',' in url:
                    urls = [u.strip() for u in url.split(',') if u.strip()]
                    logger.info(f"检测到多个URL(逗号分隔): {len(urls)}个，将逐个发送")
                else:
                    # 单个URL
                    urls = [url]

                # 记录成功和失败的URL
                success_urls = []
                failed_urls = []

                for single_url in urls:
                    # 调用send_to_specific_url函数，注意参数名称
                    single_result = send_to_specific_url(
                        url=single_url,
                        custom_message=message,  # 这里使用message参数
                        custom_title=title       # 这里使用title参数
                    )

                    if single_result:
                        success_urls.append(single_url)
                    else:
                        failed_urls.append(single_url)

                # 如果至少有一个URL成功，则认为整体成功
                result = len(success_urls) > 0

                # 准备详细的结果信息
                if result:
                    success_message = f"测试通知已发送到 {len(success_urls)}/{len(urls)} 个URL"
                    if failed_urls:
                        success_message += f"，{len(failed_urls)} 个URL发送失败"

                    return jsonify({
                        'success': True,
                        'message': success_message,
                        'details': {
                            'success_count': len(success_urls),
                            'failed_count': len(failed_urls)
                        }
                    })
                else:
                    return jsonify({
                        'success': False,
                        'message': f"所有 {len(urls)} 个URL发送都失败了",
                        'details': {
                            'success_count': 0,
                            'failed_count': len(failed_urls)
                        }
                    }), 500
            else:
                # 使用配置的所有URL发送
                from modules.bots.apprise_adapter import send_notification

                result = send_notification(
                    message=message,
                    title=title,
                    tag=tag
                )

            if result:
                return jsonify({
                    'success': True,
                    'message': '测试通知已发送'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': '发送测试通知失败'
                }), 500
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'发送测试通知失败: {str(e)}'
        }), 500
