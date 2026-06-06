import json
from datetime import datetime
from types import SimpleNamespace

from ui.renderers.base_renderer import ViewResult
from ui.renderers.task_renderer import TaskRenderer


def test_render_history_task_list_empty_returns_view_result():
    renderer = TaskRenderer()

    view = renderer.render_history_task_list({"tasks": [], "total": 0, "page": 1})

    assert isinstance(view, ViewResult)
    assert "暂无历史任务记录" in view.text
    assert view.buttons


def test_render_history_task_list_with_pagination_returns_view_result():
    renderer = TaskRenderer()
    task = SimpleNamespace(
        id=7,
        task_type="process_message",
        task_data=json.dumps({"rule_id": 3, "is_history": True}),
        status="completed",
        created_at=datetime(2026, 6, 6, 2, 0),
    )

    view = renderer.render_history_task_list({"tasks": [task], "total": 11, "page": 1})

    assert isinstance(view, ViewResult)
    assert "任务 #7" in view.text
    assert any(button.text == "下一页 ➡️" for row in view.buttons for button in row)
