"""
Command Handlers 单元测试
测试 Telegram 命令处理器的核心逻辑
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
import shlex
import sys

# sys.modules mocks are now in conftest.py

class TestBasicCommands:
    """测试基础命令：/start, /help, /changelog"""
    
    @pytest.mark.asyncio
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    async def test_start_command(self, mock_reply_and_delete, mock_async_delete):
        """测试 /start 命令返回欢迎消息"""
        from handlers.command_handlers import handle_start_command
        
        mock_event = MagicMock()
        mock_event.client = MagicMock()
        mock_event.message = MagicMock()
        mock_event.message.chat_id = 123
        mock_event.message.id = 456
        
        await handle_start_command(mock_event)
        
        mock_reply_and_delete.assert_called_once()
        call_args = mock_reply_and_delete.call_args[0]
        welcome_msg = call_args[1]
        assert "欢迎" in welcome_msg or "Welcome" in welcome_msg
    
    @pytest.mark.asyncio
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    async def test_help_command(self, mock_reply_and_delete, mock_async_delete):
        """测试 /help 命令返回帮助信息"""
        from handlers.command_handlers import handle_help_command
        
        mock_event = MagicMock()
        mock_event.client = MagicMock()
        mock_event.message = MagicMock()
        mock_event.message.chat_id = 123
        mock_event.message.id = 456
        
        await handle_help_command(mock_event, "help")
        
        mock_reply_and_delete.assert_called_once()
        call_args = mock_reply_and_delete.call_args[0]
        help_msg = call_args[1]
        assert "/start" in help_msg
        assert "/help" in help_msg
    
    @pytest.mark.asyncio
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    async def test_changelog_command(self, mock_reply_and_delete, mock_async_delete):
        """测试 /changelog 命令返回更新日志"""
        from handlers.command_handlers import handle_changelog_command
        
        mock_event = MagicMock()
        mock_event.client = MagicMock()
        mock_event.message = MagicMock()
        mock_event.message.chat_id = 123
        mock_event.message.id = 456
        
        await handle_changelog_command(mock_event)
        
        mock_reply_and_delete.assert_called_once()


class TestKeywordCommands:
    """测试关键词管理命令"""
    
    @pytest.mark.asyncio
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    async def test_add_keyword_no_args(self, mock_reply, mock_delete):
        """测试 /add 命令无参数时返回用法"""
        from handlers.command_handlers import handle_add_command
        
        mock_event = MagicMock()
        mock_event.chat_id = 123
        mock_event.client = MagicMock()
        mock_event.message = MagicMock()
        mock_event.message.chat_id = 123
        mock_event.message.id = 456
        
        await handle_add_command(mock_event, "add", [])
        
        # 无参数应该返回用法提示
        mock_reply.assert_called()

    @pytest.mark.asyncio
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    @patch('handlers.command_handlers._add_keywords_to_rule', new_callable=AsyncMock)
    @patch('handlers.command_handlers._parse_keywords', new_callable=AsyncMock)
    async def test_add_keyword_success(self, mock_parse, mock_add, mock_reply, mock_delete):
        """测试 /add 命令成功添加"""
        from handlers.command_handlers import handle_add_command
        
        mock_event = MagicMock()
        mock_event.message.text = "/add keyword1 keyword2"
        mock_event.client = AsyncMock()
        mock_event.chat_id = 123
        mock_event.message.id = 456
        
        mock_parse.return_value = ["keyword1", "keyword2"]
        mock_add.return_value = (MagicMock(), MagicMock(), {"message": "Success", "success": True})
        
        await handle_add_command(mock_event, "add", ["keyword1", "keyword2"])
        
        # 验证是否调用了 reply_and_delete (通过导入的 reply_and_delete 补丁)
        # 这里需要确保 patches 匹配
        args, kwargs = mock_reply.call_args
        assert "Success" in args[1]


class TestRuleCommands:
    """测试规则管理命令"""
    
    @pytest.mark.asyncio
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    async def test_bind_command_no_args(self, mock_reply, mock_delete):
        """测试 /bind 命令无参数时返回提示"""
        from handlers.command_handlers import handle_bind_command
        
        mock_event = MagicMock()
        mock_event.chat_id = 123
        mock_event.client = MagicMock()
        mock_event.message = MagicMock()
        mock_event.message.chat_id = 123
        mock_event.message.id = 456
        mock_client = MagicMock()
        
        await handle_bind_command(mock_event, mock_client, [])
        
        # 应该返回用法提示
        mock_reply.assert_called()

    @pytest.mark.asyncio
    @patch('handlers.command_handlers.rule_management_service')
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    @patch('core.container.container')
    async def test_bind_command_success(self, mock_container, mock_reply, mock_delete, mock_service):
        """测试 /bind 命令成功"""
        from handlers.command_handlers import handle_bind_command
        
        mock_event = MagicMock()
        mock_event.message.text = "/bind https://t.me/src https://t.me/dst"
        mock_event.chat_id = 123
        
        mock_service.bind_chat = AsyncMock(return_value={
            'success': True, 
            'rule_id': 1, 
            'source_name': 'Source', 
            'target_name': 'Target',
            'is_new': True
        })
        
        await handle_bind_command(mock_event, MagicMock(), ["https://t.me/src", "https://t.me/dst"])
        
        mock_reply.assert_called()
        args, kwargs = mock_reply.call_args
        assert "✅ 已创建" in args[1]
        assert "Source" in args[1]
        assert "Target" in args[1]

class TestSettingsCommands:
    """测试设置与切换命令"""
    
    @pytest.mark.asyncio
    @patch('handlers.button.new_menu_system.new_menu_system')
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    async def test_settings_command(self, mock_delete, mock_menu):
        """测试 /settings 命令显示主菜单"""
        from handlers.command_handlers import handle_settings_command
        
        mock_event = MagicMock()
        mock_event.message.chat_id = 123
        mock_event.message.id = 456
        mock_event.sender.id = 123
        mock_event.client = MagicMock()
        
        mock_menu.show_main_menu = AsyncMock()
        await handle_settings_command(mock_event, "settings", [])
        
        # Verify show_main_menu was called
        mock_menu.show_main_menu.assert_called_once_with(mock_event)
        # Verify async_delete_user_message was called
        mock_delete.assert_called_once()


class TestReplaceCommands:
    """测试替换规则命令"""
    
    @pytest.mark.asyncio
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    async def test_replace_command_no_args(self, mock_reply, mock_delete):
        """测试 /replace 命令无参数时返回提示"""
        from handlers.command_handlers import handle_replace_command
        
        mock_event = MagicMock()
        mock_event.chat_id = 123
        mock_event.client = MagicMock()
        mock_event.message = MagicMock()
        mock_event.message.chat_id = 123
        mock_event.message.id = 456
        
        await handle_replace_command(mock_event, [])
        
        mock_reply.assert_called()


class TestDedupCommands:
    """测试去重相关命令"""
    
    @pytest.mark.asyncio
    @patch('handlers.command_handlers.RuleQueryService')
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    @patch('core.container.container')
    async def test_dedup_enable_command_no_rule(self, mock_container, mock_reply, mock_delete, mock_query):
        """测试 /dedup 命令无规则时的处理"""
        from handlers.command_handlers import handle_dedup_enable_command
        
        mock_event = MagicMock()
        mock_event.chat_id = 123
        
        # Mock session
        mock_session = AsyncMock()
        mock_container.db.session.return_value.__aenter__.return_value = mock_session
        
        # Mock Query Tool returning None
        mock_query.get_current_rule_for_chat = AsyncMock(return_value=None)
        
        await handle_dedup_enable_command(mock_event, [])
        
        mock_reply.assert_called()
        assert "❌ 未找到管理上下文" in mock_reply.call_args[0][1]

    @pytest.mark.asyncio
    @patch('handlers.command_handlers.rule_management_service')
    @patch('handlers.command_handlers.RuleQueryService')
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    @patch('core.container.container')
    async def test_dedup_enable_command_success(self, mock_container, mock_reply, mock_delete, mock_query, mock_service):
        """测试 /dedup 成功切换"""
        from handlers.command_handlers import handle_dedup_enable_command
        
        mock_event = MagicMock()
        mock_query.get_current_rule_for_chat = AsyncMock(return_value=(MagicMock(id=1, enable_dedup=False), MagicMock(name="Source")))
        
        mock_service.update_rule = AsyncMock(return_value={"success": True})
        
        await handle_dedup_enable_command(mock_event, [])
        
        mock_reply.assert_called()
        assert "✅ 已开启去重" in mock_reply.call_args[0][1]


class TestMediaSettingsCommands:
    """测试媒体筛选设置命令"""
    
    @pytest.mark.asyncio
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    async def test_set_duration_command_no_args(self, mock_reply):
        """测试 /set_duration 无参数时返回用法"""
        from handlers.command_handlers import handle_set_duration_command
        
        mock_event = MagicMock()
        mock_event.chat_id = 123
        
        await handle_set_duration_command(mock_event, [])
        
        mock_reply.assert_called()
    
    @pytest.mark.asyncio
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    async def test_set_resolution_command_no_args(self, mock_reply):
        """测试 /set_resolution 无参数时返回用法"""
        from handlers.command_handlers import handle_set_resolution_command
        
        mock_event = MagicMock()
        mock_event.chat_id = 123
        
        await handle_set_resolution_command(mock_event, [])
        
        mock_reply.assert_called()
    
    @pytest.mark.asyncio
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    async def test_set_size_command_no_args(self, mock_reply, mock_delete):
        """测试 /set_size 无参数时返回用法"""
        from handlers.command_handlers import handle_set_size_command
        
        mock_event = MagicMock()
        mock_event.chat_id = 123
        mock_event.message = MagicMock()
        mock_event.message.chat_id = 123
        mock_event.message.id = 456
        
        await handle_set_size_command(mock_event, [])
        
        mock_reply.assert_called()


class TestUtilityFunctions:
    """测试命令处理器中的工具函数"""
    
    @pytest.mark.skip(reason="模块导入污染问题 - 需要在 conftest.py 中修复 Mock 策略")
    def test_parse_size_to_kb(self):
        """测试大小解析函数"""
        from handlers.command_handlers import _parse_size_to_kb
        
        # 测试各种单位
        assert _parse_size_to_kb("100") == 100
        assert _parse_size_to_kb("100K") == 100
        assert _parse_size_to_kb("100k") == 100
        assert _parse_size_to_kb("1M") == 1024
        assert _parse_size_to_kb("1m") == 1024
        assert _parse_size_to_kb("1G") == 1024 * 1024
        assert _parse_size_to_kb("1g") == 1024 * 1024


class TestClearCommands:
    """测试清除命令"""
    
    @pytest.mark.asyncio
    @patch('handlers.command_handlers.rule_management_service')
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    async def test_clear_all_command(self, mock_reply, mock_delete, mock_service):
        """测试 /clear_all 命令"""
        from handlers.command_handlers import handle_clear_all_command
        
        mock_event = MagicMock()
        mock_event.chat_id = 123
        mock_event.client = MagicMock()
        mock_event.message = MagicMock()
        mock_event.message.chat_id = 123
        mock_event.message.id = 456
        
        # Mock 服务返回
        mock_service.clear_all_data = AsyncMock(return_value={"success": True, "message": "数据已清空"})
        
        await handle_clear_all_command(mock_event)
        
        mock_reply.assert_called()


class TestRemoveCommands:
    """测试删除命令"""
    
    @pytest.mark.asyncio
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    @patch('handlers.command_handlers.rule_management_service')
    async def test_remove_keyword_command(self, mock_service, mock_reply, mock_delete):
        """测试 /remove_keyword 命令"""
        from handlers.command_handlers import handle_remove_command
        
        mock_event = MagicMock()
        mock_event.chat_id = 123
        mock_event.message = MagicMock()
        mock_event.message.chat_id = 123
        mock_event.message.id = 456
        
        mock_service.remove_keyword = AsyncMock(return_value={"success": True})
        
        await handle_remove_command(mock_event, "remove_keyword", ["关键词1"])
        
        mock_reply.assert_called()
    
    @pytest.mark.asyncio
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    @patch('handlers.command_handlers.rule_management_service')
    async def test_remove_replace_command(self, mock_service, mock_reply, mock_delete):
        """测试 /remove_replace 命令"""
        from handlers.command_handlers import handle_remove_command
        
        mock_event = MagicMock()
        mock_event.chat_id = 123
        mock_event.message = MagicMock()
        mock_event.message.chat_id = 123
        mock_event.message.id = 456
        
        mock_service.remove_replace = AsyncMock(return_value={"success": True})
        
        await handle_remove_command(mock_event, "remove_replace", ["1"])
        
        mock_reply.assert_called()


class TestListCommands:
    """测试列表显示命令"""
    
    @pytest.mark.asyncio
    @patch('handlers.command_handlers.RuleQueryService')
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('core.container.container')
    async def test_list_keyword(self, mock_container, mock_delete, mock_reply, mock_query):
        """测试 /list_keyword"""
        from handlers.command_handlers import handle_list_keyword_command
        
        mock_event = MagicMock()
        mock_query.get_current_rule_for_chat = AsyncMock(return_value=(MagicMock(id=1, add_mode=0), MagicMock(name="Source")))
        
        # Mock session and result
        mock_session = AsyncMock()
        mock_container.db.session.return_value.__aenter__.return_value = mock_session
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [MagicMock(keyword="kw1", is_regex=False)]
        mock_session.execute.return_value = mock_result
        
        await handle_list_keyword_command(mock_event)
        
        mock_reply.assert_called()
        assert "kw1" in mock_reply.call_args[0][1]

    @pytest.mark.asyncio
    @patch('handlers.command_handlers.RuleQueryService')
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('core.container.container')
    async def test_list_replace(self, mock_container, mock_delete, mock_reply, mock_query):
        """测试 /list_replace"""
        from handlers.command_handlers import handle_list_replace_command
        
        mock_event = MagicMock()
        mock_query.get_current_rule_for_chat = AsyncMock(return_value=(MagicMock(id=1), MagicMock(name="Source")))
        
        mock_session = AsyncMock()
        mock_container.db.session.return_value.__aenter__.return_value = mock_session
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [MagicMock(pattern="pat1", content="rep1")]
        mock_session.execute.return_value = mock_result
        
        await handle_list_replace_command(mock_event)
        
        mock_reply.assert_called_once()
        res_text = mock_reply.call_args[0][1]
        assert "匹配 `pat1` -> 替换为 `rep1`" in res_text


class TestMaintenanceCommands:
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    @patch('models.models.get_database_info', new_callable=MagicMock)
    async def test_db_info_command(self, mock_get_info, mock_reply):
        mock_get_info.return_value = {
            'db_size': 1024,
            'wal_size': 512,
            'total_size': 1536,
            'table_count': 10,
            'index_count': 5
        }
        mock_event = MagicMock()
        
        from handlers.command_handlers import handle_db_info_command
        await handle_db_info_command(mock_event)
        
        mock_reply.assert_called_once()
        assert "数据库详情" in mock_reply.call_args[0][1]

    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('handlers.command_handlers.get_logger')
    async def test_system_status_command(self, mock_get_logger, mock_delete, mock_reply):
        # 我们需要 Patch 实际被定义的模块位置，注意 handle_system_status_command 可能会重新导入
        # 最简单的方法是 Patch psutil 和 models.models 里的相关同步函数
        
        with patch('psutil.cpu_percent', return_value=10.0), \
             patch('psutil.virtual_memory') as mock_mem, \
             patch('psutil.disk_usage') as mock_disk, \
             patch('models.models.get_database_info') as mock_db_info, \
             patch('models.models.get_db_health') as mock_db_health:
            
            mock_mem.return_value.percent = 50.0
            mock_mem.return_value.used = 4 * 1024**3
            mock_mem.return_value.total = 8 * 1024**3
            mock_disk.return_value.percent = 30.0
            mock_disk.return_value.used = 100 * 1024**3
            mock_disk.return_value.total = 500 * 1024**3
            
            mock_db_info.return_value = {'total_size': 10 * 1024**2, 'table_count': 5, 'index_count': 2}
            mock_db_health.return_value = {'status': 'healthy'}
            
            mock_event = MagicMock()
            mock_event.client = MagicMock()
            mock_event.message.chat_id = 123
            mock_event.message.id = 456
            
            from handlers.command_handlers import handle_system_status_command
            await handle_system_status_command(mock_event)
            
            # 如果进入了 Exception 分支，mock_reply 会被调用，内容为 "获取系统状态失败"
            # 我们可以打印出来看看到底报了什么错
            if mock_reply.called and "失败" in mock_reply.call_args[0][1]:
                print(f"DEBUG: system_status failed with: {mock_reply.call_args[0][1]}")
            
            mock_reply.assert_called_once()
            assert "系统状态报告" in mock_reply.call_args[0][1]
            assert "10.0%" in mock_reply.call_args[0][1]
            assert "healthy" in mock_reply.call_args[0][1]


class TestUFBCommands:
    @patch('handlers.command_handlers.rule_management_service', new_callable=AsyncMock)
    @patch('services.rule_service.RuleQueryService.get_current_rule_for_chat', new_callable=AsyncMock)
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    @patch('core.container.container')
    async def test_ufb_bind_command_success(self, mock_container, mock_reply, mock_delete, mock_get_rule, mock_service):
        mock_rule = MagicMock(id=1, ufb_domain=None)
        mock_source = MagicMock()
        mock_source.name = "Source"
        mock_get_rule.return_value = (mock_rule, mock_source)
        
        mock_event = MagicMock()
        mock_event.message.text = "/ufb_bind example.com content"
        mock_service.update_rule.return_value = {'success': True}
        
        from handlers.command_handlers import handle_ufb_bind_command
        await handle_ufb_bind_command(mock_event, "ufb_bind")
        
        mock_service.update_rule.assert_called_once_with(
            rule_id=1, ufb_domain="example.com", ufb_item="content", is_ufb=True
        )
        # Check call arguments, avoiding exact match issues with mock objects
        args, kwargs = mock_reply.call_args
        assert "✅ 已绑定 UFB" in args[1]
        assert "Source" in args[1]

    @patch('handlers.command_handlers._get_current_rule_for_chat', new_callable=AsyncMock)
    @patch('handlers.command_handlers.async_delete_user_message', new_callable=AsyncMock)
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    @patch('core.container.container')
    async def test_ufb_item_change_command(self, mock_container, mock_reply, mock_delete, mock_get_rule):
        mock_rule = MagicMock(id=1)
        mock_source = MagicMock()
        mock_source.name = "Source"
        mock_get_rule.return_value = (mock_rule, mock_source)
        
        mock_event = MagicMock()
        mock_event.client = MagicMock()
        mock_event.message.chat_id = 123
        mock_event.message.id = 456
        
        from handlers.command_handlers import handle_ufb_item_change_command
        await handle_ufb_item_change_command(mock_event, "ufb_item_change")
        
        mock_reply.assert_called_once()
        assert "请选择要切换的UFB同步配置类型" in mock_reply.call_args[0][1]
        # Check if buttons are present
        assert "buttons" in mock_reply.call_args[1]


class TestAdminCommands:
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    async def test_admin_panel_command(self, mock_reply):
        mock_event = AsyncMock()
        
        from handlers.command_handlers import handle_admin_panel_command
        await handle_admin_panel_command(mock_event)
        
        mock_event.reply.assert_called_once()
        assert "系统管理面板" in mock_event.reply.call_args[0][0]
        assert "buttons" in mock_event.reply.call_args[1]


class TestExportImportCommands:
    @patch('handlers.command_handlers.rule_management_service', new_callable=AsyncMock)
    @patch('services.rule_service.RuleQueryService.get_current_rule_for_chat', new_callable=AsyncMock)
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    @patch('handlers.command_handlers.respond_and_delete', new_callable=AsyncMock)
    @patch('core.container.container')
    async def test_export_replace_command(self, mock_container, mock_respond, mock_reply, mock_get_rule, mock_service):
        mock_rule = MagicMock(id=1)
        mock_source = MagicMock()
        mock_source.name = "Source"
        mock_get_rule.return_value = (mock_rule, mock_source)
        
        mock_service.export_replace_rules.return_value = ["pat1\trep1"]
        
        mock_event = MagicMock()
        mock_event.client = AsyncMock()
        
        from handlers.command_handlers import handle_export_replace_command
        with patch('builtins.open', mock_open()):
            await handle_export_replace_command(mock_event, mock_event.client)
        
        mock_event.client.send_file.assert_called_once()
        mock_respond.assert_called_once()
        assert "Source" in mock_respond.call_args[0][1]

    @patch('handlers.command_handlers.rule_management_service', new_callable=AsyncMock)
    @patch('services.rule_service.RuleQueryService.get_current_rule_for_chat', new_callable=AsyncMock)
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    @patch('core.container.container')
    async def test_import_replace_command(self, mock_container, mock_reply, mock_get_rule, mock_service):
        mock_rule = MagicMock(id=1)
        mock_source = MagicMock()
        mock_source.name = "Source"
        mock_get_rule.return_value = (mock_rule, mock_source)
        
        mock_event = MagicMock()
        mock_event.message.file = MagicMock()
        mock_event.message.download_media = AsyncMock(return_value="temp.txt")
        
        mock_service.import_replace_rules.return_value = {'success': True, 'imported_count': 5}
        
        # Mock async with aiofiles.open
        mock_aio = MagicMock()
        mock_file = AsyncMock()
        mock_file.read.return_value = "pat1\trep1"
        mock_aio.return_value.__aenter__.return_value = mock_file
        
        with patch('aiofiles.open', mock_aio):
            from handlers.command_handlers import handle_import_command
            await handle_import_command(mock_event, "import_replace")
        
        mock_service.import_replace_rules.assert_called_once()
        args, kwargs = mock_reply.call_args
        assert "成功导入 5 条" in args[1]
        assert "Source" in args[1]


class TestMediaActionCommands:
    @patch('core.container.container')
    @patch('handlers.command_handlers.reply_and_delete', new_callable=AsyncMock)
    async def test_handle_download_command(self, mock_reply, mock_container):
        mock_event = MagicMock()
        mock_event.is_reply = True
        mock_reply_msg = AsyncMock()
        mock_reply_msg.media = True
        mock_reply_msg.id = 789
        mock_event.get_reply_message = AsyncMock(return_value=mock_reply_msg)
        mock_event.chat_id = 456
        
        mock_container.task_repo = AsyncMock()
        
        from handlers.command_handlers import handle_download_command
        await handle_download_command(mock_event, MagicMock(), [])
        
        mock_container.task_repo.push.assert_called_once()
        assert mock_container.task_repo.push.call_args[1]['task_type'] == "download_file"
        mock_reply.assert_called_once()
        assert "已加入下载队列" in mock_reply.call_args[0][1]

    @patch('handlers.button.session_management.session_manager', new_callable=AsyncMock)
    async def test_handle_dedup_scan_command(self, mock_session_manager):
        mock_event = MagicMock()
        mock_event.chat_id = 123
        mock_event.respond = AsyncMock()
        
        mock_session_manager.scan_duplicate_messages.return_value = {"Video": 5}
        
        from handlers.command_handlers import handle_dedup_scan_command
        await handle_dedup_scan_command(mock_event, [])
        
        mock_session_manager.scan_duplicate_messages.assert_called_once()
        mock_event.respond.assert_called_once()
        # Verify the progress message update (edit is called on the object returned by respond)
        mock_progress = mock_event.respond.return_value
        mock_progress.edit.assert_called()
        assert "扫描完成" in mock_progress.edit.call_args[0][0]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
