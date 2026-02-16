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
        
        # 过滤掉 None 并在 body 之前添加间距
        valid_lines = [line for line in (body_lines or []) if line is not None]
        body = "\n".join(valid_lines)
        
        # 构造最终文本
        # UIRE-3.0 规范：如果标题和面包屑已在正文中（通过 MenuBuilder），则此处应避免重复添加
        # 这里的 header 和 prefix 由调用者传入决定
        full_header = f"{header}\n\n" if header else ""
        full_prefix = prefix if prefix else ""
        
        text = f"{full_header}" f"{full_prefix}" f"{body}\n\n" f"🕒 更新于：{ts}"
        
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

    async def display_view(self, event, view_result, breadcrumb: str | None = None):
        """
        [Architecture UIRE-3.0] 
        标准视图显示方法。直接接收 ViewResult 产物。
        内部自动处理标题提取与正文分离，确保不出现重复 Header。
        """
        from ui.renderers.base_renderer import ViewResult
        if not isinstance(view_result, ViewResult):
            # 兼容字典
            text = view_result.get('text', '')
            buttons = view_result.get('buttons', [])
        else:
            text = view_result.text
            buttons = view_result.buttons

        # 如果 text 中包含 MenuBuilder 的分割符，说明它是 FullPage 模式
        if "━━━━━━━━━━━━━━" in text:
            # 此时 view_result.text = [Title] + [Divider] + [Breadcrumb] + [Body]
            # 我们直接全量作为 body 传入 _render_page，并将 _render_page 的 title 置空
            # 这样可以在保留 _render_page 的“更新时间”脚注的同时，完全尊重 Renderer 的排版
            return await self._render_page(
                event,
                title="",
                body_lines=[text],
                buttons=buttons,
                breadcrumb=breadcrumb if not ("🗺️" in text) else None # 如果自带了面包屑，则不再添加传入的
            )
        else:
            # 回退到从文本推断逻辑
             return await self._render_from_text(event, text, buttons, breadcrumb=breadcrumb)

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
