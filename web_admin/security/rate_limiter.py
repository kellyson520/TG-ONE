"""
登录限流器 - 防止暴力破解攻击

功能:
- 记录登录失败次数
- 超过阈值后自动锁定账户
- 支持自动解锁
- 支持手动解锁（管理员）

规则:
- 5分钟内最多允许5次失败尝试
- 超过后锁定账户30分钟
- 锁定期间所有登录尝试返回429

持久化: 使用 SQLite 存储，重启后不丢失
"""

from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging
import sqlite3
import threading
import os

logger = logging.getLogger(__name__)

# 默认数据库路径
_DEFAULT_DB_PATH = os.path.join(os.path.dirname(__file__), "..", "..", "data", "rate_limiter.db")


class LoginRateLimiter:
    """登录尝试限流器 (SQLite 持久化)"""
    
    # 配置常量
    MAX_ATTEMPTS = 5  # 最大失败次数
    TIME_WINDOW = timedelta(minutes=5)  # 时间窗口
    LOCKOUT_DURATION = timedelta(minutes=30)  # 锁定时长
    
    def __init__(self, db_path: str = None):
        """初始化限流器"""
        self._db_path = db_path or _DEFAULT_DB_PATH
        # 确保目录存在
        os.makedirs(os.path.dirname(self._db_path), exist_ok=True)
        self._local = threading.local()
        self._init_db()
        logger.info("登录限流器已初始化 (SQLite 持久化)")

    def _get_conn(self) -> sqlite3.Connection:
        """获取线程本地的数据库连接"""
        if not hasattr(self._local, "conn") or self._local.conn is None:
            self._local.conn = sqlite3.connect(self._db_path, timeout=10)
            self._local.conn.execute("PRAGMA journal_mode=WAL")
            self._local.conn.execute("PRAGMA busy_timeout=5000")
        return self._local.conn

    def _init_db(self):
        """初始化数据库表"""
        conn = self._get_conn()
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS login_attempts (
                key TEXT NOT NULL,
                dimension TEXT NOT NULL CHECK(dimension IN ('username', 'ip')),
                attempt_time TEXT NOT NULL,
                PRIMARY KEY (key, dimension, attempt_time)
            );
            CREATE TABLE IF NOT EXISTS login_locks (
                key TEXT NOT NULL,
                dimension TEXT NOT NULL CHECK(dimension IN ('username', 'ip')),
                unlock_time TEXT NOT NULL,
                PRIMARY KEY (key, dimension)
            );
            CREATE INDEX IF NOT EXISTS idx_attempts_key_dim ON login_attempts(key, dimension);
        """)
        conn.commit()

    def is_locked(self, username: str) -> bool:
        """
        检查账户是否被锁定
        
        Args:
            username: 用户名
            
        Returns:
            bool: True=已锁定, False=未锁定
        """
        if not username:
            return False
        
        username = username.lower()  # 统一转小写
        
        conn = self._get_conn()
        row = conn.execute(
            "SELECT unlock_time FROM login_locks WHERE key=? AND dimension='username'",
            (username,)
        ).fetchone()
        
        if not row:
            return False
        
        unlock_time = datetime.fromisoformat(row[0])
        now = datetime.now()
        
        if now < unlock_time:
            remaining = (unlock_time - now).total_seconds()
            logger.warning(
                f"账户 {username} 仍处于锁定状态，剩余 {remaining:.0f} 秒"
            )
            return True
        else:
            # 自动解锁
            logger.info(f"账户 {username} 自动解锁")
            conn.execute("DELETE FROM login_locks WHERE key=? AND dimension='username'", (username,))
            conn.execute("DELETE FROM login_attempts WHERE key=? AND dimension='username'", (username,))
            conn.commit()
        
        return False

    def is_ip_locked(self, ip_address: str) -> bool:
        """
        检查 IP 是否被锁定
        
        Args:
            ip_address: IP 地址
            
        Returns:
            bool: True=已锁定, False=未锁定
        """
        if not ip_address:
            return False
        
        conn = self._get_conn()
        row = conn.execute(
            "SELECT unlock_time FROM login_locks WHERE key=? AND dimension='ip'",
            (ip_address,)
        ).fetchone()
        
        if not row:
            return False
        
        unlock_time = datetime.fromisoformat(row[0])
        now = datetime.now()
        
        if now < unlock_time:
            remaining = (unlock_time - now).total_seconds()
            logger.warning(
                f"IP {ip_address} 仍处于锁定状态，剩余 {remaining:.0f} 秒"
            )
            return True
        else:
            logger.info(f"IP {ip_address} 自动解锁")
            conn.execute("DELETE FROM login_locks WHERE key=? AND dimension='ip'", (ip_address,))
            conn.execute("DELETE FROM login_attempts WHERE key=? AND dimension='ip'", (ip_address,))
            conn.commit()
        
        return False
    
    def get_lockout_info(self, username: str) -> Optional[Dict]:
        """
        获取锁定信息
        
        Args:
            username: 用户名
            
        Returns:
            dict: {locked: bool, unlock_at: str, remaining_seconds: int}
                  或 None（未锁定）
        """
        if not username:
            return None
        
        username = username.lower()
        
        conn = self._get_conn()
        row = conn.execute(
            "SELECT unlock_time FROM login_locks WHERE key=? AND dimension='username'",
            (username,)
        ).fetchone()
        
        if not row:
            return None
        
        unlock_time = datetime.fromisoformat(row[0])
        now = datetime.now()
        
        if now < unlock_time:
            remaining = int((unlock_time - now).total_seconds())
            return {
                'locked': True,
                'unlock_at': unlock_time.isoformat(),
                'remaining_seconds': remaining,
                'remaining_minutes': remaining // 60
            }
        else:
            # 已过期，清理
            conn.execute("DELETE FROM login_locks WHERE key=? AND dimension='username'", (username,))
            conn.execute("DELETE FROM login_attempts WHERE key=? AND dimension='username'", (username,))
            conn.commit()
        
        return None
    
    def record_failure(self, username: str, ip_address: str = None) -> bool:
        """
        记录登录失败
        
        Args:
            username: 用户名
            ip_address: IP地址（可选，用于日志和IP维度限流）
            
        Returns:
            bool: True=触发锁定, False=仅记录
        """
        if not username:
            return False
        
        username = username.lower()
        now = datetime.now()
        cutoff_time = now - self.TIME_WINDOW
        cutoff_str = cutoff_time.isoformat()
        
        conn = self._get_conn()
        
        # 清理时间窗口外的旧记录
        conn.execute(
            "DELETE FROM login_attempts WHERE key=? AND dimension='username' AND attempt_time < ?",
            (username, cutoff_str)
        )
        
        # 添加本次失败记录
        conn.execute(
            "INSERT OR IGNORE INTO login_attempts (key, dimension, attempt_time) VALUES (?, 'username', ?)",
            (username, now.isoformat())
        )
        
        # 统计当前窗口内的失败次数
        attempt_count = conn.execute(
            "SELECT COUNT(*) FROM login_attempts WHERE key=? AND dimension='username'",
            (username,)
        ).fetchone()[0]
        
        logger.warning(
            f"登录失败: username={username}, ip={ip_address}, "
            f"attempts={attempt_count}/{self.MAX_ATTEMPTS}"
        )
        
        conn.commit()
        locked = False
        
        # 检查是否超过限制
        if attempt_count >= self.MAX_ATTEMPTS:
            # 触发锁定
            unlock_time = now + self.LOCKOUT_DURATION
            conn.execute(
                "INSERT OR REPLACE INTO login_locks (key, dimension, unlock_time) VALUES (?, 'username', ?)",
                (username, unlock_time.isoformat())
            )
            conn.commit()
            
            logger.error(
                f"账户已锁定: username={username}, unlock_at={unlock_time.isoformat()}"
            )
            locked = True
        
        # IP 维度限流
        if ip_address:
            conn.execute(
                "DELETE FROM login_attempts WHERE key=? AND dimension='ip' AND attempt_time < ?",
                (ip_address, cutoff_str)
            )
            conn.execute(
                "INSERT OR IGNORE INTO login_attempts (key, dimension, attempt_time) VALUES (?, 'ip', ?)",
                (ip_address, now.isoformat())
            )
            ip_attempt_count = conn.execute(
                "SELECT COUNT(*) FROM login_attempts WHERE key=? AND dimension='ip'",
                (ip_address,)
            ).fetchone()[0]
            conn.commit()
            
            if ip_attempt_count >= self.MAX_ATTEMPTS:
                unlock_time = now + self.LOCKOUT_DURATION
                conn.execute(
                    "INSERT OR REPLACE INTO login_locks (key, dimension, unlock_time) VALUES (?, 'ip', ?)",
                    (ip_address, unlock_time.isoformat())
                )
                conn.commit()
                logger.error(
                    f"IP 已锁定: ip={ip_address}, unlock_at={unlock_time.isoformat()}"
                )
                locked = True
        
        return locked
    
    def record_success(self, username: str, ip_address: str = None):
        """
        记录登录成功，清除失败记录
        
        Args:
            username: 用户名
            ip_address: IP地址（可选，用于清除IP维度记录）
        """
        if not username:
            return
        
        username = username.lower()
        conn = self._get_conn()
        
        # 清除失败记录和锁定状态
        conn.execute("DELETE FROM login_attempts WHERE key=? AND dimension='username'", (username,))
        conn.execute("DELETE FROM login_locks WHERE key=? AND dimension='username'", (username,))
        
        # 清除IP维度记录
        if ip_address:
            conn.execute("DELETE FROM login_attempts WHERE key=? AND dimension='ip'", (ip_address,))
            conn.execute("DELETE FROM login_locks WHERE key=? AND dimension='ip'", (ip_address,))
        
        conn.commit()
        logger.info(f"登录成功，已清除限流记录: username={username}")
    
    def unlock(self, username: str):
        """
        手动解锁账户（管理员操作）
        
        Args:
            username: 用户名
        """
        if not username:
            return
        
        username = username.lower()
        conn = self._get_conn()
        
        conn.execute("DELETE FROM login_locks WHERE key=? AND dimension='username'", (username,))
        conn.execute("DELETE FROM login_attempts WHERE key=? AND dimension='username'", (username,))
        conn.commit()
        
        logger.info(f"账户已手动解锁: username={username}")
    
    def get_stats(self) -> Dict:
        """
        获取统计信息
        
        Returns:
            dict: 统计数据
        """
        conn = self._get_conn()
        
        # 清理过期的锁定
        now_str = datetime.now().isoformat()
        expired = conn.execute(
            "SELECT key FROM login_locks WHERE unlock_time < ?", (now_str,)
        ).fetchall()
        for row in expired:
            conn.execute("DELETE FROM login_locks WHERE key=?", (row[0],))
            conn.execute("DELETE FROM login_attempts WHERE key=?", (row[0],))
        conn.commit()
        
        locked_accounts = conn.execute(
            "SELECT COUNT(*) FROM login_locks WHERE dimension='username'"
        ).fetchone()[0]
        locked_ips = conn.execute(
            "SELECT COUNT(*) FROM login_locks WHERE dimension='ip'"
        ).fetchone()[0]
        accounts_with_attempts = conn.execute(
            "SELECT COUNT(DISTINCT key) FROM login_attempts WHERE dimension='username'"
        ).fetchone()[0]
        ips_with_attempts = conn.execute(
            "SELECT COUNT(DISTINCT key) FROM login_attempts WHERE dimension='ip'"
        ).fetchone()[0]
        total_attempts = conn.execute(
            "SELECT COUNT(*) FROM login_attempts"
        ).fetchone()[0]
        
        return {
            'locked_accounts': locked_accounts,
            'accounts_with_attempts': accounts_with_attempts,
            'total_attempts': total_attempts,
            'locked_ips': locked_ips,
            'ips_with_attempts': ips_with_attempts,
            'config': {
                'max_attempts': self.MAX_ATTEMPTS,
                'time_window_minutes': self.TIME_WINDOW.total_seconds() / 60,
                'lockout_duration_minutes': self.LOCKOUT_DURATION.total_seconds() / 60
            }
        }
    
    def cleanup_expired(self):
        """清理过期的记录（定期调用）"""
        now = datetime.now()
        now_str = now.isoformat()
        cutoff_str = (now - self.TIME_WINDOW).isoformat()
        
        conn = self._get_conn()
        
        # 清理过期的锁定
        expired = conn.execute(
            "SELECT key, dimension FROM login_locks WHERE unlock_time < ?", (now_str,)
        ).fetchall()
        for key, dim in expired:
            conn.execute("DELETE FROM login_locks WHERE key=? AND dimension=?", (key, dim))
            conn.execute("DELETE FROM login_attempts WHERE key=? AND dimension=?", (key, dim))
        
        # 清理时间窗口外的尝试记录
        conn.execute(
            "DELETE FROM login_attempts WHERE attempt_time < ?", (cutoff_str,)
        )
        
        conn.commit()
        
        if expired:
            logger.info(f"已清理 {len(expired)} 个过期锁定")


# 全局单例（在fastapi_app.py中初始化）
_rate_limiter_instance: Optional[LoginRateLimiter] = None


def get_rate_limiter() -> LoginRateLimiter:
    """获取限流器单例"""
    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        _rate_limiter_instance = LoginRateLimiter()
    return _rate_limiter_instance
