# Project Menu Component Inventory

## Controllers (`controllers/`)
- **`menu_controller.py`**: The central coordinator for all menu actions.
  - *Responsibilities*: Coordinates between the View (Renderers) and Service layers. Handles business logic flow.
  - *Key methods*: `show_main_menu`, `show_forward_hub`, `show_rule_list`, `run_db_reindex`.

## Callbacks (`handlers/button/callback/`)
- **`new_menu_callback.py`**: The main entry point for callback routing.
  - *Responsibilities*: Receives raw events, parses `action` strings, and dispatches to the Controller.
  - *Current State*: Bloated with direct logic and extensive `if/elif` chains. Target for refactoring.
- **`modules/rule_dedup_settings.py`**: A partial split for rule-specific deduplication settings.

## Handlers / Modules (`handlers/button/modules/`)
These files often mix Controller logic and View logic (legacy pattern).
- **`rules_menu.py`**: Handles Rule List, Multi-source Management.
- **`history.py`**: Handles History Message Processing, Time Range functionality.
- **`smart_dedup_menu.py`**: Handles Deduplication Hub and Settings.
- **`picker_menu.py`**: Handles Date/Time pickers.

## UI Renderers (`ui/renderers/`)
- **`main_menu_renderer.py`**: Renders Main Menu, Forward Hub, Dedup Hub, Analytics Hub, System Hub.
- **`rule_renderer.py`**: Renders Rule List, Detail, Settings, Keywords.
- **`settings_renderer.py`**: Renders Dedup Settings, System Monitor, DB Performance.
- **`task_renderer.py`**: Renders History Task actions and selectors.

## Refactor Scope
The refactoring will primarily target:
1.  **Splitting `new_menu_callback.py`** into smaller router modules.
2.  **Consolidating Logic**: Moving logic from `handlers/button/modules/*.py` into `controllers/` or keeping them as pure helper modules, while ensuring `new_menu_callback.py` only routes.
