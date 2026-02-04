
import asyncio
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
        logger.info("🚀 Starting system bootstrap sequence...")
        
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
            
        logger.info("✅ Bootstrap Sequence Complete. System is now RUNNING.")
        set_ready(True)

    async def _check_database(self) -> None:
        logger.info("执行数据库健康检查...")
        try:
            from scripts.ops.database_health_check import DatabaseHealthChecker
            health_checker = DatabaseHealthChecker()
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
        # 初始化容器
        container.init_with_client(self.user_client, self.bot_client)
        
        # Wire up EventBus broadcaster
        try:
            from web_admin.routers.websocket_router import broadcast_event
            container.bus.set_broadcaster(broadcast_event)
            logger.info("EventBus broadcaster wired")
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
        while not self.coordinator.is_shutting_down:
            try:
                if not ResourceGate.check_memory_safe():
                    logger.critical("⚠️ Memory limit exceeded! System stability at risk.")
                    # Future: trigger self.coordinator.shutdown() if strict mode enabled
                await asyncio.sleep(60)
            except Exception as e:
                logger.error(f"Resource monitor error: {e}")
                await asyncio.sleep(60)
    def _register_shutdown_hooks(self) -> None:
        # Priority 0: Stop accepting requests
        async def _stop_accepting_requests() -> None:
            set_ready(False)
            logger.info("系统已标记为非就绪状态")
        
        self.coordinator.register_cleanup(_stop_accepting_requests, priority=0, timeout=2.0)
        
        # Priority 1: Cron & Guards Stop
        async def _stop_auxiliary() -> None:
            from scheduler.cron_service import cron_service
            from services.system_service import guard_service
            await cron_service.stop()
            guard_service.stop_guards()
            await asyncio.sleep(0.1)
            
        self.coordinator.register_cleanup(_stop_auxiliary, priority=1, timeout=5.0, name="stop_auxiliary")
        
        # Priority 2: Shutdown Container
        self.coordinator.register_cleanup(container.shutdown, priority=2, timeout=10.0, name="container_shutdown")
        
        # Priority 3: Disconnect Clients
        async def _disconnect_clients() -> None:
            if self.user_client and self.user_client.is_connected():
                await self.user_client.disconnect()
            if self.bot_client and self.bot_client.is_connected():
                await self.bot_client.disconnect()
        
        self.coordinator.register_cleanup(_disconnect_clients, priority=3, timeout=5.0, name="telegram_clients")

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
                lang_code='en',
                commands=BOT_COMMANDS
            ))
            logger.info(f"已成功注册 {len(BOT_COMMANDS)} 个 Bot 命令")
        except Exception as e:
            logger.warning(f"注册 Bot 命令失败: {e}")

        # 发送欢迎消息
        if send_welcome_message:
            await send_welcome_message(self.bot_client)

