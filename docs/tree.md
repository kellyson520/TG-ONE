# TG ONE Project Structure

> Updated: 2026-02-07 10:50

---

## Directory Overview

```
TG ONE/
├── 📄 .dockerignore        # File
├── 📄 .env                 # File
├── 📄 .gitignore           # File
├── 📄 AGENTS.md            # AI Skills Context
├── 📄 CHANGELOG.md         # File
├── 📄 Dockerfile           # Docker Build
├── 📁 MagicMock            # Directory
├── 📄 README.md            # File
├── 📁 ai                   # AI Provider Integration
├── 📄 alembic.ini          # File
├── 📁 api                  # Directory
├── 📄 check_greenlet.py    # File
├── 📁 controllers          # Directory
├── 📁 core                 # Core Business Logic
├── 📁 data                 # Directory
├── 📄 debug_engine_internal.txt # File
├── 📄 debug_handler.py     # File
├── 📄 docker-compose.yml   # File
├── 📁 docs                 # Documentation (PSB)
├── 📁 enums                # Enumerations
├── 📁 filters              # Message Filters
├── 📁 handlers             # Command & Event Handlers
├── 📁 listeners            # Event Listeners
├── 📄 main.py              # Application Entry
├── 📁 middlewares          # Middleware Layer
├── 📁 migrations           # Directory
├── 📁 models               # Data Models
├── 📄 pytest.ini           # File
├── 📁 repositories         # Data Access Layer
├── 📄 requirements-dev.txt # File
├── 📄 requirements.txt     # Python Dependencies
├── 📁 scheduler            # Task Scheduler
├── 📁 schemas              # Directory
├── 📁 scripts              # Utility Scripts
├── 📁 services             # Service Layer
├── 📁 temp                 # Directory
├── 📁 temp_test_db         # Directory
├── 📄 test_out.txt         # File
├── 📄 test_out_utf8.txt    # File
├── 📄 test_out_v2.txt      # File
├── 📄 test_output.txt      # File
├── 📄 test_output_debug_2.txt # File
├── 📄 test_output_utf8.txt # File
├── 📄 test_results.txt     # File
├── 📁 tests                # Test Suite
├── 📄 tests_output.txt     # File
├── 📁 ui                   # Bot UI Renderer
├── 📄 version.py           # Version Info
├── 📁 web_admin            # FastAPI Admin Backend
```

---

## Detailed Structure

### 📁 `ai/`

```
├── __init__.py
├── base.py
├── claude_provider.py
├── deepseek_provider.py
├── gemini_provider.py
├── grok_provider.py
├── openai_base_provider.py
├── openai_provider.py
└── qwen_provider.py
```

### 📁 `core/`

```
├── __init__.py
├── algorithms
│   ├── ac_automaton.py
│   ├── bloom_filter.py
│   ├── hll.py
│   ├── lsh_forest.py
│   └── simhash.py
├── aop.py
├── bootstrap.py
├── cache
│   ├── persistent_cache.py
│   ├── unified_cache.py
│   └── wtinylfu.py
├── compatibility.py
├── config
│   ├── __init__.py
│   ├── ai_models.json
│   ├── delay_times.txt
│   ├── max_media_size.txt
│   ├── media_extensions.txt
│   ├── settings_loader.py
│   └── summary_times.txt
├── config_initializer.py
├── constants.py
├── container.py
├── context.py
├── database
├── database.py
├── db_factory.py
├── db_init.py
├── event_bus.py
├── exceptions.py
├── helpers
│   ├── __init__.py
│   ├── auto_delete.py
│   ├── chat_context.py
│   ├── circuit_breaker.py
│   ├── common.py
│   ├── datetime_utils.py
│   ├── db_utils.py
│   ├── dialog_helper.py
│   ├── entity_optimization.py
│   ├── entity_validator.py
│   ├── error_handler.py
│   ├── error_notifier.py
│   ├── event_optimization.py
│   ├── forward_recorder.py
│   ├── history
│   │   ├── __init__.py
│   │   ├── backpressure.py
│   │   ├── error_handler.py
│   │   ├── media_filter.py
│   │   └── progress_tracker.py
│   ├── id_utils.py
│   ├── json_utils.py
│   ├── lazy_import.py
│   ├── media
│   │   ├── __init__.py
│   │   ├── content_enhancer.py
│   │   ├── excel_importer.py
│   │   ├── file_creator.py
│   │   └── media.py
│   ├── message_utils.py
│   ├── metrics.py
│   ├── patch.py
│   ├── realtime_stats.py
│   ├── resource_gate.py
│   ├── rule_utils.py
│   ├── search_system.py
│   ├── sleep_manager.py
│   ├── smart_retry.py
│   ├── time_range.py
│   ├── tombstone.py
│   ├── trace_analyzer.py
│   └── unified_sender.py
├── lifecycle.py
├── logging.py
├── observability
│   ├── __init__.py
│   └── metrics.py
├── parsers
│   └── rss_parser.py
├── pipeline.py
├── session_wizard.py
├── shutdown.py
└── states.py
```

