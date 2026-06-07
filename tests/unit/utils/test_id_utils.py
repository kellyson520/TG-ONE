"""
Unit tests for ID utilities.
Tests normalization and candidate generation logic for Telegram IDs.
"""
import logging
from types import SimpleNamespace
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from core.helpers.id_utils import (
    build_candidate_telegram_ids,
    get_display_name_async,
    normalize_chat_id,
    resolve_entity_by_id_variants,
)


class TestIdUtils:
    
    @pytest.mark.parametrize("input_id, expected", [
        (-1001234567890, "1234567890"),
        ("-1001234567890", "1234567890"),
        (-1234567890, "1234567890"),
        ("-1234567890", "1234567890"),
        (1234567890, "1234567890"),
        ("1234567890", "1234567890"),
        (0, "0"),
        ("non_numeric", "non_numeric"),
    ])
    def test_normalize_chat_id(self, input_id, expected):
        """Test normalization of various Chat ID formats."""
        assert normalize_chat_id(input_id) == expected

    def test_build_candidate_ids_supergroup(self):
        """Test candidate generation for -100 style IDs."""
        raw_id = -1001234567890
        candidates = build_candidate_telegram_ids(raw_id)
        
        # Should contain:
        # 1. Original string: "-1001234567890"
        # 2. Normalized: "1234567890"
        # 3. Numeric string: "-1001234567890"
        # 4. Absolute numeric string: "1001234567890"
        # 5. Prefixed formats: "-1001001234567890", "-1001234567890"
        
        assert "-1001234567890" in candidates
        assert "1234567890" in candidates
        assert "1001234567890" in candidates
        assert "-1234567890" in candidates
        assert "1234567890" in candidates

    def test_build_candidate_ids_simple_group(self):
        """Test candidate generation for simple negative IDs."""
        raw_id = -12345
        candidates = build_candidate_telegram_ids(raw_id)
        
        assert "-12345" in candidates
        assert "12345" in candidates
        assert "-10012345" in candidates

    def test_build_candidate_ids_positive_user(self):
        """Test candidate generation for positive user IDs."""
        raw_id = 98765
        candidates = build_candidate_telegram_ids(raw_id)
        
        assert "98765" in candidates
        assert "-98765" in candidates
        assert "-10098765" in candidates

    def test_build_candidate_ids_strings(self):
        """Test candidate generation for string inputs."""
        assert "my_username" in build_candidate_telegram_ids("my_username")
        assert "123" in build_candidate_telegram_ids("123")

    def test_username_candidate_generation_is_not_warning_noise(self, caplog):
        """Usernames are valid chat inputs, so keep them without warning noise."""
        caplog.set_level(logging.DEBUG, logger="core.helpers.id_utils")

        candidates = build_candidate_telegram_ids("my_username")

        assert "my_username" in candidates
        assert not [
            record for record in caplog.records if record.levelno >= logging.WARNING
        ]
        assert "Skipping numeric Telegram ID variants" in caplog.text

    @pytest.mark.asyncio
    async def test_resolve_entity_logs_failed_variants_and_continues(self, caplog):
        caplog.set_level(logging.DEBUG, logger="core.helpers.id_utils")
        attempts = []

        class Client:
            async def get_entity(self, variant):
                attempts.append(variant)
                if len(attempts) < 3:
                    raise RuntimeError(f"miss {variant}")
                return SimpleNamespace(id=42, title="ok")

        with patch(
            "core.helpers.entity_optimization.get_entity_resolver",
            return_value=None,
        ):
            entity, numeric_id = await resolve_entity_by_id_variants(Client(), 42)

        assert entity.title == "ok"
        assert numeric_id == -42
        assert "Failed to resolve Telegram entity variant" in caplog.text

    @pytest.mark.asyncio
    async def test_get_display_name_async_logs_lookup_failure(self, caplog):
        caplog.set_level(logging.WARNING, logger="core.helpers.id_utils")
        service = MagicMock()
        service.get_chat_name = AsyncMock(side_effect=RuntimeError("lookup failed"))

        with patch("core.container.container") as container:
            container.chat_info_service = service

            result = await get_display_name_async(123)

        assert result == "123"
        assert "Failed to get chat display name" in caplog.text
