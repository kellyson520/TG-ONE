from types import SimpleNamespace

import pytest

from core.config import settings
from services.ai_service import AIService


class BoundedProvider:
    def __init__(self):
        self.prompts = []

    async def process_message(self, message, prompt=None, model=None, images=None):
        self.prompts.append(prompt or "")
        return f"ack:{message}"


@pytest.mark.asyncio
@pytest.mark.stress
async def test_ai_hundred_round_memory_soak(monkeypatch):
    monkeypatch.setattr(settings, "AI_MEMORY_ENABLED", True)
    monkeypatch.setattr(settings, "AI_MEMORY_MAX_TURNS", 8)
    monkeypatch.setattr(settings, "AI_MEMORY_MAX_SESSIONS", 5)
    monkeypatch.setattr(settings, "AI_MEMORY_MAX_TEXT_CHARS", 120)

    provider = BoundedProvider()

    async def fake_get_provider(_model):
        return provider

    monkeypatch.setattr("services.ai_service.get_ai_provider", fake_get_provider)

    service = AIService()
    rule = SimpleNamespace(
        id=42,
        ai_model="fake-model",
        ai_prompt="人格={Persona}\n记忆:\n{Memory}\n消息={Message}",
        ai_persona="保持一致人格，优先承接历史上下文",
    )
    context = SimpleNamespace(chat_id=9001, sender_name="tester", metadata={})
    memory_key = service.memory.make_key(rule, context)

    for idx in range(100):
        text = f"round-{idx}:" + ("上下文" * 80)
        assert await service.process_message(text, rule, context=context) == f"ack:{text}"

    assert len(provider.prompts) == 100
    assert service.memory.turn_count(memory_key) == 8
    assert len(provider.prompts[-1]) < 5000
    assert "round-0" not in provider.prompts[-1]
    assert "round-91" in provider.prompts[-1]
    assert "round-98" in provider.prompts[-1]
