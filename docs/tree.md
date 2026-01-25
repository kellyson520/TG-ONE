# TG ONE Project Structure

> Updated: 2026-01-15 21:04

---

## Directory Overview

```
TG ONE/
├── 📄 .dockerignore        # File
├── 📄 .env                 # File
├── 📄 .gitignore           # File
├── 📄 .secret_key          # File
├── 📄 AGENTS.md            # AI Skills Context
├── 📄 Dockerfile           # Docker Build
├── 📁 ai                   # AI Provider Integration
├── 📄 analytics.log        # File
├── 📁 api                  # Directory
├── 📁 archive              # Data Archival
├── 📄 cache.db             # File
├── 📁 config               # Global Config
├── 📁 controllers          # Directory
├── 📁 core                 # Core Business Logic
├── 📁 data                 # Directory
├── 📁 db                   # Directory
├── 📄 debug_output.txt     # File
├── 📄 dedup_log.txt        # File
├── 📄 docker-compose.yml   # File
├── 📁 docs                 # Documentation (PSB)
├── 📁 enums                # Enumerations
├── 📁 filters              # Message Filters
├── 📁 handlers             # Command & Event Handlers
├── 📁 listeners            # Event Listeners
├── 📁 logs                 # Directory
├── 📄 main.py              # Application Entry
├── 📁 managers             # State Managers
├── 📁 middlewares          # Middleware Layer
├── 📁 migrations           # Directory
├── 📁 models               # Data Models
├── 📄 pyproject.toml       # File
├── 📄 pytest.ini           # File
├── 📄 pytest_collect.txt   # File
├── 📄 reorganize_tasks.py  # File
├── 📁 repositories         # Data Access Layer
├── 📄 requirements.txt     # Python Dependencies
├── 📁 rss                  # RSS Services
├── 📁 scheduler            # Task Scheduler
├── 📁 scripts              # Utility Scripts
├── 📁 services             # Service Layer
├── 📁 sessions             # Directory
├── 📁 temp                 # Directory
├── 📁 temp_test_db         # Directory
├── 📁 tests                # Test Suite
├── 📁 ufb                  # UFB Client
├── 📁 ui                   # Bot UI Renderer
├── 📄 update_links.py      # File
├── 📁 utils                # Utilities
├── 📄 version.py           # Version Info
├── 📁 web_admin            # FastAPI Admin Backend
├── 📁 zhuanfaji            # Directory
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
├── compatibility.py
├── config.py
├── container.py
├── database.py
├── db_init.py
├── event_bus.py
├── exceptions.py
├── pipeline.py
├── shutdown.py
└── states.py
```

### 📁 `docs/`

