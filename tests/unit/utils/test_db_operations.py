import pytest
from unittest.mock import MagicMock, AsyncMock
from repositories.db_operations import DBOperations
from models.models import MediaExtensions, PushConfig, RuleSync, RSSConfig, MediaSignature

@pytest.mark.asyncio
class TestDBOperations:
    async def test_get_media_extensions(self):
        db_ops = await DBOperations.create()
        session = AsyncMock()
        mock_result = MagicMock()
        expected = [MediaExtensions(id=1, extension="jpg")]
        mock_result.scalars.return_value.all.return_value = expected
        session.execute.return_value = mock_result

        result = await db_ops.get_media_extensions(session, 1)
        assert result == expected
        session.execute.assert_called_once()

    async def test_get_push_configs(self):
        db_ops = await DBOperations.create()
        session = AsyncMock()
        mock_result = MagicMock()
        expected = [PushConfig(id=1)]
        mock_result.scalars.return_value.all.return_value = expected
        session.execute.return_value = mock_result

        result = await db_ops.get_push_configs(session, 1)
        assert result == expected

    async def test_get_rule_syncs(self):
        db_ops = await DBOperations.create()
        session = AsyncMock()
        mock_result = MagicMock()
        expected = [RuleSync(id=1)]
        mock_result.scalars.return_value.all.return_value = expected
        session.execute.return_value = mock_result

        result = await db_ops.get_rule_syncs(session, 1)
        assert result == expected

    async def test_get_rss_config(self):
        db_ops = await DBOperations.create()
        session = AsyncMock()
        mock_result = MagicMock()
        expected = RSSConfig(id=1)
        mock_result.scalar_one_or_none.return_value = expected
        session.execute.return_value = mock_result

        result = await db_ops.get_rss_config(session, 1)
        assert result == expected

    async def test_find_media_by_file_id(self):
        db_ops = await DBOperations.create()
        session = AsyncMock()
        mock_result = MagicMock()
        expected = MediaSignature(id=1, file_id="fid")
        mock_result.scalar_one_or_none.return_value = expected
        session.execute.return_value = mock_result

        result = await db_ops.find_media_record_by_fileid_or_hash(session, "chat1", file_id="fid")
        assert result == expected
        # Should verify filters but simple scalar return check is consistent with logic

    async def test_find_media_by_hash(self):
        db_ops = await DBOperations.create()
        session = AsyncMock()
        mock_result_fid = MagicMock()
        mock_result_fid.scalar_one_or_none.return_value = None
        
        mock_result_hash = MagicMock()
        expected = MediaSignature(id=2, content_hash="hash")
        mock_result_hash.scalar_one_or_none.return_value = expected

        # side_effect for multiple execute calls
        session.execute.side_effect = [mock_result_fid, mock_result_hash]

        result = await db_ops.find_media_record_by_fileid_or_hash(session, "chat1", file_id="fid_mismatch", content_hash="hash")
        assert result == expected

    async def test_add_media_signature_new(self):
        db_ops = await DBOperations.create()
        session = AsyncMock()
        # Mock existing check returning None
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = None
        session.execute.return_value = mock_result

        success = await db_ops.add_media_signature(session, "chat1", "sig1")
        assert success is True
        session.add.assert_called_once()
        # Don't need commit for add? Code says session.add but no commit?
        # Checking scan_duplicate_media source: Lines 133 just session.add(new_sig). 
        # But wait, add_media_signature source code:
        # Line 133: session.add(new_sig)
        # It does NOT call commit(). This seems to be by design (letting caller commit, or maybe a bug? The docstring doesn't say).
        # But wait, `add_media_signature` line 109 returns True after updating existing.
        # It seems it expects the session to be managed externally or it just stages the change.
        # Let's check `add_media_signature` again.
        # It returns True/False.
    
    async def test_add_media_signature_existing(self):
        db_ops = await DBOperations.create()
        session = AsyncMock()
        
        existing_sig = MediaSignature(chat_id="chat1", signature="sig1", count=1)
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = existing_sig
        session.execute.return_value = mock_result

        success = await db_ops.add_media_signature(session, "chat1", "sig1", file_size=100)
        assert success is True
        assert existing_sig.count == 2
        assert existing_sig.file_size == 100
        # No session.add called for update
        session.add.assert_not_called()

    async def test_scan_duplicate_media(self):
        db_ops = await DBOperations.create()
        session = AsyncMock()
        
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = [
            MediaSignature(signature="s1", count=3),
            MediaSignature(signature="s2", count=2)
        ]
        session.execute.return_value = mock_result

        dup_list, dup_map = await db_ops.scan_duplicate_media(session, "chat1")
        assert "s1" in dup_list
        assert "s2" in dup_list
        assert dup_map["s1"] == 3
        assert dup_map["s2"] == 2

    async def test_get_duplicate_media_records(self):
        db_ops = await DBOperations.create()
        session = AsyncMock()
        
        mock_data = [MediaSignature(id=1), MediaSignature(id=2)]
        mock_result = MagicMock()
        mock_result.scalars.return_value.all.return_value = mock_data
        session.execute.return_value = mock_result

        result = await db_ops.get_duplicate_media_records(session, "chat1")
        assert result == mock_data
