# 环境变量单一来源 (SSOT) 验证测试报告

## 1. 任务概述 (Overview)
本次任务成功建立了对 TG ONE 全项目环境变量“单一来源” (Single Source of Truth) 原则的自动化验证体系。通过结合单元测试与静态代码扫描，确保所有配置项在工程层面强制通过 `core.config.settings` 获取，消除了散落在业务逻辑中的环境变量直接调用。

## 2. 核心产出 (Deliverables)

### 2.1 自动化测试套件
- **测试文件**：`tests/unit/core/test_config_ssot.py`
- **主要工作**：
    - **单例验证**：确认 `settings` 对象在全局通过 `lru_cache` 保持唯一性。
    - **校验逻辑验证**：验证了 `validate_required` 在不同环境（开发/生产）下的行为，确保生产环境下缺失核心配置能强制阻断。
    - **静态扫描**：实现了一个基于正则的静态审计工具，自动扫描项目目录（如 `core`, `handlers`, `services`, `web_admin` 等），查杀非授权的 `os.getenv` 或 `os.environ` 访问。
    - **模板对齐**：验证了 `.env.template` 与 `Settings` 类定义的一致性。

### 2.2 架构合规性修复
在测试驱动下，识别并修复了以下违反 SSOT 原则的代码：
- **`web_admin/routers/settings_router.py`**：将原本扫描 `os.environ.keys()` 的逻辑改为扫描 `settings.model_fields.keys()`，实现了 API 层面的配置源收拢。
- **`services/settings_applier.py`**：移除了热更新时同步写回 `os.environ` 的冗余逻辑，强制所有消费者依赖 `settings` 对象。
- **`core/config/__init__.py`**：补全了遗漏的 `os` 导入，并新增了 `DUP_SCAN_PAGE_SIZE` 配置项，解决了测试用例无法正常实例化的问题。

## 3. 验证结果 (Verification)
- **SSOT 专项测试**：`pytest tests/unit/core/test_config_ssot.py` -> **6 Passed**。
- **核心配置回归**：`pytest tests/unit/core/` -> **25 Passed**。
- **静态审计结果**：项目全库扫描完成，无未经授权的环境变量直连代码。

## 4. 结论与后续
TG ONE 的配置系统已达到“强一致性”状态。未来新增加的任何配置项，必须在 `core.config.Settings` 类中显式定义，否则将无法被系统感知，且 CI 静态审计将报错。
建议在每次合并代码前运行 `test_config_ssot.py` 以维持这一架构纯洁度。
