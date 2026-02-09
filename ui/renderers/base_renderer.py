from typing import Dict, Any, List, Optional, Union
from telethon.tl.custom import Button
import logging
from ui.constants import UIStatus

logger = logging.getLogger(__name__)

class ViewResult:
    """统一渲染产物容器"""
    def __init__(
        self, 
        text: str, 
        buttons: List[List[Button]] = None, 
        notification: Optional[str] = None,
        show_alert: bool = False,
        force_new: bool = False,
        metadata: Dict[str, Any] = None
    ):
        self.text = text
        self.buttons = buttons or []
        self.notification = notification
        self.show_alert = show_alert
        self.force_new = force_new
        self.metadata = metadata or {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            'text': self.text,
            'buttons': self.buttons,
            'notification': self.notification,
            'show_alert': self.show_alert,
            'force_new': self.force_new,
            'metadata': self.metadata
        }

class BaseRenderer:
    """基础渲染器类"""
    
    def new_builder(self) -> 'MenuBuilder':
        """快速获取 UI 构建器实例"""
        from ui.builder import MenuBuilder
        return MenuBuilder()

    def create_back_button(self, callback_data: str, label: str = f"{UIStatus.BACK} 返回") -> List[Button]:
        return [Button.inline(label, callback_data)]
        
    def render_error(self, message: str, back_callback: str = "main_menu", detail: str = None) -> ViewResult:
        """重构：利用 MenuBuilder 渲染标准错误页面"""
        builder = self.new_builder()
        builder.set_title("操作失败", icon=UIStatus.ERROR)
        
        if detail:
            builder.add_section("错误详情", detail)
        else:
            builder.add_section("提示", message)
            
        builder.add_button("返回", action=back_callback, icon=UIStatus.BACK)
        return builder.build()

    def render_confirm(self, title: str, message: str, confirm_action: str, cancel_action: str) -> ViewResult:
        """渲染统一样式的二次确认页面 (Phase 4.6)"""
        return (self.new_builder()
            .set_title(title, icon="⚠️")
            .add_section("二次确认", message, icon=UIStatus.WARN)
            .add_button("✅ 确定执行", confirm_action, icon=UIStatus.SUCCESS)
            .add_button("❌ 取消操作", cancel_action, icon=UIStatus.ERROR)
            .build())

    def paginate_buttons(
        self, 
        items: List[Any], 
        page: int, 
        page_size: int, 
        callback_prefix: str,
        item_callback_prefix: str = None
    ) -> List[List[Button]]:
        """
        动态生成分页按钮
        items: 所有项目
        page: 当前页码 (0-indexed)
        page_size: 每页数量
        callback_prefix: 分页指令前缀 (会附加 :page_num)
        item_callback_prefix: 项目点击指令前缀 (如果项目本身就是按钮内容的一部分)
        """
        total_pages = (len(items) + page_size - 1) // page_size if items else 1
        page = max(0, min(page, total_pages - 1))
        
        start = page * page_size
        end = start + page_size
        current_items = items[start:end]
        
        buttons = []
        # 项目按钮 (假设 items 是可以显示的对象)
        for item in current_items:
            # 这里需要子类决定如何为每个 item 生成按钮，或者在这里预设逻辑
            pass

        # 导航栏
        nav_row = []
        if total_pages > 1:
            if page > 0:
                nav_row.append(Button.inline(f"{UIStatus.PREV} 上一页", f"{callback_prefix}:{page-1}"))
            
            nav_row.append(Button.inline(f"{page + 1}/{total_pages}", "ignore"))
            
            if page < total_pages - 1:
                nav_row.append(Button.inline(f"下一页 {UIStatus.NEXT}", f"{callback_prefix}:{page+1}"))
        
        if nav_row:
            buttons.append(nav_row)
            
        return buttons

