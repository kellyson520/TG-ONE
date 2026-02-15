from typing import Dict, Any
from telethon.tl.custom import Button
from ui.constants import UIStatus
from .base_renderer import BaseRenderer, ViewResult

class TaskRenderer(BaseRenderer):
    """任务渲染器 (UIRE-2.0)"""
    
    def render_history_task_selector(self, data: Dict[str, Any]) -> ViewResult:
        """渲染历史任务规则选择页面"""
        rules = data.get('rules', [])
        current_selection = data.get('current_selection', {})
        
        builder = self.new_builder()
        builder.set_title("历史消息任务配置", icon="📝")
        builder.add_breadcrumb(["首页", "补全中心", "规则筛选"])
        
        builder.add_section("操作提示", "选择一个已有的转发规则，系统将按其配置批量处理历史消息。", icon="💡")
        
        if not rules:
            builder.add_section("状态", "❌ 暂无可用规则，请先前往规则管理中心创建。", icon=UIStatus.ERROR)
            builder.add_button("前往创建", "new_menu:create_rule", icon=UIStatus.ADD)
        else:
            if current_selection.get('has_selection'):
                rule = current_selection.get('rule', {})
                builder.add_section("当前选定规则", [
                    f"ID: `{current_selection.get('rule_id')}`",
                    f"路径: `{rule.get('source_chat_title')}` ➔ `{rule.get('target_chat_title')}`"
                ], icon=UIStatus.SUCCESS)
            
            builder.add_section(f"可用规则库 ({len(rules)})", [], icon="📋")
            for rule in rules:
                builder.add_button(
                    f"{rule['source_title']} ➔ {rule['target_title']}", 
                    f"new_menu:select_history_rule:{rule['id']}"
                )
        
        builder.add_button("返回中心", "new_menu:forward_hub", icon=UIStatus.BACK)
        return builder.build()

    def render_current_history_task(self, data: Dict[str, Any]) -> ViewResult:
        """渲染当前历史任务状态页面"""
        builder = self.new_builder()
        builder.set_title("历史任务执行台", icon="🚀")
        builder.add_breadcrumb(["首页", "补全中心", "当前状态"])
        
        if not data.get('has_task', False):
            builder.add_section("活跃任务", "💤 当前无正在运行的任务。", icon=UIStatus.INFO)
            builder.add_button("启动新任务", "new_menu:history_task_selector", icon="🚀")
        else:
            status = data.get('status', 'running')
            progress = data.get('progress', {})
            percent = progress.get('percentage', 0)
            
            builder.add_section("执行状态", f"当前状态: {'🟢 运行中' if status == 'running' else '✅ 已完成'}")
            builder.add_progress_bar("总体处理进度", percent)
            
            builder.add_status_grid({
                "总计": f"{progress.get('total', 0)} 条",
                "已处理": f"{progress.get('done', 0)} 条",
                "已转发": f"{progress.get('forwarded', 0)} 条",
                "已过滤": f"{progress.get('filtered', 0)} 条"
            })
            
            if status == 'running':
                builder.add_button("刷新", "new_menu:current_history_task", icon="🔄")
                builder.add_button("停止任务", "new_menu:cancel_history_task", icon="⏹️")
            else:
                builder.add_button("任务详情", "new_menu:history_task_details", icon="📊")
                
        builder.add_button("返回", "new_menu:forward_hub", icon=UIStatus.BACK)
        return builder.build()

    def render_time_range_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染时间范围设置页面"""
        is_all = data.get('is_all_messages', True)
        
        return (self.new_builder()
            .set_title("扫描时间跨度", icon="⏰")
            .add_breadcrumb(["首页", "补全中心", "时间设置"])
            .add_section("当前模式", f"📅 {data.get('display_text', '全部时间')}")
            .add_section("模式说明", "选择全量扫描或自定义约束时间段，自定义模式可减少系统 API 调用压力。")
            .add_button("🌟 全部历史", "new_menu:set_time_range_all")
            .add_button("📅 最近7天", "new_menu:set_time_range_days:7")
            .add_button("📆 最近30天", "new_menu:set_time_range_days:30")
            .add_button("📊 最近90天", "new_menu:set_time_range_days:90")
            .add_button("🕐 自定义开始", "new_menu:set_start_time")
            .add_button("🕕 自定义结束", "new_menu:set_end_time")
            .add_button("✅ 确认保存", "new_menu:confirm_time_range", icon=UIStatus.SUCCESS)
            .add_button("返回", "new_menu:history_messages", icon=UIStatus.BACK)
            .build())

    def render_history_task_actions(self, data: Dict[str, Any]) -> ViewResult:
        """渲染历史任务的操作子菜单"""
        selected = data.get('selected', {}) or {}
        rid = selected.get('rule_id')
        
        return (self.new_builder()
            .set_title("任务指令集", icon="🧭")
            .add_breadcrumb(["首页", "补全中心", "操作指令"])
            .add_section("目标关联", f"选定规则: `{rid or '尚未选择'}`")
            .add_button("⚙️ 时间范围", "new_menu:history_time_range")
            .add_button("⏱️ 注入延迟", "new_menu:history_delay_settings")
            .add_button(f"🧹 历史去重: {'✅ ON' if data.get('dedup_enabled') else '❌ OFF'}", "new_menu:toggle_history_dedup")
            .add_button("📊 快速统计", "new_menu:history_quick_stats")
            .add_button("🧪 模拟运行", "new_menu:history_dry_run")
            .add_button("🚀 真正开始", "new_menu:start_history_task")
            .add_button("返回", "new_menu:history_messages", icon=UIStatus.BACK)
            .build())

    def render_delay_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染延迟设置页面"""
        return (self.new_builder()
            .set_title("智能速率控制", icon="⏱️")
            .add_section("流控状态", f"当前扫描间隔: `{data.get('delay_text', '1秒')}`")
            .add_section("调控策略", [
                "1-3秒: 常规任务平衡速度与安全",
                "5-10秒: 针对大批量、长周期任务",
                "30秒+: 极高安全级别，避免封号"
            ], icon="💡")
            .add_button("⚡ 无延迟", "new_menu:set_delay:0")
            .add_button("🚀 1秒", "new_menu:set_delay:1")
            .add_button("⭐ 3秒", "new_menu:set_delay:3")
            .add_button("🛡️ 5秒", "new_menu:set_delay:5")
            .add_button("🔒 10秒", "new_menu:set_delay:10")
            .add_button("👈 返回", "new_menu:history_messages", icon=UIStatus.BACK)
            .build())

    def render_history_task_list(self, data: Dict[str, Any]) -> ViewResult:
        """渲染历史任务列表页面"""
        tasks = data.get('tasks', [])
        total = data.get('total', 0)
        page = data.get('page', 1)
        
        builder = self.new_builder()
        builder.set_title("历史任务中心", icon="📜")
        builder.add_breadcrumb(["首页", "补全中心", "任务列表"])
        
        if not tasks:
            builder.add_section("任务列表", "📭 暂无历史任务记录。", icon=UIStatus.INFO)
            builder.add_button("启动新任务", "new_menu:history_task_selector", icon="🚀")
        else:
            builder.add_section(f"任务列表 (共 {total} 个)", [])
            for task in tasks:
                try:
                    import json
                    task_data = json.loads(task.task_data)
                    rule_id = task_data.get('rule_id', 'Unknown')
                    status_icon = "🟢" if task.status == 'running' else "✅" if task.status == 'completed' else "❌" if task.status == 'failed' else "⏳"
                    
                    builder.add_section(
                        f"{status_icon} 任务 #{task.id} (规则 {rule_id})",
                        [
                            f"状态: {task.status}",
                            f"创建于: {task.created_at.strftime('%m-%d %H:%M')}"
                        ]
                    )
                except Exception:
                    builder.add_section(f"⚠️ 任务 #{task.id}", ["数据解析异常"])
            
            # 翻页逻辑
            if total > 10:
                btn_row = []
                if page > 1:
                    btn_row.append(Button.inline("⬅️ 上一页", f"new_menu:history_task_list:{page-1}"))
                if total > page * 10:
                    btn_row.append(Button.inline("下一页 ➡️", f"new_menu:history_task_list:{page+1}"))
                if btn_row:
                    builder.add_button_row(btn_row)
        
        builder.add_button("返回", "new_menu:history_messages", icon=UIStatus.BACK)
        return builder.build()
