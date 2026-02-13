# Handler Purity 修复补丁

## 需要修复的文件列表

### 1. admin_callback.py (line 150)
**问题**: `from models.models import async_cleanup_old_logs`
**修复**: 改用 `system_service.cleanup_old_logs(days)`

修复代码：
```python
# 修复前 (line 150-151)
from models.models import async_cleanup_old_logs
deleted_count = await async_cleanup_old_logs(days)

# 修复后
from services.system_service import system_service
result = await system_service.cleanup_old_logs(days)
if result.get('success'):
    deleted_count = result.get('deleted_count', 0)
```

### 2. other_callback.py (line 240)
**问题**: `from models.models import Keyword` 用于手动复制关键字
**修复**: 改用 `rule_management_service.copy_keywords_from_rule()`

修复代码：
```python
# 修复前 (line 236-244)
source_rule = await container.rule_repo.get_full_rule_orm(source_id)
target_rule = await container.rule_repo.get_full_rule_orm(target_id)

if source_rule and target_rule:
    from models.models import Keyword
    for kw in source_rule.keywords:
        target_rule.keywords.append(Keyword(keyword=kw.keyword, is_regex=kw.is_regex, is_blacklist=kw.is_blacklist))
    await container.rule_repo.save_rule(target_rule)

# 修复后
from services.rule.facade import rule_management_service
result = await rule_management_service.copy_keywords_from_rule(source_id, target_id)
if result.get('success'):
    await event.answer("✅ 关键字复制成功")
```

### 3. rules_menu.py (line 16-18)
**问题**: 直接使用 SQLAlchemy 查询规则列表
**修复**: 改用 `container.rule_repo.get_all_rules_with_chats()`

修复代码：
```python
# 修复前 (line 16-33)
from sqlalchemy import func, select
from sqlalchemy.orm import selectinload
from models.models import ForwardRule
from core.container import container
async with container.db.get_session() as session:
    total = (await session.execute(select(func.count(ForwardRule.id)))).scalar() or 0
    stmt = select(ForwardRule).options(...)
    result = await session.execute(stmt)
    rules = result.scalars().all()

# 修复后
from core.container import container
all_rules = await container.rule_repo.get_all_rules_with_chats()
total = len(all_rules)
per_page = 5
start = (page - 1) * per_page
rules = all_rules[start:start + per_page]
```

### 4. system_menu.py (line 309)
**问题**: `from models.models import get_db_health`
**修复**: 改用 `system_service.get_db_health()`

修复代码：
```python
# 修复前 (line 309-310)
from models.models import get_db_health
db = get_db_health()

# 修复后
from services.system_service import system_service
db = await system_service.get_db_health()
```

### 5. button_helpers.py (line 3, 795)
**问题**: 导入 `ForwardRule` 和 `PushConfig` 用于类型检查和查询
**修复**: 这个文件是 UI 辅助函数，需要接收 DTO 而不是 ORM 对象

### 6. forward_management.py (line 78)
**问题**: `from models.models import ForwardRule`
**修复**: 改用 Repository 层方法

## 修复优先级
1. **P0 (立即修复)**: admin_callback.py, other_callback.py
2. **P1 (高优先级)**: rules_menu.py, system_menu.py  
3. **P2 (中优先级)**: button_helpers.py, forward_management.py

## 注意事项
- 所有 Service 方法需要返回统一的 `{'success': bool, ...}` 格式
- 需要检查 `system_service` 是否有 `cleanup_old_logs` 和 `get_db_health` 方法
- 如果方法不存在，需要先在 Service 层添加这些方法
