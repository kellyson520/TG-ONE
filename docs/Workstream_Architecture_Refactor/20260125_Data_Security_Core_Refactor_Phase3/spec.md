# Technical Specification: Data Security & Core Refactor Phase 3

## 1. DTO / Schema Design
We will use Pydantic v2 `BaseModel` for DTOs to ensure type safety and serialization.

### Directory Structure
```
src/
  schemas/
    __init__.py
    rule.py
    chat.py
    user.py
    common.py
```

### Example: RuleDTO
```python
from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime

class RuleBase(BaseModel):
    name: str = Field(..., min_length=1)
    keywords: List[str]
    is_active: bool = True
    # ... other fields

class RuleDTO(RuleBase):
    id: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True # ORM Compatibility
```

## 2. Service Refactoring Strategy (Splitting RuleManagementService)
Current `RuleManagementService` handles CRUD, complex logic, and config. We split it into a package `services/rule/`.

### Components
1.  **`RuleCRUDService`**: Wrapper around `RuleRepository`. Handles basic Get/Create/Update/Delete.
2.  **`RuleLogicService`**: Contains `check_message`, `evaluate_rules` logic. Pure business logic.
3.  **`RuleConfigService`**: Handles rule synchronization, settings updates.

### Facade
To minimize impact on existing code (Handlers), we maintain `RuleManagementService` class but it will now act as a Facade delegating to the sub-services.

```python
class RuleManagementService:
    def __init__(self):
        self.crud = RuleCRUDService()
        self.logic = RuleLogicService()
    
    async def get_rule(self, rule_id):
        return await self.crud.get_rule(rule_id)
```
*Note: Eventually we want to inject dependencies, but for this refactor, Facade is the bridge.*

## 3. Command Handler Splitting
Move `handlers/command_handlers.py` to `handlers/commands/`.

### Mapping
- **Media**: `download_media`, `auto_forward` related commands -> `media_commands.py`
- **Rule**: `add_rule`, `del_rule`, `list_rules` -> `rule_commands.py`
- **System**: `ping`, `status`, `restart` -> `system_commands.py`
- **Admin**: `ban`, `unban`, `promote` -> `admin_commands.py`

## 4. Database Migration (Alembic)
1.  Move models to `src/models/`.
2.  Update `core/container.py` and `db/` to point to new model locations.
3.  Initialize Alembic.
4.  Generate initial migration reflecting current state.
