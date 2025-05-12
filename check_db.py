import os
import sys
import sqlite3

def check_database():
    """检查数据库中的账号数据"""
    try:
        # 连接到数据库
        db_path = os.path.join('instance', 'app.db')
        if not os.path.exists(db_path):
            print(f"数据库文件不存在: {db_path}")
            return
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        # 获取表结构
        cursor.execute("PRAGMA table_info(social_account)")
        columns = cursor.fetchall()
        print("表结构:")
        for col in columns:
            print(f"  {col[1]} ({col[2]})")
        
        # 获取账号数据
        cursor.execute("SELECT id, type, account_id FROM social_account")
        accounts = cursor.fetchall()
        
        print(f"\n找到 {len(accounts)} 个账号:")
        for account in accounts:
            print(f"  ID: {account[0]}, 类型: {account[1]}, 账号ID: {account[2]}")
        
        # 关闭连接
        conn.close()
    except Exception as e:
        print(f"检查数据库时出错: {str(e)}")

if __name__ == "__main__":
    check_database()
