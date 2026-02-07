# 架构重构方案：智能去重引擎 (SmartDeduplicator) - 轻量化复用版

## 1. 原则与目标 (Principles & Objectives)
依据 `Standard_Whitepaper.md` (2026.1) 及用户"最大复用"的要求，本方案旨在通过**策略模式 (Strategy Pattern)** 解耦 `SmartDeduplicator`，同时最大化利用现有基础设施代码。

- **核心目标**: 将 2000 行的单体类拆解为可管理的策略类。
- **复用策略**: 
    - **完全复用** 现有的 `repositories/*` (Bloom, Archive, DuckDB)。
    - **保留** 现有的缓存机制 (Memory Cache, Local Persistence)，仅做逻辑封装。
    - **提取** 指纹计算逻辑为独立模块，但不改变算法实现。

## 2. 架构设计 (Architecture Design)

### 2.1 目录结构调整 (Refined Structure)
保持 `services/dedup/engine.py` 作为入口（Facade），将具体逻辑下沉。

```
services/dedup/
├── __init__.py           # 导出 SmartDeduplicator
├── engine.py             # [Facade] 负责编排，持有 Cache/Repo 引用，不含具体去重算法
├── types.py              # 定义 DedupResult, DedupConfig, DedupContext
├── tools.py              # [Refactor] 原 _generate_* 系列指纹计算函数 (纯逻辑复用)
└── strategies/           # [New] 具体去重逻辑
    ├── base.py           # 策略基类
    ├── signature.py      # 签名与时间窗口策略 (复用 time_window_cache)
    ├── video.py          # 视频去重策略 (包含 FileID, PartialHash)
    ├── content.py        # 内容哈希策略 (包含 TextHash, ImageHash)
    └── similarity.py     # 相似度策略 (包含 SimHash, GroupCheck)
```

### 2.2 组件交互 (Component Interaction)

#### 2.2.1 Facade (SmartDeduplicator)
- **职责**: 
  - 初始化并管理共享资源 (HLL, BloomFilter, PCache)。
  - 构建 `DedupContext` (包含消息、配置、共享资源的引用)。
  - 按顺序调用 `strategies`。
  - **复用点**: `__init__` 中对 Singleton/Global 资源的加载逻辑保持不变。

#### 2.2.2 Strategies (BaseStrategy)
每个策略类接受 `Context`，执行具体的检查逻辑。

```python
class BaseDedupStrategy(ABC):
    @abstractmethod
    async def process(self, ctx: DedupContext) -> DedupResult:
        """
        执行去重检查
        :return: DedupResult(is_duplicate=True/False, reason="...", payload=...)
        """
        pass
```

- **SignatureStrategy**: 迁移原 `_check_signature_duplicate` 逻辑。直接操作 `ctx.time_window_cache`。
- **VideoStrategy**: 迁移原 `_check_video_duplicate_by_file_id` 和 `_check_video_duplicate_by_hash`。
- **ContentStrategy**: 迁移原 `_check_content_hash_duplicate`。
- **SimilarityStrategy**: 迁移原 `_check_similarity_duplicate`。

#### 2.2.3 Tools (Fingerprint Logic)
将 `SmartDeduplicator` 中所有的 `_generate_signature`, `_calculate_simhash`, `_extract_media_features` 等**无状态**方法提取到 `tools.py`。
- **优势**: 纯函数易于测试；Facacde 和 Strategies 均可调用。

## 3. 迁移路线 (Migration Path)

1.  **Extract Tools**: 将指纹生成代码移动到 `tools.py`。`engine.py` 改为调用 `tools` 函数。
2.  **Define Types & Base**: 定义上下文和策略接口。
3.  **Refactor Strategies**: 逐步将 `check_duplicate` 中的逻辑块（签名、视频、哈希、相似度）移动到 `strategies/` 下的独立类中。
4.  **Simplify Facade**: `engine.py` 的 `check_duplicate` 简化为遍历策略链。

## 4. 风险控制 (Risk Control)
- **零逻辑变更**: 仅仅是代码位置的移动（Move Method），逻辑流保持不变。
- **状态维持**: 缓存（Cache）对象依然由 `engine.py` 实例持有，并通过 Context 传递给策略，确保内存状态的一致性（避免因拆分导致缓存失效）。
- **兼容性**: 对外接口签名完全一致。
