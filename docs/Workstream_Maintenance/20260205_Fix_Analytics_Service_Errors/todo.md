# 修复 Analytics Service 字段错误

## 任务概述
修复 `analytics_service.py` 中的 `AttributeError` 和 `IndexError`

## 错误信息
1. `AttributeError: type object 'RuleStatistics' has no attribute 'forwarded_count'`
2. `IndexError: list index out of range` (访问空的 daily_trends 列表)

## 根本原因

### 1. 字段名不匹配
`RuleStatistics` 模型的实际字段：
- `total_triggered` - 总触发次数
- `success_count` - 成功次数
- `filtered_count` - 过滤次数
- `error_count` - 错误次数

但代码中使用了不存在的 `forwarded_count`

### 2. 不安全的列表访问
```python
detailed.get('daily_trends', [{}])[0].get('yesterday_total', 0)
```
当 `daily_trends` 为空列表时，`[0]` 会抛出 `IndexError`

## 修复内容

### 文件: `services/analytics_service.py`

#### 1. 第 78 行 - 修复空列表访问
**修改前**:
```python
'yesterday_total': detailed.get('daily_trends', [{}])[0].get('yesterday_total', 0),
```

**修改后**:
```python
'yesterday_total': detailed.get('daily_trends', [{}])[0].get('yesterday_total', 0) if detailed.get('daily_trends') else 0,
```

#### 2. 第 294 行 - 修复字段名
**修改前**:
```python
.order_by(RuleStatistics.forwarded_count.desc())
```

**修改后**:
```python
.order_by(RuleStatistics.success_count.desc())
```

#### 3. 第 304 行 - 修复字段名
**修改前**:
```python
'count': stats_row.forwarded_count
```

**修改后**:
```python
'count': stats_row.success_count
```

#### 4. 第 447 行 - 修复字段名
**修改前**:
```python
stmt = select(RuleStatistics).order_by(RuleStatistics.forwarded_count.desc()).limit(10)
```

**修改后**:
```python
stmt = select(RuleStatistics).order_by(RuleStatistics.success_count.desc()).limit(10)
```

#### 5. 第 451-456 行 - 修复返回字段名
**修改前**:
```python
top_rules = [{
    'rule_id': rs.rule_id,
    'forwarded_count': rs.forwarded_count,
    'error_count': rs.error_count,
    'date': rs.date
} for rs in rule_stats]
```

**修改后**:
```python
top_rules = [{
    'rule_id': rs.rule_id,
    'success_count': rs.success_count,
    'error_count': rs.error_count,
    'date': rs.date
} for rs in rule_stats]
```

## 影响范围
- ✅ `get_analytics_overview()` - 主菜单统计概览
- ✅ `get_detailed_stats()` - 详细统计数据
- ✅ `get_detailed_analytics()` - 导出分析数据

## 验证方法
```bash
# 测试 analytics_service
python -c "import asyncio; from services.analytics_service import analytics_service; asyncio.run(analytics_service.get_analytics_overview())"
```

## 状态
- [x] 修复字段名错误
- [x] 修复列表访问错误
- [ ] 运行集成测试
- [ ] 部署验证
