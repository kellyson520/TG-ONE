from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
from datetime import datetime
import time
from typing import Any, Deque, Dict, Iterable, List, Optional

from core.config import settings


@dataclass
class AITurn:
    user: str
    assistant: str
    created_at: float


class AIConversationMemory:
    """Bounded in-process AI conversation memory, scoped by rule and source chat."""

    def __init__(
        self,
        max_sessions: Optional[int] = None,
        max_turns: Optional[int] = None,
        ttl_seconds: Optional[int] = None,
        max_text_chars: Optional[int] = None,
        clock=time.monotonic,
    ) -> None:
        self._clock = clock
        self._sessions: "OrderedDict[str, Deque[AITurn]]" = OrderedDict()
        self.max_sessions = _positive_int(max_sessions, settings.AI_MEMORY_MAX_SESSIONS)
        self.max_turns = _positive_int(max_turns, settings.AI_MEMORY_MAX_TURNS)
        self.ttl_seconds = _positive_int(ttl_seconds, settings.AI_MEMORY_TTL_SECONDS)
        self.max_text_chars = _positive_int(max_text_chars, settings.AI_MEMORY_MAX_TEXT_CHARS, minimum=32)

    def refresh_from_settings(self) -> None:
        """Apply runtime config changes without dropping valid recent memory."""
        new_max_sessions = _positive_int(getattr(settings, "AI_MEMORY_MAX_SESSIONS", None), self.max_sessions)
        new_max_turns = _positive_int(getattr(settings, "AI_MEMORY_MAX_TURNS", None), self.max_turns)
        new_ttl_seconds = _positive_int(getattr(settings, "AI_MEMORY_TTL_SECONDS", None), self.ttl_seconds)
        new_max_text_chars = _positive_int(
            getattr(settings, "AI_MEMORY_MAX_TEXT_CHARS", None),
            self.max_text_chars,
            minimum=32,
        )

        text_limit_changed = new_max_text_chars != self.max_text_chars
        turns_limit_changed = new_max_turns != self.max_turns

        self.max_sessions = new_max_sessions
        self.max_turns = new_max_turns
        self.ttl_seconds = new_ttl_seconds
        self.max_text_chars = new_max_text_chars

        if text_limit_changed or turns_limit_changed:
            for key, turns in list(self._sessions.items()):
                recent_turns = list(turns)[-self.max_turns:]
                if text_limit_changed:
                    recent_turns = [
                        AITurn(
                            user=self._clip(turn.user),
                            assistant=self._clip(turn.assistant),
                            created_at=turn.created_at,
                        )
                        for turn in recent_turns
                    ]
                self._sessions[key] = deque(recent_turns, maxlen=self.max_turns)

        self._prune()

    def make_key(self, rule: Any, context: Any) -> Optional[str]:
        rule_id = _first_scalar(rule, ("id", "rule_id"))
        chat_id = (
            _first_scalar(context, ("chat_id", "source_chat_id"))
            or _first_scalar(_read(context, "event"), ("chat_id",))
            or _first_scalar(_read(context, "message"), ("chat_id",))
        )
        if rule_id is None and chat_id is None:
            return None
        return f"rule:{rule_id or 'global'}:chat:{chat_id or 'global'}"

    def snapshot(self, key: Optional[str]) -> List[AITurn]:
        if not key:
            return []
        self._prune()
        turns = self._sessions.get(key)
        if not turns:
            return []
        self._sessions.move_to_end(key)
        return list(turns)

    def append(self, key: Optional[str], user_text: str, assistant_text: str) -> None:
        if not key:
            return
        self._prune()
        turns = self._sessions.get(key)
        if turns is None:
            turns = deque(maxlen=self.max_turns)
            self._sessions[key] = turns
        turns.append(
            AITurn(
                user=self._clip(user_text),
                assistant=self._clip(assistant_text),
                created_at=self._clock(),
            )
        )
        self._sessions.move_to_end(key)
        self._prune()

    def format_turns(self, turns: Iterable[AITurn]) -> str:
        lines: List[str] = []
        for idx, turn in enumerate(list(turns)[-self.max_turns:], 1):
            lines.append(f"User {idx}: {turn.user}")
            lines.append(f"Assistant {idx}: {turn.assistant}")
        return "\n".join(lines)

    def turn_count(self, key: str) -> int:
        return len(self._sessions.get(key, ()))

    def session_count(self) -> int:
        return len(self._sessions)

    def _clip(self, value: Any) -> str:
        text = "" if value is None else str(value)
        if len(text) <= self.max_text_chars:
            return text
        return text[: self.max_text_chars - 3] + "..."

    def _prune(self) -> None:
        now = self._clock()
        expired = [
            key for key, turns in self._sessions.items()
            if not turns or (now - turns[-1].created_at) > self.ttl_seconds
        ]
        for key in expired:
            self._sessions.pop(key, None)
        while len(self._sessions) > self.max_sessions:
            self._sessions.popitem(last=False)


