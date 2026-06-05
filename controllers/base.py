import logging
from typing import Optional, Any
from core.container import Container

logger = logging.getLogger(__name__)

class ControllerAbort(Exception):
    """用于中断控制器流程并返回错误 UI 的异常"""
    def __init__(self, message: str, back_target: str = "main_menu"):
        self.message = message
        self.back_target = back_target
        super().__init__(message)

class BaseController:
    """控制器基类"""
    def __init__(self, container: Container):
        self.container = container
        self.db = container.db
        
    async def get_rule_or_abort(self, rule_id: int, back_target: str = "rule_list"):
        """获取规则，不存在则中断并报错"""
        rule = await self.container.rule_repo.get_one(rule_id)
        if not rule:
            raise ControllerAbort(f"规则 ID {rule_id} 不存在", back_target=back_target)
        return rule

    async def check_maintenance(self, event):
        """检查系统维护模式 (管理员除外)"""
        try:
            from core.helpers.common import is_admin
            if await is_admin(event):
                return False # 管理员不受限
            
            # 通过 SystemService 检查维护模式 (符合架构规范)
            if await self.container.system_service.is_maintenance_mode():
                raise ControllerAbort("🚧 **系统维护中**\n\n当前系统正在进行维护升级，请稍后再试。", "main_menu")
            return False
        except ControllerAbort:
            raise
        except Exception as e:
            logger.error(f"Maintenance check failed: {e}")
            return False

    async def notify(self, event, text: str, alert: bool = False):
        """统一通知接口：如果是按钮回调则弹窗，如果是消息则回复"""
        try:
            if hasattr(event, 'answer'):
                await event.answer(text, alert=alert)
            else:
                await event.respond(f"{'⚠️' if alert else '✅'} {text}")
        except Exception as e:
            logger.warning(f"Notification failed: {e}")

    def handle_exception(self, e: Exception, back_target: str = "main_menu"):
        """统一异常处理逻辑"""
        # 如果是 FloodWaitError，仅记录日志，不尝试发送消息以免加重流控
        from telethon.errors import FloodWaitError
        if isinstance(e, FloodWaitError):
            logger.error(f"Controller triggered FloodWait: wait {e.seconds}s")
            return

        if isinstance(e, ControllerAbort):
            return self.container.ui.render_error(e.message, e.back_target)
        
        logger.exception("Controller Error")
        return self.container.ui.render_error(f"内部系统错误: {str(e)}", back_target)
