from typing import List, Dict, Any, Union, Optional
from telethon.tl.custom import Button
from ui.constants import UIStatus
import logging

logger = logging.getLogger(__name__)

class BaseComponent:
    """UI 组件抽象基类"""
    def render(self) -> str:
        raise NotImplementedError

class RenderMiddleware:
    """渲染中间件基类"""
    def process(self, text: str) -> str:
        return text

class SensitivityMiddleware(RenderMiddleware):
    """敏感词过滤中间件示例"""
    def process(self, text: str) -> str:
        # 这里以后可以对接敏感词库
        return text

import re

class TextUtil:
    """UI 文本处理工具集，处理 Telegram 特有的排版边界"""
    
    @staticmethod
    def escape_md(text: str) -> str:
        """极简 Markdown 逃逸，防止用户数据破坏标签"""
        if not text: return ""
        # 仅针对可能会破坏 ** 或 ` 的符号
        return text.replace("*", "＊").replace("_", "＿").replace("`", "＇")

    @staticmethod
    def smart_truncate(text: str, max_len: int = 30) -> str:
        """
        智能截断：如果是长 ID（包含数字或特殊符号），保留首尾。
        如果是普通文本，直接截断。
        """
        if not text or len(text) <= max_len:
            return text
        
        # 针对 ID 类文本优化 (首 6 尾 4)
        if re.search(r'\d', text) and len(text) > 15:
            return f"{text[:6]}...{text[-4:]}"
        
        return f"{text[:max_len-3]}..."

