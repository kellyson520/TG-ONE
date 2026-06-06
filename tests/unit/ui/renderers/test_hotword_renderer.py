from ui.renderers.hotword_renderer import hotword_renderer


def _button_data(view):
    return [
        (button.data.decode("utf-8") if isinstance(button.data, bytes) else str(button.data))
        for row in view.buttons
        for button in row
    ]


def test_global_rankings_exposes_period_switches():
    view = hotword_renderer.render_global_rankings([("测试热词", 12)], "2026-06-06", period="day")

    data = _button_data(view)

    assert "全局今日" in view.text
    assert any(item.startswith("new_menu:hotword_view_id:") and item.endswith(":month") for item in data)
    assert any(item.startswith("new_menu:hotword_view_id:") and item.endswith(":year") for item in data)
    assert any(item.startswith("new_menu:hotword_view_id:") and item.endswith(":all") for item in data)


def test_global_rankings_refresh_keeps_selected_period():
    view = hotword_renderer.render_global_rankings([("月榜热词", 8)], "2026-06-06", period="month")

    data = _button_data(view)

    assert "全局月度" in view.text
    assert any(item.startswith("new_menu:hotword_view_id:") and item.endswith(":month") for item in data)