```
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
│   ├── 20260113_Fix_Log_Page_Read_Error_Build
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
│   ├── 20260115_Service_Tests_Deep_Dive
│   │   ├── report.md
│   │   └── todo.md
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
├── Workstream_Web_UI
│   ├── report.md
│   ├── spec.md
│   └── todo.md
├── archive
│   ├── Workstream_Core_Engineering
│   │   ├── 20260109_Callback_Handler_Testing_Phase5
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260109_DebugHandlerImports
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260109_Integration_Testing_Setup
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260109_Security_Phase2
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260109_Unit_Testing_Refine
│   │   ├── 20260109_User_Handler_Testing
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260111_DB_Archive_Stability
│   │   │   └── report.md
│   │   ├── 20260111_DB_Test_Refine
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260111_Hot_Reload_Guard
│   │   │   └── spec.md
│   │   ├── 20260111_Root_Cleanup
│   │   │   └── todo.md
│   │   ├── 20260111_Security_Cleanup
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260111_Security_Phase3
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260111_Web_Interaction_Test
│   │   ├── 20260112_Bot_Features_Optimization
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260112_DB_Corruption_and_Menu_Recursion_Fix
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260112_Docker_Deploy_Fix
│   │   │   ├── process_update.md
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260112_Fix_Controllers_Error
│   │   │   ├── report.md
│   │   │   ├── report_completion.md
│   │   │   ├── report_login_fix.md
│   │   │   └── report_migration_fix.md
│   │   ├── 20260112_Fix_DB_Session_Conflict
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260112_Fix_Lifespan_Error_Plan
│   │   │   └── report.md
│   │   ├── 20260112_Fix_Settings_Menu
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260112_Fix_Startup_Crash_Plan
│   │   │   ├── reference_imports.md
│   │   │   ├── report.md
│   │   │   ├── report_imports_phase2.md
│   │   │   ├── report_imports_phase3.md
│   │   │   └── spec.md
│   │   ├── 20260112_Integration_Testing
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260112_OpenSkills_Integration_Setup
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260112_PhaseC_D_Finalize
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260112_PhaseH_Optimization_Build
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260113_Architecture_Advice_Scale
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   ├── spec_low_resource.md
│   │   │   └── todo.md
│   │   ├── 20260113_Auth_Unification_Refactor
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260113_Bot_Menu_Migration_And_Fix
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260113_Bot_Menu_Refactor_and_Callback_Fix
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260113_Bug_Fix_Suite_Build
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260113_Cache_Unification
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260113_Feature_Alignment_OldArch_Setup
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260113_Fix_Callback_Async_Error
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260113_Fix_Config_Deprecation
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260113_Fix_DB_Migration_Forward_Rules_Build
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260113_Fix_NameError_Container_Build
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260113_Fix_Settings_Serialization
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260113_Full_Link_Trace_Build
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   ├── todo.md
│   │   │   └── verify_trace.py
│   │   ├── 20260113_History_Optimization_and_Test
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260113_Log_Format_Optimization_Build
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260113_Message_Pipeline_Debug_Test
│   │   │   ├── report.md
│   │   │   ├── reproduce_cache_issue.py
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260113_Stats_Perf_Fix
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260113_Trace_Analyzer_Build
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260114_Business_Log_Enhancement_Build
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260114_Comprehensive_Pipeline_Testing
│   │   │   ├── TESTING_GUIDE.md
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260114_Core_Pipeline_Fix_And_Test
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260114_DB_Health_Check_Integration
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260114_Filter_Context_Fix
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260114_Fix_Logger_TypeError_Build
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260114_Fix_Malformed_DB
│   │   │   ├── diagnose.py
│   │   │   ├── repair_db.py
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260114_Fix_Pipeline_AttributeError
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260114_Fix_Pipeline_Context_And_Dedup
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260114_Fix_Sender_And_Stats_Runtime_Errors
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260114_Fix_Sender_Dedup_Logic_Build
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260114_Forward_Recorder_Enhancement
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260114_Graceful_Shutdown_Implementation
│   │   │   ├── ARCHITECTURE_UPDATE.md
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260114_Health_Check_Improvement
│   │   │   ├── health_report_20260114_094722.md
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   ├── system_health.py
│   │   │   └── todo.md
│   │   ├── 20260114_History_Message_Enhancement
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260114_Integration_Boundary_Tests_Build
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260114_Log_Analysis_Fix_01
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260114_Log_Level_Optimization_Build
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260114_Menu_Renderer_Fix
│   │   │   └── report.md
│   │   ├── 20260114_Menu_System_Refactor_Build
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260114_Optimize_Task_ID_Display_Build
│   │   │   ├── inspect_ids.py
│   │   │   ├── report.md
│   │   │   ├── todo.md
│   │   │   └── verify_short_id.py
│   │   ├── 20260114_Sender_Dedup_Refactor_Plan
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260114_Sender_RateLimit_Unification
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260114_Switch_Command_Fix_Phase1
│   │   │   ├── analyze_logs.py
│   │   │   ├── analyze_switch.py
│   │   │   ├── diagnosis.md
│   │   │   ├── direct_dump.py
│   │   │   ├── dump_rules.py
│   │   │   ├── migrate_db.py
│   │   │   ├── quick_test.py
│   │   │   ├── read_last_logs.py
│   │   │   ├── report.md
│   │   │   ├── summary.md
│   │   │   ├── test_id_matching.py
│   │   │   └── test_switch_logic.py
│   │   ├── 20260114_User_Rule_Match_Fix
│   │   │   ├── bot_loop_fix.md
│   │   │   ├── check_db.py
│   │   │   ├── check_db_video.py
│   │   │   ├── enable_videohash_async.py
│   │   │   ├── fix_media_types.py
│   │   │   ├── fix_report.md
│   │   │   ├── force_disable_videohash.py
│   │   │   ├── report.md
│   │   │   ├── shutdown_fix.md
│   │   │   ├── test_id_normalization.py
│   │   │   ├── todo.md
│   │   │   └── video_dedup_fix.md
│   │   ├── 20260115_Create_Task_Scanner_Skill
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260115_Display_Chat_Name_Instead_Of_ID
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260115_Fix_Service_Tests
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── report.md
│   │   ├── spec.md
│   │   └── todo.md
│   └── Workstream_Web_UI
│       ├── 20260111_Frontend_UnitTest_Setup
│       │   └── todo.md
│       ├── 20260111_Log_Viewer_Build
│       │   └── todo.md
│       ├── 20260111_Notification_System
│       │   ├── report.md
│       │   └── todo.md
│       ├── 20260111_Responsive_DarkMode
│       │   ├── report.md
│       │   └── todo.md
│       ├── 20260111_Rule_Flow_Visualization
│       │   ├── report.md
│       │   └── todo.md
│       ├── 20260111_WebSocket_UnitTest
│       │   ├── report.md
│       │   └── todo.md
│       ├── 20260111_Web_E2E_Test
│       │   ├── report.md
│       │   └── todo.md
│       ├── 20260111_Web_Optimization
│       │   └── todo.md
│       ├── 20260113_Analyze_HAR_Lag
│       │   ├── report.md
│       │   ├── spec.md
│       │   └── todo.md
│       ├── 20260113_BugFix_and_Optimization_Build
│       │   ├── report.md
│       │   ├── spec.md
│       │   └── todo.md
│       ├── 20260113_Data_Binding_Error_Handling
│       │   ├── report.md
│       │   ├── spec.md
│       │   └── todo.md
│       ├── 20260113_Fix_Auth_Deprecation_And_Settings
│       │   ├── report.md
│       │   ├── spec.md
│       │   └── todo.md
│       ├── 20260113_Fix_Settings_Log_Sidebar_Lag
│       │   ├── report.md
│       │   ├── spec.md
│       │   └── todo.md
│       ├── 20260113_Fix_Web_Auth_And_Dashboard_Hang
│       │   ├── report.md
│       │   └── todo.md
│       ├── 20260113_Fix_Web_Perf_Auth_Phase
│       │   ├── report.md
│       │   ├── spec.md
│       │   └── todo.md
│       ├── 20260113_Login_BugFix
│       │   ├── report.md
│       │   ├── spec.md
│       │   └── todo.md
│       ├── 20260113_Menu_Alignment_Build
│       │   ├── report.md
│       │   ├── spec.md
│       │   └── todo.md
│       ├── 20260113_Missing_Pages_Build
│       │   ├── report.md
│       │   └── todo.md
│       ├── 20260113_Rules_Page_Layout_Fix
│       │   ├── report.md
│       │   ├── spec.md
│       │   └── todo.md
│       ├── 20260113_Tasks_Page_Implementation_Build
│       │   ├── report.md
│       │   ├── spec.md
│       │   └── todo.md
│       ├── 20260113_Trace_UI_Integration
│       │   ├── report.md
│       │   └── todo.md
│       ├── 20260113_Web_Logs_Settings_Fix_Build
│       │   ├── report.md
│       │   ├── spec.md
│       │   └── todo.md
│       ├── 20260113_Web_Page_Implementation
│       │   ├── report.md
│       │   ├── spec.md
│       │   └── todo.md
│       ├── 20260114_Fix_Menu_Bugs_Build
│       │   ├── report.md
│       │   ├── spec.md
│       │   └── todo.md
│       ├── 20260114_Web_UI_Improvements
│       │   ├── report.md
│       │   ├── spec.md
│       │   └── todo.md
│       ├── report.md
│       ├── spec.md
│       └── todo.md
├── file_list.txt
├── finish
│   ├── Workstream_Core_Engineering
│   │   ├── 20260115_Algorithm_Phase1_Impl
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   ├── test_report.md
│   │   │   └── todo.md
│   │   ├── 20260115_Algorithm_Phase2_Impl
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260115_Algorithm_Phase3_Integration
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260115_Create_DB_Migration_Enforcer_Skill
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260115_Create_Full_System_Verification_Skill
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260115_Create_Runtime_Diagnostics_Skill
│   │   │   └── todo.md
│   │   ├── 20260115_Create_Task_Syncer_Skill
│   │   │   ├── institutionalization_report.md
│   │   │   ├── report.md
│   │   │   ├── scan_results.md
│   │   │   ├── summary_report.md
│   │   │   └── todo.md
│   │   ├── 20260115_Critical_Errors_Fix_Build
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260115_Double_Forward_Fix
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260115_Fix_Database_Compression_Columns
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260115_Fix_FastAPI_Lifespan_Error
│   │   │   ├── report.md
│   │   │   ├── skill_creation_todo.md
│   │   │   └── todo.md
│   │   ├── 20260115_Fix_Lifespan_GeneratorExit
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260115_Fix_Malformed_Session_Database
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260115_Fix_RSSPullService_Aiohttp_Missing
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260115_Fix_Unit_Test_Regression
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260115_Fix_WTinyLFU_NameError_Time
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260115_Fix_WorkerService_UnboundLocalError
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260115_Implement_Workspace_Hygiene_Skill
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260115_Import_Error_Fix_Build
│   │   │   └── report.md
│   │   ├── 20260115_Integration_Testing_Refine_Phase1
│   │   │   ├── report.md
│   │   │   ├── spec.md
│   │   │   └── todo.md
│   │   ├── 20260115_Phase5_Adaptive_Backpressure
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260115_Phase5_CircuitBreaker_Impl
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260115_Phase5_LSH_Forest_Impl
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260115_Production_Polish_Phase4
│   │   │   ├── report.md
│   │   │   └── todo.md
│   │   ├── 20260115_Refining_Scheduling_Caching
│   │   │   └── report.md
│   │   ├── 20260115_Strategic_Advisory_Plan
│   │   │   ├── implementation_summary.md
│   │   │   ├── proposal.md
│   │   │   ├── proposal_v2.md
│   │   │   ├── proposal_v3.md
│   │   │   ├── proposal_v4.md
│   │   │   ├── proposal_v5.md
│   │   │   ├── report_algorithmic_v3.md
│   │   │   ├── spec_phase5_deep.md
│   │   │   ├── summary_report.md
│   │   │   └── todo.md
│   │   └── 20260115_System_Audit_Plan
│   │       ├── report.md
│   │       ├── report_final.md
│   │       ├── report_phase_2.md
│   │       ├── spec.md
│   │       └── todo.md
│   └── Workstream_Web_UI
├── process.md
└── tree.md
```

