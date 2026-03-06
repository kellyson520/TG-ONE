from __future__ import annotations
from typing import TYPE_CHECKING, List, Optional, Any, Dict
if TYPE_CHECKING:
    from repositories.task_repo import TaskRepository
    from repositories.rule_repo import RuleRepository
    from repositories.stats_repo import StatsRepository
    from repositories.user_repo import UserRepository
    from repositories.dedup_repo import DedupRepository
    from repositories.audit_repo import AuditRepository
    from services.db_buffer import GroupCommitCoordinator
    from services.queue_service import MessageQueueService
    from services.dedup_service import DeduplicationService
    from services.state_service import StateService
    from services.media_service import MediaService
    from services.forward_service import ForwardService
    from services.remote_config_sync_service import RemoteConfigSyncService
    from services.chat_info_service import ChatInfoService
    from services.rule.facade import RuleManagementService
    from services.rule.query import RuleQueryService
    from services.rule.filter import RuleFilterService
    from aiohttp import ClientSession
    from telethon import TelegramClient

from core.event_bus import EventBus
from core.pipeline import Pipeline
# Heavy imports moved to cached_properties for Lazy Loading
# from repositories... 
# from services...

# Middlewares are now imported lazily in init_with_client
# from services.db_buffer import GroupCommitCoordinator -> moved to property

# 引入全局数据库单例获取函数
from core.db_factory import get_async_engine 
# 引入 Database 类（我们需要稍微改造它以接受现有的 engine）
from core.database import Database 
import asyncio
import logging

logger = logging.getLogger(__name__)

