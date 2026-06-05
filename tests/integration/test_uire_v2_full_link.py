import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from ui.builder import MenuBuilder
from ui.renderers.media_renderer import MediaRenderer
from ui.renderers.rule_renderer import RuleRenderer
from controllers.domain.media_controller import MediaController
from controllers.domain.rule_controller import RuleController

class MockContainer:
    def __init__(self):
        self.ui = MagicMock()
        self.ui.media = MediaRenderer()
        self.ui.rule = RuleRenderer()
        self.db = MagicMock()
        self.menu_service = AsyncMock()

@pytest.fixture
def mock_event():
    event = AsyncMock()
    event.sender_id = 123
    event.chat_id = 456
    event.answer = AsyncMock()
    return event

@pytest.fixture
def container():
    return MockContainer()

@pytest.fixture
def media_controller(container):
    ctrl = MediaController(container)
    return ctrl

@pytest.fixture
def rule_controller(container):
    ctrl = RuleController(container)
    return ctrl

@pytest.mark.asyncio
async def test_media_ai_settings_render_integration(media_controller, mock_event):
    """集成测试：MediaController -> MediaRenderer -> MenuBuilder"""
    
    # 1. Mock 外部服务返回的数据
    mock_rule_data = {
        'id': 1001,
        'is_ai': True,
        'is_summary': True,
        'ai_model': 'gpt-4o',
        'summary_time': '12:00',
        'enable_ai_upload_image': True,
        'is_keyword_after_ai': False,
        'is_top_summary': True
    }
    
    with patch("services.rule.facade.rule_management_service.get_rule_detail", new_callable=AsyncMock) as mock_get_detail, \
         patch("handlers.button.new_menu_system.new_menu_system._render_page", new_callable=AsyncMock) as mock_render:
        
        mock_get_detail.return_value = mock_rule_data
        
        # 2. 执行 Controller 方法
        await media_controller.show_ai_settings(mock_event, 1001)
        
        # 3. 验证 Render 结果
        mock_render.assert_called_once()
        _, kwargs = mock_render.call_args
        
        body = "\n".join(kwargs['body_lines'])
        buttons = kwargs['buttons']
        
        # 验证标题和图标
        assert "AI 增强设置" in kwargs['title']
        
        # 验证内容块 (Section) 是否按预期渲染
        assert "核心开关" in body
        assert "处理逻辑" in body
        assert "总结配置" in body
        
        # 验证状态矩阵 (Status Grid) 内容
        assert "gpt-4o" in body
        assert "12:00" in body
        
        # 验证按钮是否存在
        # flat_buttons = [btn.text for row in buttons for btn in row]
        # assert "切换模型" in str(buttons)
        # assert "设置提示词" in str(buttons)
        # assert "立即总结" in str(buttons)

@pytest.mark.asyncio
async def test_rule_list_render_integration(rule_controller, mock_event):
    """集成测试：RuleController -> RuleRenderer (列表及分页)"""
    
    mock_list_data = {
        'rules': [
            {'id': 1, 'source_chat_title': 'Source A', 'target_chat_title': 'Target A', 'enabled': True},
            {'id': 2, 'source_chat_title': 'Source B', 'target_chat_title': 'Target B', 'enabled': False},
        ],
        'pagination': {
            'total_count': 2,
            'page': 0,
            'total_pages': 1
        }
    }
    
    with patch("services.rule.facade.rule_management_service.get_rule_list", new_callable=AsyncMock) as mock_get_list, \
         patch("handlers.button.new_menu_system.new_menu_system._render_page", new_callable=AsyncMock) as mock_render:
        
        mock_get_list.return_value = mock_list_data
        
        await rule_controller.list_rules(mock_event, page=0)
        
        mock_render.assert_called_once()
        _, kwargs = mock_render.call_args
        
        body = "\n".join(kwargs['body_lines'])
        assert "转发规则管理" in body
        assert "Source A" in body
        assert "Target B" in body
        # 验证状态图标
        assert "✅" in body # Rule 1 enabled
        assert "❌" in body # Rule 2 disabled

@pytest.mark.asyncio
async def test_menu_builder_robustness_integration():
    """测试 MenuBuilder 的鲁棒性边界（独立集成）"""
    builder = MenuBuilder()
    
    # 1. 超长文本截断测试
    long_text = "A" * 5000
    builder.set_title("Test Title")
    builder.add_section("Header", long_text)
    
    # 2. 复杂按钮布局测试
    for i in range(10):
        builder.add_button(f"Btn {i}", f"action_{i}")
    
    # 3. 吸底按钮测试
    builder.add_button("返回", "back")
    
    result = builder.build()
    
    # 验证长度保护
    assert len(result.text) <= 4000
    assert "... (内容过长，已自动截断)" in result.text
    
    # 验证吸底布局（确认最后一个按钮包含返回）
    last_row = result.buttons[-1]
    assert any("返回" in btn.text for btn in last_row)

@pytest.mark.asyncio
async def test_text_util_smart_truncate():
    """测试 TextUtil 的智能截断（核心工具类）"""
    from ui.builder import TextUtil
    
    # 测试普通文本
    assert TextUtil.smart_truncate("Hello World", 20) == "Hello World"
    
    # 测试 ID 类文本 (包含数字且较长)
    long_id = "user_1234567890abcdefg"
    truncated = TextUtil.smart_truncate(long_id, 15)
    assert truncated.startswith("user_1")
    assert truncated.endswith("defg")
    assert "..." in truncated
    
    # 测试 Markdown 逃逸
    unsafe = "Hello * World _ Test ` Code"
    safe = TextUtil.escape_md(unsafe)
    assert "*" not in safe
    assert "_" not in safe
    assert "`" not in safe
    assert "＊" in safe
