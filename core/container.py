from core.event_bus import EventBus
from core.pipeline import Pipeline
from repositories.task_repo import TaskRepository
from repositories.rule_repo import RuleRepository
from repositories.stats_repo import StatsRepository
from repositories.user_repo import UserRepository
from repositories.audit_repo import AuditRepository
from services.download_service import DownloadService
from services.worker_service import WorkerService
from services.queue_service import MessageQueueService
from middlewares.loader import RuleLoaderMiddleware
from middlewares.dedup import DedupMiddleware
from middlewares.download import DownloadMiddleware
from middlewares.sender import SenderMiddleware
from middlewares.sender import SenderMiddleware
from middlewares.filter import FilterMiddleware
from services.db_buffer import GroupCommitCoordinator
# 引入全局数据库单例获取函数
from models.models import get_async_engine 
# 引入 Database 类（我们需要稍微改造它以接受现有的 engine）
from core.database import Database 
import os
import asyncio
from pathlib import Path
from models.models import get_async_engine
import logging

logger = logging.getLogger(__name__)

class Container:
    def __init__(self):
        # [Critical Fix] 不再创建新的 Database 实例，而是包装现有的全局引擎
        # 这样 main.py, web admin, worker 都使用同一个连接池
        engine = get_async_engine()
        self.db = Database(engine=engine) 
        logger.info(f"Container connected to shared database engine: {engine.url}")
        
        # 初始化事件总线
        self.bus = EventBus()
        logger.info("EventBus initialized")
        
        # 初始化仓库 (复用统一的 db 实例)
        self.task_repo = TaskRepository(self.db)
        self.rule_repo = RuleRepository(self.db)
        self.stats_repo = StatsRepository(self.db)
        self.user_repo = UserRepository(self.db)
        self.audit_repo = AuditRepository(self.db)
        logger.info("Repositories initialized")

        # 初始化 Group Commit Coordinator (Buffer)
        # 传递 self.db.session (async context manager) 作为 factory
        self.group_commit_coordinator = GroupCommitCoordinator(self.db.session)
        logger.info("GroupCommitCoordinator initialized")

        # 初始化 Rate Limiter Pool
        from services.rate_limiter import RateLimiterPool
        self.rate_limiter_pool = RateLimiterPool
        logger.info("RateLimiterPool initialized with presets")

        # 初始化 Metrics Collector
        from services.metrics_collector import metrics_collector
        self.metrics_collector = metrics_collector
        logger.info("MetricsCollector initialized")

        # 初始化背压队列服务 (Ingestion Buffer)
        self.queue_service = MessageQueueService(max_size=1000)
        # 设置队列消费者：将内存队列中的任务写入数据库
        self.queue_service.set_processor(self._process_ingestion_queue)
        logger.info("MessageQueueService initialized")
        
        # 初始化去重服务
        from services.dedup_service import dedup_service
        dedup_service.set_db(self.db)
        dedup_service.set_coordinator(self.group_commit_coordinator)
        logger.info("Deduplication service initialized with GroupCommit Support")
        
        # 初始化聊天信息服务
        from services.chat_info_service import chat_info_service
        chat_info_service.set_db(self.db)
        self.chat_info_service = chat_info_service
        self.chat_info_service = chat_info_service
        logger.info("ChatInfoService initialized")
        
        # 初始化 RuleManagementService
        from services.rule_management_service import RuleManagementService
        self.rule_management_service = RuleManagementService()
        logger.info("RuleManagementService initialized")
        
        # 注册事件监听
        self.bus.subscribe("FORWARD_SUCCESS", self._on_stats_update)
        self.bus.subscribe("FORWARD_FAILED", self._on_forward_failed)
        # [Scheme 7 Standard] 注册去重记录监听器
        # 只有当消息发送成功后，才将其特征指纹记录到数据库
        # 避免因发送失败而导致错误地拦截了重试消息
        from services.dedup_service import dedup_service
        self.bus.subscribe("FORWARD_SUCCESS", dedup_service.on_forward_success)
        logger.info("Event listeners registered")
        
        # 服务列表，用于统一管理生命周期
        self.services = []
        
        # 服务实例
        self.downloader = None  # 需要 client
        self.worker = None      # 需要 client
        self.scheduler = None   # 需要 client
        self.chat_updater = None  # 需要 client
        self.rss_puller = None  # 需要 client

    def init_with_client(self, user_client, bot_client):
        self.user_client = user_client
        self.bot_client = bot_client
        # 初始化服务
        self.downloader = DownloadService(user_client)
        logger.info("DownloadService initialized")
        
        # 组装管道 (Order matters!)
        pipeline = Pipeline()
        pipeline.add(RuleLoaderMiddleware(self.rule_repo))  # 1. 加载规则
        pipeline.add(DedupMiddleware())                     # 2. 去重检查
        pipeline.add(FilterMiddleware())                    # 3. 过滤 & 内容修改
        from middlewares.ai import AIMiddleware             # 引入AI中间件
        pipeline.add(AIMiddleware())                        # 4. AI 处理 (依赖 Filter 的修改)
        # 暂时移除 DownloadMiddleware
        # pipeline.add(DownloadMiddleware(self.downloader))   # 5. 下载 (如果需要)
        pipeline.add(SenderMiddleware(self.bus))            # 5. 发送 & 去重回写
        logger.info("✅ Pipeline assembled: Loader -> Dedup -> Filter -> AI -> Sender")
        
        # [Dependency Injection] 将 downloader 直接注入 worker，解耦全局依赖
        self.worker = WorkerService(user_client, self.task_repo, pipeline, self.downloader)
        logger.info("WorkerService initialized with injected dependencies")
        
        # 初始化调度器
        from scheduler.summary_scheduler import SummaryScheduler
        self.scheduler = SummaryScheduler(user_client, bot_client, self.task_repo, self.db)
        logger.info("SummaryScheduler initialized with injected dependencies")
        
        # 初始化优化的聊天更新器
        from scheduler.optimized_chat_updater import OptimizedChatUpdater
        self.chat_updater = OptimizedChatUpdater(user_client, self.db)
        logger.info("OptimizedChatUpdater initialized with injected dependencies")
        
        # 初始化通知服务 (H.5.C3)
        from services.notification_service import NotificationService
        self.notification_service = NotificationService(bot_client, self.bus)
        logger.info("NotificationService initialized")

        # 初始化 RSS 拉取服务 (AIMD)
        from services.rss_pull_service import RSSPullService
        self.rss_puller = RSSPullService(user_client, bot_client)
        logger.info("RSSPullService initialized")

        # 让 ChatInfoService 能够调用 Telegram API
        self.chat_info_service.set_client(user_client)

        return self.worker

    async def start_all(self):
        """统一启动所有服务"""
        if not self.worker or not self.scheduler or not self.chat_updater:
            raise RuntimeError("Clients not initialized. Call init_with_client() first.")
            
        logger.info("🚀 Starting all services...")
        
        # 使用 asyncio.create_task 启动并由 Container 持有引用
        self.services.append(asyncio.create_task(self.worker.start(), name="Worker"))
        self.services.append(asyncio.create_task(self.scheduler.start(), name="Scheduler"))
        self.services.append(asyncio.create_task(self.chat_updater.start(), name="ChatUpdater"))
        self.services.append(asyncio.create_task(self.rss_puller.start(), name="RSSPuller"))
        
        # 启动 StatsRepository 的缓冲刷新任务 (H.5)
        await self.stats_repo.start()
        
        # 启动背压队列服务
        # 启动背压队列服务
        await self.queue_service.start()
        
        # 启动 Group Commit Coordinator
        await self.group_commit_coordinator.start()

        # 可以在这里添加健康检查或启动顺序控制
        logger.info(f"✅ {len(self.services)} services started.")

    async def shutdown(self):
        """统一优雅关闭"""
        logger.info("🛑 Stopping all services...")
        
        # 1. 先停止接收新任务 (Scheduler)
        if self.scheduler:
            self.scheduler.stop()
            logger.info("SummaryScheduler stopped accepting new tasks")
            
        # 2. 停止消费者 (Worker)
        if self.worker:
            logger.info("Stopping WorkerService...")
            await self.worker.stop()
            logger.info("WorkerService stopped")
            
        # 3. 停止辅助服务
        if self.chat_updater:
            logger.info("Stopping OptimizedChatUpdater...")
            await self.chat_updater.stop()
            logger.info("OptimizedChatUpdater stopped")
        
        if self.downloader:
            logger.info("Stopping DownloadService...")
            await self.downloader.shutdown()
            logger.info("DownloadService stopped")

        if self.rss_puller:
            logger.info("Stopping RSSPullService...")
            await self.rss_puller.stop()
            logger.info("RSSPullService stopped")

        # 停止 StatsRepository 的缓冲刷新任务 (H.5)
        if self.stats_repo:
            logger.info("Stopping StatsRepository...")
            await self.stats_repo.stop()
            
        # 停止背压队列服务
        if self.queue_service:
            logger.info("Stopping MessageQueueService...")
            await self.queue_service.stop()
            logger.info("Stopping MessageQueueService...")
            await self.queue_service.stop()
            
        # 停止 Group Commit Coordinator
        if self.group_commit_coordinator:
            logger.info("Stopping GroupCommitCoordinator...")
            await self.group_commit_coordinator.stop()

        # 保存 Bloom Filter
        try:
            from services.bloom_filter import bloom_filter_service
            bloom_filter_service.save()
            logger.info("Bloom Filter saved")
        except Exception as e:
            logger.error(f"Failed to save Bloom Filter: {e}")

        # 4. 等待所有后台任务结束
        # cancel 掉还在运行的 task (如 scheduler 的无限循环)
        logger.info(f"Cancelling {len(self.services)} running tasks...")
        for task in self.services:
            if not task.done():
                task.cancel()
        
        logger.info("Waiting for all tasks to complete...")
        await asyncio.gather(*self.services, return_exceptions=True)
        
        # 清空服务列表
        self.services.clear()
        
        # [Fix] 不要在这里 dispose engine，因为它是全局共享的
        # 让 main.py 或生命周期管理器负责最终的 dispose
        # await self.db.close() 
        logger.info("✅ System shutdown complete")
    
    async def _on_stats_update(self, data):
        """处理转发成功事件，并发写入日志和统计表"""
        try:
            await asyncio.gather(
                self.stats_repo.log_action(data['rule_id'], data['msg_id'], "success"),
                self.stats_repo.increment_stats(data['target_id']),
                self.stats_repo.increment_rule_stats(data['rule_id'], "success")
            )
            logger.debug(f"Stats updated for rule {data['rule_id']}, message {data['msg_id']}")
        except Exception as e:
            logger.error(f"Failed to update stats: {str(e)}")

    async def _on_forward_failed(self, data):
        """处理转发失败事件"""
        try:
            rule_id = data.get('rule_id')
            if not rule_id:
                return
            
            await asyncio.gather(
                self.stats_repo.log_action(rule_id, 0, "error", result=data.get('error')),
                self.stats_repo.increment_rule_stats(rule_id, "error")
            )
            logger.debug(f"Error logged for rule {rule_id}: {data.get('error')}")
        except Exception as e:
            logger.error(f"Failed to log error: {str(e)}")

    async def _process_ingestion_queue(self, items):
        """
        处理 ingestion 队列项 (Batch)
        items: List[(task_type, payload, priority)]
        """
        try:
            if not items:
                return
            # 调用批量写入
            await self.task_repo.push_batch(items)
        except Exception as e:
            logger.error(f"Batch ingestion failed: {e}", exc_info=True)


container = Container()