### 📁 `handlers/`

```
├── __init__.py
├── advanced_media_prompt_handlers.py
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
│   │   ├── media_callback.py
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
│   ├── session_management.py
│   └── settings_manager.py
├── command_handlers.py
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
├── analytics_service.py
├── audit_service.py
├── authentication_service.py
├── batch_user_service.py
├── bloom_filter.py
├── chat_info_service.py
├── compression_service.py
├── config_service.py
├── db_buffer.py
├── dedup_service.py
├── download_service.py
├── exception_handler.py
├── forward_log_writer.py
├── forward_service.py
├── forward_settings_service.py
├── maintenance_service.py
├── metrics_collector.py
├── notification_service.py
├── queue_service.py
├── rate_limiter.py
├── rss_pull_service.py
├── rule_management_service.py
├── rule_service.py
├── session_service.py
├── settings.py
├── settings_applier.py
├── system_service.py
├── task_service.py
└── worker_service.py
```

### 📁 `ui/`

```
├── builders
│   └── time_picker.py
└── menu_renderer.py
```

### 📁 `utils/`

```
├── __init__.py
├── algorithm
│   └── lsh_forest.py
├── config
│   ├── ai_models.json
│   ├── delay_times.txt
│   ├── max_media_size.txt
│   ├── media_extensions.txt
│   └── summary_times.txt
├── core
│   ├── __init__.py
│   ├── constants.py
│   ├── env_config.py
│   ├── error_handler.py
│   ├── error_notifier.py
│   ├── json_ops.py
│   ├── log_config.py
│   ├── logger_utils.py
│   ├── patch.py
│   ├── settings.py
│   └── trace_analyzer.py
├── db
│   ├── __init__.py
│   ├── archive_init.py
│   ├── archive_manager.py
│   ├── archive_repair.py
│   ├── archive_store.py
│   ├── backup.py
│   ├── bloom_index.py
│   ├── database_cleaner.py
│   ├── database_manager.py
│   ├── db_context.py
│   ├── db_field_utils.py
│   ├── db_index_optimizer.py
│   ├── db_manager.py
│   ├── db_monitor.py
│   ├── db_operations.py
│   ├── db_optimization_suite.py
│   ├── db_sharding.py
│   ├── health_check.py
│   ├── persistent_cache.py
│   └── query_optimizer.py
├── forward_recorder.py
├── helpers
│   ├── __init__.py
│   ├── chat_context.py
│   ├── common.py
│   ├── datetime_utils.py
│   ├── dialog_helper.py
│   ├── entity_optimization.py
│   ├── entity_validator.py
│   ├── event_optimization.py
│   ├── id_utils.py
│   ├── json_utils.py
│   ├── message_utils.py
│   ├── metrics.py
│   ├── realtime_stats.py
│   ├── rule_utils.py
│   ├── search_system.py
│   ├── time_range.py
│   └── tombstone.py
├── history
│   ├── __init__.py
│   ├── backpressure.py
│   ├── error_handler.py
│   ├── media_filter.py
│   └── progress_tracker.py
├── media
│   ├── __init__.py
│   ├── content_enhancer.py
│   ├── excel_importer.py
│   ├── file_creator.py
│   └── media.py
├── network
│   ├── __init__.py
│   ├── aimd.py
│   ├── api_optimization.py
│   ├── api_optimization_config.py
│   ├── backpressure.py
│   ├── bot_heartbeat.py
│   ├── circuit_breaker.py
│   ├── log_push.py
│   ├── pid.py
│   ├── rate_limiter.py
│   ├── router.py
│   ├── telegram_api_optimizer.py
│   ├── telegram_utils.py
│   ├── telethon_session_fix.py
│   └── timing_wheel.py
├── processing
│   ├── __init__.py
│   ├── ac_automaton.py
│   ├── auto_delete.py
│   ├── batch_processor.py
│   ├── bloom_filter.py
│   ├── forward_queue.py
│   ├── hll.py
│   ├── message_task_manager.py
│   ├── rss_parser.py
│   ├── simhash.py
│   ├── smart_dedup.py
│   ├── unified_cache.py
│   └── wtinylfu.py
├── rss
│   ├── data
│   └── media
│       └── 1
├── temp
└── unified_sender.py
```

### 📁 `web_admin/`

```
├── README.md
├── __init__.py
├── app
├── core
│   └── templates.py
├── fastapi_app.py
├── middlewares
│   ├── ip_guard_middleware.py
│   └── trace_middleware.py
├── routers
│   ├── __init__.py
│   ├── auth_router.py
│   ├── page_router.py
│   ├── rule_router.py
│   ├── security_router.py
│   ├── settings_router.py
│   ├── simulator_router.py
│   ├── stats_router.py
│   ├── system_router.py
│   ├── user_router.py
│   └── websocket_router.py
├── run.py
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