class Container:
    def __init__(self) -> None:
        # [Critical Fix] 不再创建新的 Database 实例，而是包装现有的全局引擎
        # 这样 main.py, web admin, worker 都使用同一个连接池
        engine = get_async_engine()
        self.db = Database(engine=engine) 
        logger.info(f"Container connected to shared database engine: {engine.url}")

        # Initialize global HTTP Session (Infrastructure Pooling)
        self.http_session: Optional[ClientSession] = None
        
        # 初始化事件总线
        self.bus = EventBus()
        logger.info("事件总线已初始化")
        
        # 服务列表，用于统一管理生命周期
        self.services: List[asyncio.Task[Any]] = []
        
        # 服务实例 placeholders (for explicit typing if needed, otherwise rely on properties)
        self.downloader: Optional[Any] = None 
        self.worker: Optional[Any] = None      
        self.scheduler: Optional[Any] = None   
        self.chat_updater: Optional[Any] = None  
        self.rss_puller: Optional[Any] = None  
        self.user_client: Optional[TelegramClient] = None
        self.bot_client: Optional[TelegramClient] = None
        self._lifecycle: Optional[Any] = None
        
        # 注册核心事件监听 (延迟到属性访问或 start 时可能更好，但为了保证监听有效性，部分可能需要在 init 或第一次使用时注册)
        # 这里暂时保留核心的内部监听，外部服务的监听移至 dedicated setup 方法或 lazy property
        self.bus.subscribe("FORWARD_SUCCESS", self._on_stats_update)
        self.bus.subscribe("FORWARD_FAILED", self._on_forward_failed)
        self.bus.subscribe("FORWARD_FILTERED", self._on_forward_filtered)
        
        # [Scheme 7 Standard] Dedup 监听在访问 dedup_service 时自动注册? 
        # 为了避免循环依赖和过度 Eager，我们可以在 dedup_service 的 property 中注册
        
    @property
    def db_session(self):
        """数据库会话工厂别名，供 context manager 使用: async with container.db_session() as s:"""
        return self.db.session

    @property
    def async_db_session(self):
        """兼容旧版名称的数据库会话工厂"""
        return self.db.session

    # --- Repositories (Lazy) ---

    @property
    def task_repo(self) -> TaskRepository:
        if not hasattr(self, '_task_repo'):
            from repositories.task_repo import TaskRepository
            self._task_repo = TaskRepository(self.db)
        return self._task_repo

    @property
    def rule_repo(self) -> RuleRepository:
        if not hasattr(self, '_rule_repo'):
            from repositories.rule_repo import RuleRepository
            self._rule_repo = RuleRepository(self.db)
        return self._rule_repo

    @property
    def stats_repo(self) -> StatsRepository:
        if not hasattr(self, '_stats_repo'):
            from repositories.stats_repo import StatsRepository
            self._stats_repo = StatsRepository(self.db)
        return self._stats_repo

    @property
    def user_repo(self) -> UserRepository:
        if not hasattr(self, '_user_repo'):
            from repositories.user_repo import UserRepository
            self._user_repo = UserRepository(self.db)
        return self._user_repo

    @property
    def dedup_repo(self) -> DedupRepository:
        if not hasattr(self, '_dedup_repo'):
            from repositories.dedup_repo import DedupRepository
            self._dedup_repo = DedupRepository(self.db)
        return self._dedup_repo

    @property
    def audit_repo(self) -> AuditRepository:
        if not hasattr(self, '_audit_repo'):
            from repositories.audit_repo import AuditRepository
            self._audit_repo = AuditRepository(self.db)
        return self._audit_repo

    # --- Core Services (Lazy) ---

    @property
    def group_commit_coordinator(self) -> GroupCommitCoordinator:
        if not hasattr(self, '_group_commit_coordinator'):
            from services.db_buffer import GroupCommitCoordinator
            self._group_commit_coordinator = GroupCommitCoordinator(self.db.session)
            logger.info("GroupCommitCoordinator 已初始化 (惰性加载)")
        return self._group_commit_coordinator

    @property
    def metrics_collector(self) -> Any:
        if not hasattr(self, '_metrics_collector'):
            from services.metrics_collector import metrics_collector
            self._metrics_collector = metrics_collector
        return self._metrics_collector

    @property
    def rate_limiter_pool(self) -> Any:
        if not hasattr(self, '_rate_limiter_pool'):
            from services.rate_limiter import RateLimiterPool
            self._rate_limiter_pool = RateLimiterPool
        return self._rate_limiter_pool

    @property
    def queue_service(self) -> MessageQueueService:
        if not hasattr(self, '_queue_service'):
            from services.queue_service import MessageQueueService
            self._queue_service = MessageQueueService(max_size=1000)
            self._queue_service.set_processor(self._process_ingestion_queue)
            logger.info("MessageQueueService 已初始化 (惰性加载)")
        return self._queue_service

    @property
    def dedup_service(self) -> DeduplicationService:
        if not hasattr(self, '_dedup_service'):
            from services.dedup_service import dedup_service
            dedup_service.set_db(self.db)
            dedup_service.set_coordinator(self.group_commit_coordinator)
            # 延迟注册监听
            self.bus.subscribe("FORWARD_SUCCESS", dedup_service.on_forward_success)
            self._dedup_service = dedup_service
            logger.info("去重服务已初始化 (惰性加载)")
        return self._dedup_service

    @property
    def state_service(self) -> StateService:
        if not hasattr(self, '_state_service'):
            from services.state_service import state_service
            self._state_service = state_service
        return self._state_service

    @property
    def media_service(self) -> MediaService:
        # Returns (media_service, media_group_cache) tuple or just service? 
        # Original code set both. Accessor usually just needs service.
        # But for compatibility we might need to expose media_group_cache too.
        if not hasattr(self, '_media_service'):
            from services.media_service import media_service, processed_group_cache
            self._media_service = media_service
            self._media_group_cache = processed_group_cache
        return self._media_service
    
    @property
    def media_group_cache(self) -> Any:
        if not hasattr(self, '_media_group_cache'):
            # Trigger init
            _ = self.media_service
        return self._media_group_cache

    @property
    def forward_service(self) -> ForwardService:
        if not hasattr(self, '_forward_service'):
            from services.forward_service import forward_service
            self._forward_service = forward_service
        return self._forward_service

    @property
    def remote_config_sync_service(self) -> RemoteConfigSyncService:
        if not hasattr(self, '_remote_config_sync_service'):
            from services.remote_config_sync_service import remote_config_sync_service
            self._remote_config_sync_service = remote_config_sync_service
        return self._remote_config_sync_service

    @property
    def chat_info_service(self) -> ChatInfoService:
        if not hasattr(self, '_chat_info_service'):
            from services.chat_info_service import chat_info_service
            chat_info_service.set_db(self.db)
            self._chat_info_service = chat_info_service
        return self._chat_info_service

    @property
    def rule_management_service(self) -> RuleManagementService:
        if not hasattr(self, '_rule_management_service'):
            from services.rule.facade import RuleManagementService
            self._rule_management_service = RuleManagementService()
        return self._rule_management_service

    @property
    def rule_query_service(self) -> RuleQueryService:
        if not hasattr(self, '_rule_query_service'):
            from services.rule.query import RuleQueryService
            self._rule_query_service = RuleQueryService()
        return self._rule_query_service
        
    @property
    def rule_filter_service(self) -> RuleFilterService:
        if not hasattr(self, '_rule_filter_service'):
            from services.rule.filter import RuleFilterService
            self._rule_filter_service = RuleFilterService()
        return self._rule_filter_service

    @property
    def hotword_service(self) -> Any:
        if not hasattr(self, '_hotword_service'):
            from services.hotword_service import get_hotword_service
            self._hotword_service = get_hotword_service()
        return self._hotword_service

    @property
    def system_service(self) -> Any:
        if not hasattr(self, '_system_service'):
            from services.system_service import SystemService
            self._system_service = SystemService()
        return self._system_service

    @property
    def lifecycle(self) -> Any:
        return self._lifecycle

    # --- Controllers (UI/Domain) ---

    @property
    def rule_controller(self) -> Any:
        if not hasattr(self, '_rule_controller'):
            from controllers.domain import RuleController
            self._rule_controller = RuleController(self)
        return self._rule_controller

    @property
    def admin_controller(self) -> Any:
        if not hasattr(self, '_admin_controller'):
            from controllers.domain import AdminController
            self._admin_controller = AdminController(self)
        return self._admin_controller

    @property
    def media_controller(self) -> Any:
        if not hasattr(self, '_media_controller'):
            from controllers.domain import MediaController
            self._media_controller = MediaController(self)
        return self._media_controller

    @property
    def ui(self) -> Any:
        """UI 渲染器集合"""
        if not hasattr(self, '_ui'):
            from core.container import UIContainer
            self._ui = UIContainer(self)
        return self._ui

    def init_with_client(self, user_client: TelegramClient, bot_client: TelegramClient) -> Any:
        self.user_client = user_client
        self.bot_client = bot_client
        
        # 挂载生命周期管理器 (为了让 update_service 等能够访问)
        from core.lifecycle import get_lifecycle
        self._lifecycle = get_lifecycle(user_client, bot_client)
        
        # 初始化服务
        from services.download_service import DownloadService
        self.downloader = DownloadService(user_client)
        logger.info("下载服务已初始化")
        
        # 组装管道 (Order matters!)
        pipeline = Pipeline()
        from middlewares.loader import RuleLoaderMiddleware
        from middlewares.dedup import DedupMiddleware
        from middlewares.sender import SenderMiddleware
        from middlewares.filter import FilterMiddleware
        from middlewares.hotword import get_hotword_collector
        collector = get_hotword_collector()
        
        # [Filter Chain Factory Injection]
        from filters.factory import get_filter_chain_factory
        get_filter_chain_factory().set_container(self)
        
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
        from services.worker_service import WorkerService
        self.worker = WorkerService(user_client, self.task_repo, pipeline, self.downloader)
        logger.info("WorkerService 已初始化 (依赖注入完成)")
        
        # 初始化调度器
        from scheduler.summary_scheduler import SummaryScheduler
        self.scheduler = SummaryScheduler(user_client, bot_client, self.task_repo, self.db)
        logger.info("总结调度器已初始化 (依赖注入完成)")
        
        # 初始化优化的聊天更新器
        from scheduler.optimized_chat_updater import OptimizedChatUpdater
        self.chat_updater = OptimizedChatUpdater(user_client, self.db)
        logger.info("优化聊天更新器已初始化 (依赖注入完成)")
        
        # 初始化通知服务 (H.5.C3)
        from services.notification_service import NotificationService
        self.notification_service = NotificationService(bot_client, self.bus)
        logger.info("通知服务已初始化")

        # 初始化 RSS 拉取服务 (AIMD)
        from services.rss_pull_service import RSSPullService
        self.rss_puller = RSSPullService(user_client, bot_client)
        logger.info("RSS 拉取服务已初始化")

        # 让 ChatInfoService 能够调用 Telegram API
        self.chat_info_service.set_client(user_client)

        return self.worker

    async def start_all(self) -> None:
        """统一启动所有服务"""
        if not self.worker or not self.scheduler or not self.chat_updater:
            raise RuntimeError("Clients not initialized. Call init_with_client() first.")
            
        logger.info("🚀 正在启动所有服务...")

        # Initialize global HTTP session
        import aiohttp
        if self.http_session is None or self.http_session.closed:
            self.http_session = aiohttp.ClientSession()
            logger.info("全局 HTTP 会话已初始化")
        
        # Start Hotword Collector Worker
        from middlewares.hotword import get_hotword_collector
        self.services.append(asyncio.create_task(get_hotword_collector().start_worker(), name="HotwordCollector"))

        # 使用 asyncio.create_task 启动并由 Container 持有引用
        if self.worker:
            self.services.append(asyncio.create_task(self.worker.start(), name="Worker"))
        if self.scheduler:
            self.services.append(asyncio.create_task(self.scheduler.start(), name="Scheduler"))
        if self.chat_updater:
            self.services.append(asyncio.create_task(self.chat_updater.start(), name="ChatUpdater"))
        if self.rss_puller:
            self.services.append(asyncio.create_task(self.rss_puller.start(), name="RSSPuller"))
        
        # 启动 StatsRepository 的缓冲刷新任务 (H.5)
        await self.stats_repo.start()
        
        # 启动背压队列服务
        await self.queue_service.start()
        
        # 启动 Group Commit Coordinator
        await self.group_commit_coordinator.start()

        # 可以在这里添加健康检查或启动顺序控制
        logger.info(f"✅ {len(self.services)} 个服务已启动。")

    async def shutdown(self) -> None:
        """统一优雅关闭"""
        logger.info("🛑 正在停止所有服务...")
        
        # 1. 先停止接收新任务 (Scheduler)
        if self.scheduler:
            self.scheduler.stop()
            logger.info("总结调度器已停止接收新任务")
            
        # 2. 停止消费者 (Worker)
        if self.worker:
            logger.info("正在停止 WorkerService...")
            await self.worker.stop()
            logger.info("WorkerService 已停止")
            
        # 3. 停止辅助服务
        if self.chat_updater:
            logger.info("正在停止优化聊天更新器...")
            await self.chat_updater.stop()
            logger.info("优化聊天更新器已停止")
        
        if self.downloader:
            logger.info("正在停止下载服务...")
            await self.downloader.shutdown()
            logger.info("下载服务已停止")

        if self.rss_puller:
            logger.info("正在停止 RSS 拉取服务...")
            await self.rss_puller.stop()
            logger.info("RSS 拉取服务已停止")

        # 停止 StatsRepository 的缓冲刷新任务 (H.5)
        if self.stats_repo:
            logger.info("正在停止统计仓库...")
            await self.stats_repo.stop()
            
        # 停止背压队列服务
        if self.queue_service:
            logger.info("正在停止消息队列服务...")
            await self.queue_service.stop()
            
        # 停止 Group Commit Coordinator
        if self.group_commit_coordinator:
            logger.info("正在停止 GroupCommitCoordinator...")
            await self.group_commit_coordinator.stop()

        # 保存 Bloom Filter
        try:
            from services.bloom_filter import bloom_filter_service
            bloom_filter_service.save()
            logger.info("布隆过滤器已保存")
        except Exception as e:
            logger.error(f"Failed to save Bloom Filter: {e}")
            
        # Close HTTP Session
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
            logger.info("全局 HTTP 会话已关闭")

        # 4. 等待所有后台任务结束
        # cancel 掉还在运行的 task (如 scheduler 的无限循环)
        logger.info(f"正在取消 {len(self.services)} 个运行中的任务...")
        for task in self.services:
            if not task.done():
                task.cancel()
        
        logger.info("正在等待所有任务完成...")
        await asyncio.gather(*self.services, return_exceptions=True)
        
        # 清空服务列表
        self.services.clear()
        
        # [Fix] 不要在这里 dispose engine，因为它是全局共享的
        # 让 main.py 或生命周期管理器负责最终的 dispose
        # await self.db.close() 
        logger.info("✅ 系统关闭完成")
    
    async def _on_stats_update(self, data: Dict[str, Any]) -> None:
        """处理转发成功事件，并发写入日志和统计表"""
        try:
            await asyncio.gather(
                self.stats_repo.log_action(
                    data['rule_id'], data['msg_id'], "success", 
                    result=f"已转发 (模式: {data.get('mode', '未知')})",
                    msg_text=data.get('msg_text'),
                    msg_type=data.get('msg_type'),
                    processing_time=data.get('duration')
                ),
                self.stats_repo.increment_stats(data['target_id']),
                self.stats_repo.increment_rule_stats(data['rule_id'], "success")
            )
            logger.debug(f"Stats updated for rule {data['rule_id']}, message {data['msg_id']}")
        except Exception as e:
            logger.error(f"Failed to update stats: {str(e)}")

    async def _on_forward_failed(self, data: Dict[str, Any]) -> None:
        """处理转发失败事件"""
        try:
            rule_id = data.get('rule_id')
            if not rule_id:
                return
            
            await asyncio.gather(
                self.stats_repo.log_action(
                    rule_id, 0, "error", 
                    result=data.get('error'),
                    processing_time=data.get('duration')
                ),
                self.stats_repo.increment_rule_stats(rule_id, "error")
            )
            logger.debug(f"Error logged for rule {rule_id}: {data.get('error')}")
        except Exception as e:
            logger.error(f"Failed to log error: {str(e)}")

    async def _on_forward_filtered(self, data: Dict[str, Any]) -> None:
        """处理过滤拦截事件"""
        try:
            rule_id = data.get('rule_id')
            if not rule_id:
                return
            
            await asyncio.gather(
                self.stats_repo.log_action(
                    rule_id, data.get('msg_id', 0), "filtered", 
                    result=data.get('reason', '按规则过滤'),
                    msg_text=data.get('msg_text'),
                    msg_type=data.get('msg_type'),
                    processing_time=data.get('duration')
                ),
                self.stats_repo.increment_rule_stats(rule_id, "filtered")
            )
            logger.debug(f"Filter recorded for rule {rule_id}")
        except Exception as e:
            logger.error(f"Failed to log filter event: {str(e)}")

    async def _process_ingestion_queue(self, items: List[Any]) -> None:
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




