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
"""

from collections import defaultdict
from datetime import datetime, timedelta
from typing import Optional, Dict, List
import logging

logger = logging.getLogger(__name__)


class LoginRateLimiter:
    """登录尝试限流器"""
    
    # 配置常量
    MAX_ATTEMPTS = 5  # 最大失败次数
    TIME_WINDOW = timedelta(minutes=5)  # 时间窗口
    LOCKOUT_DURATION = timedelta(minutes=30)  # 锁定时长
    
    def __init__(self):
        """初始化限流器"""
        # {username: [timestamp1, timestamp2, ...]}
        self.attempts: Dict[str, List[datetime]] = defaultdict(list)
        
        # {username: unlock_time}
        self.locked: Dict[str, datetime] = {}
        
        # IP 维度限流 {ip: [timestamp1, timestamp2, ...]}
        self.ip_attempts: Dict[str, List[datetime]] = defaultdict(list)
        
        # IP 锁定 {ip: unlock_time}
        self.ip_locked: Dict[str, datetime] = {}
        
        logger.info("登录限流器已初始化")
    
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
        
        if username in self.locked:
            unlock_time = self.locked[username]
            now = datetime.now()
            
            # 检查是否已过锁定期
            if now < unlock_time:
                remaining = (unlock_time - now).total_seconds()
                logger.warning(
                    f"账户 {username} 仍处于锁定状态，剩余 {remaining:.0f} 秒"
                )
                return True
            else:
                # 自动解锁
                logger.info(f"账户 {username} 自动解锁")
                del self.locked[username]
                if username in self.attempts:
                    del self.attempts[username]
        
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
        
        if ip_address in self.ip_locked:
            unlock_time = self.ip_locked[ip_address]
            now = datetime.now()
            
            if now < unlock_time:
                remaining = (unlock_time - now).total_seconds()
                logger.warning(
                    f"IP {ip_address} 仍处于锁定状态，剩余 {remaining:.0f} 秒"
                )
                return True
            else:
                logger.info(f"IP {ip_address} 自动解锁")
                del self.ip_locked[ip_address]
                if ip_address in self.ip_attempts:
                    del self.ip_attempts[ip_address]
        
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
        
        if username in self.locked:
            unlock_time = self.locked[username]
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
                del self.locked[username]
                if username in self.attempts:
                    del self.attempts[username]
        
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
        
        # 清理时间窗口外的旧记录
        cutoff_time = now - self.TIME_WINDOW
        self.attempts[username] = [
            t for t in self.attempts[username] 
            if t > cutoff_time
        ]
        
        # 添加本次失败记录
        self.attempts[username].append(now)
        
        attempt_count = len(self.attempts[username])
        
        logger.warning(
            f"登录失败: username={username}, ip={ip_address}, "
            f"attempts={attempt_count}/{self.MAX_ATTEMPTS}"
        )
        
        locked = False
        
        # 检查是否超过限制
        if attempt_count >= self.MAX_ATTEMPTS:
            # 触发锁定
            unlock_time = now + self.LOCKOUT_DURATION
            self.locked[username] = unlock_time
            
            logger.error(
                f"账户已锁定: username={username}, unlock_at={unlock_time.isoformat()}"
            )
            locked = True
        
        # IP 维度限流
        if ip_address:
            self.ip_attempts[ip_address] = [
                t for t in self.ip_attempts[ip_address]
                if t > cutoff_time
            ]
            self.ip_attempts[ip_address].append(now)
            ip_attempt_count = len(self.ip_attempts[ip_address])
            
            if ip_attempt_count >= self.MAX_ATTEMPTS:
                unlock_time = now + self.LOCKOUT_DURATION
                self.ip_locked[ip_address] = unlock_time
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
        
        # 清除失败记录
        if username in self.attempts:
            del self.attempts[username]
        
        # 清除锁定状态
        if username in self.locked:
            del self.locked[username]
        
        # 清除IP维度记录
        if ip_address and ip_address in self.ip_attempts:
            del self.ip_attempts[ip_address]
        if ip_address and ip_address in self.ip_locked:
            del self.ip_locked[ip_address]
        
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
        
        if username in self.locked:
            del self.locked[username]
        
        if username in self.attempts:
            del self.attempts[username]
        
        logger.info(f"账户已手动解锁: username={username}")
    
    def get_stats(self) -> Dict:
        """
        获取统计信息
        
        Returns:
            dict: 统计数据
        """
        now = datetime.now()
        
        # 清理过期的锁定
        expired_locks = [
            username for username, unlock_time in self.locked.items()
            if now >= unlock_time
        ]
        for username in expired_locks:
            del self.locked[username]
        
        return {
            'locked_accounts': len(self.locked),
            'accounts_with_attempts': len(self.attempts),
            'total_attempts': sum(len(attempts) for attempts in self.attempts.values()),
            'locked_ips': len(self.ip_locked),
            'ips_with_attempts': len(self.ip_attempts),
            'config': {
                'max_attempts': self.MAX_ATTEMPTS,
                'time_window_minutes': self.TIME_WINDOW.total_seconds() / 60,
                'lockout_duration_minutes': self.LOCKOUT_DURATION.total_seconds() / 60
            }
        }
    
    def cleanup_expired(self):
        """清理过期的记录（定期调用）"""
        now = datetime.now()
        
        # 清理过期的锁定
        expired_locks = [
            username for username, unlock_time in self.locked.items()
            if now >= unlock_time
        ]
        
        for username in expired_locks:
            del self.locked[username]
            if username in self.attempts:
                del self.attempts[username]
        
        # 清理过期的IP锁定
        expired_ip_locks = [
            ip for ip, unlock_time in self.ip_locked.items()
            if now >= unlock_time
        ]
        
        for ip in expired_ip_locks:
            del self.ip_locked[ip]
            if ip in self.ip_attempts:
                del self.ip_attempts[ip]
        
        if expired_locks:
            logger.info(f"已清理 {len(expired_locks)} 个过期锁定")
        if expired_ip_locks:
            logger.info(f"已清理 {len(expired_ip_locks)} 个过期IP锁定")
        
        # 清理所有时间窗口外的尝试记录
        cutoff_time = now - self.TIME_WINDOW
        usernames_to_remove = []
        
        for username, attempts in self.attempts.items():
            # 过滤掉时间窗口外的记录
            recent_attempts = [t for t in attempts if t > cutoff_time]
            
            if recent_attempts:
                self.attempts[username] = recent_attempts
            else:
                usernames_to_remove.append(username)
        
        for username in usernames_to_remove:
            del self.attempts[username]
        
        if usernames_to_remove:
            logger.info(f"已清理 {len(usernames_to_remove)} 个用户的过期尝试记录")
        
        # 清理IP维度的时间窗口外记录
        ips_to_remove = []
        for ip, attempts in self.ip_attempts.items():
            recent_attempts = [t for t in attempts if t > cutoff_time]
            if recent_attempts:
                self.ip_attempts[ip] = recent_attempts
            else:
                ips_to_remove.append(ip)
        
        for ip in ips_to_remove:
            del self.ip_attempts[ip]


# 全局单例（在fastapi_app.py中初始化）
_rate_limiter_instance: Optional[LoginRateLimiter] = None


def get_rate_limiter() -> LoginRateLimiter:
    """获取限流器单例"""
    global _rate_limiter_instance
    if _rate_limiter_instance is None:
        _rate_limiter_instance = LoginRateLimiter()
    return _rate_limiter_instance
