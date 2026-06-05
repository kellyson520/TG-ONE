from typing import Dict, Any, List
from .base_renderer import BaseRenderer, ViewResult
from ui.constants import UIStatus

class SessionRenderer(BaseRenderer):
    """会话与消息管理渲染器 (UIRE-2.0)"""

    def render_session_hub(self, data: Dict[str, Any]) -> ViewResult:
        """渲染会话管理主页面"""
        return (self.new_builder()
            .set_title("会话管理中心", icon="💬")
            .add_breadcrumb(["首页", "系统", "会话管理"])
            .add_section("功能模块", "您可以对当前会话的消息进行深度去重扫描或按规则批量清理。", icon=UIStatus.INFO)
            .add_button("🔍 关联会话去重", "new_menu:session_dedup", icon=UIStatus.SEARCH)
            .add_button("🗑️ 批量清理消息", "new_menu:delete_session_messages", icon=UIStatus.DELETE)
            .add_button("👈 返回上一级", "new_menu:system_hub", icon=UIStatus.BACK)
            .build())

    def render_session_dedup_menu(self, data: Dict[str, Any]) -> ViewResult:
        """渲染会话去重扫描菜单"""
        return (self.new_builder()
            .set_title("会话扫描去重", icon="🔍")
            .add_breadcrumb(["首页", "会话管理", "去重扫描"])
            .add_section("扫描说明", [
                "• 采用官方 API 优化，支持全消息扫描。",
                "• 智能识别图片、视频、文件及文本重复。",
                "• 可自定义时间范围进行定向清理。"
            ], icon="💡")
            .add_button("🚀 开始深度扫描", "new_menu:start_dedup_scan", icon="🚀")
            .add_button("📊 查看上次结果", "new_menu:dedup_results", icon="📊")
            .add_button("📅 设置时间范围", "new_menu:session_dedup_time_range", icon=UIStatus.CLOCK)
            .add_button("⚙️ 去重策略设置", "new_menu:smart_dedup_settings", icon=UIStatus.SETTINGS)
            .add_button("👈 返回会话管理", "new_menu:session_management", icon=UIStatus.BACK)
            .build())

    def render_scan_results(self, data: Dict[str, Any]) -> ViewResult:
        """渲染扫描结果报告"""
        results = data.get('results', {})
        total_unique = len(results)
        total_duplicates = sum(results.values())
        
        builder = self.new_builder()
        builder.set_title("会话扫描报告", icon="📊")
        builder.add_breadcrumb(["会话管理", "扫描结果"])

        if total_unique == 0:
            builder.add_section("扫描状态", "✨ 未发现重复内容\n\n当前会话中的所有消息均为唯一。", icon=UIStatus.SUCCESS)
            builder.add_button("🔄 重新扫描", "new_menu:start_dedup_scan", icon="🔄")
        else:
            builder.add_section("汇总摘要", [], icon="📈")
            builder.add_status_grid({
                "重复种类": f"{total_unique}",
                "冗余总计": f"{total_duplicates} 条",
                "建议操作": "风险清理"
            })
            
            # 详情列表 (由于 Telegram 文本长度限制，只显示前 10)
            detail_lines = []
            for name, count in list(results.items())[:10]:
                detail_lines.append(f"• {name} ×{count}")
            if total_unique > 10:
                detail_lines.append(f"... 等共 {total_unique} 项")
                
            builder.add_section("详细内容列表 (部分)", detail_lines)
            
            builder.add_button("🗑️ 全部删除", "new_menu:delete_all_duplicates", icon=UIStatus.DELETE)
            builder.add_button("🔧 挑选删除", "new_menu:select_delete_duplicates", icon="🔧")
            builder.add_button("🔄 重新扫描", "new_menu:start_dedup_scan", icon="🔄")

        builder.add_button("👈 返回上一级", "new_menu:session_dedup", icon=UIStatus.BACK)
        return builder.build()

    def render_delete_management(self, data: Dict[str, Any]) -> ViewResult:
        """渲染批量删除管理页面"""
        time_str = data.get('time_range', '全部时间')
        status = data.get('status', '就绪')
        prog = data.get('progress', {})
        
        builder = self.new_builder()
        builder.set_title("批量清理消息", icon="🗑️")
        builder.add_breadcrumb(["首页", "会话管理", "批量清理"])
        
        builder.add_section("配置状态", [], icon=UIStatus.SETTINGS)
        builder.add_status_grid({
            "时间范围": time_str,
            "当前状态": status,
            "已处理": f"{prog.get('deleted', 0)} / {prog.get('total', 0)}"
        })
        
        builder.add_section("提示", "⚠️ 物理删除操作不可撤销，请务必先预览确认。", icon="⚠️")
        
        builder.add_button("📅 设置时间范围", "new_menu:time_range_selection", icon=UIStatus.CLOCK)
        builder.add_button("🔍 消息筛选条件", "new_menu:message_filter", icon=UIStatus.SEARCH)
        builder.add_button("👁️ 预览待删消息", "new_menu:preview_delete", icon="👁️")
        builder.add_button("🗑️ 执行批量删除", "new_menu:confirm_delete", icon=UIStatus.DELETE)
        
        if status == 'running':
            builder.add_button("⏸️ 暂停任务", "new_menu:pause_delete", icon="⏸️")
            builder.add_button("⏹️ 停止任务", "new_menu:stop_delete", icon="⏹️")
            
        builder.add_button("👈 返回会话管理", "new_menu:session_management", icon=UIStatus.BACK)
        return builder.build()

    def render_selection_menu(self, data: Dict[str, Any]) -> ViewResult:
        """渲染重复项选择删除菜单"""
        scan_counts = data.get('scan_counts', {})
        selected = data.get('selected', [])
        
        builder = self.new_builder()
        builder.set_title("挑选删除重复项", icon="🔧")
        builder.add_breadcrumb([ "会话管理", "去重", "挑选"])
        
        if not scan_counts:
             builder.add_section("状态", "❌ 暂无扫描结果", icon=UIStatus.ERROR)
        else:
            builder.add_section("重复项列表", "点击下方列表切换选中状态，确定后一键物理删除。", icon=UIStatus.INFO)
            for sig, ids in scan_counts.items():
                import hashlib
                short_id = hashlib.md5(sig.encode()).hexdigest()[:8]
                is_sel = sig in selected
                from services.session_service import session_manager
                display_name = session_manager._signature_to_display_name(sig)
                builder.add_button(f"{'✅' if is_sel else '☐'} {display_name} ×{len(ids)}", f"new_menu:toggle_select:{short_id}")
            
            builder.add_button("🗑️ 删除选中项", "new_menu:delete_selected_duplicates", icon=UIStatus.DELETE)
            
        builder.add_button("👈 返回结果页", "new_menu:dedup_results", icon=UIStatus.BACK)
        return builder.build()

    def render_delete_preview(self, data: Dict[str, Any]) -> ViewResult:
        """渲染删除预览"""
        count = data.get('count', 0)
        samples = data.get('samples', [])
        
        builder = self.new_builder()
        builder.set_title("删除预览", icon="👁️")
        builder.add_section("匹配评估", f"基于当前条件，预计将匹配 **{count}** 条消息。", icon="📊")
        
        if samples:
            sample_lines = [f"• [{m['id']}] {m['text'][:30]}..." for m in samples]
            builder.add_section("随机消息示例", sample_lines)
        
        builder.add_button("🔄 刷新预览", "new_menu:preview_delete", icon="🔄")
        builder.add_button("🔙 返回清理菜单", "new_menu:delete_session_messages", icon=UIStatus.BACK)
        return builder.build()
