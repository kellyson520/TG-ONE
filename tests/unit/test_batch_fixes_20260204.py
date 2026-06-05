import pytest
import asyncio
from unittest.mock import MagicMock, patch, AsyncMock
from models.models import ForwardRule
from enums.enums import ForwardMode
from services.rule.filter import RuleFilterService
from core.database import Database
from filters.context import MessageContext

@pytest.mark.asyncio
class TestBatchFixes20260204:
    
    async def test_rule_filter_service_enum_comparison(self):
        """测试 RuleFilterService 是否能正确比较 Enum 和 字符串"""
        # 1. 测试 Enum 模式
        mock_rule_enum = MagicMock(spec=ForwardRule)
        mock_rule_enum.forward_mode = ForwardMode.WHITELIST
        mock_rule_enum.enable_reverse_blacklist = False
        mock_rule_enum.enable_reverse_whitelist = False
        mock_rule_enum.id = 1
        mock_rule_enum.is_filter_user_info = False

        with patch.object(RuleFilterService, 'process_whitelist_mode', AsyncMock(return_value=True)) as mock_whitelist:
            # 这里的 check_keywords 会调用 process_whitelist_mode
            res = await RuleFilterService.check_keywords(mock_rule_enum, "test", None)
            assert res is True
            # 校验调用参数 (reverse_blacklist 应为 False)
            mock_whitelist.assert_called_once_with(mock_rule_enum, "test", False)

        # 2. 测试 字符串 模式
        mock_rule_str = MagicMock(spec=ForwardRule)
        mock_rule_str.forward_mode = "whitelist"
        mock_rule_str.enable_reverse_blacklist = True # 带一点变化
        mock_rule_str.enable_reverse_whitelist = False
        mock_rule_str.id = 2
        mock_rule_str.is_filter_user_info = False

        with patch.object(RuleFilterService, 'process_whitelist_mode', AsyncMock(return_value=True)) as mock_whitelist:
            res = await RuleFilterService.check_keywords(mock_rule_str, "test", None)
            assert res is True
            mock_whitelist.assert_called_once_with(mock_rule_str, "test", True)

    def test_database_sqlite_connect_args(self):
        """测试 Database 类是否只在 SQLite 下传递 check_same_thread"""
        # 增加对 event.listen 的 Mock 避免对 Mock 对象进行事件监听导致的错误
        with patch('core.database.create_async_engine') as mock_create, \
             patch('sqlalchemy.event.listen') as mock_listen:
             
            mock_engine = MagicMock()
            mock_create.return_value = mock_engine
            
            # 1. SQLite 情况
            Database(db_url="sqlite+aiosqlite:///test.db")
            # 验证参数
            call_args = mock_create.call_args[1]
            assert call_args['connect_args']['check_same_thread'] is False
            # 验证是否尝试监听 connect 事件以开启 WAL
            assert mock_listen.called
            
            # 2. PostgreSQL 情况
            mock_create.reset_mock()
            mock_listen.reset_mock()
            Database(db_url="postgresql+asyncpg://user:pass@localhost/db")
            call_args = mock_create.call_args[1]
            assert 'check_same_thread' not in call_args['connect_args']
            assert call_args['connect_args']['timeout'] == 30
            # PG 下不应监听 SQLite 专属事件
            assert not mock_listen.called

    def test_message_context_slots(self):
        """测试 MessageContext 是否包含 dup_signatures 槽位且初始化正确"""
        mock_event = MagicMock()
        mock_event.message.text = "test"
        mock_event.message.grouped_id = None
        
        ctx = MessageContext(MagicMock(), mock_event, 123, MagicMock())
        assert hasattr(ctx, 'dup_signatures')
        assert ctx.dup_signatures == []
        
        ctx.dup_signatures.append(("sig1", 123))
        assert len(ctx.dup_signatures) == 1

    async def test_callback_handler_router_mismatch_no_crash(self):
        """测试 handle_callback 在路由匹配失败时是否不会崩溃且有反馈"""
        from handlers.button.callback.callback_handlers import handle_callback
        
        # 必须 Mock 掉 Router 避免其内部初始化或路径未配置导致的问题
        with patch('handlers.button.callback.callback_handlers.callback_router') as mock_router:
            mock_router.match.return_value = None # 模拟匹配失败
            
            event = MagicMock()
            event.data = b"route_does_not_exist:v1"
            
            # 定义异步 Mock 来捕获反馈
            last_answer = [None]
            async def mock_answer(msg=None, alert=False): 
                last_answer[0] = msg
                return None
                
            event.answer = mock_answer
            
            # 执行 (不应崩溃)
            await handle_callback(event)
            
            # 验证是否有报警提示
            assert last_answer[0] == "操作已过期或指令无效"
