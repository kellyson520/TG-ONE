from ui.renderers.base_renderer import ViewResult
from ui.renderers.media_renderer import MediaRenderer


def test_render_history_hub_uses_done_progress_fallback():
    renderer = MediaRenderer()

    view = renderer.render_history_hub({
        "current_task": {
            "status": "running",
            "done": 25,
            "total": 100,
        }
    })

    assert isinstance(view, ViewResult)
    assert "25 / 100" in view.text
