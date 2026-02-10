from ui.builder import MenuBuilder
from ui.constants import UIStatus
from ui.renderers.base_renderer import ViewResult

def test_menu_builder_basic():
    builder = MenuBuilder()
    builder.set_title("测试标题", icon=UIStatus.SETTINGS)
    builder.add_breadcrumb(["首页", "子页"])
    builder.add_section("核心内容", "这是一段测试文字。")
    builder.add_button("点击我", "test_action")
    
    view = builder.build()
    
    assert isinstance(view, ViewResult)
    assert "**测试标题**" in view.text
    assert UIStatus.SETTINGS in view.text
    assert "首页 > 子页" in view.text
    assert "核心内容" in view.text
    assert len(view.buttons) == 1
    assert view.buttons[0][0].text == "点击 me" or "点击我" in view.buttons[0][0].text

def test_status_grid():
    builder = MenuBuilder()
    builder.add_status_grid({
        "数据库": ("正常", UIStatus.SUCCESS),
        "版本": "v1.0.0"
    })
    view = builder.build()
    assert UIStatus.SUCCESS in view.text
    assert "正常" in view.text
    assert "v1.0.0" in view.text

def test_progress_bar():
    builder = MenuBuilder()
    builder.add_progress_bar("下载进度", 50.0, width=10)
    view = builder.build()
    # 50% width 10 should have 5 🟩
    assert "🟩🟩🟩🟩🟩" in view.text
    assert "50.0%" in view.text

def test_smart_layout():
    builder = MenuBuilder()
    builder.add_button("短1", "a")
    builder.add_button("短2", "b")
    builder.add_button("短3", "c")
    builder.add_button("这是一个超级长的按钮标题文字", "d")
    builder.add_button("返回主菜单", "back", icon=UIStatus.BACK)
    
    view = builder.build()
    
    # 根据逻辑：
    # 短1, 短2, 短3 可能会尝试并排（如果 flush_row 逻辑触发）
    # 长按钮单独一行
    # 返回按钮单独一行
    assert len(view.buttons) >= 3
