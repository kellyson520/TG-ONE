# Task Report: 修复转发统计与节省流量显示 (Fix Forward Stats & Saved Traffic Display)

## 1. 任务概述 (Task Overview)
- **任务目标**: 解决转发管理中心统计数据（尤其是“节省流量”）不更新的问题，并强化统计看板的展示内容。
- **核心变更**: 
    - 补齐了去重中间件拦截消息时的统计数据采集逻辑。
    - 修复了文件/消息大小计算的边缘情况（文本消息大小统计）。
    - 扩展了渲染器中的详细数据展现。

## 2. 变更详情 (Changes)

### 2.1 统计采集与业务逻辑 (Backend)
- **`services/dedup_service.py`**:
    - 新增 `_on_duplicate_found` 辅助方法，统一处理拦截后的流量记录、规则过滤统计和日志记录。
    - 更新 `check_and_lock` 接口，支持传入 `rule_id` 以关联特定转发规则。
- **`middlewares/dedup.py`**:
    - 在去重检查阶段传入当前的 `rule.id`，实现精确到规则的消息拦截统计。
- **`core/helpers/forward_recorder.py`**:
    - 修复了 `_extract_message_info` 中对文本消息 `size_bytes` 的计算逻辑（之前固定为 0），现在按 UTF-8 编码字节数计算，确保“已消耗流量”统计的准确性。

### 2.2 数据分析与服务层 (Service)
- **`services/analytics_service.py`**:
    - 在 `get_analytics_overview` 和 `get_detailed_analytics` 中补全了 `saved_traffic_bytes` 字段的聚合。
- **`services/forward_service.py`**:
    - (已在前期变更) 完善了 `get_forward_stats` 返回值。

### 2.3 UI 渲染增强 (Frontend)
- **`ui/renderers/main_menu_renderer.py`**:
    - **转发中心 (`render_forward_hub`)**: 增加“拦截流量”状态项，实时显示系统拦截重复消息节省的流量。
    - **分析中心 (`render_analytics_hub`)**: 重构状态网格，同时展示“数据总量”、“拦截节省”、“最热类型”和“活跃会话”，信息维度更丰富。

## 3. 验证结果 (Verification)
- [x] **数据采集验证**: 模拟重复消息发送，确认数据库 `chat_statistics` 表中的 `saved_traffic_bytes` 字段正常递增。
- [x] **规则过滤验证**: 确认 `rule_statistics` 中的 `filtered_count` 随拦截动作同步更新。
- [x] **UI 渲染验证**: 确认 Bot 菜单中的“转发管理中心”和“数据分析中心”能够显示新添加的统计指标。
- [x] **文本统计验证**: 确认纯文本转发时，“数据传输”流量不再始终显示为 0.0 MB。

## 4. 架构合规性 (Compliance)
- **符合 DDD 设计**: 统计逻辑封装在 Service 和 Repository 层，UI 仅负责渲染 aggregate 数据。
- **无破坏性修改**: 保持了旧版接口的兼容性，通过可选参数扩展功能。
- **高性能采集**: 利用 `StatsRepository` 的缓冲刷盘机制，避免单次拦截频繁操作数据库。

## 5. 结论 (Conclusion)
任务顺利完成。系统现在能够准确、多维度地展示转发效率，为运营提供了清晰的流量节省指标。

**Next Steps**: 建议后续可以根据“节省流量”为用户生成周报或月报图表。
