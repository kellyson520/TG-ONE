from typing import Dict, Any, List
from telethon.tl.custom import Button
from .base_renderer import BaseRenderer, ViewResult
from ui.constants import UIStatus
from enums.enums import AddMode, ForwardMode, MessageMode, PreviewMode, HandleMode


class RuleRenderer(BaseRenderer):
    """规则列表与详情渲染器 (UIRE-2.0)"""
    
    def render_rule_list(self, data: Dict[str, Any]) -> ViewResult:
        """渲染规则列表页面 (Phase 4.2)"""
        rules = data.get('rules', [])
        pagination = data.get('pagination', {})
        total_count = pagination.get('total_count', 0)
        current_page = pagination.get('page', 0)
        total_pages = pagination.get('total_pages', 1)
        
        builder = self.new_builder()
        builder.set_title("转发规则管理", icon=UIStatus.SETTINGS)
        builder.add_breadcrumb(["首页", "规则库"])
        
        if not rules:
            builder.add_section("📭 暂无转发规则", "点击下方 “新建规则” 按钮开始配置您的第一个转发任务。", icon=UIStatus.INFO)
            builder.add_section("功能特性", [
                "关键词精准匹配与排除",
                "基于内容指纹的智能去重",
                "消息内容实时正则替换",
                "全媒体类型转发支持"
            ], icon=UIStatus.STAR)
        else:
            for rule in rules:
                is_enabled = rule.get('enabled', True)
                status_icon = UIStatus.SUCCESS if is_enabled else UIStatus.ERROR
                status_label = "运行" if is_enabled else "停用"
                
                # 兼容嵌套字典 {'title': ...} 和扁平字段 source_chat_title 两种数据格式
                source_chat = rule.get('source_chat') or {} # 获取显示名称
                target_chat = rule.get('target_chat') or {}

                source = (source_chat.get('title')
                          or source_chat.get('name')
                          or rule.get('source_chat_title')
                          or f"Chat {source_chat.get('telegram_chat_id', '?')}"
                          or 'Unknown')

                target = (target_chat.get('title')
                          or target_chat.get('name')
                          or rule.get('target_chat_title')
                          or f"Chat {target_chat.get('telegram_chat_id', '?')}"
                          or 'Unknown')
                
                # 构造紧凑型卡片
                builder.add_section(
                    f"{status_icon} 规则 {rule['id']} | {status_label}",
                    [
                        f"路径: `{source}` ➔ `{target}`",
                        f"配置: {rule.get('keywords_count', 0)} 关键词 | {rule.get('replace_rules_count', 0)} 替换"
                    ]
                )
            
            # 注入快捷 ID 按钮（由 MenuBuilder 自动计算布局）
            for rule in rules:
                builder.add_button(f"📝 {rule['id']}", f"new_menu:edit_rule:{rule['id']}")

            # 注入分页
            builder.add_pagination(current_page, total_pages, "new_menu:rule_list_page")

        builder.add_button("新建规则", action="new_menu:create_rule", icon=UIStatus.ADD)
        builder.add_button("统计分析", action="new_menu:rule_statistics", icon=UIStatus.STAR)
        builder.add_button("批量管理", action="new_menu:multi_source_management", icon=UIStatus.SYNC)
        builder.add_button("搜索规则", action="new_menu:search_rules", icon=UIStatus.SEARCH)
        builder.add_button("返回转发中心", action="new_menu:forward_hub", icon=UIStatus.BACK)
        
        return builder.build()

    def render_rule_detail(self, data: Dict[str, Any]) -> ViewResult:
        """渲染规则详情页面 (Phase 4.3)"""
        rule = data.get('rule', {})
        rid = rule.get('id', 'Unknown')
        is_enabled = rule.get('enabled', True)
        
        builder = self.new_builder()
        builder.set_title(f"规则详情 - {rid}", icon=UIStatus.EDIT)
        builder.add_breadcrumb(["首页", "规则库", f"规则 {rid}"])
        
        builder.add_section("基础路由", [], icon="📤")
        # 兼容嵌套字典 {'title': ...} 和扁平字段两种数据格式
        src_chat = rule.get('source_chat') or {}
        tgt_chat = rule.get('target_chat') or {}
        src_title = (src_chat.get('name') or src_chat.get('title') or rule.get('source_chat_title')
                     or f"Chat {src_chat.get('telegram_chat_id', '?')}" or 'Unknown')
        tgt_title = (tgt_chat.get('name') or tgt_chat.get('title') or rule.get('target_chat_title')
                     or f"Chat {tgt_chat.get('telegram_chat_id', '?')}" or 'Unknown')
        builder.add_status_grid({
            "源聊天": src_title,
            "目标聊天": tgt_title,
            "当前状态": ("运行中", UIStatus.SUCCESS) if is_enabled else ("已禁用", UIStatus.ERROR)
        })
        
        builder.add_section("核心功能快照", [
            f"去重控制: {'✅ 开启' if rule.get('enable_dedup', False) else '❌ 关闭'}",
            f"关键词/替换: {rule.get('keywords_count', 0)}个 / {rule.get('replace_rules_count', 0)}条",
            f"媒体过滤: {rule.get('media_filter_count', 0)}项"
        ], icon=UIStatus.SETTINGS)
        
        builder.add_section("实时运维数据", [], icon="📊")
        builder.add_status_grid({
            "最后转发": rule.get('last_forward_time', '从未'),
            "次数累计": f"{rule.get('total_forwards', 0)} 次"
        })
        
        builder.add_button("切换状态", f"new_menu:toggle_rule:{rid}", icon=UIStatus.SYNC)
        builder.add_button("删除规则", f"new_menu:delete_rule_confirm:{rid}", icon=UIStatus.TRASH)
        builder.add_button("基础设置", f"new_menu:rule_basic_settings:{rid}", icon=UIStatus.SETTINGS)
        builder.add_button("显示设置", f"new_menu:rule_display_settings:{rid}", icon=UIStatus.EDIT)
        builder.add_button("高级功能", f"new_menu:rule_advanced_settings:{rid}", icon=UIStatus.STAR)
        builder.add_button("媒体过滤", f"new_menu:media_settings:{rid}", icon=UIStatus.FILTER)
        builder.add_button("AI 增强", f"new_menu:ai_settings:{rid}", icon=UIStatus.DOT)
        builder.add_button("同步/推送", f"new_menu:rule_sync_push:{rid}", icon=UIStatus.SYNC)
        builder.add_button("关键词管理", f"new_menu:keywords:{rid}", icon=UIStatus.SEARCH)
        builder.add_button("替换规则管理", f"new_menu:replaces:{rid}", icon=UIStatus.SYNC)
        builder.add_button("返回列表", "new_menu:list_rules:0", icon=UIStatus.BACK)
        
        return builder.build()

    def render_rule_basic_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染规则基础转发设置"""
        rule = data.get('rule', {})
        rid = rule.get('id')
        
        forward_mode_map = {
            'blacklist': '仅黑名单',
            'whitelist': '仅白名单',
            'blacklist_then_whitelist': '先黑后白',
            'whitelist_then_blacklist': '先白后黑',
            ForwardMode.BLACKLIST: '仅黑名单',
            ForwardMode.WHITELIST: '仅白名单',
            ForwardMode.BLACKLIST_THEN_WHITELIST: '先黑后白',
            ForwardMode.WHITELIST_THEN_BLACKLIST: '先白后黑'
        }
        
        return (self.new_builder()
            .set_title(f"基础设置 - {rid}", icon=UIStatus.SETTINGS)
            .add_breadcrumb(["首页", "规则库", rid, "基础设置"])
            .add_section("核心配置", "调整转发的核心流转模式属性。")
            .add_button(f"转发方式: {'🤖 机器人' if rule.get('use_bot') else '👤 个人账号'}", f"new_menu:toggle_rule_set:{rid}:use_bot")
            .add_button(f"过滤模式: {forward_mode_map.get(rule.get('forward_mode'), '未知')}", f"new_menu:toggle_rule_set:{rid}:forward_mode")
            .add_button(f"处理方式: {'✍️ 编辑' if str(rule.get('handle_mode', '')).lower() == 'edit' else '📤 转发'}", f"new_menu:toggle_rule_set:{rid}:handle_mode")
            .add_button(f"删除原消息: {'✅ 是' if rule.get('is_delete_original') else '❌ 否'}", f"new_menu:toggle_rule_set:{rid}:is_delete_original")
            .add_button("返回详情", f"new_menu:rule_detail:{rid}", icon=UIStatus.BACK)
            .build())

    def render_rule_display_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染规则内容显示设置"""
        rule = data.get('rule', {})
        rid = rule.get('id')
        
        return (self.new_builder()
            .set_title(f"显示设置 - {rid}", icon="🎨")
            .add_breadcrumb(["首页", "规则库", rid, "显示设置"])
            .add_section("外观选项", "配置转发消息的样式、链接及水印显示。")
            .add_button(f"消息格式: {str(rule.get('message_mode', 'HTML')).upper()}", f"new_menu:toggle_rule_set:{rid}:message_mode")
            .add_button(f"预览链接: {'开启' if (rule.get('is_preview') == 'on' or rule.get('is_preview') == PreviewMode.ON) else '关闭' if (rule.get('is_preview') == 'off' or rule.get('is_preview') == PreviewMode.OFF) else '跟随原消息'}", f"new_menu:toggle_rule_set:{rid}:is_preview")
            .add_button(f"原始发送者: {'显示' if rule.get('is_original_sender') else '隐藏'}", f"new_menu:toggle_rule_set:{rid}:is_original_sender")
            .add_button(f"发送时间: {'显示' if rule.get('is_original_time') else '隐藏'}", f"new_menu:toggle_rule_set:{rid}:is_original_time")
            .add_button(f"原始链接: {'附带' if rule.get('is_original_link') else '不附带'}", f"new_menu:toggle_rule_set:{rid}:is_original_link")
            .add_button(f"用户隐私: {'过滤' if rule.get('is_filter_user_info') else '保留'}", f"new_menu:toggle_rule_set:{rid}:is_filter_user_info")
            .add_button(f"评论按钮: {'开启' if rule.get('enable_comment_button') else '关闭'}", f"new_menu:toggle_rule_set:{rid}:enable_comment_button")
            .add_button("返回详情", f"new_menu:rule_detail:{rid}", icon=UIStatus.BACK)
            .build())

    def render_rule_advanced_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染规则高级功能设置"""
        rule = data.get('rule', {})
        rid = rule.get('id')
        
        return (self.new_builder()
            .set_title(f"高级控制 - {rid}", icon="🚀")
            .add_breadcrumb(["首页", "规则库", rid, "高级设置"])
            .add_section("深度逻辑", "配置去重、延迟及同步等系统级行为。")
            .add_button(f"智能去重: {UIStatus.SUCCESS if rule.get('enable_dedup') else UIStatus.ERROR}", f"new_menu:toggle_rule_set:{rid}:enable_dedup")
            .add_button(f"延迟处理: {UIStatus.SUCCESS if rule.get('enable_delay') else UIStatus.ERROR}", f"new_menu:toggle_rule_set:{rid}:enable_delay")
            .add_button(f"延迟时间: {rule.get('delay_seconds', 0)} 秒", f"new_menu:set_rule_val:{rid}:delay_seconds")
            .add_button(f"强制纯转发: {'✅ 是' if rule.get('force_pure_forward') else '❌ 否'}", f"new_menu:toggle_rule_set:{rid}:force_pure_forward")
            .add_button(f"跨规同步: {'✅ 开启' if rule.get('enable_sync') else '❌ 关闭'}", f"new_menu:toggle_rule_set:{rid}:enable_sync")
            .add_button("返回详情", f"new_menu:rule_detail:{rid}", icon=UIStatus.BACK)
            .build())

    def render_rule_statistics(self, data: Dict[str, Any]) -> ViewResult:
        """渲染规则统计页面"""
        stats = data.get('statistics', {})
        total = stats.get('total_rules', 0)
        percentage = stats.get('enabled_percentage', 0)
        
        builder = self.new_builder()
        builder.set_title("转发规则统计", icon=UIStatus.STAR)
        builder.add_breadcrumb(["首页", "统计报告"])
        
        builder.add_progress_bar("规则运行健康度", percentage)
        builder.add_status_grid({
            "总规则数": f"{total} 条",
            "已启用": f"{stats.get('enabled_rules', 0)} 条 ({percentage:.1f}%)",
            "已禁用": f"{stats.get('disabled_rules', 0)} 条",
            "智能去重激活": f"{stats.get('dedup_enabled_rules', 0)} 条"
        })
        
        builder.add_button("列表管理", "new_menu:forward_management", icon=UIStatus.SETTINGS)
        builder.add_button("返回转发中心", "new_menu:forward_hub", icon=UIStatus.BACK)
        return builder.build()

    def render_manage_keywords(self, data: Dict[str, Any]) -> ViewResult:
        """渲染管理关键词页面"""
        rule_id = data.get('rule_id')
        keywords = data.get('keywords', [])
        
        builder = self.new_builder()
        builder.set_title("关键词库管理", icon=UIStatus.SEARCH)
        builder.add_breadcrumb(["首页", "规则库", rule_id, "关键词"])
        
        if not keywords:
            builder.add_section("状态", "📭 暂无关键词。所有消息将直接通过筛选。", icon=UIStatus.INFO)
        else:
            builder.add_section(f"当前词库 (共 {len(keywords)} 个)", data.get('content', '（请展开列表）'))

        builder.add_button("添加关键词", f"new_menu:kw_add:{rule_id}", icon=UIStatus.ADD)
        builder.add_button("清空词库", f"new_menu:clear_keywords_confirm:{rule_id}", icon=UIStatus.TRASH)
        builder.add_button("返回详情", f"new_menu:rule_detail:{rule_id}", icon=UIStatus.BACK)
        return builder.build()

    def render_manage_replace_rules(self, data: Dict[str, Any]) -> ViewResult:
        """渲染管理替换规则页面"""
        rule_id = data.get('rule_id')
        replace_rules = data.get('replace_rules', [])
        
        builder = self.new_builder()
        builder.set_title("内容替换引擎", icon=UIStatus.SYNC)
        builder.add_breadcrumb(["首页", "规则库", rule_id, "替换规则"])
        
        if not replace_rules:
            builder.add_section("状态", "📭 暂无替换规则。消息内容将保持原样转发。", icon=UIStatus.INFO)
        else:
            lines = [f"`{rr.get('pattern', '')}` ➜ `{rr.get('replacement', '')}`" for rr in replace_rules]
            builder.add_section("活动规则清单", lines, icon="📝")

        builder.add_button("新增替换项", f"new_menu:rr_add:{rule_id}", icon=UIStatus.ADD)
        builder.add_button("清空规则", f"new_menu:clear_replaces_confirm:{rule_id}", icon=UIStatus.TRASH)
        builder.add_button("返回详情", f"new_menu:rule_detail:{rule_id}", icon=UIStatus.BACK)
        return builder.build()

    def render_media_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染媒体过滤高级设置页"""
        rule = data.get('rule', {})
        rid = rule.get('id')
        
        builder = self.new_builder()
        builder.set_title(f"媒体过滤 - {rid}", icon=UIStatus.FILTER)
        builder.add_breadcrumb(["首页", "规则库", rid, "媒体过滤"])
        
        builder.add_section("媒体类型控制", [
            f"图片/视频/文档/音频/语音的细精细化准入控制。"
        ])
        
        builder.add_button(f"精细化类型设置", f"new_menu:media_types:{rid}", icon="📷")
        builder.add_button(f"最大文件限制: {rule.get('max_media_size', 10)}MB", f"new_menu:set_rule_val:{rid}:max_media_size", icon="📦")
        builder.add_button(f"扩展名黑/白名单", f"new_menu:media_extensions:{rid}", icon="📄")
        
        builder.add_section("高级维度过滤", [
            f"时长过滤: {'✅ 启用' if rule.get('enable_duration_filter') else '❌ 禁用'}",
            f"分辨率过滤: {'✅ 启用' if rule.get('enable_resolution_filter') else '❌ 禁用'}",
            f"字节范围过滤: {'✅ 启用' if rule.get('enable_file_size_range') else '❌ 禁用'}"
        ])
        
        builder.add_button(f"时长: {rule.get('min_duration', 0)}s - {rule.get('max_duration', '∞')}s", f"new_menu:set_rule_val:{rid}:duration_range")
        builder.add_button(f"分辨率: {rule.get('min_width', 0)}x{rule.get('min_height', 0)} 起", f"new_menu:set_rule_val:{rid}:resolution_range")
        
        builder.add_button("返回详情", f"new_menu:rule_detail:{rid}", icon=UIStatus.BACK)
        return builder.build()

    def render_ai_settings(self, data: Dict[str, Any]) -> ViewResult:
        """渲染 AI 增强设置页"""
        rule = data.get('rule', {})
        rid = rule.get('id')
        
        builder = self.new_builder()
        builder.set_title(f"AI 智慧引擎 - {rid}", icon=UIStatus.DOT)
        builder.add_breadcrumb(["首页", "规则库", rid, "AI 增强"])
        
        builder.add_section("内容重写 (Rewrite)", [
            f"启用 AI 重写: {'✅' if rule.get('is_ai') else '❌'}",
            f"当前模型: `{rule.get('ai_model') or '默认'}`"
        ])
        
        builder.add_button("切换 AI 重写", f"new_menu:toggle_rule_set:{rid}:is_ai", icon=UIStatus.SYNC)
        builder.add_button("模型切换", f"new_menu:set_rule_val:{rid}:ai_model", icon="🤖")
        builder.add_button("编辑重写提示词", f"new_menu:set_rule_val:{rid}:ai_prompt", icon="📝")
        
        builder.add_section("定时总结 (Summary)", [
            f"启用定时总结: {'✅' if rule.get('is_summary') else '❌'}",
            f"总结频率: 每天 `{rule.get('summary_time', '07:00')}`",
            f"置顶今日总结: {'✅' if rule.get('is_top_summary') else '❌'}"
        ])
        
        builder.add_button("切换定时总结", f"new_menu:toggle_rule_set:{rid}:is_summary", icon=UIStatus.SYNC)
        builder.add_button("设置总结时间", f"new_menu:set_rule_val:{rid}:summary_time", icon="⏰")
        builder.add_button("编辑总结提示词", f"new_menu:set_rule_val:{rid}:summary_prompt", icon="✍️")
        builder.add_button(f"置顶设置: {'开启' if rule.get('is_top_summary') else '关闭'}", f"new_menu:toggle_rule_set:{rid}:is_top_summary")
        
        builder.add_button("返回详情", f"new_menu:rule_detail:{rid}", icon=UIStatus.BACK)
        return builder.build()

    def render_single_rule_status(self, data: Dict[str, Any]) -> ViewResult:
        """渲染单条规则的实时运行状态"""
        rule = data.get('rule', {})
        rid = rule.get('id', 'N/A')
        stats = data.get('stats', {})
        logs = data.get('logs', [])
        
        builder = self.new_builder()
        builder.set_title(f"运行状态 - {rid}", icon="📊")
        builder.add_breadcrumb(["首页", "规则库", str(rid), "状态"])
        
        # 1. 核心统计数据
        builder.add_section("今日转发看板", [
            f"成功次数: `{stats.get('success_count', 0)}` 次",
            f"失败次数: `{stats.get('error_count', 0)}` 次",
            f"过滤跳过: `{stats.get('filtered_count', 0)}` 次",
            f"运行状态: {'🟢 正常' if rule.get('enabled', True) else '🔴 已停止'}"
        ])
        
        # 2. 最近流水记录
        if not logs:
            builder.add_section("流水记录", "📭 暂无转发记录，规则可能刚启用或未匹配到消息。", icon=UIStatus.INFO)
        else:
            log_lines = []
            for log in logs[:5]:
                # 尝试格式化时间
                dt = log.get('created_at')
                dt_str = "--:--"
                if hasattr(dt, 'strftime'):
                    dt_str = dt.strftime('%H:%M:%S')
                elif isinstance(dt, str) and 'T' in dt:
                    dt_str = dt.split('T')[1][:8]
                
                status = "✅" if log.get('action') == 'success' else "❌"
                latency = f"{log.get('processing_time', 0)}ms"
                msg_type = (log.get('message_type') or 'text').upper()
                log_lines.append(f"`{dt_str}` {status} [{msg_type}] ({latency})")
            builder.add_section("最近记录 (Limit 5)", log_lines, icon="🕒")
            
        builder.add_button("导出记录", f"new_menu:export_rule_logs:{rid}", icon="📤")
        builder.add_button("返回规则详情", f"new_menu:rule_detail:{rid}", icon=UIStatus.BACK)
        return builder.build()
