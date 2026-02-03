"""
规则管理菜单模块
处理规则列表、创建、编辑、详情等
"""
import logging
from telethon import Button
from ..base import BaseMenu

logger = logging.getLogger(__name__)

class RulesMenu(BaseMenu):
    """规则管理菜单"""

    async def show_rule_list(self, event, page=1):
        """显示规则列表 (异步分页)"""
        from sqlalchemy import func, select
        from sqlalchemy.orm import selectinload
        from models.models import ForwardRule
        from core.container import container
        page = int(page)
        per_page = 5
        async with container.db.session() as session:
            total = (await session.execute(select(func.count(ForwardRule.id)))).scalar() or 0
            total_pages = (total + per_page - 1) // per_page
            if page > total_pages and total_pages > 0: page = total_pages
            offset = (page - 1) * per_page

            stmt = select(ForwardRule).options(
                selectinload(ForwardRule.source_chat),
                selectinload(ForwardRule.target_chat),
            ).order_by(ForwardRule.id).offset(offset).limit(per_page)
            result = await session.execute(stmt)
            rules = result.scalars().all()

        text = f"📂 **规则列表** ({page}/{total_pages})\n请点击规则进行管理："
        buttons = []
        for rule in rules:
            s_name = rule.source_chat.name if rule.source_chat else "Unknown"
            t_name = rule.target_chat.name if rule.target_chat else "Unknown"
            status = "🟢" if rule.enable_rule else "🔴"
            buttons.append([Button.inline(f"{status} {s_name} ➔ {t_name}", f"rule_settings:{rule.id}")])

        nav_row = []
        if page > 1: nav_row.append(Button.inline("⬅️ 上一页", f"new_menu:list_rules:{page-1}"))
        if page < total_pages: nav_row.append(Button.inline("下一页 ➡️", f"new_menu:list_rules:{page+1}"))
        if nav_row: buttons.append(nav_row)

        buttons.append([Button.inline("👈 返回", "new_menu:forward_hub")])
        # 使用 event.edit 或 _render_page
        await self._render_page(event, title="📂 **规则列表**", body_lines=[f"({page}/{total_pages})", "请点击规则进行管理："], buttons=buttons)

    async def show_rule_selection_for_settings(self, event):
        """显示规则选择菜单，用于进入详细设置"""
        try:
            from ..forward_management import forward_manager
            rules = await forward_manager.get_channel_rules()
            if not rules:
                await self._render_from_text(event, "❌ 没有找到任何转发规则", [[Button.inline("👈 返回上一级", "new_menu:forward_management")]])
                return

            buttons = []
            for rule in rules[:10]:
                s_name = rule.source_chat.name if rule.source_chat else "未知源"
                t_name = rule.target_chat.name if rule.target_chat else "未知目标"
                buttons.append([Button.inline(f"规则{rule.id}: {s_name} → {t_name}", f"rule_settings:{rule.id}")])
            buttons.append([Button.inline("👈 返回上一级", "new_menu:forward_management")])
            await self._render_from_text(event, "⚙️ **规则详细设置**\n\n选择要配置的转发规则：", buttons)
        except Exception as e:
            logger.error(f"显示规则选择菜单失败: {str(e)}")
            await self._render_from_text(event, "❌ 获取规则列表失败", [[Button.inline("👈 返回上一级", "new_menu:forward_management")]])

    async def show_rule_management(self, event, page=0):
        """显示规则管理菜单"""
        from ..forward_management import forward_manager
        rules = await forward_manager.get_channel_rules()
        per_page = 10
        total_pages = (len(rules) + per_page - 1) // per_page
        start, end = page * per_page, (page + 1) * per_page
        current_rules = rules[start:end]

        buttons = []
        for r in current_rules:
            s_name = r.source_chat.name if r.source_chat else "Unknown"
            t_name = r.target_chat.name if r.target_chat else "Unknown"
            buttons.append([Button.inline(f"规则{r.id}: {s_name}➔{t_name}", f"rule_settings:{r.id}")])

        nav = []
        if page > 0: nav.append(Button.inline("⬅️ 上一页", f"new_menu:rule_management_page:{page-1}"))
        if end < len(rules): nav.append(Button.inline("下一页 ➡️", f"new_menu:rule_management_page:{page+1}"))
        if nav: buttons.append(nav)
        buttons.append([Button.inline("👈 返回上一级", "new_menu:forward_management")])
        
        await self._render_from_text(event, "⚙️ **规则管理**\n\n选择要配置的规则：", buttons)

    async def show_multi_source_management(self, event, page=0):
        """显示多源管理菜单"""
        from ..forward_management import forward_manager
        rules = await forward_manager.get_channel_rules()
        per_page = 10
        total_pages = (len(rules) + per_page - 1) // per_page
        start, end = page * per_page, (page + 1) * per_page
        current_rules = rules[start:end]

        buttons = []
        for r in current_rules:
            s_name = r.source_chat.name if r.source_chat else "Unknown"
            t_name = r.target_chat.name if r.target_chat else "Unknown"
            buttons.append([Button.inline(f"🔗 规则{r.id}: {s_name}➔{t_name}", f"new_menu:multi_source_detail:{r.id}")])

        nav = []
        if page > 0: nav.append(Button.inline("⬅️ 上一页", f"new_menu:multi_source_page:{page-1}"))
        if end < len(rules): nav.append(Button.inline("下一页 ➡️", f"new_menu:multi_source_page:{page+1}"))
        if nav: buttons.append(nav)
        buttons.append([Button.inline("👈 返回上一级", "new_menu:forward_management")])
        await self._render_from_text(event, "🔗 **多源管理**\n\n选择要管理的复合规则：", buttons)

    async def show_multi_source_detail(self, event, rule_id):
        """显示多源管理详细页面"""
        buttons = [
            [Button.inline("⚙️ 规则设置", f"new_menu:rule_detail_settings:{rule_id}")],
            [Button.inline("🔗 同步配置", f"new_menu:sync_config:{rule_id}")],
            [Button.inline("📊 运行状态", f"new_menu:rule_status:{rule_id}")],
            [Button.inline("👈 返回上一级", "new_menu:multi_source_management")],
        ]
        await self._render_from_text(event, f"🔗 **多源管理详情** (ID: {rule_id})\n\n请选择操作：", buttons)

    async def show_rule_status(self, event, rule_id):
        """显示规则运行状态"""
        # 暂时显示简单概览
        await self._render_from_text(event, f"📊 **规则 {rule_id} 运行状态**\n\n[开发中] 此处将显示该规则的详细转发统计、成功受限次数、实时延迟频率等。", [[Button.inline("👈 返回详情", f"new_menu:manage_multi_source:{rule_id}")]])

    async def show_sync_config(self, event, rule_id):
        """显示同步配置"""
        await self._render_from_text(event, f"🔗 **规则 {rule_id} 同步配置**\n\n[开发中] 此处将显示该规则关联的频道同步关系、来源目标映射及状态同步开关。", [[Button.inline("👈 返回详情", f"new_menu:manage_multi_source:{rule_id}")]])

rules_menu = RulesMenu()
