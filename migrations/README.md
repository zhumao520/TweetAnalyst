# 数据库迁移系统

本目录包含TweetAnalyst应用的数据库迁移脚本，用于管理数据库结构的变更。

## 概述

数据库迁移是一种管理数据库结构变更的方法，它允许我们以可控、可追踪的方式修改数据库结构，同时保留现有数据。

本项目使用自定义的迁移系统，所有迁移都集中在`db_migrations.py`文件中管理。这种方式简化了迁移过程，避免了多个分散的迁移脚本，使代码库更加整洁。

## 迁移记录表

系统会自动创建一个`db_migration_history`表来记录所有已执行的迁移，包括：

- 迁移ID
- 迁移名称
- 迁移描述
- 执行时间
- 执行结果
- 错误信息（如果有）
- 执行耗时

这样可以确保每个迁移只执行一次，并且可以追踪迁移的执行历史。

## 如何执行迁移

有三种方式可以执行数据库迁移：

### 1. 直接运行迁移脚本

```bash
python migrations/db_migrations.py
```

### 2. 使用迁移运行器

```bash
python run_migration.py
```

### 3. 通过应用初始化过程

当应用启动时，`web_app.py`中的`init_db`函数会自动执行所有未执行的迁移。

## 如何添加新的迁移

要添加新的迁移，请按照以下步骤操作：

1. 在`db_migrations.py`文件中创建一个新的迁移类，继承自`Migration`基类：

```python
class YourNewMigration(Migration):
    """描述你的迁移"""

    def __init__(self):
        super().__init__(
            id="004_your_migration_id",  # 使用递增的ID
            name="你的迁移名称",
            description="详细描述迁移的目的和内容"
        )

    def _execute(self, conn: sqlite3.Connection) -> bool:
        cursor = conn.cursor()

        # 实现你的迁移逻辑
        # 例如：添加新表、添加新字段、修改现有字段等

        conn.commit()
        return True
```

2. 在`run_all_migrations`函数中的迁移列表中添加你的新迁移：

```python
# 定义所有迁移
migrations = [
    AddBypassAIField(),
    AddNotificationServicesTable(),
    AddAccountDetailsFields(),
    YourNewMigration()  # 添加你的新迁移
]
```

## 迁移最佳实践

1. **幂等性**：确保你的迁移可以多次执行而不会产生错误。例如，在添加字段前先检查字段是否已存在。

2. **向后兼容**：尽量设计向后兼容的迁移，避免破坏现有功能。

3. **测试**：在生产环境执行前，先在测试环境测试你的迁移。

4. **备份**：在执行迁移前备份数据库。

5. **文档**：为你的迁移提供清晰的文档，说明迁移的目的和影响。

## 现有迁移

目前系统包含以下迁移：

1. **001_add_bypass_ai_field**：为SocialAccount表添加bypass_ai布尔字段，用于控制是否绕过AI判断直接推送。

2. **002_add_notification_services_table**：创建notification_services表，用于存储通知服务配置。

3. **003_add_avatar_url_field**：为SocialAccount表添加avatar_url字段，用于存储用户头像URL。

4. **004_add_account_details_fields**：为SocialAccount表添加display_name, bio, verified等详细信息字段（已集成到统一迁移系统）。

## 故障排除

如果迁移过程中出现错误，请检查日志以获取详细信息。常见问题包括：

- 数据库文件权限问题
- 表或字段已存在
- SQL语法错误
- 数据库锁定

如果需要手动修复迁移状态，可以直接编辑`db_migration_history`表。
