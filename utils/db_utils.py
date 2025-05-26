"""
数据库工具模块
提供通用的数据库操作函数，避免重复代码
"""

import sqlite3
import logging
from typing import List, Tuple, Optional, Dict, Any
from utils.logger import get_logger

logger = get_logger('utils.db_utils')

def find_duplicate_records(cursor: sqlite3.Cursor, table_name: str, unique_columns: List[str]) -> List[Tuple]:
    """
    查找表中的重复记录
    
    Args:
        cursor: 数据库游标
        table_name: 表名
        unique_columns: 用于判断重复的列名列表
        
    Returns:
        List[Tuple]: 重复记录的信息列表
    """
    logger.info(f"开始查找表 {table_name} 中的重复记录...")
    
    # 构建查询语句
    columns_str = ', '.join(unique_columns)
    query = f"""
    SELECT {columns_str}, COUNT(*) as count
    FROM {table_name}
    GROUP BY {columns_str}
    HAVING COUNT(*) > 1
    """
    
    cursor.execute(query)
    duplicates = cursor.fetchall()
    logger.info(f"在表 {table_name} 中找到 {len(duplicates)} 组重复记录")
    return duplicates

def handle_duplicate_records(
    cursor: sqlite3.Cursor, 
    conn: sqlite3.Connection,
    table_name: str, 
    unique_columns: List[str],
    priority_columns: List[str] = None
) -> int:
    """
    处理表中的重复记录，保留优先级最高的记录
    
    Args:
        cursor: 数据库游标
        conn: 数据库连接
        table_name: 表名
        unique_columns: 用于判断重复的列名列表
        priority_columns: 优先级列名列表，用于决定保留哪条记录
        
    Returns:
        int: 删除的记录数量
    """
    duplicates = find_duplicate_records(cursor, table_name, unique_columns)
    
    if not duplicates:
        logger.info(f"表 {table_name} 中没有发现重复记录，无需处理")
        return 0
    
    # 默认优先级列：优先保留最新创建的记录
    if priority_columns is None:
        priority_columns = ['created_at DESC']
    
    total_removed = 0
    
    for dup in duplicates:
        # 构建条件
        conditions = []
        values = []
        for i, col in enumerate(unique_columns):
            conditions.append(f"{col} = ?")
            values.append(dup[i])
        
        where_clause = ' AND '.join(conditions)
        
        logger.info(f"处理重复记录: {dict(zip(unique_columns, dup[:len(unique_columns)]))}, 共 {dup[-1]} 条")
        
        # 构建排序子句
        order_clause = ', '.join(priority_columns)
        
        # 获取所有重复记录
        query = f"""
        SELECT id
        FROM {table_name}
        WHERE {where_clause}
        ORDER BY {order_clause}
        """
        
        cursor.execute(query, values)
        records = cursor.fetchall()
        
        # 保留第一条记录，删除其余记录
        if len(records) > 1:
            keep_id = records[0][0]
            delete_ids = [r[0] for r in records[1:]]
            
            if delete_ids:
                placeholders = ','.join(['?'] * len(delete_ids))
                cursor.execute(f"DELETE FROM {table_name} WHERE id IN ({placeholders})", delete_ids)
                removed = len(delete_ids)
                total_removed += removed
                logger.info(f"保留记录ID: {keep_id}, 删除 {removed} 条重复记录")
    
    if total_removed > 0:
        conn.commit()
        logger.info(f"共删除 {total_removed} 条重复记录")
    
    return total_removed

def check_table_exists(cursor: sqlite3.Cursor, table_name: str) -> bool:
    """
    检查表是否存在
    
    Args:
        cursor: 数据库游标
        table_name: 表名
        
    Returns:
        bool: 表是否存在
    """
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,))
    return cursor.fetchone() is not None

def check_column_exists(cursor: sqlite3.Cursor, table_name: str, column_name: str) -> bool:
    """
    检查表中的列是否存在
    
    Args:
        cursor: 数据库游标
        table_name: 表名
        column_name: 列名
        
    Returns:
        bool: 列是否存在
    """
    cursor.execute(f"PRAGMA table_info({table_name})")
    columns = [column[1] for column in cursor.fetchall()]
    return column_name in columns

def get_table_columns(cursor: sqlite3.Cursor, table_name: str) -> List[str]:
    """
    获取表的所有列名
    
    Args:
        cursor: 数据库游标
        table_name: 表名
        
    Returns:
        List[str]: 列名列表
    """
    cursor.execute(f"PRAGMA table_info({table_name})")
    return [column[1] for column in cursor.fetchall()]

