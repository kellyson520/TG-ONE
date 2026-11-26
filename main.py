"""
Telegram 转发机器人主程序
TG ONE Refactored Entry Point
"""
import asyncio
import os
import time
import platform
import signal
import sys

# [FIX] SQLite 的临时文件（PRAGMA temp_store=FILE）默认落在 TMPDIR/系统 /tmp。
# 这台机器 /tmp 是 100MB 的 tmpfs，而热词表去重重建要对 60 万行做 GROUP BY+排序，
# 一溢写就 SQLITE_FULL —— 日志里的 "database or disk is full"，也是
# uq_hot_period_word 从来没建成、每次开机都白跑一遍全表重建的原因。
# 必须在任何 sqlite 连接建立之前设置。
_APP_ROOT = os.path.dirname(os.path.abspath(__file__))
_DATA_TEMP = os.path.join(_APP_ROOT, "data", "temp")
_SQLITE_TMP = os.path.join(_DATA_TEMP, "sqlite")
try:
    os.makedirs(_SQLITE_TMP, exist_ok=True)
    os.environ["SQLITE_TMPDIR"] = _SQLITE_TMP
    os.environ.setdefault("TMPDIR", _DATA_TEMP)
except Exception:  # 目录不可写时不要拦住启动，交给 SQLite 自己报错
    pass



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
            
    # 给优雅关闭一个总的硬超时 (40秒)，防止底层库死锁
    try:
        # 给优雅关闭一个总的硬超时 (40秒)，防止底层库死锁
        await asyncio.wait_for(lifecycle.stop(), timeout=40.0)
    except asyncio.TimeoutError:
        logger.critical("🚨 [FATAL] 优雅关闭严重超时 (40s)，强行终止进程！")
        os._exit(lifecycle.exit_code or 10)
    # 6. 返回退出码
    exit_code = lifecycle.exit_code
    logger.info(f"主程序退出, 退出码: {exit_code}")
    
    # 如果是更新，强行调用 os._exit 以确保守护进程能即时捕获，防止 asyncio.run 清理挂起
    if exit_code == 10:
        logger.warning("🚀 正在通过 os._exit(10) 强制退出以触发系统更新...")
        os._exit(10)
        
    return exit_code

if __name__ == '__main__':
    # 1. 创建并设置事件循环
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    # 设置自定义异常处理器以减少退出时的噪音
    def _loop_exception_handler(loop, context):
        msg = context.get("message")
        exception = context.get("exception")
        
        # 常见退出噪音：任务被销毁、事件循环已关闭、取消异常、传输错误
        noise_keywords = ["Task was destroyed", "Event loop is closed", "CancelledError", "Fatal error on transport"]
        
        is_noise = False
        if msg and any(x in msg for x in noise_keywords):
            is_noise = True
        elif exception and any(x in str(exception) for x in noise_keywords):
            is_noise = True
            
        if is_noise:
            # 退出阶段只记录为 debug，不作为 error 记录
            logger.debug(f"已忽略退出阶段的事件循环噪音: {context}")
            return
            
        logger.error(f"事件循环未处理异常: {context}")
        
    loop.set_exception_handler(_loop_exception_handler)
    
    exit_code = 0
    try:
        # 2. 运行主函数
        exit_code = loop.run_until_complete(main())
    except KeyboardInterrupt:
        logger.info("主程序捕获到键盘中断")
    except SystemExit as e:
        exit_code = e.code
    except Exception as e:
        logger.critical(f"系统遭遇致命错误: {e}", exc_info=True)
        exit_code = 1
    finally:
        # 3. 完美退出序列 (Perfect Teardown)
        start_time = asyncio.get_event_loop().time()
        logger.info("开始执行完美退出序列 (Perfect Teardown Sequence)...")
        
        try:
            # Step A: 取消所有未完成的任务 (Task Registry)
            logger.info("[Shutdown 1/4] 正在清理后台任务注册表...")
            from services.exception_handler import exception_handler
            loop.run_until_complete(exception_handler.cancel_all_managed_tasks(timeout=5.0))
            
            # Step B: 销毁异步生成器
            logger.info("[Shutdown 2/4] 正在清理异步生成器...")
            loop.run_until_complete(loop.shutdown_asyncgens())
            
            # Step C: 关闭默认执行器 (线程池)
            logger.info("[Shutdown 3/4] 正在关闭系统执行器线程池...")
            loop.run_until_complete(loop.shutdown_default_executor())
            
            # Step D: 最后的沉淀期 (Settling Period)
            # 给一些仍在后台或传输层排队的回调一个执行机会
            logger.info("[Shutdown 4/5] 正在等待残留回调沉淀...")
            loop.run_until_complete(asyncio.sleep(0.2))
            
            # Step E: 关闭循环
            logger.info("[Shutdown 5/5] 正在释放事件循环资源...")
            loop.close()
            
        except Exception as e:
            print(f"退出序列中发生异常 (已忽略): {e}")
            
        end_time = time.time()
        duration = end_time - start_time
        logger.info(f"✨ 完美退出序列执行完毕, 耗时: {duration:.2f}s")
            
        if os.getenv("DEBUG_SHUTDOWN_HANG") == "1":
            logger.warning("🛠️ [DEBUG] 检测到 DEBUG_SHUTDOWN_HANG=1，系统将进入挂起等待以便人工调试...")
            import time
            while True:
                time.sleep(1)
                
        logger.info(f"进程即将退出, 退出码: {exit_code}")
        sys.exit(exit_code or 0)
