
import asyncio
import logging
import os
from telethon import TelegramClient

from core.config import settings
from core.container import container
from core.config_initializer import load_dynamic_config_from_db
from core.shutdown import get_shutdown_coordinator, register_cleanup
from listeners import setup_listeners
from utils.core.logger_utils import get_logger
from core.helpers.metrics import set_ready, update_heartbeat
from services.system_service import guard_service
from scheduler.cron_service import cron_service
from services.exception_handler import exception_handler

# Optional imports
try:
    from handlers.bot_handler import send_welcome_message
except ImportError:
    send_welcome_message = None

try:
    from services.network.bot_heartbeat import start_heartbeat
except ImportError:
    start_heartbeat = None

logger = get_logger(__name__)

class Bootstrap:
    """系统引导程序"""
    
    def __init__(self, user_client: TelegramClient, bot_client: TelegramClient):
        self.user_client = user_client
        self.bot_client = bot_client
        self.coordinator = get_shutdown_coordinator()

    async def run(self):
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
        
        logger.info("✅ Bootstrap Sequence Complete. System is now RUNNING.")
        set_ready(True)

    async def _check_database(self):
        logger.info("执行数据库健康检查...")
        try:
            from scripts.database_health_check import DatabaseHealthChecker
            health_checker = DatabaseHealthChecker()
            if not await asyncio.to_thread(health_checker.auto_fix_if_needed):
                logger.error("数据库健康检查失败，程序启动中止")
                exit(1)
            logger.info("数据库健康检查通过")
        except Exception as e:
            logger.error(f"数据库健康检查异常: {e}")
            logger.warning("跳过健康检查，继续启动...")

    async def _check_db_permissions(self):
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

    async def _init_db_tables(self):
        try:
            from core.db_init import init_db_tables
            logger.info("正在初始化/迁移数据库表...")
            await init_db_tables(settings.DATABASE_URL)
            logger.info("数据库表初始化完成")
        except Exception as e:
            logger.error(f"数据库初始化失败: {e}")

    async def _load_config(self):
        logger.info("加载动态配置...")
        await load_dynamic_config_from_db(settings)
        logger.info("动态配置加载完成")

    async def _start_clients(self):
        logger.info("正在连接 Telegram 客户端...")
        await self.user_client.start(phone=settings.PHONE_NUMBER)
        me_user = await self.user_client.get_me()
        logger.info(f'用户客户端已启动: {me_user.first_name} (@{me_user.username})')

        await self.bot_client.start(bot_token=settings.BOT_TOKEN)
        me_bot = await self.bot_client.get_me()
        logger.info(f'机器人客户端已启动: {me_bot.first_name} (@{me_bot.username})')

    async def _init_optimizations(self):
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

    async def _setup_listeners(self):
        # 普通监听器
        await setup_listeners(self.user_client, self.bot_client)
        
        # 心跳
        if start_heartbeat:
             exception_handler.create_task(
                 start_heartbeat(self.user_client, self.bot_client),
                 name="bot_heartbeat"
             )
             update_heartbeat("running", source="init")

    async def _init_and_start_container(self):
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

    def _start_auxiliary_services(self):
        # 启动 Cron
        cron_service.start()
        
        # 启动 Guards
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
                exception_handler.create_task(
                    start_web_server(settings.WEB_HOST, settings.WEB_PORT), 
                    name="web_server"
                )
                logger.info(f"Web服务已启动: http://{settings.WEB_HOST}:{settings.WEB_PORT}")
            except ImportError:
                logger.warning("Web Admin 模块未找到，Web 服务未启动")
            except Exception as e:
                logger.error(f"Web 服务启动失败: {e}")
        
    def _register_shutdown_hooks(self):
        # Priority 0: Stop accepting requests
        async def _stop_accepting_requests():
            set_ready(False)
            logger.info("系统已标记为非就绪状态")
        
        self.coordinator.register_cleanup(_stop_accepting_requests, priority=0, timeout=2.0)
        
        # Priority 1: Cron & Guards Stop
        async def _stop_auxiliary():
            await cron_service.stop()
            guard_service.stop_guards()
            await asyncio.sleep(0.1)
            
        self.coordinator.register_cleanup(_stop_auxiliary, priority=1, timeout=5.0, name="stop_auxiliary")
        
        # Priority 2: Shutdown Container
        self.coordinator.register_cleanup(container.shutdown, priority=2, timeout=10.0, name="container_shutdown")
        
        # Priority 3: Disconnect Clients
        async def _disconnect_clients():
            if self.user_client and self.user_client.is_connected():
                await self.user_client.disconnect()
            if self.bot_client and self.bot_client.is_connected():
                await self.bot_client.disconnect()
        
        self.coordinator.register_cleanup(_disconnect_clients, priority=3, timeout=5.0, name="telegram_clients")

    async def _post_startup(self):
        # 注册机器人命令
        try:
             from utils.core.command_utils import register_bot_commands
             await register_bot_commands(self.bot_client)
        except Exception as e:
             logger.error(f"注册命令失败: {e}")
             
        # RSS 面板日志
        if settings.RSS_ENABLED:
            logger.info("RSS 面板统一挂载模式开启（/rss）")
        
        # 发送欢迎消息
        if send_welcome_message:
            await send_welcome_message(self.bot_client)

