
import asyncio
from datetime import datetime
from telethon import TelegramClient

from core.config import settings
from core.container import container
from core.config_initializer import load_dynamic_config_from_db
from core.shutdown import get_shutdown_coordinator
from listeners import setup_listeners
from core.logging import get_logger
from core.helpers.resource_gate import ResourceGate
from core.helpers.sleep_manager import sleep_manager
from core.helpers.tombstone import tombstone
# from services.system_service import guard_service (Moved to local)
# from scheduler.cron_service import cron_service (Moved to local)
# from services.exception_handler import exception_handler (Moved to local)
from services.update_service import update_service
from core.helpers.metrics import set_ready, update_heartbeat

from typing import Optional, Callable, Any 

send_welcome_message: Optional[Callable[[Any], Any]] = None
start_heartbeat: Optional[Callable[[Any, Any], Any]] = None

logger = get_logger(__name__)

# Optional imports
try:
    from handlers.bot_handler import send_welcome_message as _send_welcome_message
    send_welcome_message = _send_welcome_message
except ImportError as e:
    logger.debug(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')

try:
    from services.network.bot_heartbeat import start_heartbeat as _start_heartbeat
    start_heartbeat = _start_heartbeat
except ImportError as e:
    logger.debug(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')

class Bootstrap:
    """系统引导程序"""
    
    def __init__(self, user_client: TelegramClient, bot_client: TelegramClient):
        self.user_client = user_client
        self.bot_client = bot_client
        self.coordinator = get_shutdown_coordinator()

    async def run(self) -> None:
        """执行完整的系统启动序列"""
        logger.info("🚀 正在启动系统引导序列...")
        
        # 1. 基础环境与配置
        await self._check_database()
        await self._check_db_permissions()
        await self._init_db_tables()
        await self._load_config()
        
        # 2. Telegram 客户端连接
        await self._start_clients()
        
        # 3. 核心服务初始化 (Listeners, Optimization)
        await self._init_optimizations()
        await self._setup_listeners()
        
        # 4. 依赖注入与容器启动
        await self._init_and_start_container()
        
        # 5. 辅助服务 (Cron, Guards)
        self._start_auxiliary_services()
        
        # 6. 注册关闭钩子 (Cleanup Hooks)
        self._register_shutdown_hooks()
        
        # 7. 最终收尾
        await self._post_startup()
        
        # 8. 初始资源检查
        try:
            ResourceGate.enforce_memory_limit()
        except MemoryError as e:
            logger.critical(f"Start-up Memory Violation: {e}")
            # Consider exiting if crucial
            
        logger.info("✅ 引导序列完成。系统现已运行。")
        set_ready(True)

    async def _check_database(self) -> None:
        logger.info("执行数据库健康检查...")
        try:
            from scripts.ops.database_health_check import DatabaseHealthChecker
            health_checker = DatabaseHealthChecker()
            
            # [Auto-Fix] 针对 VPS 云端大数据库的自动救援逻辑
            # 如果 task_queue 包含大量完成/失败任务，启动前强制清理并释放空间
            try:
                from core.db_factory import AsyncSessionManager
                from sqlalchemy import text
                import time
                
                async with AsyncSessionManager() as session:
                    # 检查是否需要清理 (例如超过 10000 条非 pending 任务)
                    result = await session.execute(
                        text("SELECT COUNT(*) FROM task_queue WHERE status IN ('completed', 'failed')")
                    )
                    count = result.scalar() or 0
                    
                    if count > 10000:
                        logger.warning(f"⚠️ 检测到数据库积压 {count} 条历史任务，正在执行紧急清理...")
                        start_time = time.time()
                        
                        # 1. 批量删除
                        await session.execute(
                            text("DELETE FROM task_queue WHERE status IN ('completed', 'failed')")
                        )
                        await session.commit()
                        
                        # 2. 执行 VACUUM (释放空间)
                        # 注意：VACUUM 不能在事务块中运行，需要独立连接或特殊处理
                        # 在 SQLAlchemy/aiosqlite 中，session 通常处于隐式事务中
                        # 因此我们这里仅做 DELETE，VACUUM 留给 db_maintenance_service 或下次重启
                        logger.info("已完成数据清理，建议稍后执行 VACUUM")
                        
                        # 3. 更新统计信息
                        await session.execute(text("ANALYZE"))
                        
                        duration = time.time() - start_time
                        logger.info(f"✅ 数据库紧急清理完成，耗时 {duration:.2f}s")
            except Exception as cleanup_err:
                logger.error(f"启动时数据库自动清理失败: {cleanup_err}")

            if not await asyncio.to_thread(health_checker.auto_fix_if_needed):
                logger.error("数据库健康检查失败，程序启动中止")
                exit(1)
            logger.info("数据库健康检查通过")
        except Exception as e:
            logger.error(f"数据库健康检查异常: {e}")
            logger.warning("跳过健康检查，继续启动...")

    async def _check_db_permissions(self) -> None:
        logger.info("检查数据库权限...")
        try:
            from services.db_maintenance_service import db_maintenance_service
            success, total = await asyncio.to_thread(db_maintenance_service.manager.fix_all_permissions)
            if success < total:
                logger.warning(f"数据库权限检查发现问题 ({success}/{total})，但系统将尝试继续启动")
            else:
                logger.info("数据库权限检查通过")
        except Exception as e:
            logger.error(f"数据库权限检查失败: {e}")

    async def _init_db_tables(self) -> None:
        try:
            from core.db_init import init_db_tables
            logger.info("正在初始化/迁移数据库表...")
            await init_db_tables(settings.DATABASE_URL)
            logger.info("数据库表初始化完成")
            
            # [Added] 初始化热词专用数据库
            from core.db_init import init_hotword_db
            await init_hotword_db()
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")

    async def _load_config(self) -> None:
        logger.info("加载动态配置...")
        await load_dynamic_config_from_db(settings)
        logger.info("动态配置加载完成")

    async def _start_clients(self) -> None:
        logger.info("正在连接 Telegram 客户端...")
        await self.user_client.start(phone=settings.PHONE_NUMBER)
        me_user = await self.user_client.get_me()
        logger.info(f'用户客户端已启动: {me_user.first_name} (@{me_user.username})')

        await self.bot_client.start(bot_token=settings.BOT_TOKEN)
        me_bot = await self.bot_client.get_me()
        logger.info(f'机器人客户端已启动: {me_bot.first_name} (@{me_bot.username})')

    async def _init_optimizations(self) -> None:
        # API 优化器
        try:
            from services.network.api_optimization import initialize_api_optimizer
            initialize_api_optimizer(self.user_client)
            logger.info("API优化器初始化完成")
        except Exception as e:
            logger.error(f"API优化器初始化失败: {e}")

        # 实体解析器
        try:
            from core.helpers.entity_optimization import initialize_entity_resolver
            initialize_entity_resolver(self.user_client)
            logger.info("实体解析器初始化完成")
        except Exception as e:
            logger.error(f"实体解析器初始化失败: {e}")
            
        # 事件驱动监控
        try:
             from core.helpers.event_optimization import get_event_optimizer, get_event_monitor
             event_optimizer = get_event_optimizer()
             event_monitor = get_event_monitor()
             
             await event_optimizer.setup_optimized_listeners(self.user_client, self.bot_client)
             await event_monitor.start_monitoring(self.user_client)
             logger.info("事件驱动监控优化启用成功")
        except Exception as e:
             logger.error(f"事件驱动监控优化启用失败: {e}")

    async def _setup_listeners(self) -> None:
        # 普通监听器
        await setup_listeners(self.user_client, self.bot_client)
        
        # 心跳
        if start_heartbeat:
             from services.exception_handler import exception_handler
             exception_handler.create_task(
                 start_heartbeat(self.user_client, self.bot_client),
                 name="bot_heartbeat"
             )
             update_heartbeat("running", source="init")

    async def _init_and_start_container(self) -> None:
        # 1. 初始化容器
        container.init_with_client(self.user_client, self.bot_client)
        
        # 2. [关键交接] 串联内存队列与数据库持久化
        # 监听器发出的任务先进入 MessageQueueService (QoS 4.0)，
        # 然后由以下回调批量写入数据库 task_queue 表。
        if hasattr(container, 'queue_service') and hasattr(container, 'task_repo'):
            container.queue_service.set_processor(container.task_repo.push_batch)
            logger.info("✅ 已接通内存队列与数据库持久化链路 (QoS 4.0 -> DB)")
        
        # Wire up EventBus broadcaster
        try:
            from web_admin.routers.websocket_router import broadcast_event
            container.bus.set_broadcaster(broadcast_event)
            logger.info("事件总线广播器已连接")
        except ImportError:
            logger.warning("WebSocket router not found, EventBus broadcasting disabled")
        
        # 启动所有服务
        await container.start_all()
        logger.info("所有业务服务已启动")

    def _start_auxiliary_services(self) -> None:
        # 启动 Cron
        from scheduler.cron_service import cron_service
        cron_service.start()
        
        # 启动 Guards
        from services.system_service import guard_service
        from services.exception_handler import exception_handler
        
        guard_service.start_guards()
        exception_handler.create_task(
            guard_service.start_guards_async(), 
            name="guard_service_async"
        )
        
        # 启动 Web Server
        if settings.WEB_ENABLED:
            try:
                from web_admin.fastapi_app import start_web_server
                # 使用 exception_handler 启动 web server
                from services.exception_handler import exception_handler
                exception_handler.create_task(
                    start_web_server(settings.WEB_HOST, settings.WEB_PORT), 
                    name="web_server"
                )
                logger.info(f"Web服务已启动: http://{settings.WEB_HOST}:{settings.WEB_PORT}")
            except ImportError as e:
                logger.warning(f"Web Admin 模块加载失败: {e}", exc_info=True)
            except Exception as e:
                logger.error(f"Web 服务启动失败: {e}", exc_info=True)
        
        # 启动更新服务 (内部处理自动检查逻辑)
        update_service.set_bus(container.bus)
        exception_handler.create_task(
            update_service.start_periodic_check(),
            name="update_service"
        )
        logger.info("更新服务已初始化并连接至事件总线")

        # 启动资源监控
        from services.exception_handler import exception_handler
        exception_handler.create_task(
            self._resource_monitor_loop(),
            name="resource_monitor"
        )
        
        # 启动智能休眠监控
        exception_handler.create_task(
            sleep_manager.start_monitor(),
            name="sleep_manager_monitor"
        )
        
        # [Integration] 绑定休眠策略与墓碑机制
        # 当进入休眠时 -> 冻结状态释放内存
        from services.exception_handler import exception_handler
        sleep_manager.register_on_sleep(lambda: exception_handler.create_task(tombstone.freeze(), name="auto_freeze"))
        # 当唤醒时 -> 复苏状态
        sleep_manager.register_on_wake(lambda: exception_handler.create_task(tombstone.resurrect(), name="auto_resurrect"))

    async def _resource_monitor_loop(self) -> None:
        """周期性资源监控"""
        logger.info("资源监控器已启动 (Limit: 2GB)")
        while not self.coordinator.is_shutting_down():
            try:
                if not ResourceGate.check_memory_safe():
                    logger.critical("⚠️ Memory limit exceeded! System stability at risk.")
                # 使用 wait_for 或 sleep 并捕获取消
                await asyncio.sleep(60)
            except asyncio.CancelledError:
                logger.info("资源监控器已停止 (取消)")
                break
            except Exception as e:
                logger.error(f"资源监控器异常: {e}")
                try:
                    await asyncio.sleep(10)
                except asyncio.CancelledError:
                    break
    def _register_shutdown_hooks(self) -> None:
        # Priority 0: Stop accepting requests
        async def _stop_accepting_requests() -> None:
            set_ready(False)
            logger.info("系统已标记为非就绪状态")
            
            # 发送预关闭广播，允许各组件执行最后的异步持久化项
            try:
                from core.container import container
                bus = getattr(container, 'bus', None)
                if bus:
                    await bus.publish("SYSTEM_SHUTDOWN_STARTING", {"time": str(datetime.utcnow())})
            except Exception as e:
                logger.error(f"发送预关闭广播失败: {e}")
        
        self.coordinator.register_cleanup(_stop_accepting_requests, priority=0, timeout=2.0)
        
        async def _stop_auxiliary() -> None:
            from scheduler.cron_service import cron_service
            from services.system_service import guard_service
            from services.update_service import update_service
            from core.helpers.sleep_manager import sleep_manager
            
            logger.info("Stopping auxiliary services (Cron, Guards, Updates, SleepManager)...")
            await cron_service.stop()
            guard_service.stop_guards()
            update_service.stop()
            sleep_manager.stop()
            await asyncio.sleep(0.1)
            
        self.coordinator.register_cleanup(_stop_auxiliary, priority=1, timeout=5.0, name="stop_auxiliary")
        
        # Priority 2: Stop Web Server (Wait for graceful shutdown)
        if settings.WEB_ENABLED:
            try:
                from web_admin.fastapi_app import stop_web_server
                self.coordinator.register_cleanup(stop_web_server, priority=2, timeout=5.0, name="web_server_stop")
            except ImportError:
                pass
        
        # Priority 2: Shutdown Container
        self.coordinator.register_cleanup(container.shutdown, priority=2, timeout=10.0, name="container_shutdown")
        
        # Priority 3: Disconnect Clients
        async def _disconnect_clients() -> None:
            async def _safe_dc(client, name):
                if client and client.is_connected():
                    try:
                        logger.info(f"正在断开 {name} 客户端...")
                        await asyncio.wait_for(client.disconnect(), timeout=4.0)
                        logger.info(f"{name} 客户端已安全断开")
                    except asyncio.TimeoutError:
                        logger.warning(f"{name} 客户端断开超时 (4s)，强制跳过")
                    except Exception as e:
                        logger.error(f"断开 {name} 时发生错误: {e}")

            await asyncio.gather(
                _safe_dc(self.user_client, "User"),
                _safe_dc(self.bot_client, "Bot")
            )
        
        self.coordinator.register_cleanup(_disconnect_clients, priority=3, timeout=5.0, name="telegram_clients")
        
        # Priority 4: Dispose Database Engines (Final I/O cleanup)
        async def _dispose_db() -> None:
            from core.db_factory import dispose_all_engines
            await dispose_all_engines()
            
        self.coordinator.register_cleanup(_dispose_db, priority=4, timeout=5.0, name="db_engine_disposal")

    async def _post_startup(self) -> None:
        # TODO: Implement unified bot command registration if needed
        pass
             
        # RSS 面板日志
        if settings.RSS_ENABLED:
            logger.info("RSS 面板统一挂载模式开启（/rss）")
        
        # 注册 Bot 命令
        try:
            from telethon.tl.functions.bots import SetBotCommandsRequest
            from telethon.tl.types import BotCommandScopeDefault
            from handlers.bot_commands_list import BOT_COMMANDS
            
            await self.bot_client(SetBotCommandsRequest(
                scope=BotCommandScopeDefault(),
                lang_code='',
                commands=BOT_COMMANDS
            ))
            logger.info(f"已成功注册 {len(BOT_COMMANDS)} 个 Bot 命令")
        except Exception as e:
            logger.warning(f"注册 Bot 命令失败: {e}")

        # 发送欢迎消息
        if send_welcome_message:
            await send_welcome_message(self.bot_client)