class UIContainer:
    """封装所有渲染器的容器"""
    def __init__(self, container: Container):
        self._container = container

    @property
    def base(self):
        from ui.renderers.base_renderer import BaseRenderer
        return BaseRenderer()

    @property
    def main_menu(self):
        from ui.renderers.main_menu_renderer import MainMenuRenderer
        return MainMenuRenderer()

    @property
    def rule(self):
        from ui.renderers.rule_renderer import RuleRenderer
        return RuleRenderer()

    @property
    def settings(self):
        from ui.renderers.settings_renderer import SettingsRenderer
        return SettingsRenderer()

    @property
    def admin(self):
        from ui.renderers.admin_renderer import AdminRenderer
        return AdminRenderer()

    @property
    def task(self):
        from ui.renderers.task_renderer import TaskRenderer
        return TaskRenderer()

    @property
    def media(self):
        from ui.renderers.media_renderer import MediaRenderer
        return MediaRenderer()

    @property
    def dedup(self):
        from ui.renderers.dedup_renderer import DedupRenderer
        return DedupRenderer()

    @property
    def session(self):
        from ui.renderers.session_renderer import SessionRenderer
        return SessionRenderer()

    def render_error(self, message: str, back_target: str = "main_menu"):
        return self.base.render_error(message, back_target)


_container = None

def get_container() -> Container:
    """获取全局容器单例 (极致惰性执行)"""
    global _container
    if _container is None:
        _container = Container()
    return _container

# 暂时保留全局变量以保持向后兼容，但通过 get_container() 代理 (不推荐直接使用)
class ContainerProxy:
    def __getattr__(self, name: str) -> Any:
        return getattr(get_container(), name)
    
container = ContainerProxy()
