from typing import Dict, Any
from telethon.tl.custom import Button
from .base_renderer import BaseRenderer

class TaskRenderer(BaseRenderer):
    """任务渲染器"""
    
    def render_history_task_selector(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染历史任务规则选择页面"""
        try:
            rules = data.get('rules', [])
            current_selection = data.get('current_selection', {})
            
            text = "📝 **选择历史消息任务规则**\n\n"
            text += "💡 **操作提示**: 选择规则后进入操作页面进行设置\n\n"
            
            if not rules:
                text += "❌ **暂无可用规则**\n"
                text += "请先创建并启用至少一个转发规则。\n\n"
                buttons = [
                    [Button.inline("➕ 创建规则", "new_menu:create_rule")],
                    [Button.inline("👈 返回转发中心", "new_menu:forward_hub")]
                ]
                return {'text': text, 'buttons': buttons}
            
            if current_selection.get('has_selection'):
                rule = current_selection.get('rule', {})
                def _chat_text(chat: Dict[str, Any]) -> str:
                    if not isinstance(chat, dict):
                        return 'Unknown'
                    return (
                        str(chat.get('title'))
                        or str(chat.get('name'))
                        or str(chat.get('telegram_chat_id') or 'Unknown')
                    )
                text += f"✅ **当前选择**: 规则 {current_selection.get('rule_id')}\n"
                text += f"   📤 {_chat_text(rule.get('source_chat', {}))}\n"
                text += f"   📥 {_chat_text(rule.get('target_chat', {}))}\n\n"
            else:
                text += "⚪ **尚未选择规则**\n\n"
            
            text += f"📋 **可用规则** ({len(rules)} 个)\n\n"
            
            buttons = []
            for i, rule in enumerate(rules[:8], 1):
                dedup_icon = "🧹" if rule.get('enable_dedup', False) else ""
                
                rule_text = f"{i}. {rule['source_title']} → {rule['target_title']} {dedup_icon}"
                if len(rule_text) > 25:
                    rule_text = rule_text[:22] + "..."
                
                buttons.append([Button.inline(
                    rule_text,
                    f"new_menu:select_history_rule:{rule['id']}"
                )])
            
            if len(rules) > 8:
                buttons.append([Button.inline(f"📋 查看全部 {len(rules)} 个规则", "new_menu:view_all_rules")])
            
            buttons.extend([
                [Button.inline("👈 返回转发中心", "new_menu:forward_hub")]
            ])
            
            return {'text': text, 'buttons': buttons}
            
        except Exception:
            return self.create_error_view("加载失败", "错误", "new_menu:forward_hub")

    def render_current_history_task(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染当前历史任务状态页面"""
        try:
            if not data.get('has_task', False):
                text = "📋 **历史消息任务**\n\n"
                text += "💤 **当前无运行任务**\n"
                text += "点击下方按钮开始新的历史消息转发任务。\n"
                
                buttons = [
                    [Button.inline("🚀 开始新任务", "new_menu:history_task_selector")],
                    [Button.inline("👈 返回转发中心", "new_menu:forward_hub")]
                ]
                
                return {'text': text, 'buttons': buttons}
            
            status = data.get('status', 'unknown')
            progress = data.get('progress', {})
            
            text = "📋 **历史消息任务状态**\n\n"
            
            status_icons = {
                'running': '🟢 运行中',
                'completed': '✅ 已完成',
                'failed': '❌ 失败',
                'cancelled': '⏹️ 已取消'
            }
            text += f"状态: {status_icons.get(status, f'❓ {status}')}\n\n"
            
            if progress:
                total = progress.get('total', 0)
                done = progress.get('done', 0)
                forwarded = progress.get('forwarded', 0)
                filtered = progress.get('filtered', 0)
                failed = progress.get('failed', 0)
                percentage = progress.get('percentage', 0)
                
                text += "📊 **进度统计**\n"
                text += f"总计: {total} 条\n"
                text += f"已处理: {done} 条 ({percentage:.1f}%)\n"
                text += f"已转发: {forwarded} 条\n"
                text += f"已过滤: {filtered} 条\n"
                if failed > 0:
                    text += f"失败: {failed} 条\n"
                
                if total > 0:
                    text += f"\n📈 {self._render_progress_bar(percentage)} **{percentage:.1f}%**\n"
                
                estimated = data.get('estimated_remaining')
                if estimated and status == 'running':
                    text += f"\n⏱️ 预估剩余: {estimated}\n"
            
            buttons = []
            if status == 'running':
                buttons.extend([
                    [Button.inline("🔄 刷新状态", "new_menu:current_history_task"),
                     Button.inline("⏹️ 取消任务", "new_menu:cancel_history_task")]
                ])
            else:
                buttons.extend([
                    [Button.inline("🚀 开始新任务", "new_menu:history_task_selector"),
                     Button.inline("📊 查看详情", "new_menu:history_task_details")]
                ])
            
            buttons.append([Button.inline("👈 返回转发中心", "new_menu:forward_hub")])
            
            return {'text': text, 'buttons': buttons}
            
        except Exception:
            return self.create_error_view("状态加载失败", "错误", "new_menu:forward_hub")

    def render_time_range_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染时间范围设置页面"""
        try:
            is_all_messages = data.get('is_all_messages', True)
            display_text = data.get('display_text', '全部时间')
            
            text = "⏰ **时间范围设置**\n\n"
            text += f"当前设置: {display_text}\n\n"
            
            if is_all_messages:
                text += "📅 **当前模式**: 获取全部消息\n"
                text += "这将处理聊天中的所有历史消息，可能需要较长时间。\n\n"
            else:
                text += "📅 **当前模式**: 自定义时间范围\n"
                text += "仅处理指定时间范围内的消息。\n\n"
            
            text += "🎯 **快速设置**:"
            
            buttons = [
                [Button.inline("🌟 全部消息", "new_menu:set_time_range_all"),
                 Button.inline("📅 最近7天", "new_menu:set_time_range_days:7")],
                [Button.inline("📆 最近30天", "new_menu:set_time_range_days:30"),
                 Button.inline("📊 最近90天", "new_menu:set_time_range_days:90")],
                [Button.inline("🕐 自定义开始时间", "new_menu:set_start_time"),
                 Button.inline("🕕 自定义结束时间", "new_menu:set_end_time")],
                [Button.inline("✅ 确认设置", "new_menu:confirm_time_range"),
                 Button.inline("👈 返回任务设置", "new_menu:history_task_actions")]
            ]
            
            return {'text': text, 'buttons': buttons}
            
        except Exception:
             return self.create_error_view("加载失败", "错误", "new_menu:history_task_actions")

    def render_history_task_actions(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染历史任务的操作子菜单"""
        try:
            selected = data.get('selected', {}) or {}
            has_sel = selected.get('has_selection', False)
            rid = selected.get('rule_id') if has_sel else None
            dedup_enabled = data.get('dedup_enabled', False)
            title = "🧭 **历史任务 - 操作**\n\n"
            if has_sel:
                title += f"当前规则: {rid}\n\n"
            else:
                title += "未选择规则\n\n"
            buttons = [
                [Button.inline("⚙️ 时间范围", "new_menu:history_time_range")],
                [Button.inline("⏱️ 延迟设置", "new_menu:history_delay_settings")],
                [Button.inline(f"🧹 历史去重：{'开启' if dedup_enabled else '关闭'}", "new_menu:toggle_history_dedup")],
                [Button.inline("📊 快速统计(服务端)", "new_menu:history_quick_stats")],
                [Button.inline("🧪 干跑(不发送)", "new_menu:history_dry_run")],
                [Button.inline("🗑️ 清理任务状态", "new_menu:cleanup_history_tasks")],
                [Button.inline("🚀 开始任务", "new_menu:start_history_task")],
                [Button.inline("👈 返回任务选择", "new_menu:history_task_selector")]
            ]
            return {'text': title, 'buttons': buttons}
        except Exception:
            return self.create_error_view("加载失败", "错误", "new_menu:history_task_selector")

    def render_delay_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染延迟设置页面"""
        try:
            delay_text = data.get('delay_text', '1秒')
            
            text = "⏱️ **转发延迟设置**\n\n"
            text += f"当前延迟: {delay_text}\n\n"
            text += "🛡️ **延迟作用**:\n"
            text += "• 防止触发Telegram频率限制\n"
            text += "• 避免账号被限制或封禁\n"
            text += "• 提高转发成功率\n\n"
            text += "💡 **推荐设置**:\n"
            text += "• 测试环境: 无延迟或1秒\n"
            text += "• 正常使用: 1-3秒\n"
            text += "• 大量转发: 5-10秒\n"
            text += "• 敏感账号: 10秒以上\n"
            
            buttons = [
                [Button.inline("⚡ 无延迟", "new_menu:set_delay:0"),
                 Button.inline("🚀 1秒", "new_menu:set_delay:1"),
                 Button.inline("⭐ 3秒", "new_menu:set_delay:3")],
                [Button.inline("🛡️ 5秒", "new_menu:set_delay:5"),
                 Button.inline("🔒 10秒", "new_menu:set_delay:10"),
                 Button.inline("🐌 30秒", "new_menu:set_delay:30")],
                [Button.inline("🎛️ 自定义", "new_menu:custom_delay"),
                 Button.inline("👈 返回任务设置", "new_menu:history_task_actions")]
            ]
            
            return {'text': text, 'buttons': buttons}
            
        except Exception:
            return self.create_error_view("加载失败", "错误", "new_menu:history_task_actions")

    def _render_progress_bar(self, percentage: float, length: int = 15) -> str:
        """渲染平滑的Unicode进度条"""
        blocks = ["", "▏", "▎", "▍", "▌", "▋", "▊", "▉", "█"]
        full_blocks = int(percentage / 100 * length)
        
        # Clamp full_blocks
        if full_blocks < 0: full_blocks = 0
        if full_blocks > length: full_blocks = length
        
        remainder = (percentage / 100 * length) - full_blocks
        remainder_idx = int(remainder * 8)
        if remainder_idx < 0: remainder_idx = 0
        if remainder_idx > 8: remainder_idx = 8
        
        bar = "█" * full_blocks
        if full_blocks < length:
            bar += blocks[remainder_idx]
            bar += "░" * (length - full_blocks - 1)
        return f"`{bar}`"
