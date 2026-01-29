# 修复 WebAdmin 文件夹乱码问题

## 背景 (Context)
`web_admin` 目录下部分文件出现了严重的乱码（Mojibake），表现为 UTF-8 编码的内容被错误地视为 GBK 编码后再次保存，导致内容变成了“娣诲姞”、“瀵煎叆”等无意义的字符。需要系统性修复这些文件并确保全量 UTF-8。

## 策略 (Strategy)
1. **识别**: 使用 Python 脚本扫描 `web_admin` 目录，通过常用乱码特征（如 `娣诲姞`）定位受损文件。
2. **修复**: 编写修复脚本，逻辑为：将当前 UTF-8 字符串编码为 GBK 字节流，再将该字节流按 UTF-8 解码。
3. **验证**: 人工抽检修复后的文件，并运行 `encoding-fixer` 扫描器确保无误。
4. **预防**: 检查所有相关文件的备份（`.bak`），确认无误后清理。

## 待办清单 (Checklist)

### Phase 1: 诊断与准备
- [x] 编写并运行扫描脚本定位所有受损文件 (`identify_mojibake.py`)
- [x] 记录受损文件清单

### Phase 2: 修复方案验证
- [x] 在 `web_admin/rss/core/config.py` 上验证修复逻辑
- [x] 扫描并确认所有乱码文件 (Done)
- [x] 执行系统性乱码修复 (Done)
- [x] 修复所有语法与缩进错误 (Done - Auth/Feed/Generator/Entry)
- [x] 自动格式化并校验语法 (Done - Black & HealthCheck)
- [x] 完成任务报告并归档 (Done)
- [x] 编写通用的修复工具类

### Phase 3: 全量修复
- [x] 执行全量修复脚本
- [x] 检查 `.bak` 文件的状态

### Phase 4: 扫尾与质量审计
- [x] 运行 `encoding-fixer/scripts/scan.py` 进行最终审计
- [x] 更新文档并汇报成果
