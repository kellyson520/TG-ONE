from typing import Dict, Any
from .base_renderer import BaseRenderer, ViewResult
from ui.constants import UIStatus

class MediaRenderer(BaseRenderer):
    """媒体、AI 与历史任务渲染器 (UIRE-2.0)"""

    def render_history_hub(self, data: Dict[str, Any]) -> ViewResult:
        """渲染历史消息迁移中心"""
        current_task = data.get('current_task')
        builder = self.new_builder()
        builder.set_title("历史消息迁移中心", icon="补全")
        builder.add_breadcrumb(["首页", "历史中心"])
        builder.add_section("服务说明", "您可以将指定时间范围内的历史消息按照现有规则进行重发、过滤或同步。")
        
        if current_task:
            processed = current_task.get('processed', current_task.get('done', 0))
            total = current_task.get('total', 1) # 防止除零
            percent = (processed / total) * 100
            
            builder.add_section("当前活跃任务", [], icon=UIStatus.SYNC)
            builder.add_progress_bar("迁移进度", percent)
            builder.add_status_grid({
                "任务状态": (current_task.get('status', '运行中'), UIStatus.PROGRESS),
                "已处理": f"{processed} / {total}"
            })
        else:
            builder.add_section("任务状态", "当前无活跃迁移任务。", icon=UIStatus.INFO)
            
        builder.add_button("开启补全任务", action="new_menu:history_task_selector", icon=UIStatus.ADD)
        builder.add_button("任务历史", action="new_menu:history_task_list", icon=UIStatus.SEARCH)
        builder.add_button("媒体类型设置", action="new_menu:media_filter_config", icon=UIStatus.SETTINGS)
        builder.add_button("AI 增强选项", action="new_menu:ai_global_settings", icon=UIStatus.DOT)
        builder.add_button("返回主菜单", action="new_menu:main_menu", icon=UIStatus.BACK)
        
        return builder.build()

    def render_history_task_actions(self, data: Dict[str, Any]) -> ViewResult:
        """渲染历史任务操作配置页面"""
        selected = data.get('selected', {})
        dedup = data.get('dedup_enabled', False)
        
        return (self.new_builder()
            .set_title("历史迁移任务配置", icon="🚀")
            .add_breadcrumb(["首页", "补全中心", "任务预览"])
            .add_section("核心配置项", [], icon="📍")
            .add_status_grid({
                "目标规则": selected.get('id', '未选择'),
                "时间范围": data.get('time_range', '未设置'),
                "智能去重": ("已开启", UIStatus.SUCCESS) if dedup else ("已关闭", UIStatus.ERROR)
            })
            .add_section("操作引导", "确认无误后点击下方按钮开始任务。", icon="💡")
            .add_button("开始执行", action="new_menu:start_history_task", icon="🚀")
            .add_button("停止/清理", action="new_menu:cancel_history_task", icon="⏹️")
            .add_button("设置时间范围", action="new_menu:history_time_range", icon=UIStatus.CLOCK)
            .add_button("切换去重", action="new_menu:toggle_history_dedup", icon=UIStatus.SYNC)
            .add_button("返回历史中心", action="new_menu:history_messages", icon=UIStatus.BACK)
            .build())

    def render_media_filter_config(self, data: Dict[str, Any]) -> ViewResult:
        """渲染媒体转发过滤矩阵 (Phase 2.2)"""
        settings = data.get('settings', {})
        
        builder = self.new_builder()
        builder.set_title("媒体转发过滤矩阵", icon="🎬")
        builder.add_breadcrumb(["首页", "补全中心", "媒体过滤"])
        builder.add_section("配置说明", "此处设置影响‘历史补全’任务中的默认媒体过滤行为。", icon=UIStatus.INFO)
        
        # 媒体类型状态映射
        types = {
            "photo": ("图片", "🖼️"),
            "video": ("视频", "🎬"),
            "document": ("文档", "📄"),
            "audio": ("音频", "🎵"),
            "voice": ("语音", "🎙️"),
            "sticker": ("表情", "🎈")
        }
        
        status_lines = []
        for key, (label, icon) in types.items():
            enabled = settings.get(f"allow_{key}", True)
            status = "✅ 允许" if enabled else "❌ 过滤"
            status_lines.append(f"{icon} {label}: {status}")
            builder.add_button(f"{label} {'🔴' if enabled else '🟢'}", f"toggle_global_media:{key}")
            
        builder.add_section("全局配置矩阵", status_lines, icon=UIStatus.SETTINGS)
        
        builder.add_button("高级扩展名过滤", action="new_menu:media_extension_hub", icon="🧪")
        builder.add_button("返回补全中心", action="new_menu:history_messages", icon=UIStatus.BACK)
        
        return builder.build()

    def render_ai_global_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染 AI 增强全局设置 (Phase 2.2)"""
        settings = data.get('settings', {})
        
        builder = self.new_builder()
        builder.set_title("AI 增强全局面板", icon="🤖")
        builder.add_breadcrumb(["首页", "补全中心", "AI设置"])
        
        builder.add_section("服务巡检", "管理系统级 AI 预处理器和后处理钩子状态。", icon="🧠")
        
        builder.add_status_grid({
            "默认模型": settings.get('default_model', 'GPT-4o'),
            "并发限制": f"{settings.get('ai_concurrency', 5)} 条/秒",
            "重试次数": f"{settings.get('ai_retries', 3)} 次"
        })
        
        builder.add_section("全局策略", [
            f"• 兜底处理: {'转发原消息' if settings.get('ai_fallback') == 'raw' else '直接忽略'}",
            f"• 敏感词拦截: {'开启' if settings.get('enable_safety') else '关闭'}"
        ], icon="🛡️")
        
        builder.add_button("默认模型选择", action="new_menu:ai_global_model", icon="🧠")
        builder.add_button("并发配额设置", action="new_menu:ai_global_concurrency", icon="⚡")
        builder.add_button("返回补全中心", action="new_menu:history_messages", icon=UIStatus.BACK)
        
        return builder.build()

    def render_ai_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染 AI 增强设置页面 (Phase 4.5)"""
        rule = data.get('rule', {}) or data # 兼容性处理
        rid = rule.get('id', 'Unknown')
        is_ai = rule.get('is_ai', False)
        is_sum = rule.get('is_summary', False)
        
        builder = self.new_builder()
        builder.set_title(f"AI 增强设置 - {rid}", icon="🤖")
        builder.add_breadcrumb(["首页", "转发", f"AI-{rid}"])
        
        builder.add_section("核心开关", [], icon="⚡")
        builder.add_status_grid({
            "AI 增强处理": ("启用" if is_ai else "关闭", UIStatus.SUCCESS if is_ai else UIStatus.ERROR),
            "AI 自动总结": ("启用" if is_sum else "关闭", UIStatus.SUCCESS if is_sum else UIStatus.ERROR)
        })
        
        if is_ai:
            builder.add_section("处理逻辑", [], icon="🧠")
            builder.add_status_grid({
                "基础模型": rule.get('ai_model', '默认'),
                "图片上传": ("是" if rule.get('enable_ai_upload_image') else "否", UIStatus.INFO),
                "后置过滤": ("开启" if rule.get('is_keyword_after_ai') else "关闭", UIStatus.INFO)
            })
            builder.add_button("切换模型", f"change_model:{rid}", icon="🧠")
            builder.add_button("设置提示词", f"set_ai_prompt:{rid}", icon="✍️")
            builder.add_button(f"{'✅' if rule.get('enable_ai_upload_image') else '❌'} 传图", f"toggle_ai_upload_image:{rid}")
            builder.add_button(f"{'✅' if rule.get('is_keyword_after_ai') else '❌'} 后滤", f"toggle_keyword_after_ai:{rid}")

        if is_sum:
            builder.add_section("总结配置", [], icon="📋")
            builder.add_status_grid({
                "总结周期": rule.get('summary_time', '00:00'),
                "顶置消息": ("是" if rule.get('is_top_summary') else "否", UIStatus.INFO)
            })
            builder.add_button("总结频率", f"set_summary_time:{rid}", icon="⏰")
            builder.add_button("总结提示词", f"set_summary_prompt:{rid}", icon="✍️")
            builder.add_button(f"{'✅' if rule.get('is_top_summary') else '❌'} 顶置", f"toggle_top_summary:{rid}")
            builder.add_button("立即总结", f"summary_now:{rid}", icon="🚀")

        builder.add_button(f"{'🔴 关闭 AI' if is_ai else '🟢 开启 AI'}", f"toggle_ai:{rid}")
        builder.add_button(f"{'🔴 关闭总结' if is_sum else '🟢 开启总结'}", f"toggle_summary:{rid}")
        builder.add_button("返回规则设置", f"settings:{rid}", icon=UIStatus.BACK)
        return builder.build()

    def render_ai_prompt_editor(self, data: Dict[str, Any]) -> ViewResult:
        """渲染 AI 提示词编辑器"""
        rid = data.get('rule_id')
        p_type = data.get('type', '处理')
        current = data.get('current_prompt', '未设置')
        
        return (self.new_builder()
            .set_title(f"编辑 AI {p_type}提示词", icon="✍️")
            .add_section("当前提示词", f"`{current}`", icon="📝")
            .add_section("操作指引", f"请直接在对话框输入新的 AI {p_type}提示词。支持 Markdown 格式。输入 `取消` 退出。")
            .add_button("取消修改", f"new_menu:cancel_set_prompt:{rid}", icon=UIStatus.ERROR)
            .build())

    def render_model_selection(self, data: Dict[str, Any]) -> ViewResult:
        """渲染模型选择页面"""
        rid = data.get('rule_id')
        models = data.get('models', [])
        current = data.get('current_model')
        
        builder = self.new_builder()
        builder.set_title("选择 AI 引擎", icon="🧠")
        builder.add_section("当前选择", f"`{current or '默认核心'}`", icon="🎯")
        
        for model in models:
            builder.add_button(f"{'✅ ' if model == current else ''}{model}", f"select_ai_model:{rid}:{model}")
            
        builder.add_button("返回 AI 设置", f"ai_settings:{rid}", icon=UIStatus.BACK)
        return builder.build()

    def render_summary_time_selection(self, data: Dict[str, Any]) -> ViewResult:
        """渲染总结时间选择页面"""
        rid = data.get('rule_id')
        current = data.get('current_time', '00:00')
        
        builder = self.new_builder()
        builder.set_title("设置总结时间", icon="⏰")
        builder.add_section("提示", "AI 每日将在选定时间点汇总该规则下转发的所有内容。")
        
        # 常见时间点
        times = ["00:00", "08:00", "12:00", "18:00", "22:00", "23:59"]
        for t in times:
            builder.add_button(f"{'🎯 ' if t == current else ''}{t}", f"select_summary_time:{rid}:{t}")
            
        builder.add_button("返回 AI 设置", f"ai_settings:{rid}", icon=UIStatus.BACK)
        return builder.build()

    def render_media_extension_hub(self, data: Dict[str, Any]) -> ViewResult:
        """渲染高级扩展名过滤中心 (Phase 2.2)"""
        selected = data.get('selected', [])
        options = data.get('options', [])
        
        builder = self.new_builder()
        builder.set_title("高级媒体扩展名过滤", icon="🧪")
        builder.add_breadcrumb(["首页", "补全中心", "扩展名"])
        
        builder.add_section("生效机制", "选中的扩展名将在历史补全任务中被**拦截**。", icon=UIStatus.INFO)
        
        # 分页显示逻辑可以在 Controller 处理，这里简单显示
        for ext in options:
            is_selected = ext in selected
            builder.add_button(f"{'✅' if is_selected else '⬜'} .{ext}", f"toggle_global_extension:{ext}")
            
        builder.add_button("返回媒体过滤", action="new_menu:media_filter_config", icon=UIStatus.BACK)
        return builder.build()

    def render_ai_global_model_selection(self, data: Dict[str, Any]) -> ViewResult:
        """渲染 AI 全局默认模型选择"""
        models = data.get('models', [])
        current = data.get('current_model')
        
        builder = self.new_builder()
        builder.set_title("全局默认 AI 引擎", icon="🧠")
        builder.add_section("当前全局默认", f"`{current or '核心默认'}`", icon="🎯")
        
        for model in models:
            builder.add_button(f"{'✅ ' if model == current else ''}{model}", f"select_global_ai_model:{model}")
            
        builder.add_button("返回 AI 设置", action="new_menu:ai_global_settings", icon=UIStatus.BACK)
        return builder.build()

    def render_ai_global_concurrency_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染 AI 全局并发配额设置"""
        current = data.get('current_concurrency', 5)
        
        builder = self.new_builder()
        builder.set_title("AI 智能并发策略", icon="⚡")
        builder.add_section("当前配额", f"`{current}` 条/秒", icon="🔥")
        builder.add_section("策略说明", "增加并发可提升补全速度，但可能面临上游 API 频率限制 (429) 风险。", icon="💡")
        
        options = [1, 2, 3, 5, 10, 20]
        for opt in options:
            builder.add_button(f"{'🎯 ' if opt == current else ''}{opt} 条/秒", f"set_global_ai_concurrency:{opt}")
            
        builder.add_button("返回 AI 设置", action="new_menu:ai_global_settings", icon=UIStatus.BACK)
        return builder.build()
