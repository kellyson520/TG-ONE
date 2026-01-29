# Specification: Web Admin & Presentation Layer Refactoring

## 1. Directory Structure Changes

### 1.1 Web Routers (`web_admin/routers/`)
Legacy files:
- `system_router.py`
- `rule_router.py`

Target structure:
- `web_admin/routers/system/`
    - `log_router.py`
    - `maintain_router.py`
    - `stats_router.py`
- `web_admin/routers/rules/`
    - `rule_crud_router.py`
    - `rule_import_export_router.py`

### 1.2 Handlers (`handlers/button/callback/`)
Legacy:
- `callback_handlers.py` (Monolithic)

Target:
- `handlers/button/callback/modules/`
    - `rule_callbacks.py`
    - `page_navigation_callbacks.py`
    - `settings_callbacks.py`

## 2. API Standardization

### 2.1 Response Model
All API endpoints MUST return JSON matching `ResponseSchema[T]`.

```python
class ResponseSchema(Generic[T]):
    success: bool
    data: Optional[T]
    error: Optional[str]
    meta: Optional[Dict[str, Any]]
```

### 2.2 Dependency Injection
❌ Forbidden:
```python
@router.get("/")
async def get_rules():
    container = get_container() # DIRECT ACCESS
    return container.rule_service.get_all()
```

✅ Required:
```python
@router.get("/")
async def get_rules(
    service: RuleService = Depends(get_rule_service)
):
    return service.get_all()
```

## 3. Database & Architecture Compliance
- Routers MUST NOT import `sqlalchemy` or `models`.
- Routers MUST ONLY interact with `Services` via `DTOs`.
