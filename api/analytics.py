"""
数据分析API模块
处理所有数据分析相关的API请求
"""

import logging
import csv
import json
import io
from datetime import datetime, timedelta, timezone
from flask import Blueprint, request, jsonify, session, current_app, url_for, Response, make_response
from sqlalchemy import func, cast, Date, text
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

        # 获取账号数量
        account_count = SocialAccount.query.count()

        # 计算趋势数据（与上周相比）
        one_week_ago = datetime.now(timezone.utc) - timedelta(days=7)

        # 上周的总帖子数
        last_week_total = AnalysisResult.query.filter(
            AnalysisResult.created_at < one_week_ago
        ).count()

        # 上周的相关帖子数
        last_week_relevant = AnalysisResult.query.filter(
            AnalysisResult.created_at < one_week_ago,
            AnalysisResult.is_relevant == True
        ).count()

        # 上周的账号数量
        last_week_account_count = SocialAccount.query.filter(
            SocialAccount.created_at < one_week_ago
        ).count()

        # 计算趋势百分比
        total_posts_trend = round(((total_posts - last_week_total) / max(last_week_total, 1)) * 100, 1) if last_week_total > 0 else 0
        relevant_posts_trend = round(((relevant_posts - last_week_relevant) / max(last_week_relevant, 1)) * 100, 1) if last_week_relevant > 0 else 0
        account_count_trend = round(((account_count - last_week_account_count) / max(last_week_account_count, 1)) * 100, 1) if last_week_account_count > 0 else 0

        # 计算相关率趋势
        current_relevance_rate = round(relevant_posts / total_posts * 100, 2) if total_posts > 0 else 0
        last_week_relevance_rate = round(last_week_relevant / last_week_total * 100, 2) if last_week_total > 0 else 0
        relevance_rate_trend = round(current_relevance_rate - last_week_relevance_rate, 1) if last_week_relevance_rate > 0 else 0

        # 获取按社交媒体平台分组的统计数据
        platform_stats_query = text("""
            SELECT
                social_network,
                COUNT(*) as total,
                SUM(CASE WHEN is_relevant THEN 1 ELSE 0 END) as relevant
            FROM analysis_result
            GROUP BY social_network
        """)

        platform_stats = db.session.execute(platform_stats_query).fetchall()

        platform_data = []
        for item in platform_stats:
            platform = item[0]
            total = item[1] or 0
            relevant = item[2] or 0
            platform_data.append({
                'platform': platform,
                'total': total,
                'relevant': relevant,
                'relevance_rate': round(relevant / total * 100, 2) if total > 0 else 0
            })

        # 获取按账号分组的统计数据
        account_stats_query = text("""
            SELECT
                social_network,
                account_id,
                COUNT(*) as total,
                SUM(CASE WHEN is_relevant THEN 1 ELSE 0 END) as relevant
            FROM analysis_result
            GROUP BY social_network, account_id
        """)

        account_stats = db.session.execute(account_stats_query).fetchall()

        # 获取所有账号信息，包括头像URL
        accounts = {account.account_id: account for account in SocialAccount.query.all()}

        account_data = []
        for item in account_stats:
            platform = item[0]
            account_id = item[1]
            total = item[2] or 0
            relevant = item[3] or 0

            # 获取账号头像URL
            avatar_url = None
            if account_id in accounts:
                avatar_url = accounts[account_id].avatar_url

            account_data.append({
                'platform': platform,
                'account_id': account_id,
                'total': total,
                'relevant': relevant,
                'relevance_rate': round(relevant / total * 100, 2) if total > 0 else 0,
                'avatar_url': avatar_url
            })

        # 获取时间趋势数据（按天统计）
        # 获取最近30天的数据
        thirty_days_ago = datetime.now(timezone.utc) - timedelta(days=30)
        thirty_days_ago_str = thirty_days_ago.strftime('%Y-%m-%d')

        # 使用原始SQL查询来避免日期转换问题
        time_stats_query = text("""
            SELECT
                date(post_time) as date,
                COUNT(*) as total,
                SUM(CASE WHEN is_relevant THEN 1 ELSE 0 END) as relevant
            FROM analysis_result
            WHERE post_time >= :thirty_days_ago
            GROUP BY date(post_time)
            ORDER BY date(post_time)
        """)

        time_stats = db.session.execute(time_stats_query, {"thirty_days_ago": thirty_days_ago_str}).fetchall()

        time_data = []
        for item in time_stats:
            date_str = str(item[0]) if item[0] is not None else datetime.now().strftime('%Y-%m-%d')
            total = item[1] or 0
            relevant = item[2] or 0
            time_data.append({
                'date': date_str,
                'total': total,
                'relevant': relevant,
                'relevance_rate': round(relevant / total * 100, 2) if total > 0 else 0
            })

        # 计算相关性分布数据（按置信度范围分组）
        relevance_distribution = []

        # 定义置信度范围
        confidence_ranges = [
            {"min": 0, "max": 20, "range": "0-20"},
            {"min": 21, "max": 40, "range": "21-40"},
            {"min": 41, "max": 60, "range": "41-60"},
            {"min": 61, "max": 80, "range": "61-80"},
            {"min": 81, "max": 100, "range": "81-100"}
        ]

        # 查询每个范围的数量
        for range_info in confidence_ranges:
            min_val = range_info["min"]
            max_val = range_info["max"]

            # 查询在此范围内的结果数量
            count = AnalysisResult.query.filter(
                AnalysisResult.confidence >= min_val,
                AnalysisResult.confidence <= max_val
            ).count()

            relevance_distribution.append({
                "range": range_info["range"],
                "count": count
            })

        # 计算每日活跃度数据（按星期几分组）
        daily_activity = []

        # 查询每个星期几的帖子数量
        for day in range(1, 8):  # 1-7 表示周一到周日
            # 使用SQL函数提取星期几
            day_count = db.session.query(func.count()).filter(
                func.extract('dow', AnalysisResult.post_time) == day % 7  # PostgreSQL中0是周日，1-6是周一到周六
            ).scalar() or 0

            daily_activity.append({
                "day": day,
                "count": day_count
            })

        return jsonify({
            "success": True,
            "data": {
                "summary": {
                    "total_posts": total_posts,
                    "relevant_posts": relevant_posts,
                    "relevance_rate": current_relevance_rate,
                    "account_count": account_count,
                    "total_posts_trend": total_posts_trend,
                    "relevant_posts_trend": relevant_posts_trend,
                    "relevance_rate_trend": relevance_rate_trend,
                    "account_count_trend": account_count_trend
                },
                "platforms": platform_data,
                "accounts": account_data,
                "time_trend": time_data,
                "relevance_distribution": relevance_distribution,
                "daily_activity": daily_activity
            }
        })
    except Exception as e:
        logger.error(f"获取分析数据摘要时出错: {str(e)}", exc_info=True)

        # 添加更详细的错误信息
        error_type = type(e).__name__
        error_message = str(e)

        # 检查是否是SQLAlchemy错误
        if 'sqlalchemy' in error_type.lower() or 'case()' in error_message.lower():
            logger.error(f"可能是SQLAlchemy case()函数错误: {error_type} - {error_message}")
            return jsonify({
                "success": False,
                "message": f"获取数据失败: SQLAlchemy错误 - {error_type}",
                "error_details": error_message,
                "error_type": error_type
            }), 500

        return jsonify({
            "success": False,
            "message": f"获取数据失败: {error_message}",
            "error_type": error_type
        }), 500

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
        date = request.args.get('date')  # 新增：按日期过滤
        limit = request.args.get('limit', 100, type=int)
        offset = request.args.get('offset', 0, type=int)

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

        # 构建SQL查询
        sql_query = """
            SELECT * FROM analysis_result
            WHERE 1=1
        """
        params = {}

        # 按账号过滤
        if account_id:
            sql_query += " AND account_id = :account_id"
            params["account_id"] = account_id

        # 按相关性过滤
        if is_relevant is not None:
            is_relevant_bool = is_relevant.lower() == 'true'
            sql_query += " AND is_relevant = :is_relevant"
            params["is_relevant"] = is_relevant_bool

        # 按日期过滤（新增）
        if date:
            sql_query += " AND date(created_at) = :date"
            params["date"] = date

        # 获取总数
        count_query = text(f"SELECT COUNT(*) FROM ({sql_query}) as count_query")
        total = db.session.execute(count_query, params).scalar() or 0

        # 添加排序和分页
        sql_query += " ORDER BY created_at DESC LIMIT :limit OFFSET :offset"
        params["limit"] = limit
        params["offset"] = offset

        # 执行查询
        results_query = text(sql_query)
        results_raw = db.session.execute(results_query, params).fetchall()

        # 将结果转换为字典列表
        results = []
        for row in results_raw:
            result_dict = {}
            for column in AnalysisResult.__table__.columns:
                result_dict[column.name] = getattr(row, column.name)
            results.append(result_dict)

        return jsonify({
            "success": True,
            "data": results,
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
        one_day_ago_str = one_day_ago.strftime('%Y-%m-%d %H:%M:%S')

        # 使用原始SQL查询来避免日期转换问题
        notifications_query = text("""
            SELECT * FROM analysis_result
            WHERE is_relevant = 1
            AND created_at >= :one_day_ago
            ORDER BY created_at DESC
            LIMIT 10
        """)

        notifications_result = db.session.execute(notifications_query, {"one_day_ago": one_day_ago_str})

        # 将结果转换为字典列表
        notifications = []
        for row in notifications_result:
            notification = {}
            for column in AnalysisResult.__table__.columns:
                notification[column.name] = getattr(row, column.name)
            notifications.append(notification)

        # 转换为JSON格式
        result = []
        for notification in notifications:
            result.append({
                'id': notification['id'],
                'title': f'来自 {notification["social_network"]}: {notification["account_id"]} 的更新',
                'content': notification['content'][:100] + ('...' if len(notification['content']) > 100 else ''),
                'time': notification['created_at'] if notification['created_at'] else datetime.now().isoformat(),
                'read': False,  # 默认未读
                'url': url_for('results', _external=True) + f'?id={notification["id"]}',
                'confidence': notification.get('confidence'),  # 添加置信度
                'reason': notification.get('reason')  # 添加理由
            })

        return jsonify({"success": True, "data": result})
    except Exception as e:
        logger.error(f"获取通知时出错: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"获取通知失败: {str(e)}"}), 500

@analytics_api.route('/export', methods=['GET'])
def export_analytics_data():
    """导出分析数据"""
    # 检查用户是否已登录
    if 'user_id' not in session:
        return jsonify({"success": False, "message": "未登录"}), 401

    try:
        # 获取请求参数
        export_format = request.args.get('format', 'csv')
        date_range = request.args.get('date_range', 'all')
        include_charts = request.args.get('include_charts', 'true').lower() == 'true'

        # 处理日期范围
        date_from = None
        date_to = None

        if date_range == 'week':
            date_from = datetime.now(timezone.utc) - timedelta(days=7)
        elif date_range == 'month':
            date_from = datetime.now(timezone.utc) - timedelta(days=30)
        elif date_range == 'custom':
            date_from_str = request.args.get('date_from')
            date_to_str = request.args.get('date_to')

            if date_from_str:
                date_from = datetime.fromisoformat(date_from_str)
            if date_to_str:
                date_to = datetime.fromisoformat(date_to_str)

        # 构建查询
        query = AnalysisResult.query

        if date_from:
            query = query.filter(AnalysisResult.post_time >= date_from)
        if date_to:
            query = query.filter(AnalysisResult.post_time <= date_to)

        # 获取数据
        results = query.order_by(AnalysisResult.post_time.desc()).all()

        # 获取平台统计数据
        platform_stats = {}
        for result in results:
            platform = result.social_network
            if platform not in platform_stats:
                platform_stats[platform] = {
                    'total': 0,
                    'relevant': 0
                }

            platform_stats[platform]['total'] += 1
            if result.is_relevant:
                platform_stats[platform]['relevant'] += 1

        # 获取账号统计数据
        account_stats = {}
        for result in results:
            account_key = f"{result.social_network}:{result.account_id}"
            if account_key not in account_stats:
                account_stats[account_key] = {
                    'platform': result.social_network,
                    'account_id': result.account_id,
                    'total': 0,
                    'relevant': 0
                }

            account_stats[account_key]['total'] += 1
            if result.is_relevant:
                account_stats[account_key]['relevant'] += 1

        # 计算相关率
        for platform in platform_stats:
            total = platform_stats[platform]['total']
            relevant = platform_stats[platform]['relevant']
            platform_stats[platform]['relevance_rate'] = round(relevant / total * 100, 2) if total > 0 else 0

        for account_key in account_stats:
            total = account_stats[account_key]['total']
            relevant = account_stats[account_key]['relevant']
            account_stats[account_key]['relevance_rate'] = round(relevant / total * 100, 2) if total > 0 else 0

        # 准备导出数据
        export_data = {
            'summary': {
                'total_posts': len(results),
                'relevant_posts': sum(1 for r in results if r.is_relevant),
                'export_date': datetime.now(timezone.utc).isoformat(),
                'date_range': {
                    'type': date_range,
                    'from': date_from.isoformat() if date_from else None,
                    'to': date_to.isoformat() if date_to else None
                }
            },
            'platforms': [
                {
                    'platform': platform,
                    'total': stats['total'],
                    'relevant': stats['relevant'],
                    'relevance_rate': stats['relevance_rate']
                }
                for platform, stats in platform_stats.items()
            ],
            'accounts': list(account_stats.values()),
            'results': [
                {
                    'id': result.id,
                    'platform': result.social_network,
                    'account_id': result.account_id,
                    'post_id': result.post_id,
                    'post_time': result.post_time.isoformat() if result.post_time else None,
                    'content': result.content,
                    'is_relevant': result.is_relevant,
                    'confidence': result.confidence,
                    'reason': result.reason,
                    'analysis': result.analysis,
                    'created_at': result.created_at.isoformat() if result.created_at else None
                }
                for result in results
            ]
        }

        # 根据格式导出数据
        if export_format == 'json':
            # JSON格式
            response = make_response(json.dumps(export_data, ensure_ascii=False, indent=2))
            response.headers['Content-Type'] = 'application/json'
            response.headers['Content-Disposition'] = f'attachment; filename=analytics_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            return response

        elif export_format == 'csv':
            # CSV格式
            output = io.StringIO()
            writer = csv.writer(output)

            # 写入标题行
            writer.writerow(['ID', '平台', '账号ID', '帖子ID', '发布时间', '内容', '是否相关', '置信度', '原因', '分析', '创建时间'])

            # 写入数据行
            for result in results:
                writer.writerow([
                    result.id,
                    result.social_network,
                    result.account_id,
                    result.post_id,
                    result.post_time.isoformat() if result.post_time else '',
                    result.content,
                    '是' if result.is_relevant else '否',
                    result.confidence,
                    result.reason,
                    result.analysis,
                    result.created_at.isoformat() if result.created_at else ''
                ])

            response = make_response(output.getvalue())
            response.headers['Content-Type'] = 'text/csv; charset=utf-8'
            response.headers['Content-Disposition'] = f'attachment; filename=analytics_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
            return response

        elif export_format == 'excel':
            # 返回JSON格式，前端可以使用库将其转换为Excel
            response = make_response(json.dumps(export_data, ensure_ascii=False))
            response.headers['Content-Type'] = 'application/json'
            response.headers['Content-Disposition'] = f'attachment; filename=analytics_export_{datetime.now().strftime("%Y%m%d_%H%M%S")}.json'
            return response

        else:
            return jsonify({"success": False, "message": f"不支持的导出格式: {export_format}"}), 400

    except Exception as e:
        logger.error(f"导出分析数据时出错: {str(e)}", exc_info=True)
        return jsonify({"success": False, "message": f"导出数据失败: {str(e)}"}), 500

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

        # 处理post_time，确保它是字符串类型
        post_time = data['post_time']
        if isinstance(post_time, str):
            try:
                # 清理字符串中的额外空格
                post_time = post_time.strip()
                post_time = datetime.fromisoformat(post_time)
            except ValueError as e:
                return jsonify({"success": False, "message": f"post_time格式错误: {str(e)}"}), 400
        # 如果已经是datetime对象，直接使用
        elif not isinstance(post_time, datetime):
            return jsonify({"success": False, "message": "post_time必须是ISO格式的字符串或datetime对象"}), 400

        # 获取AI提供商和模型
        ai_provider = data.get('ai_provider')
        ai_model = data.get('ai_model')

        # 如果没有指定AI提供商和模型，则从AI设置中获取优先级最高的健康AI提供商和模型
        if not ai_provider or ai_provider == 'error' or ai_provider == 'undefined' or not ai_model or ai_model == 'error' or ai_model == 'undefined':
            try:
                # 导入AI提供商模型
                from models.ai_provider import AIProvider

                # 获取优先级最高的健康AI提供商
                default_provider = AIProvider.query.filter_by(is_active=True, health_status='healthy').order_by(AIProvider.priority).first()

                # 如果没有健康的AI提供商，则获取优先级最高的活跃AI提供商
                if not default_provider:
                    default_provider = AIProvider.query.filter_by(is_active=True).order_by(AIProvider.priority).first()

                # 如果找到了默认提供商，则使用其名称和模型
                if default_provider:
                    if not ai_provider or ai_provider == 'error' or ai_provider == 'undefined':
                        ai_provider = default_provider.name

                    if not ai_model or ai_model == 'error' or ai_model == 'undefined':
                        ai_model = default_provider.model
                else:
                    # 如果没有找到默认提供商，则使用配置中的默认值
                    from services.config_service import get_config

                    if not ai_provider or ai_provider == 'error' or ai_provider == 'undefined':
                        ai_provider = '默认提供商'

                    if not ai_model or ai_model == 'error' or ai_model == 'undefined':
                        ai_model = get_config('LLM_API_MODEL', 'gpt-4')
            except Exception as e:
                logger.warning(f"获取默认AI提供商时出错: {str(e)}")

                # 如果出错，使用硬编码的默认值
                if not ai_provider or ai_provider == 'error' or ai_provider == 'undefined':
                    ai_provider = '默认提供商'

                if not ai_model or ai_model == 'error' or ai_model == 'undefined':
                    ai_model = 'gpt-4'

        # 创建分析结果
        result = AnalysisResult(
            social_network=data['social_network'],
            account_id=data['account_id'],
            post_id=data['post_id'],
            post_time=post_time,
            content=data['content'],
            analysis=data['analysis'],
            is_relevant=data['is_relevant'],
            confidence=data.get('confidence'),  # 新字段，可选
            reason=data.get('reason'),  # 新字段，可选
            has_media=data.get('has_media', False),  # 媒体内容标志
            media_content=data.get('media_content'),  # 媒体内容JSON
            ai_provider=ai_provider,  # AI提供商
            ai_model=ai_model  # AI模型
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
