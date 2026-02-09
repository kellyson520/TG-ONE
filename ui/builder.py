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
    TG ONE UI 声明式构建引擎 (UIRE-2.0)
    鲁棒性增强版：集成防御性文本处理与动态布局引擎。
    """
    
    MAX_TEXT_LENGTH = 3800  # 预留冗余空间
    _middlewares: List[RenderMiddleware] = [SensitivityMiddleware()]

    @classmethod
    def register_middleware(cls, middleware: RenderMiddleware):
        cls._middlewares.append(middleware)

    def __init__(self):
        self._title: str = ""
        self._breadcrumb: List[str] = []
        self._components: List[Union[str, BaseComponent]] = []
        self._buttons: List[List[Dict[str, Any]]] = [] # 修改为多行存储
        self._divider = "━━━━━━━━━━━━━━"
        
    def _safe_str(self, val: Any, escape: bool = True) -> str:
        """安全转换并应用 Markdown 逃逸"""
        s = str(val) if val is not None else ""
        if escape:
            s = TextUtil.escape_md(s)
        return s[:self.MAX_TEXT_LENGTH]

    def set_title(self, text: str, icon: str = "") -> 'MenuBuilder':
        """设置标题，自动应用防御性处理"""
        text = self._safe_str(text) or "系统菜单"
        icon_part = f"{icon} " if icon else ""
        self._title = f"{icon_part}**{text}**"
        return self
        
    def add_breadcrumb(self, path: List[str]) -> 'MenuBuilder':
        """添加导航路径，支持 ID 智能缩略"""
        if path:
            self._breadcrumb = [TextUtil.smart_truncate(self._safe_str(p)) for p in path if p]
        return self
        
    def add_section(self, header: str, content: Union[str, List[str]], icon: str = "", fallback: str = "（暂无数据）") -> 'MenuBuilder':
        """内容分块，支持空值 Fallback 与列表格式化"""
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
                # 对数值类不截断，对字符串类可能截断
                val_str = self._safe_str(value)
                if len(val_str) > 20: val_str = TextUtil.smart_truncate(val_str, 20)
                lines.append(f"  {icon} **{key_str}**: `{val_str}`")
            else:
                val_str = self._safe_str(val)
                if len(val_str) > 20: val_str = TextUtil.smart_truncate(val_str, 20)
                lines.append(f"  {UIStatus.DOT} **{key_str}**: `{val_str}`")
        
        self._components.append("\n".join(lines))
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
        # 如果没有已存在的平铺行，创建一个
        if not self._buttons or not isinstance(self._buttons[-1], list) or self._buttons[-1][0].get('_is_row'):
            self._buttons.append([])
        
        self._buttons[-1].append({
            "label": f"{icon} {label}" if icon else label,
            "action": action
        })
        return self
        
    def add_button_row(self, buttons: List[tuple]) -> 'MenuBuilder':
        """添加强制原子行按钮，不会被重新排列 (格式: [(label, action), ...])"""
        row = []
        for label, action in buttons:
             row.append({
                "label": self._safe_str(label),
                "action": action,
                "_is_row": True # 标记此行已人工干预
            })
        if row:
            self._buttons.append(row)
        return self

    def _apply_smart_layout(self) -> List[List[Button]]:
        """高级布局算法：平衡单行按钮与多列网格"""
        if not self._buttons:
            return []
            
        final_layout = []
        
        # 定义后置处理：返回/取消 始终在最下
        is_sticky_bottom = lambda label: any(x in label for x in [UIStatus.BACK, "返回", "取消", "关闭"])

        sticky_buttons = []
        
        for raw_row in self._buttons:
            # 如果是人工干预行，直接通过
            if raw_row and raw_row[0].get('_is_row'):
                final_layout.append([Button.inline(b["label"], b["action"]) for b in raw_row])
                continue
                
            # 否则进行流式排版
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
                # 针对不同长度动态决定列数
                if label_len > 12: 
                    flush()
                    final_layout.append([Button.inline(btn["label"], btn["action"])])
                elif len(current_row) >= (2 if label_len > 6 else 3):
                    flush()
                    current_row.append(btn)
                else:
                    current_row.append(btn)
            flush()

        # 处理吸底按钮
        if sticky_buttons:
            for i in range(0, len(sticky_buttons), 2):
                chunk = sticky_buttons[i:i+2]
                final_layout.append([Button.inline(b["label"], b["action"]) for b in chunk])
                
        return final_layout

    def add_pagination(self, page: int, total_pages: int, callback_prefix: str) -> 'MenuBuilder':
        """分页器作为原子行注入"""
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
        """编译 ViewResult，执行最终边界对齐"""
        from ui.renderers.base_renderer import ViewResult
        
        output_parts = []
        if self._title:
            output_parts.append(self._title)
            output_parts.append(self._divider)
            
        if self._breadcrumb:
            breadcrumb_str = f" 📍 *{' > '.join(self._breadcrumb)}*"
            output_parts.append(breadcrumb_str)
            
        if self._components:
            content_block = []
            for comp in self._components:
                content_block.append(comp.render() if isinstance(comp, BaseComponent) else comp)
            output_parts.append("\n" + "\n\n".join(content_block))
            
        text = "\n".join(output_parts)
        for mw in self._middlewares:
            text = mw.process(text)
            
        # 兜底截断
        if len(text) > self.MAX_TEXT_LENGTH:
            text = text[:self.MAX_TEXT_LENGTH] + "\n\n... (内容过长，已自动截断)"
            
        return ViewResult(text=text, buttons=self._apply_smart_layout())
