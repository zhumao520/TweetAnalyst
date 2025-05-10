"""
数据分析API模块
处理所有数据分析相关的API请求
"""

import logging
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, session, current_app, url_for
from sqlalchemy import func, cast, Date
from models import db, AnalysisResult, SocialAccount

# 创建日志记录器
logger = logging.getLogger('api.analytics')

# 创建Blueprint
analytics_api = Blueprint('analytics_api', __name__, url_prefix='/analytics')

@analytics_api.route('/summary', methods=['GET'])
def get_summary():
    """获取分析数据摘要"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取总体统计数据
        total_posts = AnalysisResult.query.count()
        relevant_posts = AnalysisResult.query.filter_by(is_relevant=True).count()

        # 获取按社交媒体平台分组的统计数据
        platform_stats = db.session.query(
            AnalysisResult.social_network,
            db.func.count(AnalysisResult.id).label('total'),
            db.func.sum(db.case([(AnalysisResult.is_relevant, 1)], else_=0)).label('relevant')
        ).group_by(AnalysisResult.social_network).all()

        platform_data = [
            {
                'platform': item[0],
                'total': item[1],
                'relevant': item[2] or 0,
                'relevance_rate': round((item[2] or 0) / item[1] * 100, 2) if item[1] > 0 else 0
            }
            for item in platform_stats
        ]

        # 获取按账号分组的统计数据
        account_stats = db.session.query(
            AnalysisResult.social_network,
            AnalysisResult.account_id,
            db.func.count(AnalysisResult.id).label('total'),
            db.func.sum(db.case([(AnalysisResult.is_relevant, 1)], else_=0)).label('relevant')
        ).group_by(AnalysisResult.social_network, AnalysisResult.account_id).all()

        account_data = [
            {
                'platform': item[0],
                'account_id': item[1],
                'total': item[2],
                'relevant': item[3] or 0,
                'relevance_rate': round((item[3] or 0) / item[2] * 100, 2) if item[2] > 0 else 0
            }
            for item in account_stats
        ]

        # 获取时间趋势数据（按天统计）
        # 获取最近30天的数据
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)

        time_stats = db.session.query(
            cast(AnalysisResult.post_time, Date).label('date'),
            db.func.count(AnalysisResult.id).label('total'),
            db.func.sum(db.case([(AnalysisResult.is_relevant, 1)], else_=0)).label('relevant')
        ).filter(AnalysisResult.post_time >= thirty_days_ago)\
         .group_by(cast(AnalysisResult.post_time, Date))\
         .order_by(cast(AnalysisResult.post_time, Date)).all()

        time_data = [
            {
                'date': item[0].isoformat(),
                'total': item[1],
                'relevant': item[2] or 0,
                'relevance_rate': round((item[2] or 0) / item[1] * 100, 2) if item[1] > 0 else 0
            }
            for item in time_stats
        ]

        return jsonify({
            "success": True,
            "data": {
                "summary": {
                    "total_posts": total_posts,
                    "relevant_posts": relevant_posts,
                    "relevance_rate": round(relevant_posts / total_posts * 100, 2) if total_posts > 0 else 0
                },
                "platforms": platform_data,
                "accounts": account_data,
                "time_trend": time_data
            }
        })
    except Exception as e:
        logger.error(f"获取分析数据摘要时出错: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"获取数据失败: {str(e)}"}), 500

@analytics_api.route('/results', methods=['GET'])
def get_results():
    """获取分析结果"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取查询参数
        result_id = request.args.get('id')
        account_id = request.args.get('account_id')
        is_relevant = request.args.get('is_relevant')
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)

        # 构建查询
        query = AnalysisResult.query

        # 按ID查询
        if result_id:
            result = AnalysisResult.query.get(result_id)
            if result:
                return jsonify({
                    "success": True,
                    "data": [result.to_dict()],
                    "total": 1,
                    "limit": 1,
                    "offset": 0
                })
            else:
                return jsonify({
                    "success": True,
                    "data": [],
                    "total": 0,
                    "limit": limit,
                    "offset": offset
                })

        # 按账号过滤
        if account_id:
            query = query.filter_by(account_id=account_id)

        # 按相关性过滤
        if is_relevant is not None:
            is_relevant_bool = is_relevant.lower() == 'true'
            query = query.filter_by(is_relevant=is_relevant_bool)

        # 获取总数
        total = query.count()

        # 分页查询
        results = query.order_by(AnalysisResult.created_at.desc()).offset(offset).limit(limit).all()

        return jsonify({
            "success": True,
            "data": [result.to_dict() for result in results],
            "total": total,
            "limit": limit,
            "offset": offset
        })
    except Exception as e:
        logger.error(f"获取分析结果时出错: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"获取数据失败: {str(e)}"}), 500

@analytics_api.route('/notifications', methods=['GET'])
def get_notifications():
    """获取最新通知"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取最近24小时内的相关结果作为通知
        one_day_ago = datetime.now(timezone.utc) - timedelta(hours=24)

        notifications = AnalysisResult.query.filter(
            AnalysisResult.is_relevant == True,
            AnalysisResult.created_at >= one_day_ago
        ).order_by(AnalysisResult.created_at.desc()).limit(10).all()

        # 转换为JSON格式
        result = []
        for notification in notifications:
            result.append({
                'id': notification.id,
                'title': f'来自 {notification.social_network}: {notification.account_id} 的更新',
                'content': notification.content[:100] + ('...' if len(notification.content) > 100 else ''),
                'time': notification.created_at.isoformat(),
                'read': False,  # 默认未读
                'url': url_for('results', _external=True) + f'?id={notification.id}',
                'confidence': notification.confidence,  # 添加置信度
                'reason': notification.reason  # 添加理由
            })

        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"获取通知时出错: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"获取通知失败: {str(e)}"}), 500

@analytics_api.route('/save_result', methods=['POST'])
def save_result():
    """保存分析结果"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        data = request.get_json()

        # 验证必要参数
        required_fields = ['social_network', 'account_id', 'post_id', 'post_time', 'content', 'analysis', 'is_relevant']
        for field in required_fields:
            if field not in data:
                return jsonify({"success": False, "message": f"缺少必要参数: {field}"}), 400

        # 创建分析结果
        result = AnalysisResult(
            social_network=data['social_network'],
            account_id=data['account_id'],
            post_id=data['post_id'],
            post_time=datetime.fromisoformat(data['post_time']),
            content=data['content'],
            analysis=data['analysis'],
            is_relevant=data['is_relevant'],
            confidence=data.get('confidence'),  # 新字段，可选
            reason=data.get('reason')  # 新字段，可选
        )

        db.session.add(result)
        db.session.commit()

        logger.info(f"已保存分析结果: {result.id}")

        return jsonify({
            "success": True,
            "message": "分析结果已保存",
            "data": {
                "id": result.id
            }
        })
    except Exception as e:
        db.session.rollback()
        logger.error(f"保存分析结果时出错: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"保存分析结果失败: {str(e)}"}), 500
