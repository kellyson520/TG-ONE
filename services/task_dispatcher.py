import asyncio
import json
import time
from datetime import datetime
from core.config import settings
from core.logging import get_logger

logger = get_logger(__name__)

class TaskDispatcher:
    """
    中央任务分发器 (Centralized Task Dispatcher)
    借鉴成熟消息队列 (Celery/SQS) 的 Prefetch 与 Backpressure 设计。
    负责从数据库批量拉取任务，通过 pre-parse 减轻 Worker 负载，并提供原子锁定。
    """
    def __init__(self, repo, queue: asyncio.Queue, client=None):
        self.repo = repo
        self.queue = queue
        self.client = client
        self.running = False
        self._task = None
        
        # [NEW] 实体预热缓存 (防止重复调用 API)
        self._entity_cache = set()
        self._last_cache_clear = time.time()
        
        # 自制休眠配置 (Inspired by Binary Exponential Backoff)
        self.min_sleep = getattr(settings, 'TASK_DISPATCHER_SLEEP_BASE', 1.0)
        self.max_sleep = getattr(settings, 'TASK_DISPATCHER_MAX_SLEEP', 30.0)
        self.current_sleep = self.min_sleep
        
        # 统计指标 (Observability)
        self.total_dispatched = 0
        self.last_fetch_count = 0
        self.start_time = None

    async def start(self):
        """启动分发循环"""
        if self.running:
            return
        self.running = True
        self.start_time = time.time()
        self._task = asyncio.create_task(self._dispatch_loop(), name="task_dispatcher")
        logger.info(f"🚀 TaskDispatcher 启动 (Batch: {settings.TASK_DISPATCHER_BATCH_SIZE}, QueueSize: {settings.WORKER_QUEUE_SIZE})")

    async def stop(self):
        """停止分发循环"""
        self.running = False
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except asyncio.CancelledError:
                pass
        logger.info("🛑 TaskDispatcher 已停止")

    async def _dispatch_loop(self):
        """主分发核心循环 (Central Fetch & Pre-Parse)"""
        while self.running:
            try:
                # 1. 背压控制 (Backpressure)
                if self.queue.full():
                    logger.debug("Dispatcher 触发背压停顿 (Queue Full)")
                    await asyncio.sleep(1.0)
                    continue

                # 2. 批量拉取与原子锁定
                batch_size = settings.TASK_DISPATCHER_BATCH_SIZE
                tasks = await self.repo.fetch_next(limit=batch_size)
                
                if not tasks:
                    self.last_fetch_count = 0
                    await self._adaptive_sleep()
                    continue

                # [NEW] 预热实体缓存 (Entity Prefetching)
                if self.client:
                    await self._prefetch_entities(tasks)

                # 3. 预处理与分发
                self._reset_sleep()
                
                # [Optimization] 媒体组聚合逻辑
                # 确保同一媒体组的任务作为一个批次分发给同一个 Worker
                # 从而减少 Worker 重复获取原始消息和下载媒体的开销
                task_groups = {}
                for task in tasks:
                    try:
                        if task.task_data:
                            task.payload = json.loads(task.task_data)
                        else:
                            task.payload = {}
                        
                        # 确定分组 ID (有 grouped_id 则使用，否则使用 ID 模拟)
                        gid = task.grouped_id or f"single-{task.id}"
                        if gid not in task_groups:
                            task_groups[gid] = []
                        task_groups[gid].append(task)
                        
                    except Exception as e:
                        logger.error(f"Task pre-parse failed for ID {task.id}: {e}")
                        task.payload = {}
                        task_groups[f"err-{task.id}"] = [task]

                for gid, group_list in task_groups.items():
                    # 入队 (作为 List[TaskQueue] 载荷)
                    await self.queue.put(group_list)
                    self.total_dispatched += len(group_list)
                    self.last_fetch_count = len(tasks)
                
                # [Anti-Starvation] 稍微出让事件循环时间
                await asyncio.sleep(0.05)

            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Dispatcher loop panic: {e}", exc_info=True)
                await asyncio.sleep(5) # 严重错误时进行冷静期休眠

    async def _adaptive_sleep(self):
        """自适应退避 (Exponential Backoff with Jitter)"""
        import random
        # 增加随机扰动因子，防止多个 Dispatcher 并发启动时的惊群效应
        jitter = random.uniform(0.8, 1.2)
        sleep_time = self.current_sleep * jitter
        
        logger.debug(f"Dispatcher 空载，进入休眠: {sleep_time:.2f}s (Current: {self.current_sleep:.2f}s)")
        await asyncio.sleep(sleep_time)
        
        # 指数增长 (1.5x)
        if self.current_sleep < self.max_sleep:
            self.current_sleep = min(self.current_sleep * 1.5, self.max_sleep)

    def throttle(self):
        """外部触发的降速背压，强制拉高休眠时间实现软熔断"""
        self.current_sleep = min(self.current_sleep * 2.0, self.max_sleep)

    def _reset_sleep(self):
        """重置休眠"""
        self.current_sleep = self.min_sleep

    async def _prefetch_entities(self, tasks):
        """预热 Telethon 实体缓存，防止 Worker 出现 Cache Miss 导致的 API 延迟"""
        current_chat_ids = set()
        for t in tasks:
            try:
                # 尝试从 task_data 提取 chat_id
                data = json.loads(t.task_data)
                cid = data.get('chat_id') or data.get('peer_id')
                if cid: 
                    try:
                        current_chat_ids.add(int(cid))
                    except: pass
            except: pass
            
        # 定期清理本地去重缓存 (每小时)，防止内存增长
        if time.time() - self._last_cache_clear > 3600:
            self._entity_cache.clear()
            self._last_cache_clear = time.time()

        # 过滤掉已经预热过的 (减少对 Telethon 内部 get_entity 的重复调用)
        to_fetch = current_chat_ids - self._entity_cache
        if not to_fetch:
            return
        
        logger.debug(f"Dispatcher 正在预热 {len(to_fetch)} 个实体缓存...")
        for cid in to_fetch:
            try:
                # get_entity 会自动更新 Telethon 内部缓存，它是线程/协程安全的
                await self.client.get_entity(cid)
                self._entity_cache.add(cid)
            except Exception as e:
                logger.warning(f"Entity prefetch failed for {cid}: {e}")
                # 失败了也记录，避免在同一小时内反复尝试
                self._entity_cache.add(cid)

    def get_stats(self):
        """获取分发器状态"""
        uptime = time.time() - self.start_time if self.start_time else 0
        return {
            "total_dispatched": self.total_dispatched,
            "last_fetch": self.last_fetch_count,
            "current_queue_size": self.queue.qsize(),
            "uptime_sec": int(uptime),
            "throughput_per_min": int(self.total_dispatched / (uptime / 60)) if uptime > 60 else 0
        }