class MenuBuilder:
    """
    TG ONE UI 声明式构建引擎 (UIRE-3.0)
    旗舰版：集成回调安全防御、自动前缀分发、动态样式栅格。
    """
    
    MAX_TEXT_LENGTH = 3800  # 预留冗余空间
    MAX_CALLBACK_LENGTH = 64 # Telegram 协议硬限制
    DEFAULT_PREFIX = "new_menu:"
    
    _middlewares: List[RenderMiddleware] = [SensitivityMiddleware()]

    @classmethod
    def register_middleware(cls, middleware: RenderMiddleware):
        cls._middlewares.append(middleware)

    def __init__(self, use_prefix: bool = True):
        self._title: str = ""
        self._breadcrumb: List[str] = []
        self._components: List[Union[str, BaseComponent]] = []
        self._buttons: List[List[Dict[str, Any]]] = []
        self._use_prefix = use_prefix
        self._divider = "━━━━━━━━━━━━━━"
        
    def _safe_str(self, val: Any, escape: bool = True) -> str:
        """安全转换并应用 Markdown 逃逸"""
        s = str(val) if val is not None else ""
        if escape:
            s = TextUtil.escape_md(s)
        return s[:self.MAX_TEXT_LENGTH]

    def _format_action(self, action: str) -> str:
        """应用规则：所有 Action 必须符合 64 字节安全限制并自动补全前缀"""
        if not action or action == "ignore":
            return action
            
        modified_action = action
        # 1. 自动补全前缀 (仅在新系统中生效)
        if self._use_prefix and not action.startswith(self.DEFAULT_PREFIX) and not action.startswith("main_menu"):
            # 排除掉一些已知的旧系统前缀或排除项
            if not any(action.startswith(p) for p in ["rule_settings:", "media_settings:", "ai_settings:"]):
                modified_action = f"{self.DEFAULT_PREFIX}{action}"
        
        # 2. 长度截断校验 (Telegram 协议限制)
        if len(modified_action.encode('utf-8')) > self.MAX_CALLBACK_LENGTH:
            logger.error(f"UIRE-3.0 Alert: Callback data too long ({len(modified_action)} bytes): {modified_action}")
            # 进行紧急截断或散列处理 (待后续实现散列逻辑)，目前先截断
            return modified_action.encode('utf-8')[:self.MAX_CALLBACK_LENGTH].decode('utf-8', 'ignore')
            
        return modified_action

    def set_title(self, text: str, icon: str = "") -> 'MenuBuilder':
        """设置标题，自动应用防御性处理"""
        text = self._safe_str(text) or "系统控制中心"
        icon_part = f"{icon} " if icon else ""
        self._title = f"{icon_part}**{text}**"
        return self
        
    def add_breadcrumb(self, path: List[str]) -> 'MenuBuilder':
        """添加导航路径，支持 ID 智能缩略与样式增强"""
        if path:
            self._breadcrumb = [TextUtil.smart_truncate(self._safe_str(p)) for p in path if p]
        return self
        
    def add_section(self, header: str, content: Union[str, List[str]], icon: str = "", fallback: str = "（暂无数据）") -> 'MenuBuilder':
        """内容分块，支持标题勋章与多行对齐"""
        header = self._safe_str(header)
        icon_part = f"{icon} " if icon else ""
        text = f"{icon_part}**{header}**\n"
        
        if not content:
            content_part = f"  _{fallback}_"
        elif isinstance(content, list):
            valid_items = [self._safe_str(i) for i in content if i]
            if not valid_items:
                content_part = f"  _{fallback}_"
            else:
                content_part = "\n".join([f"  {UIStatus.DOT} {item}" for item in valid_items])
        else:
            lines = self._safe_str(content).split('\n')
            content_part = "\n".join([f"  {line}" if line.strip() else "  " for line in lines])
            
        self._components.append(text + content_part)
        return self
        
    def add_status_grid(self, items: Dict[str, Union[str, tuple]]) -> 'MenuBuilder':
        """健壮的状态矩阵，自动处理 ID 缩略"""
        if not items: return self
        lines = []
        for key, val in items.items():
            key_str = self._safe_str(key)
            if isinstance(val, tuple) and len(val) == 2:
                value, icon = val
                val_str = self._safe_str(value)
                if len(val_str) > 20: val_str = TextUtil.smart_truncate(val_str, 20)
                lines.append(f"  {icon} **{key_str}**: `{val_str}`")
            else:
                val_str = self._safe_str(val)
                if len(val_str) > 20: val_str = TextUtil.smart_truncate(val_str, 20)
                lines.append(f"  {UIStatus.DOT} **{key_str}**: `{val_str}`")
        
        self._components.append("\n".join(lines))
        return self
    
    def add_alert(self, message: str, level: str = UIStatus.WARNING) -> 'MenuBuilder':
        """快捷添加醒目警告/通知块"""
        self._components.append(f"\n> {level} **提示**: _{self._safe_str(message)}_")
        return self

    def add_progress_bar(self, label: str, percent: float, width: int = 8) -> 'MenuBuilder':
        """精准进度条，支持异常数值防御"""
        try:
            percent = float(percent)
        except (ValueError, TypeError):
            percent = 0.0
            
        percent = max(0.0, min(100.0, percent))
        filled = int((percent / 100) * width)
        empty = width - filled
        
        icon = "🏁" if percent >= 100 else UIStatus.PROGRESS
        bar = "🟩" * filled + "⬜" * empty
        self._components.append(f"  {icon} **{self._safe_str(label)}**\n  {bar} `{percent:.1f}%`")
        return self

    def add_button(self, label: str, action: str, icon: str = "") -> 'MenuBuilder':
        """添加平铺按钮，由布局引擎自动排列"""
        label = self._safe_str(label)
        if not self._buttons or not isinstance(self._buttons[-1], list) or self._buttons[-1][0].get('_is_row'):
            self._buttons.append([])
        
        self._buttons[-1].append({
            "label": f"{icon} {label}" if icon else label,
            "action": self._format_action(action)
        })
        return self
        
    def add_button_row(self, buttons: List[tuple]) -> 'MenuBuilder':
        """添加原子行按钮 ([(label, action), ...])"""
        row = []
        for label, action in buttons:
             row.append({
                "label": self._safe_str(label),
                "action": self._format_action(action),
                "_is_row": True
            })
        if row:
            self._buttons.append(row)
        return self

    def _apply_smart_layout(self) -> List[List[Button]]:
        """UIRE-3.0 增强型布局引擎"""
        if not self._buttons:
            return []
            
        final_layout = []
        is_sticky_bottom = lambda label: any(x in label for x in [UIStatus.BACK, "返回", "取消", "关闭"])
        sticky_buttons = []
        
        for raw_row in self._buttons:
            if raw_row and raw_row[0].get('_is_row'):
                final_layout.append([Button.inline(b["label"], b["action"]) for b in raw_row])
                continue
                
            current_row = []
            def flush():
                if current_row:
                    final_layout.append([Button.inline(b["label"], b["action"]) for b in current_row])
                    current_row.clear()

            for btn in raw_row:
                if is_sticky_bottom(btn["label"]):
                    sticky_buttons.append(btn)
                    continue
                    
                label_len = len(btn["label"])
                if label_len > 12: 
                    flush()
                    final_layout.append([Button.inline(btn["label"], btn["action"])])
                elif len(current_row) >= (2 if label_len > 6 else 3):
                    flush()
                    current_row.append(btn)
                else:
                    current_row.append(btn)
            flush()

        if sticky_buttons:
            # 返回按钮逻辑：如果只有一个，独占一行；如果有两个，合并
            for i in range(0, len(sticky_buttons), 2):
                chunk = sticky_buttons[i:i+2]
                final_layout.append([Button.inline(b["label"], b["action"]) for b in chunk])
                
        return final_layout

    def add_pagination(self, page: int, total_pages: int, callback_prefix: str) -> 'MenuBuilder':
        """分页器注入"""
        if total_pages <= 1: return self
        page = max(0, min(page, total_pages - 1))
        
        row = []
        if page > 0:
            row.append((f"{UIStatus.PREV} 上一页", f"{callback_prefix}:{page-1}"))
        row.append((f"{page + 1}/{total_pages}", "ignore"))
        if page < total_pages - 1:
            row.append((f"下一页 {UIStatus.NEXT}", f"{callback_prefix}:{page+1}"))
            
        return self.add_button_row(row)

    def build(self):
        """编译 ViewResult"""
        from ui.renderers.base_renderer import ViewResult
        
        output_parts = []
        if self._title:
            output_parts.append(self._title)
            output_parts.append(self._divider)
            
        if self._breadcrumb:
            breadcrumb_str = f" 🗺️ *{' ➜ '.join(self._breadcrumb)}*"
            output_parts.append(breadcrumb_str)
            
        if self._components:
            content_block = []
            for comp in self._components:
                # 兼容旧版本可能直接添加字符串的情况
                content_block.append(comp.render() if hasattr(comp, 'render') else str(comp))
            output_parts.append("\n" + "\n\n".join(content_block))
            
        text = "\n".join(output_parts)
        for mw in self._middlewares:
            text = mw.process(text)
            
        if len(text) > self.MAX_TEXT_LENGTH:
            text = text[:self.MAX_TEXT_LENGTH] + "\n\n... (内容过长，已自动截断)"
            
        return ViewResult(text=text, buttons=self._apply_smart_layout())
