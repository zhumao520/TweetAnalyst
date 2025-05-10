"""
通知API模块
处理所有通知相关的API请求
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify, session, current_app
from models import db, AnalysisResult, SocialAccount

# 创建日志记录器
logger = logging.getLogger('api.notifications')

# 创建Blueprint
notifications_api = Blueprint('notifications_api', __name__, url_prefix='/notifications')

@notifications_api.route('', methods=['GET'])
def get_notifications():
    """获取通知列表"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取最近的分析结果作为通知
        days = request.args.get('days', default=7, type=int)
        limit = request.args.get('limit', default=10, type=int)

        # 验证参数
        if days < 1:
            days = 7
        if limit < 1:
            limit = 10
        elif limit > 50:
            limit = 50

        # 计算时间范围
        since_date = datetime.now() - timedelta(days=days)

        # 查询最近的分析结果
        results = AnalysisResult.query.filter(
            AnalysisResult.created_at >= since_date
        ).order_by(
            AnalysisResult.created_at.desc()
        ).limit(limit).all()

        # 转换为通知格式
        notifications = []
        for result in results:
            # 获取关联的账号
            account = SocialAccount.query.get(result.account_id)
            account_name = account.account_id if account else "未知账号"

            # 创建通知
            notification = {
                "id": f"result_{result.id}",
                "title": f"{'相关' if result.is_relevant else '非相关'}内容分析",
                "content": f"{account_name}: {result.content[:50]}...",
                "time": result.created_at.isoformat(),
                "url": f"/results?id={result.id}",
                "type": "analysis",
                "is_relevant": result.is_relevant
            }
            notifications.append(notification)

        return jsonify({
            "success": True,
            "data": notifications
        })
    except Exception as e:
        logger.error(f"获取通知列表时出错: {str(e)}")
        return jsonify({"success": False, "message": f"获取通知列表时出错: {str(e)}"}), 500
