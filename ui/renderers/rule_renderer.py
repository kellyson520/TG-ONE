from typing import Dict, Any, List
from telethon.tl.custom import Button
from .base_renderer import BaseRenderer

class RuleRenderer(BaseRenderer):
    """规则列表与详情渲染器"""
    
    def render_rule_list(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染规则列表页面"""
        try:
            rules = data.get('rules', [])
            pagination = data.get('pagination', {})
            
            text = (
                "⚙️ **转发规则管理**\n"
                "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
            )
            
            if not rules:
                text += (
                    "📭 **暂无转发规则**\n\n"
                    "💡 **开始使用**\n"
                    "点击下方 ➕ 新建规则 按钮创建您的第一个转发规则。\n\n"
                    "🔧 **功能说明**\n"
                    "• 支持关键词匹配\n"
                    "• 智能内容去重\n"
                    "• 灵活筛选规则\n"
                    "• 媒体文件转发\n"
                )
            else:
                total_count = pagination.get('total_count', 0)
                current_page = pagination.get('page', 0) + 1
                total_pages = pagination.get('total_pages', 1)
                page_size = pagination.get('page_size', 10)
                start_index = (current_page - 1) * page_size + 1
                end_index = min(current_page * page_size, total_count)
                
                text += f"📋 **规则列表概览** (共 {total_count:,} 条，当前第 {current_page}/{total_pages} 页，显示 {start_index}-{end_index} 条)\n\n"
                
                for i, rule in enumerate(rules, start_index):
                    source = rule.get('source_chat', {})
                    target = rule.get('target_chat', {})
                    
                    status_icon = "🟢" if rule.get('enabled', True) else "🔴"
                    status_text = "运行中" if rule.get('enabled', True) else "已停用"
                    dedup_icon = "🧹 去重" if rule.get('enable_dedup', False) else "📝 普通"
                    
                    source_name = source.get('title', 'Unknown')[:15]
                    target_name = target.get('title', 'Unknown')[:15]
                    if len(source.get('title', '')) > 15:
                        source_name += "..."
                    if len(target.get('title', '')) > 15:
                        target_name += "..."
                    
                    keywords_count = rule.get('keywords_count', 0)
                    replace_count = rule.get('replace_rules_count', 0)
                    
                    text += (
                        f"{status_icon} **规则 {rule['id']}** ({status_text})\n"
                        f"  📤 **源**：{source_name}\n"
                        f"  📥 **目标**：{target_name}\n"
                        f"  🏷️ **配置**：{keywords_count} 关键词 • {replace_count} 替换 • {dedup_icon}\n\n"
                    )
            
            # 分页信息
            current_page = pagination.get('page', 0) + 1
            total_pages = pagination.get('total_pages', 1)
            if total_pages > 1:
                text += (
                    "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━\n"
                    f"📄 **分页导航** 第 {current_page}/{total_pages} 页\n"
                )
            
            buttons = []
            
            # 规则操作按钮
            if rules:
                rule_buttons = []
                for rule in rules[:10]:
                    rule_buttons.append(Button.inline(
                        f"📝 规则{rule['id']}", 
                        f"new_menu:edit_rule:{rule['id']}"
                    ))
                
                for i in range(0, len(rule_buttons), 2):
                    row = rule_buttons[i:i+2]
                    buttons.append(row)
            
            # 分页按钮
            page_buttons = []
            if pagination.get('has_prev', False):
                page_buttons.append(Button.inline("⬅️ 上页", f"new_menu:rule_list_page:{pagination.get('page', 0) - 1}"))
            else:
                page_buttons.append(Button.inline("⬅️ 上页", "noop"))
                
            if pagination.get('has_next', False):
                page_buttons.append(Button.inline("➡️ 下页", f"new_menu:rule_list_page:{pagination.get('page', 0) + 1}"))
            else:
                page_buttons.append(Button.inline("➡️ 下页", "noop"))
            
            buttons.append(page_buttons)
            
            buttons.extend([
                [Button.inline("➕ 创建新规则", "new_menu:create_rule"),
                 Button.inline("📊 统计分析", "new_menu:rule_statistics")],
                [Button.inline("🔗 批量管理", "new_menu:multi_source_management"),
                 Button.inline("🔍 搜索规则", "new_menu:search_rules")],
                [Button.inline("🎛️ 全局筛选设置", "new_menu:filter_settings"),
                 Button.inline("🔄 刷新数据", "new_menu:forward_management")],
                [Button.inline("🔙 返回转发中心", "new_menu:forward_hub")]
            ])
            
            return {'text': text, 'buttons': buttons}
            
        except Exception as e:
            return self.create_error_view("加载失败", "页面数据加载出现问题，请稍后重试。", "new_menu:forward_hub")

    def render_rule_detail(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染规则详情页面"""
        try:
            rule = data.get('rule', {})
            rid = rule.get('id', 'Unknown')
            
            text = f"📋 **规则详情 - {rid}**\n\n"
            
            source = rule.get('source_chat', {})
            target = rule.get('target_chat', {})
            
            text += "📤 **源聊天**\n"
            text += f"   {source.get('title', 'Unknown')} ({source.get('telegram_chat_id', 'Unknown')})\n\n"
            
            text += "📥 **目标聊天**\n"
            text += f"   {target.get('title', 'Unknown')} ({target.get('telegram_chat_id', 'Unknown')})\n\n"
            
            settings = rule.get('settings', {})
            text += "⚙️ **规则设置**\n"
            text += f"   启用状态: {'✅ 已启用' if settings.get('enabled', True) else '❌ 已禁用'}\n"
            text += f"   智能去重: {'✅ 已启用' if settings.get('enable_dedup', False) else '❌ 已禁用'}\n"
            
            if settings.get('enable_dedup', False):
                text += f"   时间窗口: {settings.get('dedup_time_window_hours', 24)} 小时\n"
                text += f"   相似度阈值: {settings.get('similarity_threshold', 0.85):.0%}\n"
            
            text += "\n"
            
            keywords = rule.get('keywords', [])
            text += f"🏷️ **关键词** ({len(keywords)} 个)\n"
            if keywords:
                for kw in keywords[:5]:
                    text += f"   • {kw}\n"
                if len(keywords) > 5:
                    text += f"   ... 还有 {len(keywords) - 5} 个\n"
            else:
                text += "   无关键词设置\n"
            text += "\n"
            
            replace_rules = rule.get('replace_rules', [])
            text += f"🔄 **替换规则** ({len(replace_rules)} 个)\n"
            if replace_rules:
                for rr in replace_rules[:3]:
                    text += f"   • {rr.get('pattern', '')} → {rr.get('replacement', '')}\n"
                if len(replace_rules) > 3:
                    text += f"   ... 还有 {len(replace_rules) - 3} 个\n"
            else:
                text += "   无替换规则设置\n"
            
            buttons = [
                [
                    Button.inline("🟢/🔴 切换状态", f"new_menu:toggle_rule:{rid}"),
                    Button.inline("🗑️ 删除规则", f"new_menu:delete_rule_confirm:{rid}")
                ],
                [
                    Button.inline("📝 基础转发设置", f"new_menu:rule_basic_settings:{rid}"),
                    Button.inline("🎨 内容显示设置", f"new_menu:rule_display_settings:{rid}")
                ],
                [
                    Button.inline("🚀 高级功能配置", f"new_menu:rule_advanced_settings:{rid}"),
                    Button.inline("🎬 媒体过滤规则", f"media_settings:{rid}")
                ],
                [
                    Button.inline("🤖 AI 增强处理", f"ai_settings:{rid}"),
                    Button.inline("🔔 推送/同步设置", f"new_menu:rule_sync_push:{rid}")
                ],
                [
                    Button.inline("🏷️ 管理关键词", f"new_menu:keywords:{rid}"),
                    Button.inline("🔄 管理替换规则", f"new_menu:replaces:{rid}")
                ],
                [Button.inline("👈 返回列表", "new_menu:list_rules:0")]
            ]
            
            return {'text': text, 'buttons': buttons}
            
        except Exception:
            return self.create_error_view("详情加载失败", "错误", "new_menu:list_rules:0")

    def render_rule_basic_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染规则基础转发设置"""
        rule = data.get('rule', {})
        rid = rule.get('id')
        
        text = f"⚙️ **基础转发设置 - {rid}**\n\n"
        text += "配置转发的核心行为，如运行模式、转发身份等。\n\n"
        
        forward_mode_map = {
            'blacklist': '仅黑名单',
            'whitelist': '仅白名单',
            'blacklist_then_whitelist': '先黑后白',
            'whitelist_then_blacklist': '先白后黑'
        }
        
        buttons = [
            [Button.inline(f"运行状态: {'🟢 开启' if rule.get('enabled') else '🔴 禁用'}", f"new_menu:toggle_rule_set:{rid}:enabled")],
            [Button.inline(f"转发方式: {'🤖 机器人' if rule.get('use_bot') else '👤 个人账号'}", f"new_menu:toggle_rule_set:{rid}:use_bot")],
            [Button.inline(f"过滤模式: {forward_mode_map.get(rule.get('forward_mode'), rule.get('forward_mode'))}", f"new_menu:toggle_rule_set:{rid}:forward_mode")],
            [Button.inline(f"处理方式: {'✍️ 编辑' if rule.get('handle_mode') == 'edit' else '📤 转发'}", f"new_menu:toggle_rule_set:{rid}:handle_mode")],
            [Button.inline(f"删除原消息: {'✅ 是' if rule.get('is_delete_original') else '❌ 否'}", f"new_menu:toggle_rule_set:{rid}:is_delete_original")],
            [Button.inline("👈 返回规则详情", f"new_menu:rule_detail:{rid}")]
        ]
        return {'text': text, 'buttons': buttons}

    def render_rule_display_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染规则内容显示设置"""
        rule = data.get('rule', {})
        rid = rule.get('id')
        
        text = f"🎨 **内容显示设置 - {rid}**\n\n"
        text += "配置转发后消息的外观展示，如图标、链接、发送者信息等。\n\n"
        
        mode_val = rule.get('message_mode', 'MARKDOWN')
        if hasattr(mode_val, 'value'):
            mode_val = mode_val.value
        elif hasattr(mode_val, 'name'):
            mode_val = mode_val.name
        
        buttons = [
            [Button.inline(f"消息格式: {str(mode_val).upper()}", f"new_menu:toggle_rule_set:{rid}:message_mode")],
            [Button.inline(f"预览链接: {'✅ 开启' if rule.get('is_preview') else '❌ 关闭'}", f"new_menu:toggle_rule_set:{rid}:is_preview")],
            [Button.inline(f"原始发送者: {'✅ 显示' if rule.get('is_original_sender') else '❌ 隐藏'}", f"new_menu:toggle_rule_set:{rid}:is_original_sender")],
            [Button.inline(f"发送时间: {'✅ 显示' if rule.get('is_original_time') else '❌ 隐藏'}", f"new_menu:toggle_rule_set:{rid}:is_original_time")],
            [Button.inline(f"原始链接: {'✅ 附带' if rule.get('is_original_link') else '❌ 不附带'}", f"new_menu:toggle_rule_set:{rid}:is_original_link")],
            [Button.inline(f"过滤发送者信息: {'✅ 是' if rule.get('is_filter_user_info') else '❌ 否'}", f"new_menu:toggle_rule_set:{rid}:is_filter_user_info")],
            [Button.inline(f"显示评论按钮: {'✅ 是' if rule.get('enable_comment_button') else '❌ 否'}", f"new_menu:toggle_rule_set:{rid}:enable_comment_button")],
            [Button.inline("👈 返回规则详情", f"new_menu:rule_detail:{rid}")]
        ]
        return {'text': text, 'buttons': buttons}

    def render_rule_advanced_settings(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染规则高级功能设置"""
        rule = data.get('rule', {})
        rid = rule.get('id')
        
        text = f"🚀 **高级功能配置 - {rid}**\n\n"
        text += "配置转发的流转逻辑，如去重、延迟、同步等高级控制。\n\n"
        
        buttons = [
            [Button.inline(f"智能去重: {'✅ 开启' if rule.get('enable_dedup') else '❌ 关闭'}", f"new_menu:toggle_rule_set:{rid}:enable_dedup")],
            [Button.inline(f"延迟处理: {'✅ 开启' if rule.get('enable_delay') else '❌ 关闭'}", f"new_menu:toggle_rule_set:{rid}:enable_delay")],
            [Button.inline(f"延迟时间: {rule.get('delay_seconds', 0)} 秒", f"new_menu:set_rule_val:{rid}:delay_seconds")],
            [Button.inline(f"强制纯转发: {'✅ 是' if rule.get('force_pure_forward') else '❌ 否'}", f"new_menu:toggle_rule_set:{rid}:force_pure_forward")],
            [Button.inline(f"规则快速同步: {'✅ 开启' if rule.get('enable_sync') else '❌ 关闭'}", f"new_menu:toggle_rule_set:{rid}:enable_sync")],
            [Button.inline("👈 返回规则详情", f"new_menu:rule_detail:{rid}")]
        ]
        return {'text': text, 'buttons': buttons}
    
    def render_rule_statistics(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染规则统计页面"""
        try:
            stats = data.get('statistics', {})
            total = stats.get('total_rules', 0)
            enabled = stats.get('enabled_rules', 0)
            disabled = stats.get('disabled_rules', 0)
            dedup_enabled = stats.get('dedup_enabled_rules', 0)
            percentage = stats.get('enabled_percentage', 0)
            
            text = "📊 **转发规则统计**\n\n"
            text += "📈 **总体统计**\n"
            text += f"总规则数: {total} 条\n"
            text += f"已启用: {enabled} 条 ({percentage:.1f}%)\n"
            text += f"已禁用: {disabled} 条\n"
            text += f"启用去重: {dedup_enabled} 条\n\n"
            
            if total > 0:
                enabled_bars = int(enabled / total * 10)
                disabled_bars = 10 - enabled_bars
                text += "📊 **启用状态分布**\n"
                text += f"{'🟢' * enabled_bars}{'⚪' * disabled_bars}\n"
                text += f"启用: {enabled_bars}/10 • 禁用: {disabled_bars}/10\n\n"
            
            if total > 0:
                dedup_percentage = (dedup_enabled / total) * 100
                text += "🧹 **去重功能使用率**\n"
                text += f"{dedup_percentage:.1f}% 的规则启用了智能去重\n"
            
            buttons = [
                [Button.inline("📋 查看规则列表", "new_menu:forward_management"),
                 Button.inline("➕ 创建新规则", "new_menu:create_rule")],
                [Button.inline("🔄 刷新统计", "new_menu:rule_statistics"),
                 Button.inline("👈 返回转发中心", "new_menu:forward_hub")]
            ]
            return {'text': text, 'buttons': buttons}
        except Exception:
            return self.create_error_view("统计加载失败", "错误", "new_menu:forward_hub")

    def render_manage_keywords(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染管理关键词页面"""
        try:
            rule_id = data.get('rule_id')
            keywords = data.get('keywords', [])
            text = f"🏷️ **管理关键词**\n\n规则: {rule_id}\n"
            text += f"当前共有 {len(keywords)} 个关键词\n\n"
            if keywords:
                for item in keywords:
                    tag = '(正则)' if item.get('is_regex') else ''
                    mode = '黑' if item.get('is_blacklist', True) else '白'
                    text += f"{item.get('index')}. [{mode}]{tag} {item.get('text','')}\n"
            else:
                text += "暂无关键词\n"

            buttons = [
                [Button.inline("➕ 添加关键词", f"new_menu:kw_add:{rule_id}")],
                [Button.inline("🗑️ 删除关键词", f"new_menu:kw_delete:{rule_id}")],
                [Button.inline("👈 返回规则详情", f"new_menu:edit_rule_settings:{rule_id}")]
            ]
            return {'text': text, 'buttons': buttons}
        except Exception:
            return self.create_error_view("加载失败", "错误", f"new_menu:edit_rule_settings:{data.get('rule_id')}")

    def render_manage_replace_rules(self, data: Dict[str, Any]) -> Dict[str, Any]:
        """渲染管理替换规则页面"""
        try:
            rule_id = data.get('rule_id')
            replace_rules = data.get('replace_rules', [])
            text = f"🔄 **管理替换规则**\n\n规则: {rule_id}\n"
            text += f"当前共有 {len(replace_rules)} 条替换规则\n\n"
            if replace_rules:
                for rr in replace_rules:
                    pattern = rr.get('pattern', '')
                    replacement = rr.get('replacement', '')
                    text += f"{rr.get('index')}. {pattern} → {replacement}\n"
            else:
                text += "暂无替换规则\n"

            buttons = [
                [Button.inline("➕ 新增替换规则", f"new_menu:rr_add:{rule_id}")],
                [Button.inline("🗑️ 删除替换规则", f"new_menu:rr_delete:{rule_id}")],
                [Button.inline("👈 返回规则详情", f"new_menu:edit_rule_settings:{rule_id}")]
            ]
            return {'text': text, 'buttons': buttons}
        except Exception:
             return self.create_error_view("加载失败", "错误", f"new_menu:edit_rule_settings:{data.get('rule_id')}")
