# 修复启动阶段的循环导入错误 (Fix Circular Import Startup Error)

## 背景 (Context)
系统启动时报 `ImportError: cannot import name 'container' from partially initialized module 'core.container'`。
错误链条：`main.py` -> `lifecycle` -> `bootstrap` -> `container` -> `middlewares.dedup` -> `dedup_service` -> `dedup_engine` -> `container` (Cycle)。

## 策略 (Strategy)
1. **解构顶层导入**: 移除 `services/dedup/engine.py` 中的顶层 `container` 导入，改为在方法内或通过属性懒加载。
2. **中间件延迟加载**: 调整 `core/container.py`，将 `middlewares` 的导入下沉到 `init_with_client` 方法中，防止在 `container` 模块初始化时尚未完成定义的类被引用。
3. **验证脚本**: 编写独立脚本验证导入链条的完整性。

## 待办清单 (Checklist)

### Phase 1: 核心修复
- [x] 移除 `services/dedup/engine.py` 的顶层 `container` 导入
- [x] 重构 `core/container.py` 的中间件加载机制（懒加载）
- [x] 修复 `admin_callback.py` 中的潜在 lint 错误（已在上一轮完成）

### Phase 2: 验证与发布
- [x] 编写并运行 `scripts/verify_import.py` 验证导入链
- [x] 运行 Local CI 确保无回归
- [x] 更新版本号至 v1.2.3.5
- [ ] 推送修复代码
