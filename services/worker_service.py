import asyncio
import json
import random
import time
import psutil
import gc
from datetime import datetime, timedelta
from core.pipeline import MessageContext
from services.queue_service import FloodWaitException
from core.exceptions import TransientError, PermanentError
from core.config import settings

from core.logging import get_logger, short_id
from services.queue_service import get_messages_queued, send_file_queued
from filters.delay_filter import RescheduleTaskException

logger = get_logger(__name__)

class WorkerService:
    def __init__(self, client, task_repo, pipeline, downloader=None):
        self.client = client
        self.repo = task_repo
        self.pipeline = pipeline
        self.downloader = downloader
        self.running = False
        # 动态休眠策略配置
        self.min_sleep = 0.5  # 最小休眠时间 (秒)
        self.max_sleep = 30.0  # 最大休眠时间 (秒)
        self.current_sleep = self.min_sleep
        self.sleep_increment = 1.0  
        
        # [NEW] 中央分发资源
        self.task_queue = asyncio.Queue(maxsize=settings.WORKER_QUEUE_SIZE)
        self.dispatcher = None # 在 start() 中初始化
        
        # [NEW] 资源阈值
        self.mem_warning = settings.MEMORY_WARNING_THRESHOLD_MB
        self.mem_critical = settings.MEMORY_CRITICAL_THRESHOLD_MB
        self.last_gc_time = 0
        self.last_critical_alert = 0 # 上次发送内存紧急告警的时间
        self.critical_mode = False   # 是否处于熔断模式

    async def start(self):
        """启动 Worker 服务 (动态并发池)"""
        self.running = True
        logger.info(f"WorkerService 启动 (Min: {settings.WORKER_MIN_CONCURRENCY}, Max: {settings.WORKER_MAX_CONCURRENCY})")
        
        self.workers = {} # task -> worker_id
        
        # [Fix] 启动前清理僵尸任务，防止历史遗留的 running 任务占用状态
        try:
            count = await self.repo.rescue_stuck_tasks(timeout_minutes=15)
            if count > 0:
                logger.info(f"♻️ 系统启动救援: 已重置 {count} 个僵尸任务为 PENDING 状态")
        except Exception as e:
            logger.error(f"Failed to rescue tasks during startup: {e}")

        # [Phase 14] 启动中央分发器 (Dispatcher)
        from services.task_dispatcher import TaskDispatcher
        self.dispatcher = TaskDispatcher(self.repo, self.task_queue)
        await self.dispatcher.start()

        # 启动初始 Workers
        for i in range(settings.WORKER_MIN_CONCURRENCY):
            self._spawn_worker()

        # 启动弹性伸缩监控
        self._monitor_task = asyncio.create_task(self._monitor_scaling(), name="worker_scaling_monitor")
        
        # [NEW] 启动 Loop Lag 监控
        self._lag_monitor_task = asyncio.create_task(self._monitor_loop_lag(), name="loop_lag_monitor")
        
        # 保持主任务运行（用于接收停止信号）
        while self.running:
            await asyncio.sleep(1)

    def _spawn_worker(self):
        """Spawn a new worker"""
        if len(self.workers) >= settings.WORKER_MAX_CONCURRENCY:
            return

        worker_id = f"worker-{short_id(None, 4)}"
        task = asyncio.create_task(self._worker_loop(worker_id), name=worker_id)
        self.workers[task] = worker_id
        logger.debug(f"Spawned worker {worker_id} (Total: {len(self.workers)})")
        task.add_done_callback(lambda t: self.workers.pop(t, None))

    async def _kill_worker(self):
        """Kill an idle worker (approximate)"""
        if len(self.workers) <= settings.WORKER_MIN_CONCURRENCY:
            return

        # Simple kill: Cancel the last added task
        # Improvement: Cancel idle workers?
        # For now, just pop one randomly or last
        task = list(self.workers.keys())[-1]
        worker_id = self.workers[task]
        task.cancel()
        logger.debug(f"Scaling down: Cancelled worker {worker_id}")

    async def _monitor_scaling(self):
        """
        智能化动态伸缩监控 (Resource-Aware & Load-Adaptive)
        策略：
        1. [分级扩容] 根据积压量级决定扩容速度
        2. [系统负载保护] 监控 CPU/内存，高负载时抑制扩容
        3. [平滑缩容] 采用延迟缩容，防止震荡
        """
        logger.info(f"🚀 [WorkerService] 智能化动态伸缩监控已启动 (Max: {settings.WORKER_MAX_CONCURRENCY})")
        
        idle_cycles = 0 # 连续空闲周期计数
        
        while self.running:
            try:
                await asyncio.sleep(10) # 每10秒检查一次
                
                # 获取队列状态
                queue_status = await self.repo.get_queue_status()
                logger.info(f"🔍 [WorkerService] Managed Queue status: {queue_status}")
                # 修复 P0: 使用正确键名 active_queues
                pending_count = queue_status.get('active_queues', 0)
                current_workers = len(self.workers)
                
                # --- 第一步：资源守卫 (Resource Guard) ---
                try:
                    # 使用 psutil 获取更准确的 CPU 使用率 (指定 interval)
                    # 但是在 async 循环中不能长时间阻塞，改用非阻塞获取
                    # interval=None 会返回上一秒到现在的时间差
                    cpu_usage = psutil.cpu_percent(interval=None)
                    process = psutil.Process()
                    memory_info = process.memory_info()
                    memory_mb = memory_info.rss / 1024 / 1024
                    
                    # 获取系统总体负载 (Load Average)
                    try:
                        load_1, load_5, load_15 = psutil.getloadavg()
                        cpu_count = psutil.cpu_count()
                        load_ratio = load_1 / cpu_count if cpu_count else 0
                    except (AttributeError, Exception):
                        load_ratio = 0
                except Exception:
                    cpu_usage = 0
                    memory_mb = 0
                    load_ratio = 0
                    
                # 计算内存增速 (用于 Adaptive GC)
                mem_growth = memory_mb - getattr(self, 'last_memory_mb', 0)
                self.last_memory_mb = memory_mb

                # --- 第二步：计算目标 Worker 数 (Target Logic) ---
                # 策略：只要有积压就积极扩容，充分利用空闲资源
                if pending_count == 0:
                    target_count = settings.WORKER_MIN_CONCURRENCY
                else:
                    # 按照积压量级分档
                    if pending_count > 10000:
                        # 极端积压：允许达到最大值
                        target_count = settings.WORKER_MAX_CONCURRENCY
                    elif pending_count > 1000:
                        # 大量积压：每 100 个任务加 1 个 worker
                        target_count = settings.WORKER_MIN_CONCURRENCY + (pending_count // 100)
                    elif pending_count > 100:
                        # 中等积压：每 20 个任务加 1 个 worker
                        target_count = settings.WORKER_MIN_CONCURRENCY + (pending_count // 20)
                    else:
                        # 轻微积压 (1~100)：每 3 个任务加 1 个 worker，至少 +1
                        target_count = settings.WORKER_MIN_CONCURRENCY + max(1, pending_count // 3)

                # 约束目标值
                target_count = max(settings.WORKER_MIN_CONCURRENCY, min(settings.WORKER_MAX_CONCURRENCY, target_count))

                # --- 第三步：执行调整 (Execution & Guard) ---
                log_diagnostic = False
                if idle_cycles % 6 == 0: # 每分钟记录一次诊断
                     log_diagnostic = True
                     # [Fix] 每分钟尝试救援一次超时严重的任务
                     await self.repo.rescue_stuck_tasks(timeout_minutes=20)
                
                if log_diagnostic:
                    logger.info(f"📊 [WorkerService] 系统负载: CPU={cpu_usage}%, Load={load_ratio:.2f}, RAM={memory_mb:.1f}MB | 积压={pending_count}, Workers={current_workers}/{target_count}")

                if current_workers < target_count:
                    # 扩容守卫：资源检查按优先级排列，任何一个触发都阻止扩容
                    scale_blocked = False
                    
                    if cpu_usage > 80 or load_ratio > 1.2:
                        if log_diagnostic:
                            logger.warning(f"⚠️ [WorkerService] 系统高负载，已暂停扩容计划 (CPU={cpu_usage}%, Load={load_ratio:.2f})")
                        scale_blocked = True
                    
                    if memory_mb > self.mem_critical:
                        # 内存危急：触发动态水位线软熔断 (Soft-Start Throttling)
                        current_time = time.time()
                        if current_time - self.last_critical_alert > 300:
                            logger.warning(f"🚨 [ResourceGuard] 内存触及 Fatal 水位 (RSS={memory_mb:.1f}MB > {self.mem_critical}MB)，触发自适应背压降速。")
                            self.last_critical_alert = current_time

                        # 动态调大 Dispatcher 休眠时间，复用 _adaptive_sleep 退避机制
                        if self.dispatcher:
                            self.dispatcher.throttle()
                        
                        # 自适应分代回收 (Adaptive GC)
                        if mem_growth > 50:
                            gc.collect() # 增速过快时深度回收
                        else:
                            gc.collect(1) # 平缓时仅回收年轻代，避免 CPU 毛刺
                        
                        scale_blocked = True
                    elif memory_mb > self.mem_warning: 
                        if log_diagnostic:
                            logger.warning(f"⚠️ [ResourceGuard] 内存触及 Warning 水位 ({memory_mb:.1f}MB > {self.mem_warning}MB)，触发降速与轻量 GC")
                        
                        if self.dispatcher:
                            # 轻度降速
                            self.dispatcher.current_sleep = min(self.dispatcher.current_sleep * 1.5, self.dispatcher.max_sleep)
                            
                        # 轻量级 GC
                        if mem_growth > 20:
                            gc.collect(1)
                            
                        scale_blocked = True
                    else:
                        # 内存回落：不再瞬间拉满，而是随 Dispatcher self.current_sleep 的自然回落进行平滑重置
                        pass
                    
                    if not scale_blocked:
                        diff = target_count - current_workers
                        # 扩容步长更保守：一次最多增加 3 个
                        step = min(diff, 3) 
                        logger.info(f"📈 [WorkerService] 扩容中: +{step} workers (负载正常)")
                        for _ in range(step):
                            self._spawn_worker()

                    idle_cycles = 0 
                
                elif current_workers > target_count:
                    # 缩容策略：更激进地释放资源
                    idle_cycles += 1
                    # 如果 CPU 非常高，立即缩容，不需要等待 3 个周期
                    if cpu_usage > 95 or load_ratio > 2.0:
                         logger.warning(f"🚨 [WorkerService] 极端高负载，紧急释放资源: -2 workers")
                         for _ in range(min(current_workers - settings.WORKER_MIN_CONCURRENCY, 2)):
                             await self._kill_worker()
                         idle_cycles = 0
                    elif idle_cycles >= 3:
                        diff = max(1, (current_workers - target_count) // 2) # 分批次缩容
                        logger.info(f"📉 [WorkerService] 缩容中: -{diff} workers")
                        for _ in range(diff):
                            await self._kill_worker()
                        idle_cycles = 0
                else:
                    idle_cycles = 0

            except Exception as e:
                logger.error(f"Scaling monitor error: {e}", exc_info=True)
                await asyncio.sleep(5)

    async def _monitor_loop_lag(self):
        """[Resource Guard] 监控事件循环延迟 (Loop Lag)"""
        threshold = settings.LOOP_LAG_THRESHOLD_MS / 1000.0
        while self.running:
            try:
                start = asyncio.get_event_loop().time()
                await asyncio.sleep(1.0)
                lag = asyncio.get_event_loop().time() - start - 1.0
                
                if lag > threshold:
                    logger.warning(f"⚠️ [LoopLag] 检测到异步延迟: {lag:.3f}s (阈值: {threshold}s)，系统负载处于高位")
                    # 如果延迟过高，由调度器决定是否降速 (未来可增加联动)
                
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Loop lag monitor error: {e}")
                await asyncio.sleep(10)

    async def _worker_loop(self, worker_id: str):
        """单个 Worker 的工作循环 (支持批量任务处理)"""
        logger.debug(f"[{worker_id}] Loop Started")
        
        while self.running:
            try:
                try:
                      # [Optimization] 改为从中央队列获取任务批次，彻底消除 DB 锁竞争
                      tasks = await self.task_queue.get()
                      # 如果 Dispatcher 放入的是单个任务，包装为列表；如果是列表（媒体组），直接使用
                      if not isinstance(tasks, list):
                          tasks = [tasks]
                except asyncio.CancelledError:
                     logger.debug(f"[{worker_id}] Cancelled during queue.get")
                     raise

                # [Fix] 这里的 tasks 永远不为空，因为 Dispatcher 只会在有任务时才放入队列
                # queue.get() 在没有任务时会处于阻塞状态，不消耗 CPU
                
                # 按照 grouped_id 对拉取到的任务进行分组 (媒体组聚合)
                # 如果没有 grouped_id，则视为独立任务
                task_groups = {}
                for t in tasks:
                    gid = t.grouped_id or f"single-{t.id}"
                    if gid not in task_groups:
                        task_groups[gid] = []
                    task_groups[gid].append(t)

                # 依次处理每个任务组
                for gid, group in task_groups.items():
                    # 确保连接正常
                    await self._ensure_connected()
                    
                    main_task = group[0]
                    sub_tasks = group[1:] if len(group) > 1 else []
                    
                    # [关键] 绑定上下文
                    log = logger.bind(worker_id=worker_id, task_id=main_task.id, task_type=main_task.task_type)
                    
                    try:
                        await self._process_task_safely(main_task, log, group_tasks=sub_tasks)
                    except Exception as e:
                        log.error(f"group_processing_failed", error=str(e), gid=gid)

            except asyncio.CancelledError:
                logger.debug(f"[{worker_id}] Cancelled")
                break
            except Exception as e:
                logger.error(f"[{worker_id}] Loop Error: {e}")
                await asyncio.sleep(1)

    async def _process_task_safely(self, task, log, group_tasks: list = None):
        """处理基础任务的安全封装，支持传入预先锁定的媒体组任务"""
        try:
            payload = json.loads(task.task_data)
            
            # [Optimization] 处理不需要预取消息的任务类型
            if task.task_type == "message_delete":
                chat_id = payload.get('chat_id')
                message_ids = payload.get('message_ids', [])
                if not chat_id or not message_ids:
                    log.error("delete_task_invalid_payload", payload=payload)
                    await self.repo.fail(task.id, "Invalid Delete Payload")
                    return
                
                try:
                    log.info(f"🗑️ [Worker] 执行删除消息任务: Chat={chat_id}, IDs={message_ids}")
                    await self.client.delete_messages(chat_id, message_ids)
                    await self.repo.complete(task.id)
                    return
                except Exception as e:
                    log.error(f"delete_messages_failed", error=str(e))
                    await self._retry_task(task, e, log)
                    return

            if task.task_type == "custom_task":
                log.info(f"⚙️ [Worker] 处理自定义任务: {payload.get('action')}")
                # TODO: 以后可扩展基于 action 的路由
                await self.repo.complete(task.id)
                return

            # --- 以下是需要获取原始消息的任务类型 (process_message, download_file, manual_download) ---
            chat_id = payload.get('chat_id')
            msg_id = payload.get('message_id')
            
            # [优化] 获取聊天显示名称
            from core.helpers.id_utils import get_display_name_async
            chat_display = await get_display_name_async(chat_id)
            
            log.info(f"🔄 [Worker] 开始处理任务 {short_id(task.id)}: 来源={chat_display}({chat_id}), 消息ID={msg_id}")
            grouped_id = payload.get('grouped_id') # 获取 grouped_id
            
            if not chat_id or not msg_id:
                log.error("task_invalid_payload", task_data=task.task_data)
                await self.repo.fail(task.id, "Invalid Payload")
                return

            if group_tasks:
                log.info(f"aggregated_group_tasks", count=len(group_tasks), grouped_id=grouped_id)
            else:
                group_tasks = []
            
            # 收集所有相关任务（当前任务 + 同组任务）
            all_related_tasks = [task] + group_tasks
            all_message_ids = [msg_id]
            
            # 解析同组任务的 message_id
            if group_tasks:
                for t in group_tasks:
                    try:
                        p = json.loads(t.task_data)
                        if p.get('message_id'):
                            all_message_ids.append(p.get('message_id'))
                    except Exception as ex:
                        logger.warning(f"Failed to parse group task data: {ex}")
            
            # 关键点：从 Telethon 获取真实消息对象 (批量获取)
            # 如果消息已过期或被删，这里会返回 None
            messages = await get_messages_queued(self.client, chat_id, ids=all_message_ids)
            
            # 过滤掉 None (有些消息可能已被删)
            valid_messages = []
            if isinstance(messages, list):
                valid_messages = [m for m in messages if m]
            elif messages:
                    valid_messages = [messages]

            if not valid_messages:
                log.debug("task_source_message_not_found", chat_id=chat_id, message_ids=all_message_ids)
                # 消息不存在，标记为失败
                await self.repo.fail(task.id, "Source message not found")
                for t in group_tasks:
                    await self.repo.fail(t.id, "Source message not found (Group)")
                return
            
            primary_message = valid_messages[0]
            logger.debug(f"📥 [Worker] 成功获取消息对象: ID={primary_message.id}, 内容预览={primary_message.text[:20] if primary_message.text else 'No Text'}")
            
            # === 进入处理管道 ===
            if task.task_type == "process_message":
                # 走完整管道
                ctx = MessageContext(
                    client=self.client,
                    task_id=task.id,
                    chat_id=chat_id,
                    message_id=msg_id,
                    message_obj=primary_message,
                    # 注入媒体组信息
                    is_group=bool(grouped_id),
                    group_messages=valid_messages if grouped_id else [],
                    related_tasks=group_tasks
                )
                # [关键] 注入目标规则 ID (用于历史任务或转发历史)
                if payload.get('rule_id'):
                    ctx.metadata['target_rule_id'] = int(payload['rule_id'])
                
                # 注入历史任务标记
                if payload.get('is_history'):
                    ctx.metadata['is_history'] = True
                # 执行管道 (Middleware Chain)
                try:
                    await self.pipeline.execute(ctx)
                except FloodWaitException as e:
                    # 捕获FloodWaitException，将其转化为我们定义的 TransientError
                    await self._retry_group(all_related_tasks, e, log)
                    return
                except TransientError as e:
                    # 处理自定义瞬态错误
                    await self._retry_group(all_related_tasks, e, log)
                    return
                except PermanentError as e:
                    # 处理自定义永久错误
                    log.error("task_permanent_error", error=str(e), error_type="Permanent")
                    await self.repo.fail(task.id, str(e))
                    for t in group_tasks:
                        await self.repo.fail(t.id, str(e))
                    return
            
            elif task.task_type == "download_file":
                # 直接调用下载服务，绕过 RuleLoader 和 Filter
                # 这是一个"特权"任务
                if not self.downloader:
                    log.error("downloader_not_initialized")
                    await self.repo.fail(task.id, "Downloader not initialized")
                    return
                
                sub_folder = str(chat_id)
                try:
                    await self.downloader.push_to_queue(primary_message, sub_folder)
                except FloodWaitException as e:
                    # 捕获FloodWaitException，将其转化为我们定义的 TransientError
                    await self._retry_task(task, e, log)
                    return
                except TransientError as e:
                    # 处理自定义瞬态错误
                    await self._retry_task(task, e, log)
                    return
                except PermanentError as e:
                    # 处理自定义永久错误
                    log.error("task_permanent_error", error=str(e), error_type="Permanent")
                    await self.repo.fail(task.id, str(e))
                    return
            
            elif task.task_type == "manual_download":
                # 处理手动下载任务，直接调用DownloadService
                # 可以指定一个特殊的下载目录，如 "./downloads/manual"
                if not self.downloader:
                    log.error("downloader_not_initialized")
                    await self.repo.fail(task.id, "Downloader not initialized")
                    return
                
                # 使用"manual"作为子文件夹，区分手动下载和自动下载
                try:
                    path = await self.downloader.push_to_queue(
                        primary_message, 
                        sub_folder="manual"
                    )
                    log.info("manual_download_completed", path=path)
                    
                    # [Scheme 7 Feature] 如果有目标ID，则执行转发
                    target_id = payload.get('target_chat_id')
                    if target_id:
                        try:
                            await send_file_queued(
                                self.client,
                                target_id,
                                path,
                                caption=primary_message.text or ""
                            )
                            log.info(f"manual_forward_completed", target_id=target_id)
                        except Exception as e:
                            log.error(f"manual_forward_failed", target_id=target_id, error=str(e))
                            # 注意：这里我们只记录错误，不抛出异常，因为下载已经成功了
                except FloodWaitException as e:
                    # 捕获FloodWaitException，使用统一的重试逻辑
                    await self._retry_task(task, e, log)
                    return
                except TransientError as e:
                    # 处理自定义瞬态错误
                    await self._retry_task(task, e, log)
                    return
                except PermanentError as e:
                    # 处理自定义永久错误
                    log.error("task_permanent_error", error=str(e), error_type="Permanent")
                    await self.repo.fail(task.id, str(e))
                    return
            
            # === 任务成功 ===
            # [Fix] 必须完成所有相关的媒体组任务，否则它们会被其他 Worker 重复获取
            await self.repo.complete(task.id)
            if group_tasks:
                for t in group_tasks:
                    await self.repo.complete(t.id)
                logger.debug(f"task_completed_with_group: count={len(group_tasks)}")
            else:
                logger.debug("task_completed")

        except Exception as e:
            if isinstance(e, RescheduleTaskException):
                    # [非阻塞延迟处理]
                    # 捕获 RescheduleTaskException，将任务以指定延迟重新放入队列
                    log.info("task_delay_requested", delay_seconds=e.delay_seconds)
                    
                    next_run = datetime.utcnow() + timedelta(seconds=e.delay_seconds)
                    await self.repo.reschedule(task.id, next_run)
                    
                    # 如果有同组任务，也一起延迟
                    if group_tasks and 'group_tasks' in locals():
                        for t in group_tasks:
                            await self.repo.reschedule(t.id, next_run)
                    return
                    
            if isinstance(e, (FloodWaitException, TransientError)):
                # 捕获FloodWaitException或TransientError，使用统一的重试逻辑
                log.warning(f"任务遇到瞬态错误，将重试: 类型={type(e).__name__}, 错误={str(e)}")
                await self._retry_task(task, e, log)
            elif isinstance(e, PermanentError):
                # 处理自定义永久错误
                log.error(f"任务永久失败: 错误={str(e)}, 类型=Permanent, 规则ID={task.rule_id if hasattr(task, 'rule_id') else 'N/A'}", exc_info=True)
                await self.repo.fail(task.id, str(e))
            else:
                from core.helpers.id_utils import get_display_name_async
                chat_display = await get_display_name_async(chat_id)
                log.exception(f"任务未处理错误: 错误={str(e)}, 任务ID={short_id(task.id)}, 任务类型={task.task_type}, 来源={chat_display}({chat_id}), 消息ID={msg_id}")
                # 记录具体的错误信息到数据库
                await self.repo.fail(task.id, f"Unhandled: {str(e)}")

    # ... Helper methods stay same ...

    def get_performance_stats(self):
        """[Observability] 获取 Worker 性能与调度统计"""
        # [NEW] 统计信息汇总
        stats = {
            "current_workers": len(self.workers),
            "queue_depth": self.task_queue.qsize() if self.task_queue else 0,
            "max_concurrency": settings.WORKER_MAX_CONCURRENCY,
        }
        
        # 调度器统计
        if getattr(self, 'dispatcher', None):
            stats["dispatcher"] = self.dispatcher.get_stats()
        
        # 精确内存统计 (psutil)
        try:
            import psutil
            process = psutil.Process()
            mem = psutil.virtual_memory()
            stats["memory"] = {
                "process_rss_mb": round(process.memory_info().rss / (1024*1024), 1),
                "sys_available_mb": round(mem.available / (1024*1024), 1),
                "sys_usage_percent": mem.percent
            }
            if hasattr(mem, 'swap_used'):
                stats["memory"]["swap_used_mb"] = round(mem.swap_used / (1024*1024), 1)
        except Exception:
            pass
            
        return stats

    async def stop(self):
        """优雅停止 Worker"""
        logger.info("worker_stopping")
        self.running = False
        if getattr(self, '_monitor_task', None):
            self._monitor_task.cancel()
        if getattr(self, '_lag_monitor_task', None):
            self._lag_monitor_task.cancel()
        
        # Stop dispatcher
        if self.dispatcher:
            await self.dispatcher.stop()
        
        # Cancel all workers
        for task in list(self.workers.keys()):
            task.cancel()
        
        if self.workers:
            await asyncio.gather(*self.workers.keys(), return_exceptions=True)
            
        logger.info("worker_stopped_completely")


    async def _adaptive_sleep(self):
        """自适应休眠：如果没有任务，逐步增加休眠时间，减少资源消耗"""
        # [Phase 13 Optimization] 如果进入深度休眠 (current_sleep 已经达到较大值)，触发 GC
        if self.current_sleep >= self.max_sleep:
             collected = gc.collect()
             if collected > 0:
                 logger.debug(f"[GC] Idle cleanup collected {collected} objects")
                 
        await asyncio.sleep(self.current_sleep)
        if self.current_sleep < self.max_sleep:
            self.current_sleep = min(self.current_sleep + self.sleep_increment, self.max_sleep)

    def _reset_sleep(self):
        """重置休眠时间"""
        self.current_sleep = self.min_sleep

    async def _ensure_connected(self):
        """确保 Telethon 客户端已连接"""
        if not self.client.is_connected():
            logger.warning("Client disconnected. Attempting to reconnect...")
            try:
                await self.client.connect()
            except Exception as e:
                logger.error(f"Reconnection failed: {e}")
                # 等待一会儿再重试，避免死循环冲击
                await asyncio.sleep(5)
    
    def _calculate_backoff(self, retry_count: int) -> float:
        """
        计算指数退避时间
        公式: min(base * (factor ^ retries), max) + jitter
        """
        # 防止指数爆炸
        safe_retries = min(retry_count, 10)
        
        delay = settings.RETRY_BASE_DELAY * (settings.RETRY_BACKOFF_FACTOR ** safe_retries)
        
        # 截断到最大延迟
        delay = min(delay, settings.RETRY_MAX_DELAY)
        
        # 添加 0-10% 的随机抖动，防止惊群效应 (Thundering Herd)
        jitter = delay * random.uniform(0, 0.1)
        
        return delay + jitter
    
    async def _retry_task(self, task, error, log):
        """
        处理任务重试，根据错误类型和重试次数决定后续操作
        """
        current_retries = task.attempts + 1
        
        # 如果超过最大重试次数，升级为永久失败
        if current_retries > settings.MAX_RETRIES:
            log.error("task_max_retries_exceeded", retry_count=current_retries, max_retries=settings.MAX_RETRIES, error=str(error))
            await self.repo.fail(task.id, f"Max retries exceeded: {str(error)}")
            return

        # 计算等待时间
        if isinstance(error, FloodWaitException):
            wait_seconds = error.seconds + 1 # 额外多等1秒保险
        else:
            wait_seconds = self._calculate_backoff(current_retries)
            
        next_run = datetime.utcnow() + timedelta(seconds=wait_seconds)
        
        log.warning(
            "task_rescheduled", 
            retry_count=current_retries,
            max_retries=settings.MAX_RETRIES,
            wait_seconds=wait_seconds,
            next_run=next_run.isoformat(),
            error_type=type(error).__name__,
            error=str(error)
        )
        
        # 调用reschedule方法，更新task.next_retry_at字段
        await self.repo.reschedule(
            task.id, 
            next_run
        )
        
    async def _retry_group(self, tasks, error, log):
        """
        批量处理任务重试
        """
        for task in tasks:
            await self._retry_task(task, error, log)