### 📁 `docs/`

```
├── API_CONTRACT.md
├── Frontend_Backend_Integration_Plan.md
├── Frontend_Backend_Integration_Summary.md
├── Standard_Whitepaper.md
├── Workstream_Architecture_Refactor
│   ├── 20260125_Core_Infrastructure_Cleanup_Phase2
│   │   ├── spec.md
│   │   └── todo.md
│   ├── 20260125_Data_Security_Core_Refactor_Phase3
│   │   ├── report.md
│   │   ├── review_status.md
│   │   ├── spec.md
│   │   ├── test_results.md
│   │   └── todo.md
│   ├── 20260125_Phase2_BugFixing_Verification
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260126_Service_Layer_Refactor_Phase4
│   │   ├── spec.md
│   │   └── todo.md
│   ├── 20260127_Phase8_Engineering_Excellence
│   │   └── todo.md
│   ├── 20260203_Modernize_Calls
│   │   └── todo.md
│   ├── report.md
│   ├── report_encoding_fix.md
│   ├── report_phase11_observability.md
│   ├── report_phase4_followup.md
│   ├── report_phase7_cleanup.md
│   ├── report_phase9_security.md
│   └── todo.md
├── Workstream_Core
│   ├── 20260204_Dedup_Engine_Unit_Tests
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260204_Fix_Circular_Import_Startup_Error
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260204_P0_Fix_N_Plus_One
│   │   └── todo.md
│   └── 20260204_P2_P3_Optimization
├── Workstream_Core_Engineering
│   ├── 20260112_Fix_Graceful_Shutdown_and_Logger_Error
│   │   └── todo.md
│   ├── 20260112_Full_System_Comprehensive_Verification
│   │   └── todo.md
│   ├── 20260112_Next_Phase_Plan
│   │   ├── duplicate_analysis.md
│   │   ├── spec.md
│   │   └── todo.md
│   ├── 20260113_Fix_Container_NameError_in_RuleService
│   │   └── todo.md
│   ├── 20260113_Full_Link_Unit_Testing
│   │   └── todo.md
│   ├── 20260113_Log_Archive_Implementation_Phase3
│   │   ├── spec.md
│   │   └── todo.md
│   ├── 20260113_System_Optimization_Proposal
│   │   ├── spec.md
│   │   └── todo.md
│   ├── 20260114_Bot_Menu_Refinement_L3
│   │   ├── spec.md
│   │   └── todo.md
│   ├── 20260114_Project_Security_Audit
│   │   ├── security_check_report.md
│   │   ├── spec.md
│   │   └── todo.md
│   ├── 20260115_Expand_Project_Test_Coverage
│   │   ├── p0_utils_part2_report.md
│   │   ├── p0_utils_report.md
│   │   ├── spec.md
│   │   └── todo.md
│   ├── 20260115_Service_Tests_Deep_Dive
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260129_Fix_Remaining_Integration_Tests
│   │   └── todo.md
│   ├── 20260130_Fix_CI_Timeout_And_Tests
│   │   ├── report.md
│   │   └── todo.md
│   ├── Phase_3_1_WebSocket_Infrastructure.md
│   ├── Phase_3_2_Task_Queue_Realtime.md
│   ├── Phase_3_3_Log_Streaming.md
│   ├── Phase_3_4_System_Stats.md
│   ├── debug_artifacts
│   │   └── test_import.py
│   ├── report.md
│   ├── spec.md
│   ├── test_coverage_improvement.md
│   ├── test_fix_progress.md
│   ├── test_summary.txt
│   └── todo.md
├── Workstream_Documentation
│   └── 20260109_Task_Backlog_Archive
│       ├── readme.md
│       └── todo.md
├── Workstream_Feature
├── Workstream_Infrastructure
│   ├── 20260127_Github_CI
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260202_Fix_Orchestration_Error
│   │   ├── report.md
│   │   └── todo.md
│   └── 20260204_Industrial_Grade_Update_System
│       ├── report.md
│       └── todo.md
├── Workstream_Maintenance
│   ├── 20260116_Telethon_Database_Corruption_Recurrence_Fix
│   │   └── todo.md
│   ├── 20260202_Enhance_Update_System
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260202_Fix_Cache_Corruption
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260202_Fix_Duplicate_Task_Fetching
│   │   └── todo.md
│   ├── 20260202_Fix_Secondary_Errors
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260202_Menu_Structural_Fix
│   │   ├── plan.md
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260203_Menu_System_Audit_and_Refactor
│   │   └── todo.md
│   ├── 20260204_Fix_Menu_Navigation_And_Data
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260204_GitPush_Changelog
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260205_Fix_Analytics_Service_Errors
│   │   └── todo.md
│   ├── 20260205_Fix_Async_And_Null_Errors
│   │   └── todo.md
│   ├── 20260205_Fix_Callback_And_Import_Errors
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260205_Fix_Database_Pool_Timeout
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260206_Architecture_Upgrade_Report.md
│   ├── 20260206_Fix_Sqlite_Lock_Error
│   │   └── todo.md
│   └── 20260206_Verify_Archive_Tests
│       └── todo.md
├── Workstream_UI_UX
│   └── 20260115_Web_Interface_Refactor
│       ├── spec.md
│       └── todo.md
├── Workstream_Web_Fault_Analysis
│   ├── 20260115_Web_500_Lag_Analysis
│   │   ├── report.md
│   │   └── todo.md
│   └── 20260116_Edge_Browser_Performance_Fix
│       ├── report.md
│       ├── spec.md
│       └── todo.md
├── Workstream_Web_UI
│   ├── report.md
│   ├── spec.md
│   └── todo.md
├── architecture_diagram.mermaid
├── archive
│   ├── Workstream_Architecture_Refactor
│   │   ├── 20260126_Phase5_Stability_Async_Governance
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260126_Web_Admin_Refactor_Phase6
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260130_ConfigAudit_Phase1
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260130_ConfigSSOT_Validation
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260131_DeadCode_and_Verification
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260131_Phase8_Remaining_Exec
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   └── 20260131_Type_Hinting_Coverage
│   │       ├── mypy_report.txt
│   │       ├── report.md
│   │       └── todo.md
│   ├── Workstream_Core
│   │   ├── 20260203_Fix_Container_AttributeError
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260204_Fix_AddMode_KeyError
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   └── 20260204_Menu_System_Integrity_Audit
│   │       ├── audit_report.md
│   │       ├── deep_audit_final_report.md
│   │       ├── deep_audit_summary.md
│   │       ├── handler_audit_report.md
│   │       ├── report.md
│   │       ├── test_results.md
│   │       └── todo.md
│   ├── Workstream_Core_Engineering
│   │   ├── 20260129_Align_Tests_UserHandler
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260129_Align_Tests_With_Project_Code
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260130_CI_Recursion_Fix
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   └── 20260202_Fix_Callback_And_Web_Tests
│   │       ├── report.md
│   │       └── todo.md
│   ├── Workstream_Feature
│   │   └── 20260202_Online_Update_Feature
│   │       ├── report.md
│   │       ├── spec.md
│   │       └── todo.md
│   ├── Workstream_Infrastructure
│   │   └── 20260127_Local_CI_Workflow
│   │       ├── report.md
│   │       └── todo.md
│   ├── Workstream_Maintenance
│   │   ├── 20260127_Fix_WebAdmin_Encoding
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260202_Fix_CSRF_Verification_Failed
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260202_Fix_ChatInfoService_NameError
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260202_Fix_Chat_Attribute_Error
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260202_Fix_JSON_Serialization_Error
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260202_Fix_Log_Duplication
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260202_Fix_Log_Errors
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260202_Fix_Menu_Callback_Error
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260202_Fix_RuleRepo_UnboundLocalError
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260202_Fix_WebAdmin_Port_Hardcoding
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260202_Remove_Cloud_CI
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260203_Fix_Missing_Route_RuleSettingsNew
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260203_Fix_NewMenuSystem_AttributeError
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260203_Fix_RuleRepository_AttributeError
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260203_Fix_Update_Comparison
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260203_Fix_Version_Pagination
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260204_Fix_Changelog_Edit_Message_Error
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260204_Fix_Config_Syntax_Error
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260204_Fix_Database_And_Import_Issues
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260204_Fix_Logic_And_Performance_Issues
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260204_Fix_Stability_Safety_Concurrency
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260204_Fix_Triple_Core_Issues
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260205_Deep_Audit_Menu_and_Logic
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260205_Fix_AttributeError_Settings_ENABLE_BATCH_FORWARD_API
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260205_Fix_Media_Filter_Unresponsive
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260206_Fix_Archive_Integration_Test
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260206_Fix_Triple_Errors
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260206_Hotfix_Four_Errors
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260206_Verify_Archive_System
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   └── 20260207_Hotfix_Sync_And_UI_Fixes
│   │       ├── report.md
│   │       └── todo.md
│   └── Workstream_UI_UX
│       └── 20260205_Upgrade_Date_Picker
│           ├── report.md
│           ├── spec.md
│           └── todo.md
├── file_list.txt
├── finish
├── fixes
│   ├── DEPLOYMENT_CHECKLIST.md
│   ├── SUMMARY_dedup_fix.md
│   └── dedup_critical_fix_20260205.md
├── process.md
└── tree.md
```