class AIPromptBuilder:
    def __init__(self, memory: Optional[AIConversationMemory] = None) -> None:
        self.memory = memory or AIConversationMemory()

    def build(
        self,
        template: str,
        rule: Any,
        context: Any,
        message_text: str,
        memory_turns: Optional[Iterable[AITurn]] = None,
    ) -> str:
        prompt = template or ""
        persona = self._resolve_persona(rule, context)
        memory_text = self.memory.format_turns(memory_turns or [])
        variables = {
            "Message": message_text or "",
            "SourceChat": self._resolve_source_chat(rule, context),
            "TargetChat": self._resolve_target_chat(rule, context),
            "Sender": self._resolve_sender(context),
            "DateTime": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Time": datetime.now().strftime("%H:%M:%S"),
            "Now": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "RuleDescription": _first_scalar(rule, ("description",)) or "",
            "Description": _first_scalar(rule, ("description",)) or "",
            "Persona": persona,
            "Personality": persona,
            "Role": persona,
            "Memory": memory_text,
            "Conversation": memory_text,
            "History": memory_text,
        }

        for name, value in variables.items():
            prompt = prompt.replace(f"{{{name}}}", value)
            prompt = prompt.replace(f"{{{name.lower()}}}", value)

        if bool(getattr(settings, "AI_PROMPT_AUTO_CONTEXT", True)):
            sections: List[str] = []
            if persona and not _contains_any(template, ("Persona", "Personality", "Role")):
                sections.append(f"人格设定:\n{persona}")
            if memory_text and not _contains_any(template, ("Memory", "Conversation", "History")):
                sections.append(f"对话记忆:\n{memory_text}")
            if sections:
                prompt = "\n\n".join([*sections, prompt]) if prompt else "\n\n".join(sections)

        return prompt

    def _resolve_persona(self, rule: Any, context: Any) -> str:
        metadata = _read(context, "metadata")
        if isinstance(metadata, dict):
            for key in ("ai_persona", "persona", "personality", "role"):
                if _valid_scalar(metadata.get(key)):
                    return str(metadata[key])
        return (
            _first_scalar(context, ("ai_persona", "persona", "personality", "role"))
            or _first_scalar(rule, ("ai_persona", "persona", "personality", "ai_role", "role"))
            or getattr(settings, "DEFAULT_AI_PERSONA", "")
            or ""
        )

    def _resolve_source_chat(self, rule: Any, context: Any) -> str:
        return (
            _first_scalar(context, ("source_chat_title", "source_chat_name", "chat_title", "chat_name"))
            or _nested_scalar(context, ("event.chat.title", "event.chat.username"))
            or _nested_scalar(rule, ("source_chat.title", "source_chat.name", "source_chat.chat_name"))
            or ""
        )

    def _resolve_target_chat(self, rule: Any, context: Any) -> str:
        return (
            _first_scalar(context, ("target_chat_title", "target_chat_name"))
            or _nested_scalar(rule, ("target_chat.title", "target_chat.name", "target_chat.chat_name"))
            or ""
        )

    def _resolve_sender(self, context: Any) -> str:
        return (
            _first_scalar(context, ("sender_name", "sender_id"))
            or _nested_scalar(context, ("event.sender_id", "event.sender.first_name", "event.sender.username"))
            or ""
        )


def _contains_any(template: str, names: Iterable[str]) -> bool:
    source = template or ""
    return any(f"{{{name}}}" in source or f"{{{name.lower()}}}" in source for name in names)


def _read(obj: Any, name: str) -> Any:
    if obj is None:
        return None
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _valid_scalar(value: Any) -> bool:
    return isinstance(value, (str, int, float)) and str(value) != ""


def _first_scalar(obj: Any, names: Iterable[str]) -> Optional[str]:
    for name in names:
        value = _read(obj, name)
        if _valid_scalar(value):
            return str(value)
    return None


def _nested_scalar(obj: Any, paths: Iterable[str]) -> Optional[str]:
    for path in paths:
        cur = obj
        for part in path.split("."):
            cur = _read(cur, part)
            if cur is None:
                break
        if _valid_scalar(cur):
            return str(cur)
    return None


def _positive_int(value: Any, fallback: Any, minimum: int = 1) -> int:
    raw = fallback if value is None else value
    try:
        parsed = int(raw)
    except (TypeError, ValueError):
        parsed = int(fallback)
    return max(minimum, parsed)
