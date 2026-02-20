# TG ONE Project Structure

> Updated: 2026-02-20 09:29

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
├── 📁 alembic              # Directory
├── 📄 alembic.ini          # File
├── 📁 api                  # Directory
├── 📁 controllers          # Directory
├── 📁 core                 # Core Business Logic
├── 📁 data                 # Directory
├── 📄 docker-compose.yml   # File
├── 📁 docs                 # Documentation (PSB)
├── 📁 enums                # Enumerations
├── 📁 filters              # Message Filters
├── 📁 handlers             # Command & Event Handlers
├── 📄 inspect_queue.py     # File
├── 📁 listeners            # Event Listeners
├── 📁 logs                 # Directory
├── 📄 main.py              # Application Entry
├── 📄 manage_update.py     # File
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
├── 📁 tests                # Test Suite
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
├── archive
│   ├── bridge.py
│   └── engine.py
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
│   ├── msg_utils.py
│   ├── patch.py
│   ├── priority_utils.py
│   ├── realtime_stats.py
│   ├── resource_gate.py
│   ├── rule_utils.py
│   ├── search_system.py
│   ├── sleep_manager.py
│   ├── smart_retry.py
│   ├── sqlite_config.py
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
├── states.py
└── stats_manager.py
```

### 📁 `docs/`

```
├── API_CONTRACT.md
├── Frontend_Backend_Integration_Plan.md
├── Frontend_Backend_Integration_Summary.md
├── Standard_Whitepaper.md
├── Workstream_Analytics
│   └── 20260219_Fix_Forward_Stats_Display
│       ├── report.md
│       ├── spec.md
│       ├── task.json
│       └── todo.md
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
│   ├── 20260207_Dedup_Engine_Refactor
│   │   ├── spec.md
│   │   └── todo.md
│   ├── report.md
│   ├── report_encoding_fix.md
│   ├── report_phase11_observability.md
│   ├── report_phase4_followup.md
│   ├── report_phase7_cleanup.md
│   ├── report_phase9_security.md
│   └── todo.md
├── Workstream_Bugfix
│   ├── 20260210_Fix_Container_AttributeError_and_Dedup_Fingerprint
│   │   └── todo.md
│   ├── 20260211_Fix_Alembic_Migration
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260211_Fix_EventBus_Emit_Error
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260211_Fix_Menu_Localization_And_System_Errors
│   │   └── todo.md
│   ├── 20260213_Fix_TaskExecution_Stall
│   │   ├── spec.md
│   │   └── todo.md
│   ├── 20260213_Fix_Update_Restart_Loop
│   │   ├── debug_scripts
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260213_Fix_WorkerService_Scaling_Monitor_Error
│   ├── 20260215_Fix_RuleLog_AttributeError
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260215_Fix_WebTimeDiffAndAccessLog
│   │   └── todo.md
│   ├── 20260216_Fix_Forward_Stats_Empty_Display
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260218_Fix_Analytics_Buttons
│   │   └── todo.md
│   ├── 20260218_Fix_Analytics_Worker_Registry
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260219_Fix_Database_Locked_Error
│   │   ├── report.md
│   │   ├── spec.md
│   │   └── todo.md
│   ├── 20260219_Fix_DuckDB_Timestamp_Cast
│   │   ├── report.md
│   │   └── todo.md
│   └── Menu_Quality_Improvements_Report.md
├── Workstream_Core
│   ├── 20260204_Dedup_Engine_Unit_Tests
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260204_Fix_Circular_Import_Startup_Error
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260204_P0_Fix_N_Plus_One
│   │   └── todo.md
│   ├── 20260204_P2_P3_Optimization
│   ├── 20260207_Dedup_Business_Completion
│   │   └── todo.md
│   ├── Task_Fix_Dedup_Overaggressive
│   │   ├── report.md
│   │   └── todo.md
│   └── Task_Upgrade_Dedup_Algorithm
│       ├── report.md
│       ├── spec.md
│       └── todo.md
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
│   ├── 20260208_Project_Health_Audit_And_Risk_Assessment
│   │   ├── Assessment_Report.md
│   │   └── todo.md
│   ├── 20260208_Refactor_Menu_System_And_Handler_Purity
│   │   ├── spec.md
│   │   └── todo.md
│   ├── 20260209_Controller_and_View_Modularization
│   │   ├── Proposal.md
│   │   ├── UI_GUIDE.md
│   │   ├── spec.md
│   │   ├── todo.md
│   │   ├── ui_upgrade_proposal.md
│   │   └── ui_upgrade_todo.md
│   ├── 20260210_Fix_Alembic_Migration
│   │   └── todo.md
│   ├── 20260210_Perfect_Shutdown_Architecture
│   │   ├── report.md
│   │   ├── spec.md
│   │   └── todo.md
│   ├── 20260211_Menu_Architecture_Deep_Audit
│   │   ├── audit_report.md
│   │   ├── handler_purity_deep_check_final.md
│   │   ├── handler_purity_fix_complete.md
│   │   ├── handler_purity_fix_patch.md
│   │   ├── handler_purity_fix_summary.md
│   │   ├── handler_session_usage_audit.md
│   │   ├── implementation_report.md
│   │   ├── implementation_report_final.md
│   │   ├── missing_logic_fix_report.md
│   │   ├── missing_logic_fix_report_round2.md
│   │   ├── phase1.1_report.md
│   │   ├── phase1.2_report.md
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
├── Workstream_Database
│   └── 20260210_Fix_AccessControlList_AlreadyExists_Error
│       └── todo.md
├── Workstream_Database_Optimization
│   ├── 20260218_Fix_SQLite_Locked_TaskQueue
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260218_Hot_Cold_Tiering_Universal
│   │   ├── spec.md
│   │   └── todo.md
│   └── 20260220_Fix_Database_Transaction_and_Integrity_Errors
│       └── todo.md
├── Workstream_Deduplication
│   └── 20260207_Upgrade_Deduplication_Engine_v4
│       ├── report.md
│       ├── spec.md
│       └── todo.md
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
│   ├── 20260206_Verify_Archive_Tests
│   │   └── todo.md
│   ├── 20260208_Fix_Import_Error_Startup
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260208_Investigate_Forward_Delay
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260208_LogAnalysis_P1
│   │   └── todo.md
│   ├── 20260219_Fix_Archive_and_Cleanup_Paths
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260220_Fix_UIStatus_Attribute_Error
│   │   ├── constants.py.bak
│   │   ├── report.md
│   │   ├── spec.md
│   │   └── todo.md
│   └── Task_Bind_Web_Port
│       └── todo.md
├── Workstream_MenuSystem
│   ├── 20260214_Menu_Callback_and_API_Consistency_Audit
│   │   ├── audit_report.md
│   │   ├── spec.md
│   │   └── todo.md
│   ├── 20260216_Refactor_Analytics_Menu_Architecture
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260216_Refactor_History_Task_List_Architecture
│   │   ├── report.md
│   │   └── todo.md
│   └── 20260216_Refactor_MenuController_CVM_Standardization
│       ├── report.md
│       └── todo.md
├── Workstream_Ops
│   ├── 20260210_Upgrade_Update_Service_NonGit
│   │   ├── report.md
│   │   ├── spec.md
│   │   └── todo.md
│   └── Fix_Non_Git_Update
├── Workstream_Optimization
│   ├── 20260213_Task_Queue_Throughput_and_Failure_Optimization
│   │   ├── spec.md
│   │   └── todo.md
│   ├── 20260219_VPS_High_Load_Fix
│   │   ├── report.md
│   │   └── todo.md
│   ├── 20260219_Worker_Memory_Crisis_Fix
│   │   ├── report.md
│   │   ├── spec.md
│   │   └── todo.md
│   └── 20260219_Worker_Performance_Boost
│       ├── report.md
│       ├── spec.md
│       └── todo.md
├── Workstream_Refactor
│   └── Callback_Split_Plan
│       ├── inventory
│       │   └── components.md
│       ├── proposal.md
│       └── todo.md
├── Workstream_Testing
│   └── Task_Integration_Mixed_Media
│       ├── report.md
│       ├── spec.md
│       └── todo.md
├── Workstream_TimeFlow
│   └── 20260216_TimeFlow_Init
│       ├── roadmap.md
│       └── todo.md
├── Workstream_UI
│   ├── 20260207_FixBackNavigation
│   │   ├── report.md
│   │   └── todo.md
│   └── 20260208_Unified_Command_Menu_System
│       ├── spec.md
│       └── todo.md
├── Workstream_UI_UX
│   ├── 20260115_Web_Interface_Refactor
│   │   ├── spec.md
│   │   └── todo.md
│   └── 20260214_UI_Replacement_Feasibility
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
├── Workstream_Web_Real_Integration
│   ├── 20260215_Real_Data_Integration
│   │   └── todo.md
│   ├── spec.md
│   └── todo.md
├── Workstream_Web_UI
│   ├── 20260214_Real_Data_Integration
│   │   └── todo.md
│   ├── Mock_API_Server
│   │   ├── report.md
│   │   └── todo.md
│   ├── report.md
│   ├── spec.md
│   └── todo.md
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
│   ├── Workstream_Bugfix
│   │   ├── 20260208_FixSenderFilterMetadata
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260208_Fix_Encoding_BotCommands
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260209_Fix_Shutdown_Hang
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260210_Fix_Update_Failure
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260211_Fix_SessionCallback_ImportError
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260211_Fix_Unmatched_Button_Actions
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260211_Fix_ViewResult_NameError
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260212_KeywordFilterFix
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260214_Fix_SQLite_Disk_IO_Error
│   │   │   ├── auto_fix_readme.md
│   │   │   ├── check_integrity.py
│   │   │   ├── proposal_statistics_persistence.md
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260215_FixUnknownForwarderDisplay
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260215_FixUnknownRecordAndTaskFetchFailure
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260215_FixWebBugs
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260215_Fix_Optional_NameError
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260216_Fix_History_Message_Menu_Actions
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   └── 20260216_Fix_Unmatched_History_Actions
│   │       ├── report.md
│   │       ├── spec.md
│   │       └── todo.md
│   ├── Workstream_Core
│   │   ├── 20260203_Fix_Container_AttributeError
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260204_Fix_AddMode_KeyError
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260204_Menu_System_Integrity_Audit
│   │   │   ├── audit_report.md
│   │   │   ├── deep_audit_final_report.md
│   │   │   ├── deep_audit_summary.md
│   │   │   ├── handler_audit_report.md
│   │   │   ├── report.md
│   │   │   ├── test_results.md
│   │   │   └── todo.md
│   │   └── 20260207_FixGreenletError_History
│   │       ├── report.md
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
│   │   ├── 20260202_Fix_Callback_And_Web_Tests
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260208_Implement_Priority_Queue
│   │   │   ├── checklist_qos_v3.md
│   │   │   ├── checklist_qos_v4.md
│   │   │   ├── performance_analysis_v4.md
│   │   │   ├── proposal_v2_dynamic_qos.md
│   │   │   ├── proposal_v3_fair_qos.md
│   │   │   ├── proposal_v4_lane_routing.md
│   │   │   ├── proposal_v5_autonomous.md
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   └── 20260209_Fix_Async_SystemExit_Error
│   │       ├── report.md
│   │       ├── spec.md
│   │       └── todo.md
│   ├── Workstream_Deduplication
│   │   ├── 20260207_Fix_Dedup_Repository_AttributeError
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   └── 20260207_Fix_Media_Signature_Integrity_Error_P1
│   │       ├── report.md
│   │       └── todo.md
│   ├── Workstream_Feature
│   │   └── 20260202_Online_Update_Feature
│   │       ├── report.md
│   │       ├── spec.md
│   │       └── todo.md
│   ├── Workstream_Infrastructure
│   │   ├── 20260127_Local_CI_Workflow
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260208_Advanced_Update_Interface
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260208_Beautify_Docker_Build_UX
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260208_Enhance_Priority_Display
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260208_Enhance_Update_Service
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   └── 20260208_Update_Build_System_to_uv
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
│   │   ├── 20260207_Enhance_Update_Robustness
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   ├── test_plan.md
│   │   │   └── todo.md
│   │   ├── 20260207_Fix_Empty_Text_Deduplication_Bug
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260207_Fix_Filter_Deduplication_Conflict
│   │   │   ├── report
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260207_Hotfix_Sync_And_UI_Fixes
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260207_Restore_MultiSource_Menu
│   │   │   └── report.md
│   │   ├── 20260208_Fix_Forward_Hub_Refresh_Error
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260208_Fix_Missing_Dependency_Check_Log
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   └── 20260208_Fix_Redundant_Shutdown_Warning
│   │       ├── report.md
│   │       ├── spec.md
│   │       └── todo.md
│   ├── Workstream_MenuSystem
│   │   ├── 20260216_Fix_Forward_Hub_Buttons
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260216_Fix_Forward_Stats_Display
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   └── 20260216_Fix_MultiSource_Management_Layout
│   │       ├── report.md
│   │       ├── spec.md
│   │       └── todo.md
│   ├── Workstream_Optimization
│   │   └── 20260212_API_Performance_Optimization
│   │       ├── report.md
│   │       ├── spec.md
│   │       └── todo.md
│   ├── Workstream_UI_UX
│   │   └── 20260205_Upgrade_Date_Picker
│   │       ├── report.md
│   │       ├── spec.md
│   │       └── todo.md
│   └── session_menu_deprecated.py
├── file_list.txt
├── finish
├── fixes
│   ├── DEPLOYMENT_CHECKLIST.md
│   ├── SUMMARY_dedup_fix.md
│   ├── dedup_critical_fix_20260205.md
│   └── fix_analytics_and_media_strategy.md
├── process.md
├── setup_guide.md
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
│   │   ├── menu_entrypoint.py
│   │   ├── modules
│   │   │   ├── __init__.py
│   │   │   ├── changelog_callback.py
│   │   │   ├── common_utils.py
│   │   │   ├── rule_actions.py
│   │   │   ├── rule_dedup_settings.py
│   │   │   ├── rule_nav.py
│   │   │   ├── rule_settings.py
│   │   │   └── sync_settings.py
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
│   │   └── system_menu.py
│   ├── new_menu_system.py
│   ├── settings_manager.py
│   └── strategies
│       ├── __init__.py
│       ├── admin.py
│       ├── ai.py
│       ├── analytics.py
│       ├── base.py
│       ├── copy.py
│       ├── dedup.py
│       ├── entry_point.py
│       ├── history.py
│       ├── media.py
│       ├── push.py
│       ├── registry.py
│       ├── rules.py
│       ├── search.py
│       ├── settings.py
│       ├── system.py
│       └── ufb.py
├── command_handlers.py
├── commands
│   ├── admin_commands.py
│   ├── cancel_command.py
│   ├── dedup_commands.py
│   ├── media_commands.py
│   ├── menu_diagnostics.py
│   ├── rule_commands.py
│   ├── stats_commands.py
│   └── system_commands.py
├── link_handlers.py
├── list_handlers.py
├── priority_handler.py
├── prompt_handlers.py
├── search_ui_manager.py
└── user_handler.py
```

### 📁 `services/`

```
├── __init__.py
├── access_control_service.py
├── active_session_service.py
├── ai_service.py
├── analytics_service.py
├── audit_service.py
├── authentication_service.py
├── backup_service.py
├── batch_user_service.py
├── bloom_filter.py
├── cache_service.py
├── chat_info_service.py
├── compression_service.py
├── config_service.py
├── db_buffer.py
├── db_maintenance_service.py
├── dedup
│   ├── __init__.py
│   ├── engine.py
│   ├── strategies
│   │   ├── __init__.py
│   │   ├── album.py
│   │   ├── base.py
│   │   ├── content.py
│   │   ├── signature.py
│   │   ├── similarity.py
│   │   ├── sticker.py
│   │   └── video.py
│   ├── tools.py
│   └── types.py
├── dedup_service.py
├── download_service.py
├── exception_handler.py
├── forward_log_writer.py
├── forward_service.py
├── forward_settings_service.py
├── legacy_backup_bridge.py
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
├── task_dispatcher.py
├── task_service.py
├── update_service.py
├── user_service.py
└── worker_service.py
```

### 📁 `ui/`

```
├── builder.py
├── builders
│   └── time_picker.py
├── constants.py
├── menu_renderer.py
└── renderers
    ├── admin_renderer.py
    ├── base_renderer.py
    ├── dedup_renderer.py
    ├── main_menu_renderer.py
    ├── media_renderer.py
    ├── rule_renderer.py
    ├── session_renderer.py
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
├── frontend
│   ├── README.md
│   ├── components.json
│   ├── dist
│   │   ├── assets
│   │   │   ├── index-BJH_9hPs.css
│   │   │   └── index-CfQzsMIS.js
│   │   └── index.html
│   ├── eslint.config.js
│   ├── index.html
│   ├── lint_output.txt
│   ├── lint_output_2.txt
│   ├── package-lock.json
│   ├── package.json
│   ├── postcss.config.js
│   ├── src
│   │   ├── App.css
│   │   ├── App.tsx
│   │   ├── components
│   │   │   ├── layout
│   │   │   │   ├── Header.tsx
│   │   │   │   ├── Layout.tsx
│   │   │   │   └── Sidebar.tsx
│   │   │   └── ui
│   │   │       ├── accordion.tsx
│   │   │       ├── alert-dialog.tsx
│   │   │       ├── alert.tsx
│   │   │       ├── aspect-ratio.tsx
│   │   │       ├── avatar.tsx
│   │   │       ├── badge.tsx
│   │   │       ├── breadcrumb.tsx
│   │   │       ├── button-group.tsx
│   │   │       ├── button.tsx
│   │   │       ├── calendar.tsx
│   │   │       ├── card.tsx
│   │   │       ├── carousel.tsx
│   │   │       ├── chart.tsx
│   │   │       ├── checkbox.tsx
│   │   │       ├── collapsible.tsx
│   │   │       ├── command.tsx
│   │   │       ├── context-menu.tsx
│   │   │       ├── dialog.tsx
│   │   │       ├── drawer.tsx
│   │   │       ├── dropdown-menu.tsx
│   │   │       ├── empty.tsx
│   │   │       ├── field.tsx
│   │   │       ├── form.tsx
│   │   │       ├── hover-card.tsx
│   │   │       ├── input-group.tsx
│   │   │       ├── input-otp.tsx
│   │   │       ├── input.tsx
│   │   │       ├── item.tsx
│   │   │       ├── kbd.tsx
│   │   │       ├── label.tsx
│   │   │       ├── menubar.tsx
│   │   │       ├── navigation-menu.tsx
│   │   │       ├── pagination.tsx
│   │   │       ├── popover.tsx
│   │   │       ├── progress.tsx
│   │   │       ├── radio-group.tsx
│   │   │       ├── resizable.tsx
│   │   │       ├── scroll-area.tsx
│   │   │       ├── select.tsx
│   │   │       ├── separator.tsx
│   │   │       ├── sheet.tsx
│   │   │       ├── sidebar.tsx
│   │   │       ├── skeleton.tsx
│   │   │       ├── slider.tsx
│   │   │       ├── sonner.tsx
│   │   │       ├── spinner.tsx
│   │   │       ├── switch.tsx
│   │   │       ├── table.tsx
│   │   │       ├── tabs.tsx
│   │   │       ├── textarea.tsx
│   │   │       ├── toggle-group.tsx
│   │   │       ├── toggle.tsx
│   │   │       └── tooltip.tsx
│   │   ├── hooks
│   │   │   └── use-mobile.ts
│   │   ├── index.css
│   │   ├── lib
│   │   │   ├── api-client.ts
│   │   │   ├── api.ts
│   │   │   ├── utils.ts
│   │   │   └── websocket.ts
│   │   ├── main.tsx
│   │   ├── pages
│   │   │   ├── Archive.tsx
│   │   │   ├── AuditLogs.tsx
│   │   │   ├── Dashboard.tsx
│   │   │   ├── Downloads.tsx
│   │   │   ├── History.tsx
│   │   │   ├── Login.tsx
│   │   │   ├── Logs.tsx
│   │   │   ├── Rules.tsx
│   │   │   ├── Security.tsx
│   │   │   ├── Settings.tsx
│   │   │   ├── Tasks.tsx
│   │   │   ├── Users.tsx
│   │   │   └── Visualization.tsx
│   │   ├── services
│   │   │   ├── auth-service.ts
│   │   │   └── system-service.ts
│   │   ├── store
│   │   │   └── index.ts
│   │   └── types
│   │       └── index.ts
│   ├── tailwind.config.js
│   ├── tsconfig.app.json
│   ├── tsconfig.json
│   ├── tsconfig.node.json
│   └── vite.config.ts
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
│   ├── rules
│   │   ├── rule_content_router.py
│   │   ├── rule_crud_router.py
│   │   └── rule_viz_router.py
│   ├── security_router.py
│   ├── settings_router.py
│   ├── simulator_router.py
│   ├── spa_router.py
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
├── schemas
│   ├── response.py
│   └── rule_schemas.py
└── security
    ├── __init__.py
    ├── csrf.py
    ├── deps.py
    ├── exceptions.py
    ├── log_broadcast_handler.py
    ├── password_validator.py
    └── rate_limiter.py
```