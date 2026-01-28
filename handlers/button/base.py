"""
菜单系统基础类
提供统一的渲染接口和公共工具
"""
import logging
from datetime import datetime
from services.network.telegram_utils import safe_edit

logger = logging.getLogger(__name__)

class BaseMenu:
    """菜单基础类"""

    async def _render_page(
        self,
        event,
        title: str,
        body_lines: list[str],
        buttons,
        breadcrumb: str | None = None,
    ):
        """统一渲染页面：标题/面包屑/更新时间/正文/按钮"""
        try:
            ts = datetime.now().strftime("%H:%M:%S")
        except Exception:
            ts = "--:--:--"
        header = title.strip()
        prefix = f"{breadcrumb}\n\n" if breadcrumb else ""
        body = "\n".join([line for line in (body_lines or []) if line is not None])
        text = f"{header}\n\n" f"{prefix}" f"{body}\n\n" f"更新时间：{ts}"
        
        try:
            edited = await safe_edit(event, text, buttons)
            if not edited:
                await event.respond(text, buttons=buttons)
        except Exception as e:
            logger.debug(f"渲染页面失败，回退到直接响应: {e}")
            try:
                await event.respond(text, buttons=buttons)
            except Exception:
                raise

    async def _render_from_text(
        self, event, text: str, buttons, breadcrumb: str | None = None
    ):
        """从已有文本推断标题与正文，统一到 _render_page 渲染。"""
        try:
            raw = text or ""
            lines = [ln for ln in raw.split("\n")]
            if lines:
                title_line = lines[0].strip() or "菜单"
                title = title_line
                body = lines[1:] if len(lines) > 1 else []
            else:
                title = "菜单"
                body = []
            await self._render_page(
                event,
                title=title,
                body_lines=body,
                buttons=buttons,
                breadcrumb=breadcrumb,
            )
        except Exception as e:
            logger.debug(f"从文本渲染失败，使用安全编辑回退: {e}")
            try:
                edited = await safe_edit(event, text, buttons)
                if not edited:
                    await event.respond(text, buttons=buttons)
            except Exception:
                await event.respond(text, buttons=buttons)

    async def _edit_text(self, event, text: str, buttons):
        return await self._render_from_text(event, text, buttons)
