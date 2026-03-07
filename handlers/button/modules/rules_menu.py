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
        """显示规则列表 (异步分页) - 使用 Repository 层"""
        from core.container import container
        
        page = int(page)
        per_page = 5
        
        # 使用 Repository 层获取所有规则
        all_rules = await container.rule_repo.get_all_rules_with_chats()
        total = len(all_rules)
        total_pages = max(1, (total + per_page - 1) // per_page)
        
        if page > total_pages and total_pages > 0:
            page = total_pages
            
        # 内存分页
        start = (page - 1) * per_page
        end = start + per_page
        rules = all_rules[start:end]

        text = f"📂 **规则列表** ({page}/{total_pages})\\n请点击规则进行管理："
        buttons = []
        for rule in rules:
            s_name = rule.source_chat.name if rule.source_chat else "Unknown"
            t_name = rule.target_chat.name if rule.target_chat else "Unknown"
            status = "🟢" if rule.enable_rule else "🔴"
            buttons.append([Button.inline(f"{status} {s_name} ➔ {t_name}", f"new_menu:rule_detail:{rule.id}")])

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
                buttons.append([Button.inline(f"规则{rule.id}: {s_name} → {t_name}", f"new_menu:rule_detail:{rule.id}")])
            buttons.append([Button.inline("👈 返回上一级", "new_menu:forward_management")])
            await self._render_from_text(event, "⚙️ **规则详细设置**\n\n选择要配置的转发规则：", buttons)
        except Exception as e:
            logger.error(f"显示规则选择菜单失败: {str(e)}")
            await self._render_from_text(event, "❌ 获取规则列表失败", [[Button.inline("👈 返回上一级", "new_menu:forward_management")]])

    async def show_rule_management(self, event, page=0):
        """显示规则管理菜单"""
        from ..forward_management import forward_manager
        rules = await forward_manager.get_channel_rules()
        per_page = 5
        total_pages = (len(rules) + per_page - 1) // per_page
        start, end = page * per_page, (page + 1) * per_page
        current_rules = rules[start:end]

        buttons = []
        for r in current_rules:
            s_name = r.source_chat.name if r.source_chat else "Unknown"
            t_name = r.target_chat.name if r.target_chat else "Unknown"
            buttons.append([Button.inline(f"规则{r.id}: {s_name}➔{t_name}", f"new_menu:rule_detail:{r.id}")])

        nav = []
        if total_pages > 1:
            if page > 0:
                nav.append(Button.inline("⬅️ 上一页", f"new_menu:rule_management_page:{page-1}"))
            else:
                nav.append(Button.inline("⬅️", "noop"))
            
            nav.append(Button.inline(f"{page+1}/{total_pages}", "noop"))
            
            if page + 1 < total_pages:
                nav.append(Button.inline("下一页 ➡️", f"new_menu:rule_management_page:{page+1}"))
            else:
                nav.append(Button.inline("➡️", "noop"))
        if nav: buttons.append(nav)
        
        buttons.append([Button.inline("👈 返回上一级", "new_menu:forward_hub")])
        
        await self._render_from_text(event, "⚙️ **规则管理**\n\n选择要配置的规则：", buttons)

    async def show_multi_source_management(self, event, page=0):
        """显示多源管理菜单 (快速开关)"""
        from ..forward_management import forward_manager
        rules = await forward_manager.get_channel_rules()
        per_page = 5
        page = int(page)
        total_pages = (len(rules) + per_page - 1) // per_page
        start, end = page * per_page, (page + 1) * per_page
        current_rules = rules[start:end]

        buttons = []
        for r in current_rules:
            s_name = r.source_chat.name if r.source_chat else "Unknown"
            t_name = r.target_chat.name if r.target_chat else "Unknown"
            # 根据当前状态显示不同的图标和动作
            status_icon = "🟢" if r.enable_rule else "🔴"
            action_text = "开启中" if r.enable_rule else "已关闭"
            btn_text = f"{status_icon} {action_text} 规则{r.id}: {s_name}➔{t_name}"
            # 回调携带来源标识和页码
            buttons.append([Button.inline(btn_text, f"new_menu:toggle_rule:{r.id}:multi:{page}")])

        nav = []
        if total_pages > 1:
            if page > 0:
                nav.append(Button.inline("⬅️ 上一页", f"new_menu:multi_source_page:{page-1}"))
            else:
                nav.append(Button.inline("⬅️", "noop"))
            
            nav.append(Button.inline(f"{page+1}/{total_pages}", "noop"))
            
            if page + 1 < total_pages:
                nav.append(Button.inline("下一页 ➡️", f"new_menu:multi_source_page:{page+1}"))
            else:
                nav.append(Button.inline("➡️", "noop"))
        if nav: buttons.append(nav)
        
        buttons.append([Button.inline("👈 返回上一级", "new_menu:forward_hub")])
        await self._render_from_text(event, "🔗 **多源管理 (快速开关)**\n\n点击规则可快速 开启/关闭 转发：", buttons)

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
        """显示规则运行状态 - 使用真实数据"""
        from core.container import container
        from datetime import datetime
        from sqlalchemy import select
        
        rule_id = int(rule_id)
        # 1. 获取规则详情
        rule = await container.rule_repo.get_one(rule_id)
        if not rule:
            await event.answer("❌ 规则不存在", alert=True)
            return

        # 2. 获取今日统计
        today = datetime.now().strftime('%Y-%m-%d')
        async with container.db.get_session() as session:
            from models.models import RuleStatistics
            stmt = select(RuleStatistics).where(RuleStatistics.rule_id == rule_id, RuleStatistics.date == today)
            res = await session.execute(stmt)
            stat_obj = res.scalar_one_or_none()
            stats = {
                'success_count': stat_obj.success_count if stat_obj else 0,
                'error_count': stat_obj.error_count if stat_obj else 0,
                'filtered_count': stat_obj.filtered_count if stat_obj else 0
            }

        # 3. 获取最近日志
        items, _ = await container.stats_repo.get_rule_logs(rule_id, page=1, size=5)
        logs = []
        for item in items:
            logs.append({
                'action': item.action,
                'message_type': item.message_type,
                'processing_time': item.processing_time,
                'created_at': item.created_at
            })

        # 4. 渲染
        data = {
            'rule': {'id': rule.id, 'enabled': rule.enable_rule},
            'stats': stats,
            'logs': logs
        }
        
        view_result = container.ui.rule.render_single_rule_status(data)
        await self._render_page(
            event, 
            title=view_result.title,
            body_lines=[view_result.text],
            buttons=view_result.buttons,
            breadcrumb=view_result.breadcrumb
        )

    async def show_sync_config(self, event, rule_id):
        """显示同步配置"""
        from core.container import container
        rule_id = int(rule_id)
        
        # 获取当前规则的同步目标
        async with container.db.get_session() as session:
            from core.helpers.common import get_db_ops
            db_ops = await get_db_ops()
            sync_targets = await db_ops.get_rule_syncs(session, rule_id)
            target_ids = [s.sync_rule_id for s in sync_targets]
            
        text = f"🔗 **规则 {rule_id} 同步状态**\n\n"
        if not target_ids:
            text += "📭 当前规则未关联任何同步目标。\n启用同步后，转发成功的状态将同步至目标规则。"
        else:
            text += f"当前已关联 {len(target_ids)} 个同步目标规则：\n"
            for tid in target_ids:
                text += f"• 规则 ID: `{tid}`\n"
        
        buttons = [
            [Button.inline("⚙️ 详细管理同步", f"new_menu:sync_rule_page:{rule_id}:0")],
            [Button.inline("👈 返回详情", f"new_menu:manage_multi_source:{rule_id}")]
        ]
        await self._render_from_text(event, text, buttons, breadcrumb=f"🏠 > 📝 {rule_id} > 🔗")

rules_menu = RulesMenu()
