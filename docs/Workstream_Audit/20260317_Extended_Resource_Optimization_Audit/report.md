# 20260317_Extended_Resource_Optimization_Audit 交付报告

## 📌 审计概览 (Combined Summary)
在本轮全链路全栈状态审查中，精准查获了两处隐藏较深的 **常驻纯内存无界字典膨胀（Memory Leak Due to Unbounded Dicts）**，可能会在数十万条消息高频对刷的长跑周期下导致高耗能 OOM。目前在报告输出前已直接将其进行平滑修饰与上线拦截。

---

### 🚨 深度排查点与修复对齐 (Risk Fix Matrix)

#### 🔴 1. 去重 L1 文本指纹无界膨胀 [P0 级风险]
*   **受灾链路**: `services/dedup/engine.py` 内部 `self.text_fp_cache`
*   **问题所在**: 每当消息进行去重指纹录入，fp 就会源源不断写入字典中。系统对 sig、chash 设有 `max_signature_cache_size` 限额，但 **唯独漏掉了 text_fp_cache**。
*   **修补加固**: 已在底层指纹注入流中，加塞 `self.text_fp_cache[cid].popitem(last=False)`。保持 1000 限界滑窗，堵住此漏点。

#### 🟠 2. API 缓降缓存常驻堆积 [P1 级风险]
*   **受灾链路**: `services/network/telegram_api_optimizer.py` 
*   **问题所在**: 内部 `_search_cache` 和 `_media_info_cache` 只在每次 select 时比对 TTL 时间，但属于全局单例并且**没有主动清扫 routine**。在数天不重启的情况下字典项会一直占用内存储备。
*   **修补加固**: 已注入 **写入自稳 GC 算法 (GC on Write)**。在更新项时若 size 突破 500，会自动过滤 5 分钟前的过气要素重新洗牌，维持低峰能耗。

---

### ✅ 架构高光时刻 (Architectural Compliments)
1. **多层解耦流畅**: `filters/` 链路里的 Filter 接驳了 `MessageContext` 的统一字段缓存（如 `check_message_text`），避免了各自拼装 message 的**重复计算冗余**。
2. **LRU 缓存合规**: 全链路 `@lru_cache` 均有 size 限（或系统 fallback 128），规范性极高。

---

## 🛠️ 后续打理
风险点已随针织网封底。`docs/process.md` 任务状态已切换：**完成 100%**。
