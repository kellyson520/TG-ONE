from telethon import TelegramClient, types
from telethon.tl.types import BotCommand
from telethon.tl.functions.bots import SetBotCommandsRequest
from models.models import init_db
from core.config import settings
from listeners import setup_listeners
from core.container import container
import os
import asyncio
import logging
import multiprocessing
import gc
import platform
import hashlib
# import json  # Replaced by optimized wrapper
from utils.core import json_ops as json
# 尝试启用uvloop以提高性能
if platform.system() != 'Windows' and os.environ.get('DISABLE_UVLOOP', '').lower() != 'true':
    try:
        import uvloop
        # 使用更安全的方式启用uvloop，只在异步上下文中生效
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
        logging.getLogger(__name__).info("已设置uvloop高性能事件循环策略")
    except ImportError:
        logging.getLogger(__name__).info("未安装uvloop，使用默认事件循环")
elif os.environ.get('DISABLE_UVLOOP', '').lower() == 'true':
    logging.getLogger(__name__).info("uvloop已通过环境变量禁用")


from scheduler.summary_scheduler import SummaryScheduler
# 已移除废弃的ChatUpdater - 使用OptimizedChatUpdater替代
from handlers.bot_handler import send_welcome_message
 
from utils.core.log_config import setup_logging
from utils.core.constants import CLEAR_TEMP_ON_START
from scheduler.db_archive_job import archive_once
from utils.helpers.metrics import set_ready, set_health, ARCHIVE_RUN_TOTAL, ARCHIVE_RUN_SECONDS
import signal
from services.system_service import guard_service
# 新增1：目录守护
import threading, time, pathlib
# 新增2：内存守卫
from utils.helpers.tombstone import tombstone
import psutil
# 从settings中获取临时文件清理阈值，默认5 GiB
TEMP_GUARD_MAX   = settings.TEMP_GUARD_MAX
TEMP_GUARD_PATH  = settings.TEMP_DIR  # 使用 settings 中的 TEMP_DIR 配置

# 应用 UVLOOP 兼容性补丁
from core.compatibility import apply_uvloop_patch
apply_uvloop_patch()

# 设置Docker日志的默认配置，如果docker-compose.yml中没有配置日志选项将使用这些值
os.environ.setdefault('DOCKER_LOG_MAX_SIZE', '10m')
os.environ.setdefault('DOCKER_LOG_MAX_FILE', '3')

# 设置日志配置
setup_logging()

logger = logging.getLogger(__name__)
# 启动时输出一次日志级别自检，便于诊断环境变量与实际级别
try:
    root_lvl = logging.getLevelName(logging.getLogger().level)
    logger.info(
        f"Logging check: effective={root_lvl}, LOG_LEVEL_env={settings.LOG_LEVEL}, "
        f"DRY_RUN_LOG_LEVEL={settings.DRY_RUN_LOG_LEVEL}, TELETHON_LOG_LEVEL={settings.TELETHON_LOG_LEVEL}"
    )
except Exception:
    pass

 

# 从设置获取配置
api_id = settings.API_ID
api_hash = settings.API_HASH
bot_token = settings.BOT_TOKEN
phone_number = settings.PHONE_NUMBER

aps_scheduler = None
web_server_instance = None


# 创建客户端
# 使用 settings 中的路径配置
settings.SESSION_DIR.mkdir(parents=True, exist_ok=True)
settings.TEMP_DIR.mkdir(parents=True, exist_ok=True)
try:
    from utils.network.telethon_session_fix import ensure_sessions_ok
    ensure_sessions_ok([str(settings.SESSION_DIR / 'user'), str(settings.SESSION_DIR / 'bot')])
except Exception:
    pass


# 清空临时文件夹 (同步版本，供线程池调用)
def _clear_temp_dir_sync():
    """同步版本的临时目录清理 (在线程池中执行)"""
    count = 0
    for file in os.listdir(settings.TEMP_DIR):
        try:
            file_path = os.path.join(settings.TEMP_DIR, file)
            if os.path.isfile(file_path):
                os.remove(file_path)
                count += 1
        except Exception:
            pass
    return count