### 📁 `handlers/`

```
├── __init__.py
├── advanced_media_prompt_handlers.py
├── bot_commands_list.py
├── bot_handler.py
├── button
│   ├── __init__.py
│   ├── base.py
│   ├── button_helpers.py
│   ├── callback
│   │   ├── __init__.py
│   │   ├── admin_callback.py
│   │   ├── advanced_media_callback.py
│   │   ├── ai_callback.py
│   │   ├── callback_handlers.py
│   │   ├── generic_toggle.py
│   │   ├── media_callback.py
│   │   ├── modules
│   │   │   ├── __init__.py
│   │   │   ├── changelog_callback.py
│   │   │   ├── common_utils.py
│   │   │   ├── rule_actions.py
│   │   │   ├── rule_nav.py
│   │   │   ├── rule_settings.py
│   │   │   └── sync_settings.py
│   │   ├── new_menu_callback.py
│   │   ├── other_callback.py
│   │   ├── push_callback.py
│   │   └── search_callback.py
│   ├── forward_management.py
│   ├── modules
│   │   ├── __init__.py
│   │   ├── analytics_menu.py
│   │   ├── filter_menu.py
│   │   ├── history.py
│   │   ├── picker_menu.py
│   │   ├── rules_menu.py
│   │   ├── session_menu.py
│   │   ├── smart_dedup_menu.py
│   │   └── system_menu.py
│   ├── new_menu_system.py
│   └── settings_manager.py
├── command_handlers.py
├── commands
│   ├── admin_commands.py
│   ├── cancel_command.py
│   ├── dedup_commands.py
│   ├── media_commands.py
│   ├── rule_commands.py
│   ├── stats_commands.py
│   └── system_commands.py
├── link_handlers.py
├── list_handlers.py
├── prompt_handlers.py
├── search_ui_manager.py
└── user_handler.py
```

