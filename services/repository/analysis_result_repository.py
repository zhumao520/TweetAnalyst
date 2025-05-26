"""
分析结果仓储
处理分析结果相关的数据库操作
"""

from typing import Optional, List, Dict, Any, Tuple
from datetime import datetime, timedelta
from sqlalchemy import func, desc, and_, or_, cast, Date
from models.analysis_result import AnalysisResult
from . import BaseRepository

class AnalysisResultRepository(BaseRepository[AnalysisResult]):
    """分析结果仓储类"""
    
    def __init__(self):
        """初始化分析结果仓储"""
        super().__init__(AnalysisResult)
    
    def get_by_post_id(self, post_id: str) -> Optional[AnalysisResult]:
        """
        根据帖子ID获取分析结果
        
        Args:
            post_id: 帖子ID
            
        Returns:
            Optional[AnalysisResult]: 找到的分析结果，如果不存在则返回None
        """
        return self.find_one(post_id=post_id)
    
    def get_by_account_id(self, account_id: str, page: int = 1, per_page: int = 20) -> Any:
        """
        根据账号ID获取分析结果
        
        Args:
            account_id: 账号ID
            page: 页码
            per_page: 每页数量
            
        Returns:
            Any: 分页结果
        """
        return self.paginate(page=page, per_page=per_page, account_id=account_id)
    
    def get_relevant_results(self, page: int = 1, per_page: int = 20) -> Any:
        """
        获取相关的分析结果
        
        Args:
            page: 页码
            per_page: 每页数量
            
        Returns:
            Any: 分页结果
        """
        return self.paginate(page=page, per_page=per_page, is_relevant=True)
    
    def get_by_date_range(self, start_date: datetime, end_date: datetime, page: int = 1, per_page: int = 20) -> Any:
        """
        根据日期范围获取分析结果
        
        Args:
            start_date: 开始日期
            end_date: 结束日期
            page: 页码
            per_page: 每页数量
            
        Returns:
            Any: 分页结果
        """
        query = self.query().filter(
            and_(
                AnalysisResult.post_time >= start_date,
                AnalysisResult.post_time <= end_date
            )
        )
        return query.order_by(desc(AnalysisResult.post_time)).paginate(page=page, per_page=per_page)
    
    def get_by_filters(self, filters: Dict[str, Any], page: int = 1, per_page: int = 20) -> Any:
        """
        根据过滤条件获取分析结果
        
        Args:
            filters: 过滤条件
            page: 页码
            per_page: 每页数量
            
        Returns:
            Any: 分页结果
        """
        query = self.query()
        
        # 处理账号ID过滤
        if 'account_id' in filters and filters['account_id']:
            query = query.filter(AnalysisResult.account_id == filters['account_id'])
        
        # 处理相关性过滤
        if 'is_relevant' in filters and filters['is_relevant'] is not None:
            query = query.filter(AnalysisResult.is_relevant == filters['is_relevant'])
        
        # 处理日期过滤
        if 'date' in filters and filters['date']:
            date_obj = datetime.strptime(filters['date'], '%Y-%m-%d')
            next_day = date_obj + timedelta(days=1)
            query = query.filter(
                and_(
                    AnalysisResult.post_time >= date_obj,
                    AnalysisResult.post_time < next_day
                )
            )
        
        # 处理日期范围过滤
        if 'start_date' in filters and filters['start_date']:
            start_date = datetime.strptime(filters['start_date'], '%Y-%m-%d')
            query = query.filter(AnalysisResult.post_time >= start_date)
        
        if 'end_date' in filters and filters['end_date']:
            end_date = datetime.strptime(filters['end_date'], '%Y-%m-%d')
            # 设置为当天结束时间
            end_date = end_date.replace(hour=23, minute=59, second=59)
            query = query.filter(AnalysisResult.post_time <= end_date)
        
        # 处理社交网络类型过滤
        if 'social_network' in filters and filters['social_network']:
            query = query.filter(AnalysisResult.social_network == filters['social_network'])
        
        # 处理AI提供商过滤
        if 'ai_provider' in filters and filters['ai_provider']:
            query = query.filter(AnalysisResult.ai_provider == filters['ai_provider'])
        
        # 处理置信度过滤
        if 'min_confidence' in filters and filters['min_confidence'] is not None:
            query = query.filter(AnalysisResult.confidence >= filters['min_confidence'])
        
        if 'max_confidence' in filters and filters['max_confidence'] is not None:
            query = query.filter(AnalysisResult.confidence <= filters['max_confidence'])
        
        # 处理媒体内容过滤
        if 'has_media' in filters and filters['has_media'] is not None:
            query = query.filter(AnalysisResult.has_media == filters['has_media'])
        
        # 处理排序
        sort_field = filters.get('sort_field', 'post_time')
        sort_order = filters.get('sort_order', 'desc')
        
        if hasattr(AnalysisResult, sort_field):
            if sort_order.lower() == 'asc':
                query = query.order_by(getattr(AnalysisResult, sort_field))
            else:
                query = query.order_by(desc(getattr(AnalysisResult, sort_field)))
        else:
            # 默认按发布时间降序排序
            query = query.order_by(desc(AnalysisResult.post_time))
        
        return query.paginate(page=page, per_page=per_page)
    
    def get_statistics(self) -> Dict[str, Any]:
        """
        获取统计数据
        
        Returns:
            Dict[str, Any]: 统计数据
        """
        total_count = self.count()
        relevant_count = self.count(is_relevant=True)
        
        # 按日期统计
        date_stats = self.query().with_entities(
            func.date(AnalysisResult.post_time).label('date'),
            func.count().label('count'),
            func.sum(AnalysisResult.is_relevant.cast(db.Integer)).label('relevant_count')
        ).group_by('date').order_by('date').all()
        
        # 按账号统计
        account_stats = self.query().with_entities(
            AnalysisResult.account_id,
            func.count().label('count'),
            func.sum(AnalysisResult.is_relevant.cast(db.Integer)).label('relevant_count')
        ).group_by(AnalysisResult.account_id).all()
        
        # 按社交网络类型统计
        network_stats = self.query().with_entities(
            AnalysisResult.social_network,
            func.count().label('count'),
            func.sum(AnalysisResult.is_relevant.cast(db.Integer)).label('relevant_count')
        ).group_by(AnalysisResult.social_network).all()
        
        return {
            'total_count': total_count,
            'relevant_count': relevant_count,
            'date_stats': [{'date': str(item.date), 'count': item.count, 'relevant_count': item.relevant_count} for item in date_stats],
            'account_stats': [{'account_id': item.account_id, 'count': item.count, 'relevant_count': item.relevant_count} for item in account_stats],
            'network_stats': [{'social_network': item.social_network, 'count': item.count, 'relevant_count': item.relevant_count} for item in network_stats]
        }
    
    def create_result(self, result_data: Dict[str, Any]) -> AnalysisResult:
        """
        创建新的分析结果
        
        Args:
            result_data: 分析结果数据
            
        Returns:
            AnalysisResult: 创建的分析结果
        """
        return self.create(**result_data)
    
    def delete_old_results(self, days: int = 30, only_irrelevant: bool = True) -> int:
        """
        删除旧的分析结果
        
        Args:
            days: 保留天数
            only_irrelevant: 是否只删除不相关的结果
            
        Returns:
            int: 删除的记录数
        """
        cutoff_date = datetime.now() - timedelta(days=days)
        query = self.query().filter(AnalysisResult.post_time < cutoff_date)
        
        if only_irrelevant:
            query = query.filter(AnalysisResult.is_relevant == False)
        
        records_to_delete = query.all()
        count = len(records_to_delete)
        
        for record in records_to_delete:
            self.delete(record)
        
        return count
