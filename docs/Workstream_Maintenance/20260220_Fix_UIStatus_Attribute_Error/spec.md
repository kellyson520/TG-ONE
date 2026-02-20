# 技术方案: 修复 UIStatus 属性缺失

## 问题描述
`AttributeError: type object 'UIStatus' has no attribute 'DELETE'`
发生于 `ui/renderers/session_renderer.py` 第 15 行及后续多处。

## 修复方案
在 `ui/constants.py` 的 `UIStatus` 类中定义 `DELETE` 常量。

### 修改细节
文件: `ui/constants.py`

```python
class UIStatus:
    # ... 现有属性
    TRASH = "🗑️"
    DELETE = "🗑️"  # 新增，兼容 SessionRenderer
    # ...
```

## 风险评估
- **影响范围**: 极低。仅增加一个常量映射，不影响现有逻辑。
- **回滚方案**: 删除新增的 `DELETE` 属性。
