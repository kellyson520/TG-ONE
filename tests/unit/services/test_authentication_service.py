import pytest
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch
from services.authentication_service import AuthenticationService
from models.models import User, ActiveSession

@pytest.fixture
def auth_service():
    return AuthenticationService()

@pytest.fixture
def mock_user():
    user = MagicMock(spec=User)
    user.id = 1
    user.username = "testuser"
    user.password = "hashed_password"
    user.is_active = True
    return user

@pytest.mark.asyncio
async def test_authenticate_user_success(auth_service, mock_user):
    with patch("core.container.container.user_repo.get_user_for_auth", new_callable=AsyncMock) as mock_get_user:
        with patch("services.authentication_service.check_password_hash") as mock_check_hash:
            mock_get_user.return_value = mock_user
            mock_check_hash.return_value = True
            
            user = await auth_service.authenticate_user("testuser", "password")
            
            assert user is not None
            assert user.id == 1
            mock_get_user.assert_called_with("testuser")
            mock_check_hash.assert_called_with("hashed_password", "password")

@pytest.mark.asyncio
async def test_authenticate_user_fail_password(auth_service, mock_user):
     with patch("core.container.container.user_repo.get_user_for_auth", new_callable=AsyncMock) as mock_get_user:
        with patch("services.authentication_service.check_password_hash") as mock_check_hash:
            mock_get_user.return_value = mock_user
            mock_check_hash.return_value = False
            
            user = await auth_service.authenticate_user("testuser", "wrong")
            assert user is None

@pytest.mark.asyncio
async def test_create_tokens(auth_service):
    # Test access token
    access = auth_service.create_access_token({"sub": "1"})
    assert isinstance(access, str)
    
    # Test refresh token
    refresh = auth_service.create_refresh_token({"sub": "1"})
    assert isinstance(refresh, str)

@pytest.mark.asyncio
async def test_refresh_access_token(auth_service):
    # This requires DB mocking which is complex with pure unit test without DB
    # We will mock the DB session interactions
    refresh_token = auth_service.create_refresh_token({"sub": "1"})
    
    with patch("core.container.container.db.session") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__.return_value = mock_session
        
        # Mock result of select(ActiveSession)
        mock_result = MagicMock()
        mock_active_session = MagicMock(spec=ActiveSession)
        # Mock database storing hash, not raw token
        import hashlib
        token_hash = hashlib.sha256(refresh_token.encode()).hexdigest()
        mock_active_session.refresh_token_hash = token_hash
        mock_active_session.expires_at = datetime.utcnow() + timedelta(days=1)
        
        # When scalar_one_or_none is called
        mock_result.scalar_one_or_none.return_value = mock_active_session
        mock_session.execute.return_value = mock_result
        
        new_token = await auth_service.refresh_access_token(refresh_token)
        
        assert new_token is not None
        assert isinstance(new_token, tuple) # Updated service returns (access, refresh)
        assert len(new_token) == 2

@pytest.mark.asyncio
async def test_generate_2fa_secret(auth_service, mock_user):
    with patch("core.container.container.db.session") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__.return_value = mock_session
        
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result
        
        secret, otpauth, qr_b64 = await auth_service.generate_2fa_secret(1)
        
        assert len(secret) == 32
        assert "otpauth://" in otpauth
        assert qr_b64 is not None
        assert mock_user.totp_secret == secret
        mock_session.commit.assert_called_once()

@pytest.mark.asyncio
async def test_verify_and_enable_2fa_success(auth_service, mock_user):
    import pyotp
    secret = pyotp.random_base32()
    mock_user.totp_secret = secret
    
    with patch("core.container.container.db.session") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__.return_value = mock_session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result
        
        totp = pyotp.TOTP(secret)
        token = totp.now()
        
        success = await auth_service.verify_and_enable_2fa(1, token)
        
        assert success is True
        assert mock_user.is_2fa_enabled is True
        mock_session.commit.assert_called_once()

@pytest.mark.asyncio
async def test_verify_2fa_login_success(auth_service, mock_user):
    import pyotp
    secret = pyotp.random_base32()
    mock_user.totp_secret = secret
    mock_user.is_2fa_enabled = True
    mock_user.last_otp_token = None  # 初始状态
    
    with patch("core.container.container.user_repo.get_user_auth_by_id", new_callable=AsyncMock) as mock_get:
        with patch("core.container.container.db.session") as mock_session_ctx:
            mock_get.return_value = mock_user
            
            # Mock database session for anti-replay check
            mock_session = AsyncMock()
            mock_session_ctx.return_value.__aenter__.return_value = mock_session
            
            # Mock session.get to return a db_user object
            mock_db_user = MagicMock(spec=User)
            mock_db_user.id = 1
            mock_db_user.last_otp_token = None  # No replay
            mock_session.get.return_value = mock_db_user
            
            totp = pyotp.TOTP(secret)
            token = totp.now()
            
            success = await auth_service.verify_2fa_login(1, token)
            assert success is True
            
            # Verify anti-replay update was called
            assert mock_db_user.last_otp_token == token
            mock_session.commit.assert_called_once()

@pytest.mark.asyncio
async def test_disable_2fa(auth_service, mock_user):
    mock_user.is_2fa_enabled = True
    
    with patch("core.container.container.db.session") as mock_session_ctx:
        mock_session = AsyncMock()
        mock_session_ctx.return_value.__aenter__.return_value = mock_session
        mock_result = MagicMock()
        mock_result.scalar_one_or_none.return_value = mock_user
        mock_session.execute.return_value = mock_result
        
        success = await auth_service.disable_2fa(1)
        
        assert success is True
        assert mock_user.is_2fa_enabled is False
        assert mock_user.totp_secret is None
        mock_session.commit.assert_called_once()