def add_column_if_not_exists(
    cursor: sqlite3.Cursor, 
    conn: sqlite3.Connection,
    table_name: str, 
    column_name: str, 
    column_type: str,
    default_value: str = None
) -> bool:
    """
    如果列不存在则添加列
    
    Args:
        cursor: 数据库游标
        conn: 数据库连接
        table_name: 表名
        column_name: 列名
        column_type: 列类型
        default_value: 默认值
        
    Returns:
        bool: 是否成功添加列
    """
    if check_column_exists(cursor, table_name, column_name):
        logger.info(f"列 {table_name}.{column_name} 已存在，无需添加")
        return True
    
    try:
        # 构建ALTER TABLE语句
        alter_sql = f"ALTER TABLE {table_name} ADD COLUMN {column_name} {column_type}"
        if default_value:
            alter_sql += f" DEFAULT {default_value}"
        
        logger.info(f"添加列 {table_name}.{column_name}")
        cursor.execute(alter_sql)
        conn.commit()
        logger.info(f"成功添加列 {table_name}.{column_name}")
        return True
    except Exception as e:
        logger.error(f"添加列 {table_name}.{column_name} 时出错: {str(e)}")
        conn.rollback()
        return False

def create_index_if_not_exists(
    cursor: sqlite3.Cursor,
    conn: sqlite3.Connection,
    index_name: str,
    table_name: str,
    columns: List[str],
    unique: bool = False
) -> bool:
    """
    如果索引不存在则创建索引
    
    Args:
        cursor: 数据库游标
        conn: 数据库连接
        index_name: 索引名
        table_name: 表名
        columns: 列名列表
        unique: 是否为唯一索引
        
    Returns:
        bool: 是否成功创建索引
    """
    # 检查索引是否已存在
    cursor.execute("SELECT name FROM sqlite_master WHERE type='index' AND name=?", (index_name,))
    if cursor.fetchone():
        logger.info(f"索引 {index_name} 已存在，无需创建")
        return True
    
    try:
        # 构建CREATE INDEX语句
        unique_str = "UNIQUE " if unique else ""
        columns_str = ', '.join(columns)
        create_sql = f"CREATE {unique_str}INDEX {index_name} ON {table_name} ({columns_str})"
        
        logger.info(f"创建索引 {index_name}")
        cursor.execute(create_sql)
        conn.commit()
        logger.info(f"成功创建索引 {index_name}")
        return True
    except Exception as e:
        logger.error(f"创建索引 {index_name} 时出错: {str(e)}")
        conn.rollback()
        return False

def execute_sql_file(cursor: sqlite3.Cursor, conn: sqlite3.Connection, sql_file_path: str) -> bool:
    """
    执行SQL文件
    
    Args:
        cursor: 数据库游标
        conn: 数据库连接
        sql_file_path: SQL文件路径
        
    Returns:
        bool: 是否成功执行
    """
    try:
        with open(sql_file_path, 'r', encoding='utf-8') as f:
            sql_content = f.read()
        
        # 分割SQL语句并执行
        statements = sql_content.split(';')
        for statement in statements:
            statement = statement.strip()
            if statement:
                cursor.execute(statement)
        
        conn.commit()
        logger.info(f"成功执行SQL文件: {sql_file_path}")
        return True
    except Exception as e:
        logger.error(f"执行SQL文件 {sql_file_path} 时出错: {str(e)}")
        conn.rollback()
        return False

def backup_table(cursor: sqlite3.Cursor, conn: sqlite3.Connection, table_name: str, backup_suffix: str = "_backup") -> bool:
    """
    备份表
    
    Args:
        cursor: 数据库游标
        conn: 数据库连接
        table_name: 表名
        backup_suffix: 备份表后缀
        
    Returns:
        bool: 是否成功备份
    """
    backup_table_name = f"{table_name}{backup_suffix}"
    
    try:
        # 删除已存在的备份表
        cursor.execute(f"DROP TABLE IF EXISTS {backup_table_name}")
        
        # 创建备份表
        cursor.execute(f"CREATE TABLE {backup_table_name} AS SELECT * FROM {table_name}")
        conn.commit()
        
        logger.info(f"成功备份表 {table_name} 到 {backup_table_name}")
        return True
    except Exception as e:
        logger.error(f"备份表 {table_name} 时出错: {str(e)}")
        conn.rollback()
        return False