### 📁 `services/`

```
├── access_control_service.py
├── active_session_service.py
├── ai_service.py
├── analytics_service.py
├── audit_service.py
├── authentication_service.py
├── batch_user_service.py
├── bloom_filter.py
├── cache_service.py
├── chat_info_service.py
├── compression_service.py
├── config_service.py
├── db_buffer.py
├── db_maintenance_service.py
├── dedup
│   └── engine.py
├── dedup_service.py
├── download_service.py
├── exception_handler.py
├── forward_log_writer.py
├── forward_service.py
├── forward_settings_service.py
├── media_hydration_service.py
├── media_service.py
├── menu_service.py
├── metrics_collector.py
├── network
│   ├── __init__.py
│   ├── aimd.py
│   ├── api_optimization.py
│   ├── api_optimization_config.py
│   ├── backpressure.py
│   ├── bot_heartbeat.py
│   ├── circuit_breaker.py
│   ├── client_pool.py
│   ├── log_push.py
│   ├── pid.py
│   ├── rate_limiter.py
│   ├── router.py
│   ├── telegram_api_optimizer.py
│   ├── telegram_utils.py
│   ├── telethon_session_fix.py
│   └── timing_wheel.py
├── notification_service.py
├── queue_service.py
├── rate_limiter.py
├── remote_config_sync_service.py
├── rss_pull_service.py
├── rss_service.py
├── rule
│   ├── __init__.py
│   ├── crud.py
│   ├── facade.py
│   ├── filter.py
│   ├── logic.py
│   └── query.py
├── rule_management_service.py
├── rule_service.py
├── search_service.py
├── session_service.py
├── settings.py
├── settings_applier.py
├── smart_buffer.py
├── state_service.py
├── system_service.py
├── task_service.py
├── update_service.py
├── user_service.py
└── worker_service.py
```

