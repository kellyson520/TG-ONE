import asyncio
import json
import random
import math
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
        self.sleep_increment = 1.0  # 每次增加的休眠时间

    async def start(self):
        """启动 Worker 服务 (动态并发池)"""
        self.running = True
        logger.info(f"WorkerService 启动 (Min: {settings.WORKER_MIN_CONCURRENCY}, Max: {settings.WORKER_MAX_CONCURRENCY})")
        
        self.workers = {} # task -> worker_id
        
        # 启动初始 Workers
        for i in range(settings.WORKER_MIN_CONCURRENCY):
            self._spawn_worker()
            
        # 启动弹性伸缩监控
        self._monitor_task = asyncio.create_task(self._monitor_scaling(), name="worker_scaling_monitor")
        
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
        """Monitor queue depth and scale workers"""
        while self.running:
            try:
                await asyncio.sleep(10) # 每10秒检查一次
                
                status = await self.repo.get_queue_status()
                pending = status.get('active_queues', 0)
                current_workers = len(self.workers)
                
                # Scaling Logic
                # 如果 pending > current_workers * 2，扩容
                # 如果 pending == 0，缩容
                
                if pending > current_workers * 2 and current_workers < settings.WORKER_MAX_CONCURRENCY:
                    scale_up = min(settings.WORKER_MAX_CONCURRENCY - current_workers, math.ceil(pending / 2))
                    logger.info(f"Scaling UP: Pending={pending}, Workers={current_workers} -> +{scale_up}")
                    for _ in range(scale_up):
                        self._spawn_worker()
                        
                elif pending == 0 and current_workers > settings.WORKER_MIN_CONCURRENCY:
                    logger.info(f"Scaling DOWN: Pending=0, Workers={current_workers} -> -1")
                    await self._kill_worker()
                    
            except Exception as e:
                logger.error(f"Scaling monitor error: {e}")
                await asyncio.sleep(5)

    async def _worker_loop(self, worker_id: str):
        """单个 Worker 的工作循环"""
        logger.debug(f"[{worker_id}] Loop Started")
        
        while self.running:
            task = None
            try:
                # 获取任务
                # 注意：Worker cancel 时，这里可能会抛出 CancelledError
                try:
                      tasks = await self.repo.fetch_next()
                except asyncio.CancelledError:
                     logger.debug(f"[{worker_id}] Cancelled during fetch")
                     raise

                if not tasks:
                    # 没任务时，增加休眠
                    await self._adaptive_sleep() 
                    continue
                
                # 第一个是主任务
                task = tasks[0]
                group_tasks = tasks[1:] if len(tasks) > 1 else []
                
                self._reset_sleep() # 有任务，重置休眠
                
                # ----------------- Worker Logic Copied & Adapted -----------------
                # 确保连接正常，防止 Telethon 断连导致处理失败
                await self._ensure_connected()
                
                # [关键] 绑定上下文：此后该循环内的所有日志都会自动带上 task_id
                log = logger.bind(worker_id=worker_id, task_id=task.id, task_type=task.task_type)
                
                # Worker Logic (Simplified for integration)
                await self._process_task_safely(task, log, group_tasks=group_tasks)
                # -----------------------------------------------------------------

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
            log.info(f"📥 [Worker] 成功获取消息对象: ID={primary_message.id}, 内容预览={primary_message.text[:20] if primary_message.text else 'No Text'}")
            
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
                log.info(f"task_completed_with_group", count=len(group_tasks))
            else:
                log.info("task_completed")

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

    async def stop(self):
        """优雅停止 Worker"""
        logger.info("worker_stopping")
        self.running = False
        if getattr(self, '_monitor_task', None):
            self._monitor_task.cancel()
        
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
             import gc
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
        current_retries = task.retry_count + 1
        
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