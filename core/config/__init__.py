from pydantic_settings import BaseSettings
from pydantic import Field, ConfigDict
from functools import lru_cache
from typing import Optional, List, Any, Union
from pathlib import Path
import os
import logging
import secrets

# 设置日志
logger = logging.getLogger(__name__)

# 从文件加载RSS密钥的辅助函数
def _load_rss_secret_key() -> Optional[str]:
    """从文件或环境变量加载RSS密钥"""
    rss_key = os.getenv("RSS_SECRET_KEY")
    if not rss_key:
        try:
            # 定位到项目根目录下的 rss/secret.key
            base_dir = Path(__file__).resolve().parent.parent.parent
            key_file = base_dir / "rss" / "secret.key"
            
            if key_file.exists():
                # 读取文件内容并去除空白字符
                content = key_file.read_text(encoding='utf-8').strip()
                if content:
                    rss_key = content
        except Exception as e:
            # 即使读取失败也不要让程序崩溃，记录警告即可
            logger.warning(f"尝试读取 RSS 密钥文件失败: {e}")
    return rss_key

class Settings(BaseSettings):
    """应用配置类，使用Pydantic v2实现类型安全的配置管理"""
    
    # === 基础配置 ===
    APP_ENV: str = Field(
        default="development",
        env="APP_ENV",
        description="应用环境: development, testing, production"
    )
    DEBUG: bool = Field(
        default=False,
        env="DEBUG",
        description="是否启用调试模式"
    )
    
    # === 项目路径配置 ===
    BASE_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent,
        description="项目根目录"
    )
    DOWNLOAD_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "downloads",
        env="DOWNLOAD_DIR",
        description="下载文件存储目录"
    )
    SESSION_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "sessions",
        env="SESSION_DIR",
        description="会话文件存储目录"
    )
    TEMP_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "temp",
        env="TEMP_DIR",
        description="临时文件存储目录"
    )
    LOG_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "logs",
        env="LOG_DIR",
        description="日志文件存储目录"
    )
    DB_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "db",
        env="DB_DIR",
        description="数据库文件存储目录"
    )
    
    # === 日志配置 ===
    LOG_LEVEL: str = Field(
        default="INFO",
        env="LOG_LEVEL",
        description="日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )
    DRY_RUN_LOG_LEVEL: str = Field(
        default="INFO",
        env="DRY_RUN_LOG_LEVEL",
        description="模拟运行模式的日志级别"
    )
    TELETHON_LOG_LEVEL: str = Field(
        default="WARNING",
        env="TELETHON_LOG_LEVEL",
        description="Telethon 库的日志级别"
    )
    
    # === 数据库配置 ===
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///db/forward.db",
        env="DATABASE_URL",
        description="数据库连接URL"
    )
    DB_POOL_SIZE: int = Field(
        default=20,
        env="DB_POOL_SIZE",
        description="数据库连接池大小"
    )
    DB_MAX_OVERFLOW: int = Field(
        default=30,
        env="DB_MAX_OVERFLOW",
        description="数据库连接池最大溢出连接数"
    )
    DB_ECHO: bool = Field(
        default=False,
        env="DB_ECHO",
        description="是否打印SQL语句"
    )
    DB_POOL_TIMEOUT: int = Field(default=30, env="DB_POOL_TIMEOUT")
    DB_POOL_RECYCLE: int = Field(default=3600, env="DB_POOL_RECYCLE")
    DB_POOL_PRE_PING: bool = Field(default=True, env="DB_POOL_PRE_PING")
    DB_PATH: str = Field(
        default="db/forward.db",
        env="DB_PATH",
        description="SQLite 数据库文件相对路径"
    )

    # === Web Admin Defaults ===
    WEB_ADMIN_USERNAME: Optional[str] = Field(default=None, env="WEB_ADMIN_USERNAME")
    WEB_ADMIN_PASSWORD: Optional[str] = Field(default=None, env="WEB_ADMIN_PASSWORD")
    COOKIE_SECURE: bool = Field(default=False, env="COOKIE_SECURE")
    
    # === API Optimization ===
    API_LOG_LEVEL: str = Field(default="WARNING", env="API_LOG_LEVEL")
    ENABLE_API_DEBUG: bool = Field(default=False, env="ENABLE_API_DEBUG")
    
    # === Worker 重试策略 ===
    RETRY_BASE_DELAY: float = Field(
        default=1.0,
        env="RETRY_BASE_DELAY",
        description="基础延迟时间（秒）"
    )
    RETRY_MAX_DELAY: float = Field(
        default=3600.0,
        env="RETRY_MAX_DELAY",
        description="最大延迟时间（秒）"
    )
    RETRY_BACKOFF_FACTOR: float = Field(
        default=2.0,
        env="RETRY_BACKOFF_FACTOR",
        description="退避因子"
    )
    MAX_RETRIES: int = Field(
        default=5,
        env="MAX_RETRIES",
        description="最大重试次数"
    )
    
    # === Telegram API 配置 ===
    API_ID: Optional[int] = Field(
        default=None,
        env="API_ID",
        description="Telegram API ID"
    )
    API_HASH: Optional[str] = Field(
        default=None,
        env="API_HASH",
        description="Telegram API Hash"
    )
    BOT_TOKEN: Optional[str] = Field(
        default=None,
        env="BOT_TOKEN",
        description="Telegram Bot Token"
    )
    PHONE_NUMBER: Optional[str] = Field(
        default=None,
        env="PHONE_NUMBER",
        description="Telegram 手机号"
    )
    
    # === 清理和归档配置 ===
    CLEANUP_CRON_TIMES: Union[List[str], str] = Field(
        default=["03:30"],
        env="CLEANUP_CRON_TIMES",
        description="清理任务执行时间列表"
    )
    AUTO_ARCHIVE_ENABLED: bool = Field(
        default=True,
        env="AUTO_ARCHIVE_ENABLED",
        description="是否启用自动归档"
    )
    AUTO_GC_ENABLED: bool = Field(
        default=True,
        env="AUTO_GC_ENABLED",
        description="是否启用自动垃圾回收"
    )
    ARCHIVE_COMPACT_ENABLED: bool = Field(
        default=False,
        env="ARCHIVE_COMPACT_ENABLED",
        description="是否启用归档压缩"
    )
    ARCHIVE_COMPACT_MIN_FILES: int = Field(
        default=10,
        env="ARCHIVE_COMPACT_MIN_FILES",
        description="归档压缩的最小文件数"
    )
    ARCHIVE_WRITE_PARALLEL: bool = Field(
        default=True,
        env="ARCHIVE_WRITE_PARALLEL",
        description="是否启用并行归档写入"
    )
    GC_KEEP_DAYS: int = Field(
        default=3,
        env="GC_KEEP_DAYS",
        description="垃圾回收保留天数"
    )
    GC_TEMP_DIRS: Union[List[str], str] = Field(
        default=["./temp"],
        env="GC_TEMP_DIRS",
        description="垃圾回收临时目录列表"
    )
    TEMP_GUARD_MAX: int = Field(
        default=5 * 1024**3,  # 5 GiB
        env="TEMP_GUARD_MAX",
        description="临时目录最大大小"
    )
    
    # === RSS 配置 ===
    RSS_ENABLED: bool = Field(
        default=False,
        env="RSS_ENABLED",
        description="是否启用RSS功能"
    )
    RSS_SECRET_KEY: Optional[str] = Field(
        default_factory=_load_rss_secret_key,
        env="RSS_SECRET_KEY",
        description="RSS 密钥"
    )
    RSS_HOST: str = Field(default="127.0.0.1", env="RSS_HOST")
    RSS_PORT: int = Field(default=8000, env="RSS_PORT")
    RSS_MEDIA_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "rss" / "media",
        env="RSS_MEDIA_DIR"
    )
    WEB_ENABLED: bool = Field(
        default=True,
        env="WEB_ENABLED",
        description="是否启用Web服务"
    )
    WEB_HOST: str = Field(
        default="0.0.0.0",
        env="WEB_HOST",
        description="Web服务监听地址"
    )
    WEB_PORT: int = Field(
        default=8080,
        env="WEB_PORT",
        description="Web服务监听端口"
    )
    
    # === 业务规则 ===
    DEFAULT_MAX_MEDIA_SIZE: int = Field(
        default=10,
        env="DEFAULT_MAX_MEDIA_SIZE",
        description="默认媒体大小限制（MB）"
    )
    DEFAULT_SUMMARY_TIME: str = Field(
        default="07:00",
        env="DEFAULT_SUMMARY_TIME",
        description="默认总结时间"
    )
    HISTORY_MESSAGE_LIMIT: int = Field(
        default=0,
        env="HISTORY_MESSAGE_LIMIT",
        description="历史消息数量限制，0表示无限制"
    )
    BOT_MESSAGE_DELETE_TIMEOUT: int = Field(default=300, env="BOT_MESSAGE_DELETE_TIMEOUT")
    USER_MESSAGE_DELETE_ENABLE: bool = Field(default=False, env="USER_MESSAGE_DELETE_ENABLE")
    
    # === 数据库健康检查 ===
    ENABLE_DB_HEALTH_CHECK: bool = Field(
        default=True,
        env="ENABLE_DB_HEALTH_CHECK",
        description="是否在启动时检查数据库完整性"
    )
    ENABLE_DB_AUTO_REPAIR: bool = Field(
        default=True,
        env="ENABLE_DB_AUTO_REPAIR",
        description="检测到损坏时是否尝试自动修复 (VACUUM)"
    )
    
    # === Security / JWT Config ===
    SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_hex(32),
        env="SECRET_KEY",
        description="JWT 密钥"
    )
    ALGORITHM: str = Field(default="HS256", env="JWT_ALGORITHM")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30, env="ACCESS_TOKEN_EXPIRE_MINUTES")
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7, env="REFRESH_TOKEN_EXPIRE_DAYS")

    # === 通知配置 ===
    ADMIN_IDS: Union[List[int], str] = Field(
        default=[],
        env="ADMIN_IDS",
        description="管理员 Telegram ID 列表，用于接收系统通知"
    )
    
    # === Worker 动态池配置 ===
    WORKER_MIN_CONCURRENCY: int = Field(
        default=2,
        env="WORKER_MIN_CONCURRENCY",
        description="Worker 最小并发数"
    )
    WORKER_MAX_CONCURRENCY: int = Field(
        default=10,
        env="WORKER_MAX_CONCURRENCY",
        description="Worker 最大并发数"
    )

    # 模型配置 - Pydantic v2 语法
    model_config = ConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        frozen=False,  # 允许在运行时修改配置
        title="应用配置",
        description="TelegramForwarder 应用配置"
    )

    from pydantic import field_validator

    @field_validator("CLEANUP_CRON_TIMES", "GC_TEMP_DIRS", "ADMIN_IDS", mode="before")
    @classmethod
    def parse_list_fields(cls, v: Any) -> List[Any]:
        if isinstance(v, str):
            import json
            try:
                # 尝试 JSON 解析
                return json.loads(v)
            except json.JSONDecodeError:
                # 逗号分隔回退
                return [t.strip() for t in v.split(",") if t.strip()]
        return v
    
    def validate_required(self) -> None:
        """验证必要的配置项"""
        missing = []
        if not self.API_ID:
            missing.append("API_ID")
        if not self.API_HASH:
            missing.append("API_HASH")
        if not self.BOT_TOKEN:
            missing.append("BOT_TOKEN")
        if not self.PHONE_NUMBER:
            missing.append("PHONE_NUMBER")
        if missing:
            logger.error(
                f"缺少必要环境变量: {', '.join(missing)}。请在 .env 中配置后重试。"
            )
            raise SystemExit(1)
    


# 单例模式获取配置 - 使用lru_cache确保全局只有一个实例
@lru_cache()
def get_settings() -> Settings:
    """获取配置实例，使用lru_cache实现单例模式"""
    return Settings()

# 全局配置实例，方便直接导入使用
settings = get_settings()