### 📁 `ui/`

```
├── builders
│   └── time_picker.py
├── menu_renderer.py
└── renderers
    ├── base_renderer.py
    ├── main_menu_renderer.py
    ├── rule_renderer.py
    ├── settings_renderer.py
    └── task_renderer.py
```

### 📁 `web_admin/`

```
├── README.md
├── __init__.py
├── api
│   └── deps.py
├── core
│   └── templates.py
├── fastapi_app.py
├── mappers
│   └── rule_mapper.py
├── middlewares
│   ├── context_middleware.py
│   ├── ip_guard_middleware.py
│   ├── maintenance.py
│   ├── metrics_middleware.py
│   ├── rate_limit_middleware.py
│   └── trace_middleware.py
├── routers
│   ├── __init__.py
│   ├── auth_router.py
│   ├── page_router.py
│   ├── rules
│   │   ├── rule_content_router.py
│   │   ├── rule_crud_router.py
│   │   └── rule_viz_router.py
│   ├── security_router.py
│   ├── settings_router.py
│   ├── simulator_router.py
│   ├── stats_router.py
│   ├── system
│   │   ├── __init__.py
│   │   ├── log_router.py
│   │   ├── maintain_router.py
│   │   └── stats_router.py
│   ├── user_router.py
│   └── websocket_router.py
├── rss
│   ├── __init__.py
│   ├── api
│   │   ├── __init__.py
│   │   └── endpoints
│   │       ├── __init__.py
│   │       ├── feed.py
│   │       └── subscription.py
│   ├── configs
│   │   └── title_template.json
│   ├── core
│   │   └── __init__.py
│   ├── crud
│   │   └── entry.py
│   ├── models
│   │   ├── entry.py
│   │   └── schemas.py
│   ├── routes
│   │   ├── auth.py
│   │   └── rss.py
│   ├── services
│   │   ├── __init__.py
│   │   ├── feed_generator.py
│   │   └── feed_generator.py.new.py
│   └── templates
│       ├── login.html
│       ├── register.html
│       ├── rss_dashboard.html
│       └── rss_subscriptions.html
├── run.py
├── schemas
│   ├── response.py
│   └── rule_schemas.py
├── security
│   ├── __init__.py
│   ├── csrf.py
│   ├── deps.py
│   ├── exceptions.py
│   ├── log_broadcast_handler.py
│   ├── password_validator.py
│   └── rate_limiter.py
├── static
│   ├── css
│   │   └── main.css
│   ├── js
│   │   ├── command_panel.js
│   │   └── main.js
│   └── libs
│       ├── bootstrap
│       │   ├── css
│       │   │   └── bootstrap.min.css
│       │   └── js
│       │       └── bootstrap.bundle.min.js
│       ├── bootstrap-icons
│       │   └── font
│       │       ├── bootstrap-icons.css
│       │       └── fonts
│       │           ├── bootstrap-icons.woff
│       │           └── bootstrap-icons.woff2
│       └── echarts
│           └── echarts.min.js
└── templates
    ├── archive.html
    ├── audit_logs.html
    ├── base.html
    ├── components
    │   └── command_panel.html
    ├── dashboard.html
    ├── downloads.html
    ├── history.html
    ├── index.html
    ├── login.html
    ├── logs.html
    ├── register.html
    ├── rules.html
    ├── security.html
    ├── settings.html
    ├── tasks.html
    ├── users.html
    └── visualization.html
```