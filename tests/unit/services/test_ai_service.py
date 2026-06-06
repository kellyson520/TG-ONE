from types import SimpleNamespace

import pytest

from core.config import settings
from services.ai_service import AIService


class FakeProvider:
    def __init__(self):
        self.calls = []

    async def process_message(self, message, prompt=None, model=None, images=None):
        self.calls.append(
            {
                "message": message,
                "prompt": prompt,
                "model": model,
                "images": images or [],
            }
        )
        return f"reply:{message}"


def _rule(**overrides):
    data = {
        "id": 7,
        "ai_model": "fake-model",
        "ai_prompt": "人格={Persona}\n来源={SourceChat}\n目标={TargetChat}\n记忆:\n{Memory}\n消息={Message}",
        "ai_persona": "严谨、简洁、保持事实边界",
        "description": "测试规则",
        "source_chat": SimpleNamespace(title="源频道"),
        "target_chat": SimpleNamespace(title="目标频道"),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


def _context(**overrides):
    data = {
        "chat_id": 100,
        "sender_name": "Alice",
        "metadata": {},
    }
    data.update(overrides)
    return SimpleNamespace(**data)


@pytest.mark.asyncio
async def test_ai_prompt_builds_persona_memory_and_chat_context(monkeypatch):
    monkeypatch.setattr(settings, "AI_MEMORY_ENABLED", True)
    monkeypatch.setattr(settings, "AI_MEMORY_MAX_TURNS", 4)
    provider = FakeProvider()

    async def fake_get_provider(_model):
        return provider

    monkeypatch.setattr("services.ai_service.get_ai_provider", fake_get_provider)
    service = AIService()
    rule = _rule()
    context = _context()

    first = await service.process_message("msg-0", rule, context=context)
    second = await service.process_message("msg-1", rule, context=context)

    assert first == "reply:msg-0"
    assert second == "reply:msg-1"
    assert "严谨、简洁" in provider.calls[-1]["prompt"]
    assert "源频道" in provider.calls[-1]["prompt"]
    assert "目标频道" in provider.calls[-1]["prompt"]
    assert "msg-0" in provider.calls[-1]["prompt"]
    assert "reply:msg-0" in provider.calls[-1]["prompt"]


@pytest.mark.asyncio
async def test_ai_memory_keeps_only_recent_turns_across_long_dialogue(monkeypatch):
    monkeypatch.setattr(settings, "AI_MEMORY_ENABLED", True)
    monkeypatch.setattr(settings, "AI_MEMORY_MAX_TURNS", 4)
    monkeypatch.setattr(settings, "AI_MEMORY_MAX_SESSIONS", 10)
    provider = FakeProvider()

    async def fake_get_provider(_model):
        return provider

    monkeypatch.setattr("services.ai_service.get_ai_provider", fake_get_provider)
    service = AIService()
    rule = _rule()
    context = _context()
    memory_key = service.memory.make_key(rule, context)

    for idx in range(100):
        assert await service.process_message(f"msg-{idx}", rule, context=context) == f"reply:msg-{idx}"

    final_prompt = provider.calls[-1]["prompt"]
    assert service.memory.turn_count(memory_key) == 4
    assert "msg-0" not in final_prompt
    assert "msg-94" not in final_prompt
    assert "msg-95" in final_prompt
    assert "msg-98" in final_prompt


@pytest.mark.asyncio
async def test_ai_empty_or_failed_response_does_not_pollute_memory(monkeypatch):
    monkeypatch.setattr(settings, "AI_MEMORY_ENABLED", True)

    class EmptyProvider(FakeProvider):
        async def process_message(self, message, prompt=None, model=None, images=None):
            self.calls.append({"message": message, "prompt": prompt})
            return ""

    provider = EmptyProvider()

    async def fake_get_provider(_model):
        return provider

    monkeypatch.setattr("services.ai_service.get_ai_provider", fake_get_provider)
    service = AIService()
    rule = _rule()
    context = _context()
    memory_key = service.memory.make_key(rule, context)

    assert await service.process_message("original", rule, context=context) == "original"
    assert service.memory.turn_count(memory_key) == 0


@pytest.mark.asyncio
async def test_ai_auto_context_injects_persona_when_template_has_no_placeholder(monkeypatch):
    monkeypatch.setattr(settings, "AI_MEMORY_ENABLED", True)
    provider = FakeProvider()

    async def fake_get_provider(_model):
        return provider

    monkeypatch.setattr("services.ai_service.get_ai_provider", fake_get_provider)
    service = AIService()
    rule = _rule(ai_prompt="请改写：")
    context = _context(metadata={"persona": "像资深运营一样输出"})

    await service.process_message("第一轮", rule, context=context)
    await service.process_message("第二轮", rule, context=context)

    prompt = provider.calls[-1]["prompt"]
    assert "人格设定:" in prompt
    assert "像资深运营一样输出" in prompt
    assert "对话记忆:" in prompt
    assert "第一轮" in prompt


@pytest.mark.asyncio
async def test_ai_prompt_uses_default_persona(monkeypatch):
    monkeypatch.setattr(settings, "AI_MEMORY_ENABLED", False)
    monkeypatch.setattr(settings, "DEFAULT_AI_PERSONA", "全局默认人格")
    provider = FakeProvider()

    async def fake_get_provider(_model):
        return provider

    monkeypatch.setattr("services.ai_service.get_ai_provider", fake_get_provider)
    service = AIService()
    rule = _rule(ai_prompt="请改写：", ai_persona=None)

    await service.process_message("内容", rule, context=_context())

    assert "人格设定:" in provider.calls[-1]["prompt"]
    assert "全局默认人格" in provider.calls[-1]["prompt"]


@pytest.mark.asyncio
async def test_ai_service_uses_summary_prompt_for_summary_rules(monkeypatch):
    monkeypatch.setattr(settings, "AI_MEMORY_ENABLED", False)
    provider = FakeProvider()

    async def fake_get_provider(_model):
        return provider

    monkeypatch.setattr("services.ai_service.get_ai_provider", fake_get_provider)
    service = AIService()
    rule = _rule(is_summary=True, summary_prompt="总结模板：{Message}", ai_prompt="重写模板：{Message}")

    await service.process_message("需要总结", rule, context=_context())

    assert "总结模板：需要总结" in provider.calls[-1]["prompt"]
    assert "重写模板" not in provider.calls[-1]["prompt"]


@pytest.mark.asyncio
async def test_ai_service_reads_runtime_default_model_and_prompt(monkeypatch):
    monkeypatch.setattr(settings, "AI_MEMORY_ENABLED", False)
    monkeypatch.setattr(settings, "DEFAULT_AI_MODEL", "runtime-model")
    monkeypatch.setattr(settings, "DEFAULT_AI_PROMPT", "运行时默认：{Message}")
    provider = FakeProvider()

    async def fake_get_provider(_model):
        return provider

    monkeypatch.setattr("services.ai_service.get_ai_provider", fake_get_provider)
    service = AIService()
    rule = _rule(ai_model=None, ai_prompt=None, ai_persona=None)

    await service.process_message("内容", rule, context=_context())

    assert provider.calls[-1]["model"] == "runtime-model"
    assert provider.calls[-1]["prompt"].endswith("运行时默认：内容")


@pytest.mark.asyncio
async def test_ai_memory_refreshes_runtime_bounds(monkeypatch):
    monkeypatch.setattr(settings, "AI_MEMORY_ENABLED", True)
    monkeypatch.setattr(settings, "AI_MEMORY_MAX_TURNS", 4)
    provider = FakeProvider()

    async def fake_get_provider(_model):
        return provider

    monkeypatch.setattr("services.ai_service.get_ai_provider", fake_get_provider)
    service = AIService()
    rule = _rule()
    context = _context()
    memory_key = service.memory.make_key(rule, context)

    for idx in range(4):
        await service.process_message(f"before-{idx}", rule, context=context)
    assert service.memory.turn_count(memory_key) == 4

    monkeypatch.setattr(settings, "AI_MEMORY_MAX_TURNS", 2)
    await service.process_message("after", rule, context=context)

    assert service.memory.turn_count(memory_key) == 2
    final_prompt = provider.calls[-1]["prompt"]
    assert "before-0" not in final_prompt
    assert "before-3" in final_prompt
