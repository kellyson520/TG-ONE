"""
Recovery Codes 单元测试

测试 authentication_service 中的备份码功能:
- 生成备份码
- 哈希存储
- 验证和消费
- 状态查询

创建于: 2026-01-11
Phase B.1: Recovery Codes
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import json
import hashlib


class TestRecoveryCodes:
    """Recovery Codes 功能测试"""
    
    @pytest.fixture
    def auth_service(self):
        """创建 AuthenticationService 实例"""
        from services.authentication_service import AuthenticationService
        return AuthenticationService()
    
    def test_generate_recovery_codes_format(self, auth_service):
        """测试备份码生成格式"""
        codes = auth_service._generate_recovery_codes(10)
        
        assert len(codes) == 10
        for code in codes:
            # 格式: XXXX-XXXX (8 hex + 1 dash = 9 chars)
            assert len(code) == 9
            assert "-" in code
            parts = code.split("-")
            assert len(parts) == 2
            assert len(parts[0]) == 4
            assert len(parts[1]) == 4
            # 应该是有效的大写十六进制 (0-9, A-F)
            full_hex = parts[0] + parts[1]
            assert all(c in "0123456789ABCDEF" for c in full_hex), f"Invalid hex: {full_hex}"
    
    def test_generate_recovery_codes_uniqueness(self, auth_service):
        """测试备份码唯一性"""
        codes = auth_service._generate_recovery_codes(100)
        
        # 所有码应该都是唯一的
        assert len(set(codes)) == len(codes)
    
    def test_hash_recovery_codes_structure(self, auth_service):
        """测试备份码哈希结构"""
        codes = ["AAAA-BBBB", "CCCC-DDDD"]
        hashed = auth_service._hash_recovery_codes(codes)
        
        assert len(hashed) == 2
        for entry in hashed:
            assert "hash" in entry
            assert "used" in entry
            assert entry["used"] is False
            # 验证是 SHA256 哈希 (64 hex chars)
            assert len(entry["hash"]) == 64
    
    def test_hash_recovery_codes_consistency(self, auth_service):
        """测试哈希一致性"""
        code = "ABCD-1234"
        expected_hash = hashlib.sha256(code.encode()).hexdigest()
        
        hashed = auth_service._hash_recovery_codes([code])
        assert hashed[0]["hash"] == expected_hash
    
    @pytest.mark.asyncio
    async def test_generate_recovery_codes_integration(self, auth_service):
        """测试完整的备份码生成流程"""
        mock_user = MagicMock(id=1, backup_codes=None)
        
        # Setup Mock Session
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        
        # Setup Result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result
        
        # Mock DB context manager
        mock_db_context = MagicMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_container = MagicMock()
        mock_container.db.get_session = MagicMock(return_value=mock_db_context)
        
        with patch("core.container.container", mock_container):
            codes = await auth_service.generate_recovery_codes(user_id=1)
        
        # 验证返回了 10 个明文码
        assert len(codes) == 10
        
        # 验证用户的 backup_codes 被更新
        assert mock_user.backup_codes is not None
        stored_data = json.loads(mock_user.backup_codes)
        assert len(stored_data) == 10
        
        # 验证 commit 被调用
        mock_session.commit.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_verify_recovery_code_success(self, auth_service):
        """测试备份码验证成功"""
        code = "ABCD-1234"
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        
        mock_user = MagicMock(
            id=1,
            backup_codes=json.dumps([
                {"hash": code_hash, "used": False},
                {"hash": "other_hash", "used": False}
            ])
        )
        
        # Setup Mock Session
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        mock_session.commit = AsyncMock()
        
        # Setup Result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result
        
        # Mock DB context manager
        mock_db_context = MagicMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_container = MagicMock()
        mock_container.db.get_session = MagicMock(return_value=mock_db_context)
        
        with patch("core.container.container", mock_container):
            result = await auth_service.verify_recovery_code(user_id=1, code=code)
        
        assert result is True
        
        # 验证备份码被标记为已使用
        stored_data = json.loads(mock_user.backup_codes)
        assert stored_data[0]["used"] is True
        assert stored_data[1]["used"] is False
    
    @pytest.mark.asyncio
    async def test_verify_recovery_code_already_used(self, auth_service):
        """测试备份码已使用"""
        code = "ABCD-1234"
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        
        mock_user = MagicMock(
            id=1,
            backup_codes=json.dumps([
                {"hash": code_hash, "used": True}  # 已使用
            ])
        )
        
        # Setup Mock Session
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        
        # Setup Result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result
        
        # Mock DB context manager
        mock_db_context = MagicMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_container = MagicMock()
        mock_container.db.get_session = MagicMock(return_value=mock_db_context)
        
        with patch("core.container.container", mock_container):
            result = await auth_service.verify_recovery_code(user_id=1, code=code)
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_verify_recovery_code_invalid(self, auth_service):
        """测试备份码无效"""
        mock_user = MagicMock(
            id=1,
            backup_codes=json.dumps([
                {"hash": "valid_hash", "used": False}
            ])
        )
        
        # Setup Mock Session
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        
        # Setup Result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result
        
        # Mock DB context manager
        mock_db_context = MagicMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_container = MagicMock()
        mock_container.db.get_session = MagicMock(return_value=mock_db_context)
        
        with patch("core.container.container", mock_container):
            result = await auth_service.verify_recovery_code(user_id=1, code="WRONG-CODE")
        
        assert result is False
    
    @pytest.mark.asyncio
    async def test_get_recovery_codes_status(self, auth_service):
        """测试获取备份码状态"""
        mock_user = MagicMock(
            id=1,
            backup_codes=json.dumps([
                {"hash": "h1", "used": False},
                {"hash": "h2", "used": True},
                {"hash": "h3", "used": False},
                {"hash": "h4", "used": True},
                {"hash": "h5", "used": False}
            ])
        )
        
        # Setup Mock Session
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        
        # Setup Result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result
        
        # Mock DB context manager
        mock_db_context = MagicMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_container = MagicMock()
        mock_container.db.get_session = MagicMock(return_value=mock_db_context)
        
        with patch("core.container.container", mock_container):
            status = await auth_service.get_recovery_codes_status(user_id=1)
        
        assert status["total"] == 5
        assert status["used"] == 2
        assert status["remaining"] == 3
        assert status["has_codes"] is True
    
    @pytest.mark.asyncio
    async def test_get_recovery_codes_status_no_codes(self, auth_service):
        """测试获取备份码状态 (无备份码)"""
        mock_user = MagicMock(id=1, backup_codes=None)
        
        # Setup Mock Session
        mock_session = MagicMock()
        mock_session.execute = AsyncMock()
        
        # Setup Result
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result
        
        # Mock DB context manager
        mock_db_context = MagicMock()
        mock_db_context.__aenter__ = AsyncMock(return_value=mock_session)
        mock_db_context.__aexit__ = AsyncMock(return_value=None)
        
        mock_container = MagicMock()
        mock_container.db.get_session = MagicMock(return_value=mock_db_context)
        
        with patch("core.container.container", mock_container):
            status = await auth_service.get_recovery_codes_status(user_id=1)
        
        assert status["total"] == 0
        assert status["has_codes"] is False
