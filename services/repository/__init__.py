"""
数据访问层
提供统一的数据库操作接口，使用仓储模式（Repository Pattern）
"""

from typing import TypeVar, Generic, Type, List, Optional, Dict, Any, Union, Tuple
from sqlalchemy.orm import Query
from sqlalchemy import desc, asc
from models import db

# 定义泛型类型变量，表示任何数据库模型
T = TypeVar('T')

class BaseRepository(Generic[T]):
    """
    基础仓储类，提供通用的数据库操作

    泛型参数:
        T: 数据库模型类型
    """

    def __init__(self, model_class: Type[T]):
        """
        初始化仓储

        Args:
            model_class: 数据库模型类
        """
        self.model_class = model_class

    def get_by_id(self, id: int) -> Optional[T]:
        """
        根据ID获取实体

        Args:
            id: 实体ID

        Returns:
            Optional[T]: 找到的实体，如果不存在则返回None
        """
        return self.model_class.query.get(id)

    def get_all(self) -> List[T]:
        """
        获取所有实体

        Returns:
            List[T]: 实体列表
        """
        return self.model_class.query.all()

    def find(self, **kwargs) -> List[T]:
        """
        根据条件查找实体

        Args:
            **kwargs: 过滤条件

        Returns:
            List[T]: 符合条件的实体列表
        """
        return self.model_class.query.filter_by(**kwargs).all()

    def find_one(self, **kwargs) -> Optional[T]:
        """
        根据条件查找单个实体

        Args:
            **kwargs: 过滤条件

        Returns:
            Optional[T]: 找到的实体，如果不存在则返回None
        """
        return self.model_class.query.filter_by(**kwargs).first()

    def create(self, **kwargs) -> T:
        """
        创建新实体

        Args:
            **kwargs: 实体属性

        Returns:
            T: 创建的实体
        """
        entity = self.model_class(**kwargs)
        return self.save(entity)

    def update(self, entity: T, **kwargs) -> T:
        """
        更新实体

        Args:
            entity: 要更新的实体
            **kwargs: 要更新的属性

        Returns:
            T: 更新后的实体
        """
        for key, value in kwargs.items():
            setattr(entity, key, value)
        return self.save(entity)

    def save(self, entity: T) -> T:
        """
        保存实体

        Args:
            entity: 要保存的实体

        Returns:
            T: 保存后的实体
        """
        db.session.add(entity)
        db.session.commit()
        return entity

    def delete(self, entity: T) -> bool:
        """
        删除实体

        Args:
            entity: 要删除的实体

        Returns:
            bool: 是否成功删除
        """
        try:
            db.session.delete(entity)
            db.session.commit()
            return True
        except Exception:
            db.session.rollback()
            return False

    def delete_by_id(self, id: int) -> bool:
        """
        根据ID删除实体

        Args:
            id: 实体ID

        Returns:
            bool: 是否成功删除
        """
        entity = self.get_by_id(id)
        if entity:
            return self.delete(entity)
        return False

    def count(self, **kwargs) -> int:
        """
        计算符合条件的实体数量

        Args:
            **kwargs: 过滤条件

        Returns:
            int: 实体数量
        """
        return self.model_class.query.filter_by(**kwargs).count()

    def exists(self, **kwargs) -> bool:
        """
        检查是否存在符合条件的实体

        Args:
            **kwargs: 过滤条件

        Returns:
            bool: 是否存在
        """
        return self.model_class.query.filter_by(**kwargs).first() is not None

    def query(self) -> Query:
        """
        获取查询对象，用于构建复杂查询

        Returns:
            Query: 查询对象
        """
        return self.model_class.query

    def paginate(self, page: int = 1, per_page: int = 20, **kwargs) -> Any:
        """
        分页查询

        Args:
            page: 页码，从1开始
            per_page: 每页数量
            **kwargs: 过滤条件

        Returns:
            Any: 分页结果
        """
        return self.model_class.query.filter_by(**kwargs).paginate(page=page, per_page=per_page)

    def order_by(self, field: str, ascending: bool = True, **kwargs) -> List[T]:
        """
        排序查询

        Args:
            field: 排序字段
            ascending: 是否升序
            **kwargs: 过滤条件

        Returns:
            List[T]: 排序后的实体列表
        """
        query = self.model_class.query.filter_by(**kwargs)
        if ascending:
            return query.order_by(asc(getattr(self.model_class, field))).all()
        else:
            return query.order_by(desc(getattr(self.model_class, field))).all()
