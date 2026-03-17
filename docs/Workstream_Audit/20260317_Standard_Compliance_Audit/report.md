# 20260317_Standard_Compliance_Audit 审计报告

## 📌 审计摘要 (Summary)
对 TG ONE 项目进行了深度架构合规性扫描，全面对照 `Standard_Whitepaper.md`。
**结论**: 项目在 **配置SSOT** (`os.getenv`) 方面整改彻底且效果极佳；但在 **Handler 纯洁性**、**模块级实例化** 以及 **调试日志残留** 方面存在 P1 级架构债务。

---

## 🚨 风险矩阵 (Risk Matrix)

### 🔴 1. Handler 纯洁性违规 (Handler Purity) - [P1]
*   **规则**: Handlers MUST NOT import `sqlalchemy` or `models.models`。
*   **证据**:
    *   `handlers\button\button_helpers.py:3`: **顶层导入** `from models.models import ForwardRule`
    *   `handlers\button\modules\rules_menu.py:158`: 延迟导入 `sqlalchemy import select`
    *   `handlers\button\modules\rules_menu.py:170`: 延迟导入 `models.models import RuleStatistics`
    *   `handlers\button\forward_management.py:78`: 延迟导入 `models.models import ForwardRule`
*   **整改建议**: Handler 绝不应该直接操作 ORM，必须将其封装进对应的 `Service`（如 `RuleService` / `QueryService`）。

---

### 🟠 2. 调试日志残留 (Print Abuse) - [P1]
*   **规则**: 生产环境绝不能使用 `print` 代替 `logging`，防止泄露或日志失控。
*   **证据**:
    *   `handlers\user_handler.py`: **大量调试 print 残留** ( line 128~150 )
    *   `print("DEBUG: Inside _fallback_process_forward_rule")`
    *   `print(f"DEBUG: calling _prepare_message_text with {message_text}")`
*   **整改建议**: 立即使用 `core.logging` 或直接清理这些 debug 语句。

---

### 🟡 3. God File (超长文件) - [P1]
*   **规则**: 单业务领域文件不应超过 1000 行。
*   **证据**:
    *   `handlers\commands\rule_commands.py` - **1297 行**
    *   `services\session_service.py` - **1184 行**
    *   `services\update_service.py` - **1051 行**
    *   `core\helpers\search_system.py` - **1003 行**
*   **整改建议**: 
    *   `rule_commands.py`：按命令组（查看、增删改）拆分。
    *   `session_service.py`：按业务（会话生命周期、激活状态、保活）解耦。

---

### 🔵 4. 模块实例化超前 (Ultra-Lazy Execution) - [P1]
*   **规则**: 严禁在模块顶层对重型对象（Service / DB）实例化。
*   **证据**:
    *   数十个 `services/` 在文件底部执行了 `audit_service = AuditService()` 顶层赋值。
*   **分析**: 这会导致启动时开销大及 Mock 困难。鉴于属于全局级架构债，建议有计划地重构成懒加载获取。

---

## ✅ 亮点统计
*   **os.getenv 查杀率**: **100%**。项目完全通过 `core.config.settings` 统一收拢。

---

## 🛠️ 后续执行计划 (Next Steps)
1. **P2 级纯打扫**：优先清理 `user_handler.py` 中的 `print` 残留。
2. **P1 级重构**：
   * 迁移 `rules_menu.py` 和 `forward_management.py` 中的 SQLAlchemy 依赖至 Service。
   * 拆分 `rule_commands.py` 压缩代码。