async def clear_temp_dir_async():
    """异步版本的临时目录清理 (Phase H.4: 避免阻塞事件循环)"""
    try:
        count = await asyncio.to_thread(_clear_temp_dir_sync)
        if count > 0:
            logger.info(f"已清理 {count} 个临时文件")
        return count
    except Exception as e:
        logger.warning(f"清理临时目录失败: {e}")
        return 0

# 兼容旧代码的同步接口
def clear_temp_dir():
    _clear_temp_dir_sync()


settings.validate_required()

# 启动时可选清空临时目录 (同步执行，因为此时事件循环可能未就绪)
if CLEAR_TEMP_ON_START:
    try:
        _clear_temp_dir_sync()
    except Exception:
        pass

# 创建客户端 - 修复uvloop事件循环问题
# 在初始化TelegramClient之前，确保主线程有一个事件循环
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
user_client = TelegramClient('./sessions/user', api_id, api_hash)
bot_client = TelegramClient('./sessions/bot', api_id, api_hash)

# 数据库健康检查
logger.info("执行数据库健康检查...")
try:
    from scripts.database_health_check import DatabaseHealthChecker
    health_checker = DatabaseHealthChecker()
    if not health_checker.auto_fix_if_needed():
        logger.error("数据库健康检查失败，程序启动中止")
        exit(1)
    logger.info("数据库健康检查通过")
except Exception as e:
    logger.error(f"数据库健康检查异常: {e}")
    logger.warning("跳过健康检查，继续启动...")





