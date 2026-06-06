from types import SimpleNamespace
from unittest.mock import AsyncMock

import pytest

from core.config import settings
from core.pipeline import MessageContext
from middlewares.ai import AIMiddleware
from services.ai_service import AIService


class RecordingProvider:
    def __init__(self):
        self.calls = []

    async def process_message(self, message, prompt=None, model=None, images=None):
        self.calls.append(
            {
                "message": message,
                "prompt": prompt or "",
                "model": model,
                "images": images or [],
            }
        )
        return f"reply:{message}"


class StaticAIService:
    def __init__(self, result_prefix="ai"):
        self.calls = []
        self.result_prefix = result_prefix

    async def process_message(self, text, rule, images=None, context=None):
        self.calls.append({"text": text, "rule": rule, "context": context})
        return f"{self.result_prefix}:{text}"


def _rule(**overrides):
    data = {
        "id": 7,
        "is_ai": True,
        "is_summary": False,
        "ai_model": "fake-model",
        "ai_prompt": "人格={Persona}\n记忆:\n{Memory}\n消息={Message}",
        "ai_persona": "稳定人格",
        "summary_prompt": None,
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _ctx(text, rules, message_id=1, metadata=None):
    return MessageContext(
        client=AsyncMock(),
        task_id=1,
        chat_id=12345,
        message_id=message_id,
        message_obj=SimpleNamespace(id=message_id, text=text, message=text, media=None),
        rules=rules,
        metadata=metadata or {},
    )


@pytest.mark.asyncio
async def test_ai_middleware_uses_service_prompt_persona_and_memory(monkeypatch):
    monkeypatch.setattr(settings, "AI_MEMORY_ENABLED", True)
    monkeypatch.setattr(settings, "AI_MEMORY_MAX_TURNS", 4)
    provider = RecordingProvider()

    async def fake_get_provider(_model):
        return provider

    monkeypatch.setattr("services.ai_service.get_ai_provider", fake_get_provider)

    service = AIService()
    middleware = AIMiddleware(service=service)
    rule = _rule()

    await middleware.process(_ctx("first", [rule], message_id=1), AsyncMock())
    ctx2 = _ctx("second", [rule], message_id=2)
    next_call = AsyncMock()
    await middleware.process(ctx2, next_call)

    assert next_call.await_count == 1
    assert ctx2.metadata["modified_text_7"] == "reply:second"
    assert ctx2.metadata["modified_text"] == "reply:second"
    final_prompt = provider.calls[-1]["prompt"]
    assert "稳定人格" in final_prompt
    assert "first" in final_prompt
    assert "reply:first" in final_prompt


@pytest.mark.asyncio
async def test_ai_middleware_does_not_leak_ai_output_to_non_ai_rules():
    ai_rule = _rule(id=7, is_ai=True)
    plain_rule = _rule(id=8, is_ai=False, is_summary=False)
    service = StaticAIService()
    middleware = AIMiddleware(service=service)
    ctx = _ctx("original", [ai_rule, plain_rule])
    next_call = AsyncMock()

    await middleware.process(ctx, next_call)

    assert next_call.await_count == 1
    assert ctx.metadata["modified_text_7"] == "ai:original"
    assert "modified_text_8" not in ctx.metadata
    assert "modified_text" not in ctx.metadata


@pytest.mark.asyncio
async def test_ai_middleware_processes_rule_specific_filtered_text():
    rule = _rule(id=7, is_ai=True)
    service = StaticAIService()
    middleware = AIMiddleware(service=service)
    ctx = _ctx("original", [rule], metadata={"modified_text_7": "filtered"})

    await middleware.process(ctx, AsyncMock())

    assert service.calls[0]["text"] == "filtered"
    assert ctx.metadata["modified_text_7"] == "ai:filtered"
