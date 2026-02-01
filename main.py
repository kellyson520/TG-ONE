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
    except ImportError:
        pass

from telethon import TelegramClient
from core.config import settings
from core.logging import setup_logging

# 2. 初始日志系统
root_logger = setup_logging()

# 3. 安装日志推送 (可选)
try:
    from services.network.log_push import install_log_push_handlers
    install_log_push_handlers(root_logger)
except ImportError:
    pass

from core.logging import get_logger
logger = get_logger(__name__)

# 2. 初始化全局客户端 (保持兼容性)
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

async def main():
    """主入口函数"""
    # 3. 运行引导程序 (使用统一生命周期管理器)
    from core.lifecycle import get_lifecycle
    lifecycle = get_lifecycle(user_client, bot_client)
    
    try:
        await lifecycle.start()
    except Exception as e:
        logger.critical(f"系统启动失败: {e}", exc_info=True)
        # 尝试优雅关闭
        await lifecycle.stop()
        sys.exit(1)
        
    # 4. 保持运行
    logger.info(f"系统主循环已启动 (PID: {os.getpid()}) - 按 Ctrl+C 停止")
    
    # 等待关闭信号
    stop_event = asyncio.Event()
    
    # 注册信号处理
    def handle_signal():
        if not stop_event.is_set():
            logger.info("Received stop signal, initiating shutdown...")
            stop_event.set()
    
    try:
        loop = asyncio.get_running_loop()
        if platform.system() != 'Windows':
            for sig in (signal.SIGINT, signal.SIGTERM):
                loop.add_signal_handler(sig, handle_signal)
    except NotImplementedError:
        pass

    # 主循环
    try:
        while not stop_event.is_set():
            await asyncio.sleep(1)
    except asyncio.CancelledError:
        pass
    except KeyboardInterrupt:
        logger.info("KeyboardInterrupt in loop")
        handle_signal()
            
    # 5. 优雅关闭
    logger.info("正在执行主程序退出流程...")
    await lifecycle.stop()

if __name__ == '__main__':
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        # 捕获最外层的 KeyboardInterrupt (如 Windows 下的 Ctrl+C)
        pass
    except Exception as e:
        logger.critical(f"Fatal startup error: {e}", exc_info=True)