async def start_clients():
    # 首先检查并修复数据库权限问题
    logger.info("检查数据库权限...")
    try:
        from utils.db.database_manager import ensure_database_permissions
        # 使用线程池执行同步操作，避免阻塞事件循环
        if not await asyncio.to_thread(ensure_database_permissions):
            logger.warning("数据库权限检查发现问题，但系统将继续启动")
        else:
            logger.info("数据库权限检查通过")
    except Exception as e:
        logger.error(f"数据库权限检查失败: {e}")
        logger.warning("跳过权限检查，继续启动...")

    # [Fix] 确保数据库表结构已初始化/迁移
    try:
        from core.db_init import init_db_tables
        logger.info("正在初始化/迁移数据库表...")
        await init_db_tables(settings.DATABASE_URL)
        logger.info("数据库表初始化完成")
    except Exception as e:
        logger.error(f"数据库初始化失败: {e}")
        # 不中断启动，后续服务可能会重试或失败
    
    # 初始化全局变量
    global scheduler, chat_updater, aps_scheduler
    
    # 加载动态配置
    logger.info("加载动态配置...")
    await settings.load_dynamic_config()
    logger.info("动态配置加载完成")
    
    # [Refactor Fix] 初始化 StateManager
    # 替换为通过 Container 或 Service 初始化，旧 managers.state_manager 已废弃
    try:
        # 尝试通过容器或服务层初始化会话管理
        # 假设 session_service 已在 container 中注册或自动管理
        logger.info("Session/State 管理器准备就绪 (由 Container 管理)")
    except Exception as e:
        logger.error(f"Session 管理器初始化失败: {e}")

    try:
        # 启动用户客户端
        await user_client.start(phone=phone_number)
        me_user = await user_client.get_me()
        print(f'用户客户端已启动: {me_user.first_name} (@{me_user.username})')

        # 启动机器人客户端
        await bot_client.start(bot_token=bot_token)
        me_bot = await bot_client.get_me()
        print(f'机器人客户端已启动: {me_bot.first_name} (@{me_bot.username})')

        # 初始化API优化器
        try:
            from utils.network.api_optimization import initialize_api_optimizer
            initialize_api_optimizer(user_client)
            logger.info("API优化器初始化完成")
        except Exception as e:
            logger.error(f"API优化器初始化失败: {e}")
            
        # 初始化实体解析器
        try:
            from utils.helpers.entity_optimization import initialize_entity_resolver
            initialize_entity_resolver(user_client)
            logger.info("实体解析器初始化完成")
        except Exception as e:
            logger.error(f"实体解析器初始化失败: {e}")

        # 设置消息监听器
        await setup_listeners(user_client, bot_client)
        try:
            from utils.network.bot_heartbeat import start_heartbeat, update_heartbeat
            asyncio.create_task(start_heartbeat(user_client, bot_client))
            update_heartbeat("running", source="init")
        except Exception:
            pass
        
        # 初始化容器与依赖注入
        container.init_with_client(user_client, bot_client)
        
        # 启动所有服务
        await container.start_all()
        logger.info("业务Worker已启动")
        
        # 注册优雅关闭清理回调
        from core.shutdown import get_shutdown_coordinator
        coordinator = get_shutdown_coordinator()
        
        # Priority 0: 停止接收新请求
        async def _stop_accepting_requests():
            """标记系统为非就绪状态，停止接收新请求"""
            set_ready(False)
            logger.info("系统已标记为非就绪状态")
        
        coordinator.register_cleanup(
            callback=_stop_accepting_requests,
            priority=0,
            timeout=2.0,
            name="stop_accepting_requests"
        )

        
        # Priority 1: 停止容器服务
        coordinator.register_cleanup(
            callback=container.shutdown,
            priority=1,
            timeout=10.0,
            name="container_shutdown"
        )
        
        # Priority 2: 断开 Telegram 客户端
        async def _disconnect_clients():
            if user_client and user_client.is_connected():
                await user_client.disconnect()
            if bot_client and bot_client.is_connected():
                await bot_client.disconnect()
        
        coordinator.register_cleanup(
            callback=_disconnect_clients,
            priority=2,
            timeout=5.0,
            name="telegram_clients"
        )
        
        # Priority 3: 停止守护服务
        async def _stop_guards():
            guard_service.stop_guards()
            await asyncio.sleep(0.1)  # 给守护线程时间退出
        
        coordinator.register_cleanup(
            callback=_stop_guards,
            priority=3,
            timeout=2.0,
            name="guard_service"
        )
        
        logger.info("✓ 优雅关闭清理回调已注册")
        
        
        # 启用事件驱动监控优化
        try:
            from utils.helpers.event_optimization import get_event_optimizer, get_event_monitor
            event_optimizer = get_event_optimizer()
            event_monitor = get_event_monitor()
            
            # 设置优化的事件监听器
            await event_optimizer.setup_optimized_listeners(user_client, bot_client)
            
            # 启动事件驱动监控
            await event_monitor.start_monitoring(user_client)
            
            logger.info("事件驱动监控优化启用成功")
        except Exception as e:
            logger.error(f"事件驱动监控优化启用失败: {e}")

        # 注册命令
        await register_bot_commands(bot_client)
        
        # [Refactor Fix] 移除旧的 managers 初始化代码
        # 所有的管理器逻辑 (MediaGroup, UnifiedForward, Deduplication) 
        # 现在应当由 container 和 services 自动处理，或者已经迁移到了 utils/processing
        logger.info("统一管理器初始化完成 (通过 Service 容器)")
        try:
            from scheduler.aps_jobs import setup_apscheduler
            aps_scheduler = setup_apscheduler()
        except Exception:
            aps_scheduler = None
        if aps_scheduler is None:
            async def _archive_cron():
                import asyncio
                import datetime
                times = settings.CLEANUP_CRON_TIMES
                while True:
                    try:
                        now = datetime.datetime.now()
                        deltas = []
                        for t in times:
                            try:
                                hh, mm = [int(x) for x in t.split(':')]
                            except Exception:
                                continue
                            target = now.replace(hour=hh, minute=mm, second=0, microsecond=0)
                            if target <= now:
                                target += datetime.timedelta(days=1)
                            deltas.append((target - now).total_seconds())
                        sleep_s = min(deltas) if deltas else 86400
                        await asyncio.sleep(sleep_s)
                        loop = asyncio.get_event_loop()
                        if settings.AUTO_ARCHIVE_ENABLED:
                            start = loop.time()
                            status = 'success'
                            try:
                                await loop.run_in_executor(None, archive_once)
                            except Exception:
                                status = 'error'
                            finally:
                                duration = loop.time() - start
                                ARCHIVE_RUN_SECONDS.observe(duration)
                                ARCHIVE_RUN_TOTAL.labels(status=status).inc()
                        if settings.AUTO_GC_ENABLED:
                            from scheduler.db_archive_job import garbage_collect_once
                            try:
                                await loop.run_in_executor(None, garbage_collect_once)
                            except Exception:
                                pass
                    except Exception:
                        pass
            try:
                asyncio.create_task(_archive_cron())
            except Exception:
                pass
            async def _compact_cron():
                import asyncio
                import datetime
                from utils.db.archive_store import compact_small_files
                while True:
                    try:
                        if not settings.ARCHIVE_COMPACT_ENABLED:
                            await asyncio.sleep(3600)
                            continue
                        now = datetime.datetime.now()
                        target = now.replace(hour=4, minute=30, second=0, microsecond=0)
                        if target <= now:
                            target += datetime.timedelta(days=1)
                        await asyncio.sleep((target - now).total_seconds())
                        loop = asyncio.get_event_loop()
                        await loop.run_in_executor(None, compact_small_files, 'media_signatures', settings.ARCHIVE_COMPACT_MIN_FILES)
                    except Exception:
                        pass
            try:
                asyncio.create_task(_compact_cron())
            except Exception:
                pass

            async def _cleanup_temp_cron():
                """定期清理临时文件"""
                import asyncio
                while True:
                    try:
                        # 每小时执行一次
                        await asyncio.sleep(3600)
                        logger.info("开始定时清理临时目录...")
                        count = await clear_temp_dir_async()
                        logger.info(f"定时清理完成，删除了 {count} 个文件")
                    except Exception as e:
                        logger.error(f"定时清理临时目录失败: {e}")
                        await asyncio.sleep(60) # 出错后等待一分钟
            try:
                asyncio.create_task(_cleanup_temp_cron())
            except Exception:
                pass
        
        # 聊天更新器已在上面使用OptimizedChatUpdater启动

        # RSS 面板已在统一 Web 服务中按需挂载到 /rss，无需单独进程
        if settings.RSS_ENABLED:
            logger.info("RSS 面板统一挂载模式开启（/rss）")
        else:
            logger.info("RSS 面板未启用")

        # 发送欢迎消息
        await send_welcome_message(bot_client)

        # 等待两个客户端都断开连接 或 收到停止信号
        set_ready(True)
        logger.info("🚀 System Online. Press Ctrl+C to stop.")
        
        # 等待停止信号 或 客户端断开
        await asyncio.wait(
            [
                asyncio.create_task(user_client.run_until_disconnected()),
                asyncio.create_task(bot_client.run_until_disconnected())
            ],
            return_when=asyncio.FIRST_COMPLETED
        )
    finally:
        # [Refactor Fix] 移除旧 managers 的 cleanup
        # StateManager, MediaGroupManager, ForwardManager, DeduplicationManager 的清理
        # 应当由 container.shutdown() 统一处理
        
        # 停止 aps_scheduler
        try:
            if aps_scheduler:
                aps_scheduler.shutdown(wait=False)
        except Exception:
            pass
        
        # 如果 RSS 服务在运行，停止它
        if 'rss_process' in locals() and rss_process.is_alive():
            rss_process.terminate()
            rss_process.join()
        
        # 执行优雅关闭 - 所有服务由 container 统一管理
        await container.shutdown()


