# 去重系统修复 - 部署清单

## ✅ 已完成的修复

### 1. 代码修复
- [x] 修复 `DedupRepository.batch_add()` 方法缺失
  - 文件: `repositories/dedup_repo.py`
  - 行数: 102-120
  - 功能: 批量插入媒体签名记录

- [x] 修复持久化缓存逻辑错误
  - 文件: `services/dedup/engine.py`
  - 修改点:
    - [x] 移除 `_record_message` 中的自动PCache写入 (行1341-1343)
    - [x] 在签名重复检测时添加PCache写入 (行354-359)
    - [x] 在内容哈希重复检测时添加PCache写入 (行597-602)
    - [x] 在相似度重复检测时添加PCache写入 (行634-641)

### 2. 验证脚本
- [x] 创建快速验证脚本: `verify_dedup_fix.py`
- [x] 创建集成测试: `tests/integration/test_dedup_fix.py`
- [x] 创建清理脚本: `cleanup_dedup_cache.py`

### 3. 文档
- [x] 详细修复报告: `docs/fixes/dedup_critical_fix_20260205.md`
- [x] 执行摘要: `docs/fixes/SUMMARY_dedup_fix.md`
- [x] 部署清单: `docs/fixes/DEPLOYMENT_CHECKLIST.md` (本文件)

---

## 📋 部署步骤

### 步骤1: 验证修复 ✅
```bash
cd "c:/Users/lihuo/Desktop/重构/TG ONE"
python verify_dedup_fix.py
```

**预期输出**:
```
✅ batch_add 方法存在
✅ batch_add 方法签名正确
✅ 已移除 _record_message 中的自动PCache写入
✅ 签名重复检测: 已添加PCache写入逻辑
✅ 内容哈希重复检测: 已添加PCache写入逻辑
✅ 相似度重复检测: 已添加PCache写入逻辑
```

### 步骤2: 清理旧缓存 (可选但推荐)
```bash
python cleanup_dedup_cache.py
```

**注意**: 
- 这将删除所有旧的去重缓存数据
- 删除后系统将重新学习去重规则
- 如果不确定,可以跳过此步骤,让缓存自然过期

### 步骤3: 重启应用程序
```bash
# 停止当前运行的应用
# 方法1: 如果使用systemd
sudo systemctl restart tg-one

# 方法2: 如果使用Docker
docker-compose restart

# 方法3: 如果直接运行
# Ctrl+C 停止,然后重新运行
python main.py
```

### 步骤4: 监控日志
启动后观察日志,确认:
- [ ] 应用正常启动
- [ ] 去重引擎初始化成功
- [ ] 不再出现 `'DedupRepository' object has no attribute 'batch_add'` 错误
- [ ] 不再出现所有消息都被误判为重复的情况

**关键日志**:
```
✅ 正常: "去重检查完成，耗时: 0.XXXs，结果: 不重复"
✅ 正常: "签名重复命中: 时间窗口内重复"
❌ 异常: "签名重复: persistent cache 命中" (所有消息都显示这个)
```

### 步骤5: 功能测试
- [ ] 发送一条新消息 → 应该正常转发
- [ ] 发送相同的消息 → 应该被拦截(检测到重复)
- [ ] 发送不同的消息 → 应该正常转发
- [ ] 检查批量写入日志 → 应该正常工作,无错误

---

## 🔍 问题排查

### 问题1: 仍然出现 batch_add 错误
**可能原因**: 代码未生效
**解决方案**:
1. 确认 `repositories/dedup_repo.py` 已保存
2. 重启应用程序
3. 检查是否有多个Python进程在运行

### 问题2: 仍然所有消息都被判为重复
**可能原因**: 旧的PCache数据污染
**解决方案**:
1. 运行 `python cleanup_dedup_cache.py` 清理缓存
2. 重启应用程序
3. 如果使用Redis,可以直接清空: `redis-cli FLUSHDB`

### 问题3: 去重功能完全失效
**可能原因**: 配置问题
**解决方案**:
1. 检查去重配置是否启用
2. 查看日志中的错误信息
3. 确认数据库连接正常

---

## 📊 监控指标

建议监控以下指标:

### 去重性能
- `dedup_check_seconds`: 去重检查耗时
- `dedup_decisions_total`: 去重决策总数
- `dedup_hits_total`: 去重命中总数

### 缓存性能
- `dedup_pcache_hit_rate`: PCache命中率
- `dedup_pcache_write_total`: PCache写入次数
- `video_hash_pcache_hits_total`: 视频哈希缓存命中数

### 系统健康
- 批量写入成功率
- 去重误判率
- 转发成功率

---

## 🎯 成功标准

部署成功的标志:
- ✅ 应用正常启动,无错误日志
- ✅ 新消息可以正常转发
- ✅ 重复消息被正确拦截
- ✅ 不同消息不会互相干扰
- ✅ 批量写入正常工作
- ✅ 持久化缓存命中率合理 (建议 < 10%)

---

## 📝 回滚方案

如果修复后出现问题,可以回滚:

### 回滚步骤
1. 恢复旧版本代码
   ```bash
   git checkout HEAD~1 -- repositories/dedup_repo.py
   git checkout HEAD~1 -- services/dedup/engine.py
   ```

2. 重启应用程序

3. 报告问题,等待进一步修复

### 临时解决方案
如果无法立即修复,可以临时禁用去重功能:
```python
# 在配置中设置
DEDUP_ENABLED = False
```

---

## 📞 联系支持

如有问题,请提供:
1. 错误日志 (最近100行)
2. 系统配置 (去重相关)
3. 复现步骤
4. 关联ID: 1303046d

---

**修复版本**: v1.0.0-dedup-fix  
**修复日期**: 2026-02-05  
**修复人员**: Antigravity AI  
**审核状态**: 待人工验证
