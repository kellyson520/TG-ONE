import logging
import asyncio


class WebSocketLogHandler(logging.Handler):
    """
    一个将日志消息广播到 WebSocket 的日志处理器。
    """
    def __init__(self, level=logging.INFO):
        super().__init__(level=level)
        # 延迟获取 broadcast_log，避免循环导入
        self._broadcast_func = None

    def emit(self, record: logging.LogRecord):
        try:
            if self._broadcast_func is None:
                from web_admin.routers.websocket_router import broadcast_log
                self._broadcast_func = broadcast_log

            msg = self.format(record)
            
            # 检查是否有正在运行的事件循环
            try:
                loop = asyncio.get_running_loop()
                if loop and loop.is_running():
                    # 在后台创建任务发送广播，不阻塞日志记录
                    loop.create_task(self._broadcast_func(
                        level=record.levelname,
                        message=msg,
                        module=record.name
                    ))
            except RuntimeError:
                # 没有运行中的 loop，忽略（通常在启动/关闭阶段）
                pass
        except Exception:
            # 日志处理器本身不应抛出异常干扰主逻辑
            pass

def install_websocket_log_handler():
    """安装 WebSocket 日志显示到 root logger"""
    root_logger = logging.getLogger()
    
    # 检查是否已安装
    for h in root_logger.handlers:
        if isinstance(h, WebSocketLogHandler):
            return
            
    handler = WebSocketLogHandler()
    # 使用简单的格式，因为前端会解析
    formatter = logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    handler.setFormatter(formatter)
    
    root_logger.addHandler(handler)