async def register_bot_commands(bot):
    """注册机器人命令 (Optimized with Hash Check)"""
    
    commands = [
        # 基础命令
        BotCommand(
            command='start',
            description='开始使用'
        ),
        BotCommand(
            command='help',
            description='查看帮助'
        ),
        # 绑定和设置
        BotCommand(
            command='bind',
            description='绑定源聊天'
        ),
        BotCommand(
            command='settings',
            description='管理转发规则（新菜单）'
        ),

        BotCommand(
            command='switch',
            description='切换当前需要设置的聊天规则'
        ),
        # 关键字管理
        BotCommand(
            command='add',
            description='添加关键字'
        ),
        BotCommand(
            command='add_regex',
            description='添加正则关键字'
        ),
        BotCommand(
            command='add_all',
            description='添加普通关键字到所有规则'
        ),
        BotCommand(
            command='add_regex_all',
            description='添加正则表达式到所有规则'
        ),
        BotCommand(
            command='list_keyword',
            description='列出所有关键字'
        ),
        BotCommand(
            command='remove_keyword',
            description='删除关键字'
        ),
        BotCommand(
            command='remove_keyword_by_id',
            description='按ID删除关键字'
        ),
        BotCommand(
            command='remove_all_keyword',
            description='删除当前频道绑定的所有规则的指定关键字'
        ),
        # 替换规则管理
        BotCommand(
            command='replace',
            description='添加替换规则'
        ),
        BotCommand(
            command='replace_all',
            description='添加替换规则到所有规则'
        ),
        BotCommand(
            command='list_replace',
            description='列出所有替换规则'
        ),
        BotCommand(
            command='remove_replace',
            description='删除替换规则'
        ),
        # 导入导出功能
        BotCommand(
            command='export_keyword',
            description='导出当前规则的关键字'
        ),
        BotCommand(
            command='export_replace',
            description='导出当前规则的替换规则'
        ),
        BotCommand(
            command='import_keyword',
            description='导入普通关键字'
        ),
        BotCommand(
            command='import_regex_keyword',
            description='导入正则表达式关键字'
        ),
        BotCommand(
            command='import_replace',
            description='导入替换规则'
        ),
        # UFB相关功能
        BotCommand(
            command='ufb_bind',
            description='绑定ufb域名'
        ),
        BotCommand(
            command='ufb_unbind',
            description='解绑ufb域名'
        ),
        BotCommand(
            command='ufb_item_change',
            description='切换ufb同步配置类型'
        ),
        BotCommand(
            command='clear_all_keywords',
            description='清除当前规则的所有关键字'
        ),
        BotCommand(
            command='clear_all_keywords_regex',
            description='清除当前规则的所有正则关键字'
        ),
        BotCommand(
            command='clear_all_replace',
            description='清除当前规则的所有替换规则'
        ),
        BotCommand(
            command='copy_keywords',
            description='复制参数规则的关键字到当前规则'
        ),
        BotCommand(
            command='copy_keywords_regex',
            description='复制参数规则的正则关键字到当前规则'
        ),
        BotCommand(
            command='copy_replace',
            description='复制参数规则的替换规则到当前规则'
        ),
        BotCommand(
            command='copy_rule',
            description='复制参数规则到当前规则'
        ),
        BotCommand(
            command='changelog',
            description='查看更新日志'
        ),
        BotCommand(
            command='list_rule',
            description='列出所有转发规则'
        ),
        BotCommand(
            command='delete_rule',
            description='删除转发规则'
        ),
        # 增强搜索功能
        BotCommand(
            command='search',
            description='智能搜索（增强版）'
        ),
        BotCommand(
            command='search_bound',
            description='搜索已绑定的群组'
        ),
        BotCommand(
            command='search_public',
            description='搜索公开群组'
        ),
        BotCommand(
            command='search_all',
            description='搜索所有群组（已绑定+公开）'
        ),
        BotCommand(
            command='delete_rss_user',
            description='删除RSS用户'
        ),
        # 去重相关
        BotCommand(
            command='dedup',
            description='切换当前规则去重开关'
        ),
        BotCommand(
            command='dedup_scan',
            description='扫描目标会话重复媒体'
        ),
        # 数据库管理
        BotCommand(
            command='db_info',
            description='查看数据库信息'
        ),
        BotCommand(
            command='db_backup',
            description='备份数据库'
        ),
        BotCommand(
            command='db_optimize',
            description='优化数据库'
        ),
        BotCommand(
            command='db_health',
            description='数据库健康检查'
        ),
        # 视频缓存管理
        BotCommand(
            command='video_cache_stats',
            description='查看视频哈希缓存统计'
        ),
        BotCommand(
            command='video_cache_clear',
            description='清理视频哈希缓存'
        ),
        # 系统管理
        BotCommand(
            command='system_status',
            description='查看系统状态'
        ),
        BotCommand(
            command='admin',
            description='管理面板'
        ),


        # BotCommand(
        #     command='clear_all',
        #     description='慎用！清空所有数据'
        # ),
    ]

    # 计算命令哈希
    try:
        cmd_data = json.dumps([{"c": c.command, "d": c.description} for c in commands], sort_keys=True)
        current_hash = hashlib.md5(cmd_data.encode()).hexdigest()
        
        hash_file = settings.BASE_DIR / 'data' / 'bot_commands.hash'
        if hash_file.exists():
            with open(hash_file, 'r') as f:
                stored_hash = f.read().strip()
            if stored_hash == current_hash:
                logger.debug('Bot commands unchanged, skipping registration.')
                return
    except Exception as e:
        logger.warning(f"Failed to check command hash: {e}")
        current_hash = None
        hash_file = None

    try:
        result = await bot(SetBotCommandsRequest(
            scope=types.BotCommandScopeDefault(),
            lang_code='',  # 空字符串表示默认语言
            commands=commands
        ))
        if result:
            logger.info('已成功注册机器人命令')
            # 保存新哈希
            if hash_file and current_hash:
                try:
                    hash_file.parent.mkdir(exist_ok=True, parents=True)
                    with open(hash_file, 'w') as f:
                        f.write(current_hash)
                except Exception:
                    pass
        else:
            logger.error('注册机器人命令失败')
    except Exception as e:
        logger.error(f'注册机器人命令时出错: {str(e)}')


