import pytest
from web_admin.security.rate_limiter import LoginRateLimiter
from datetime import datetime, timedelta

class TestLoginRateLimiter:
    @pytest.fixture
    def limiter(self):
        return LoginRateLimiter()

    def test_record_failure_and_lockout(self, limiter):
        username = "testuser"
        
        # 记录4次失败
        for _ in range(4):
            is_locked = limiter.record_failure(username)
            assert is_locked is False
            assert limiter.is_locked(username) is False

        # 第5次失败应触发锁定
        is_locked = limiter.record_failure(username)
        assert is_locked is True
        assert limiter.is_locked(username) is True

    def test_is_locked_case_insensitivity(self, limiter):
        limiter.record_failure("TestUser")
        limiter.record_failure("testuser")
        limiter.record_failure("TESTUSER")
        limiter.record_failure("tEStUsEr")
        assert len(limiter.attempts["testuser"]) == 4
        
        limiter.record_failure("testuser")
        assert limiter.is_locked("TESTUSER") is True

    def test_record_success_clears_attempts(self, limiter):
        username = "testuser"
        limiter.record_failure(username)
        assert len(limiter.attempts[username]) == 1
        
        limiter.record_success(username)
        assert username not in limiter.attempts
        assert username not in limiter.locked

    def test_manual_unlock(self, limiter):
        username = "testuser"
        for _ in range(5):
            limiter.record_failure(username)
        assert limiter.is_locked(username) is True
        
        limiter.unlock(username)
        assert limiter.is_locked(username) is False
        assert username not in limiter.attempts

    def test_get_lockout_info(self, limiter):
        username = "testuser"
        info = limiter.get_lockout_info(username)
        assert info is None
        
        for _ in range(5):
            limiter.record_failure(username)
            
        info = limiter.get_lockout_info(username)
        assert info["locked"] is True
        assert info["remaining_seconds"] > 0
        assert "unlock_at" in info

    def test_time_window_cleanup(self, limiter, monkeypatch):
        username = "testuser"
        # 模拟 10 分钟前的一次尝试
        old_time = datetime.now() - timedelta(minutes=10)
        limiter.attempts[username].append(old_time)
        
        # 记录一次新尝试，应该清理掉旧的
        limiter.record_failure(username)
        assert len(limiter.attempts[username]) == 1
        assert old_time not in limiter.attempts[username]

    def test_auto_unlock_after_duration(self, limiter, monkeypatch):
        username = "testuser"
        for _ in range(5):
            limiter.record_failure(username)
        
        assert limiter.is_locked(username) is True
        
        # 模拟时间流逝 (31分钟后)
        future_time = datetime.now() + timedelta(minutes=31)
        
        # 我们需要 Mock datetime.now() 或者直接修改锁定时间
        limiter.locked[username] = datetime.now() - timedelta(seconds=1)
        
        assert limiter.is_locked(username) is False
        assert username not in limiter.locked
