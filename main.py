"""
Telegram 转发机器人主程序
TG ONE Refactored Entry Point
"""
import asyncio
import os
import platform
import signal
import sys

# 1. 设置事件循环策略 (必须在最前面)
if platform.system() == 'Windows':
    # Windows 下使用 SelectorEventLoopPolicy 以避免 ProactorEventLoop 的某些问题
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
else:
    try:
        import uvloop
        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError as e:
        import logging
        logging.getLogger(__name__).debug(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')

from telethon import TelegramClient
from core.config import settings
from core.logging import setup_logging

# 2. 初始日志系统
root_logger = setup_logging()

# 3. 安装日志推送 (可选)
try:
    from services.network.log_push import install_log_push_handlers
    install_log_push_handlers(root_logger)
except ImportError as e:
    import logging
    logging.getLogger(__name__).debug(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')

from core.logging import get_logger
logger = get_logger(__name__)

# 2. 初始化助手 (不再在此处初始化以避免 Loop 冲突)

async def main():
    """主入口函数"""
    # --- 1. 升级后置处理 (关键插入点) ---
    # 在加载任何 ORM 模型或启动 Web 服务前执行
    # 确保数据库 Schema 与新代码匹配，并启动健康观察期
    from services.update_service import update_service
    await update_service.verify_update_health()    # 检查历史故障并尝试自愈
    await update_service.post_update_bootstrap()   # 执行迁移等任务
    
    # 3. 初始化全局客户端 (在异步环境内初始化，确保绑定正确的 Event Loop)
    try:
        user_client = TelegramClient(
            str(settings.SESSION_DIR / "user"), 
            settings.API_ID, 
            settings.API_HASH
        )
        
        bot_client = TelegramClient(
            str(settings.SESSION_DIR / "bot"), 
            settings.API_ID, 
            settings.API_HASH
        )
    except Exception as e:
        logger.critical(f"客户端初始化失败: {e}。请检查 API_ID/API_HASH/SESSION_DIR 配置。")
        sys.exit(1)

    # 4. 运行会话向导检测 (新增)
    from core.session_wizard import session_wizard
    if not await session_wizard.ensure_session():
        logger.critical("❌ 会话文件检查不通过或向导中止。系统将尝试继续启动，但可能会因为未认证而失败。")

    # 5. 运行引导程序 (使用统一生命周期管理器)
    from core.lifecycle import get_lifecycle
    lifecycle = get_lifecycle(user_client, bot_client)
    
    try:
        await lifecycle.start()
    except Exception as e:
        logger.critical(f"系统启动失败: {e}", exc_info=True)
        # 注意：lifecycle.start() 内部在捕获严重异常时已调用过 stop()，此处不再重复调用
        sys.exit(1)
        
    # 4. 保持运行
    logger.info(f"系统主循环已启动 (PID: {os.getpid()}) - 按 Ctrl+C 停止")
    
    # 注册信号处理
    def handle_signal():
        if not lifecycle.stop_event.is_set():
            logger.info("Received stop signal, initiating shutdown...")
            lifecycle.shutdown(0)
    
    try:
        loop = asyncio.get_running_loop()
        if platform.system() != 'Windows':
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, handle_signal)
    except NotImplementedError as e:
        logger.debug(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')

    # 主循环
    try:
        await lifecycle.stop_event.wait()
    except asyncio.CancelledError as e:
        logger.debug(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt in loop")
        handle_signal()
            
    # 5. 优雅关闭
    logger.info("正在执行主程序退出流程...")
    try:
        # 给优雅关闭一个总的硬超时 (40秒)，防止底层库死锁
        await asyncio.wait_for(lifecycle.stop(), timeout=40.0)
    except asyncio.TimeoutError:
        logger.critical("🚨 [FATAL] 优雅关闭严重超时 (40s)，强行终止进程！")
        import os
        os._exit(lifecycle.exit_code or 10)
    except Exception as e:
        logger.error(f"关闭过程中发生错误: {e}")
    
    # 6. 返回退出码
    return lifecycle.exit_code

if __name__ == '__main__':
    try:
        # 获取由 main() 返回的退出码
        exit_code = asyncio.run(main())
        sys.exit(exit_code or 0)
    except KeyboardInterrupt:
        # 捕获最外层的 KeyboardInterrupt (如 Windows 下的 Ctrl+C)
        sys.exit(0)
    except SystemExit as e:
        # 如果 main() 或其调用的函数直接调用了 sys.exit
        sys.exit(e.code)
    except Exception as e:
        logger.critical(f"Fatal startup error: {e}", exc_info=True)
        sys.exit(1)