def _install_signal_handlers(loop: asyncio.AbstractEventLoop):
    """
    安装信号处理器，使用 ShutdownCoordinator 进行优雅关闭
    """
    from core.shutdown import get_shutdown_coordinator
    
    stop_event = asyncio.Event()
    coordinator = get_shutdown_coordinator()

    async def _shutdown_all():
        """优雅关闭所有组件 (通过 ShutdownCoordinator)"""
        logger.info("收到停止信号，触发优雅关闭协调器...")
        
        # 使用协调器执行所有注册的清理任务
        success = await coordinator.shutdown()
        
        if success:
            logger.info("✓ 优雅关闭成功完成")
            import sys
            sys.exit(0)
        else:
            logger.warning("✗ 优雅关闭部分失败，强制退出")
            import sys
            sys.exit(1)

    def _signal_handler(sig, frame):
        logger.info(f"收到信号 {sig}，开始优雅关停…")
        loop.call_soon_threadsafe(lambda: asyncio.create_task(_shutdown_all()))

    for s in (signal.SIGINT, signal.SIGTERM):
        try:
            signal.signal(s, _signal_handler)
        except Exception:
            pass
    return stop_event


if __name__ == '__main__':
    # 启动系统守护线程
    guard_service.start_guards()

    # 原有代码不动
    loop = asyncio.get_event_loop()
    
    # 存储所有需要在关闭时取消的任务
    background_tasks = []

    # 启动异步配置守护任务
    background_tasks.append(loop.create_task(guard_service.start_config_guard()))
    # 启动内存维护守护任务 (Phase H.4)
    background_tasks.append(loop.create_task(guard_service.start_memory_guard()))
    # 启动数据库健康检查守护任务 (Phase H.5)
    background_tasks.append(loop.create_task(guard_service.start_db_health_guard()))

    # 导入 FastAPI 应用
    from web_admin.fastapi_app import app as fastapi_app
    import uvicorn

    async def start_web_server(host: str, port: int):
        """
        在当前 asyncio 循环中启动 Uvicorn 服务器
        """
        global web_server_instance
        config = uvicorn.Config(
            app=fastapi_app,
            host=host,
            port=port,
            log_level="info",
            loop="asyncio"
        )
        server = uvicorn.Server(config)
        web_server_instance = server
        
        # 注册 Web 服务器清理回调
        from core.shutdown import get_shutdown_coordinator
        coordinator = get_shutdown_coordinator()
        
        async def _stop_web_server():
            """停止 Web 服务器"""
            if web_server_instance:
                logger.info("正在停止 Web 服务器...")
                web_server_instance.should_exit = True
                # 等待服务器完全停止
                await asyncio.sleep(0.5)
        
        coordinator.register_cleanup(
            callback=_stop_web_server,
            priority=0,  # 最高优先级，先停止接收请求
            timeout=2.0,
            name="web_server"
        )
        
        # 将 uvicorn 的运行作为一个 Task
        logger.info(f"正在启动 Web Admin (FastAPI) 于 http://{host}:{port}")
        await server.serve()



    _install_signal_handlers(loop)

    # 1. Telegram Clients 任务
    client_task = loop.create_task(start_clients())
    background_tasks.append(client_task)

    # 2. Web Server 任务 (同进程启动)
    web_task = None
    if settings.WEB_ENABLED:
        web_host = settings.WEB_HOST
        web_port = settings.WEB_PORT
        web_task = loop.create_task(start_web_server(web_host, web_port))
        background_tasks.append(web_task)
    else:
        logger.info("Web 服务已禁用")

    # 主循环阻塞点
    try:
        # 使用 wait 而不是 gather，这样我们可以更好地控制退出
        done, pending = loop.run_until_complete(asyncio.wait(background_tasks, return_when=asyncio.FIRST_COMPLETED))
        for task in done:
            if task.exception():
                logger.error(f"Task failed with exception: {task.exception()}")
                # 打印堆栈以便调试
                import traceback
                traceback.print_exception(type(task.exception()), task.exception(), task.exception().__traceback__)
            else:
                logger.info(f"Task completed successfully: {task}")
    except KeyboardInterrupt:
        print("正在关闭...")
    except Exception as e:
        # 防护：确保 e 转为字符串，避免 logger 内部因 e 对象异常而报错
        err_msg = str(e) if e else "Unknown error"
        logger.error(f"主进程发生异常: {err_msg}")
    finally:
        # 优雅关闭逻辑
        logger.info("系统进入最后关停阶段...")
        set_ready(False)
        
        # 停止守护信号
        guard_service.stop_guards()
        
        # 取收并取消所有任务
        pending = [t for t in background_tasks if not t.done()]
        if pending:
            logger.info(f"正在清理 {len(pending)} 个待处理后台任务...")
            for task in pending:
                task.cancel()
            
            # 允许任务执行清理
            try:
                loop.run_until_complete(asyncio.wait(pending, timeout=3.0))
            except asyncio.CancelledError:
                # 这是正常的任务取消行为
                logger.debug("后台任务已取消")
            except Exception as e:
                logger.warning(f"清理后台任务时出现异常: {e}")
        
        # 显式关闭循环
        try:
            loop.run_until_complete(loop.shutdown_asyncgens())
            loop.close()
        except Exception as e:
            print(f"关闭事件循环时出错: {e}")
        
        logger.info("✅ 系统已退出")
