from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from functools import lru_cache
from typing import Optional, List, Any, Union
from pathlib import Path

import logging
import secrets
import os

# 设置日志
logger = logging.getLogger(__name__)

# 从文件加载RSS密钥的辅助函数
def _load_rss_secret_key() -> Optional[str]:
    """从文件加载RSS密钥"""
    rss_key = None
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
        description="应用环境: development, testing, production"
    )
    DEBUG: bool = Field(
        default=False,
        description="是否启用调试模式"
    )
    
    # === 项目路径配置 ===
    BASE_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent,
        description="项目根目录"
    )
    DOWNLOAD_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "downloads",
        description="下载文件存储目录"
    )
    SESSION_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "sessions",
        description="会话文件存储目录"
    )
    TEMP_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "temp",
        description="临时文件存储目录"
    )
    LOG_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "logs",
        description="日志文件存储目录"
    )
    DB_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "db",
        description="数据库文件存储目录"
    )
    BACKUP_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "backups",
        description="数据库备份存储目录"
    )
    
    # === 日志配置 ===
    LOG_LEVEL: str = Field(
        default="INFO",
        description="日志级别: DEBUG, INFO, WARNING, ERROR, CRITICAL"
    )
    LOG_FORMAT: str = Field(default="text")
    LOG_INCLUDE_TRACEBACK: bool = Field(default=False)
    LOG_COLOR: bool = Field(default=True)
    LOG_MAX_BYTES: int = Field(default=10 * 1024 * 1024)
    LOG_BACKUP_COUNT: int = Field(default=5)
    LOG_KEY_ONLY: bool = Field(default=True)
    
    LOG_MUTE_LOGGERS: Union[List[str], str] = Field(default=[])
    LOG_MUTE_CATEGORIES: Union[List[str], str] = Field(default=[])
    LOG_DROP_PATTERNS: str = Field(default="")
    LOG_ALLOW_PATTERNS: str = Field(default="")
    LOG_GLOBAL_DROP_PATTERNS: str = Field(default="")
    LOG_LEVEL_OVERRIDES: str = Field(default="")

    DRY_RUN_LOG_LEVEL: str = Field(
        default="INFO",
        description="模拟运行模式的日志级别"
    )
    TELETHON_LOG_LEVEL: str = Field(
        default="WARNING",
        description="Telethon 库的日志级别"
    )
    
    # === 数据库配置 ===
    DATABASE_URL: str = Field(
        default="sqlite+aiosqlite:///db/forward.db",
        description="数据库连接URL"
    )
    DB_POOL_SIZE: int = Field(
        default=20,
        description="数据库连接池大小"
    )
    DB_MAX_OVERFLOW: int = Field(
        default=30,
        description="数据库连接池最大溢出连接数"
    )
    DB_ECHO: bool = Field(
        default=False,
        description="是否打印SQL语句"
    )
    DB_POOL_TIMEOUT: int = Field(default=30)
    DB_POOL_RECYCLE: int = Field(default=3600)
    DB_POOL_PRE_PING: bool = Field(default=True)
    DB_PATH: str = Field(
        default="db/forward.db",
        description="SQLite 数据库文件相对路径"
    )

    # === Web Admin Defaults ===
    WEB_ADMIN_USERNAME: Optional[str] = Field(default=None)
    WEB_ADMIN_PASSWORD: Optional[str] = Field(default=None)
    COOKIE_SECURE: bool = Field(default=False)
    ALLOW_REGISTRATION: bool = Field(
        default=False, 
        description="是否允许 Web 用户注册"
    )
    
    # === 媒体处理配置 ===
    MAX_MEDIA_SIZE: float = Field(
        default=2000.0, 
        description="允许下载的最大媒体文件大小 (MB)"
    )
    
    # === 聊天信息更新配置 ===
    CHAT_UPDATE_TIME: str = Field(
        default="03:00", 
        description="每天定时更新聊天信息的时间"
    )
    CHAT_UPDATE_LIMIT: int = Field(
        default=50, 
        description="单次更新的最大聊天数量"
    )
    CHAT_UPDATE_BATCH_SIZE: int = Field(
        default=10,
        description="聊天信息更新批量处理大小"
    )
    CHAT_UPDATE_SLEEP_BASE: float = Field(
        default=2.0, 
        description="更新每个聊天后的基础休眠时间"
    )
    CHAT_UPDATE_SLEEP_JITTER: float = Field(
        default=0.5, 
        description="体眠时间抖动系数"
    )

    # === 持久化缓存 ===
    REDIS_URL: Optional[str] = Field(
        default=None, 
        description="Redis 连接 URL (例如 redis://localhost:6379/0)"
    )
    PERSIST_CACHE_SQLITE: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "db" / "cache.db",
        description="SQLite 持久化缓存文件路径"
    )

    # === API 优化与流量控制 ===
    API_LOG_LEVEL: str = Field(default="WARNING")
    ENABLE_API_DEBUG: bool = Field(default=False)
    
    ENABLE_KEYWORD_SEARCH_API: bool = Field(default=True)
    ENABLE_MEDIA_INFO_OPTIMIZATION: bool = Field(default=True)
    FORWARD_ENABLE_BATCH_API: bool = Field(default=True)
    
    FORWARD_MAX_BATCH_SIZE: int = Field(default=50)
    FORWARD_MIN_BATCH_SIZE: int = Field(default=2)
    
    MEDIA_SAMPLE_SIZE: int = Field(default=1024)
    ENABLE_MEDIA_CACHE: bool = Field(default=True)
    
    SEARCH_CACHE_TTL: int = Field(default=300)
    MAX_SEARCH_RESULTS: int = Field(default=100)
    
    ENABLE_AUTO_FALLBACK: bool = Field(default=True)
    API_FALLBACK_TIMEOUT: int = Field(default=10)
    MAX_API_RETRIES: int = Field(default=3)
    
    ENABLE_PERFORMANCE_MONITORING: bool = Field(default=True)

    # === 流量控制与节流 ===
    FORWARD_GLOBAL_MIN_INTERVAL_MS: int = Field(default=0)
    FORWARD_TARGET_MIN_INTERVAL_MS: int = Field(default=1200)
    FORWARD_PAIR_MIN_INTERVAL_MS: int = Field(default=800)
    FORWARD_PACING_JITTER: float = Field(default=0.2)
    
    # === 监控与健康检查 ===
    HEALTH_HOST: str = Field(default="0.0.0.0")
    HEALTH_PORT: int = Field(default=9000)
    
    # === 联网更新配置 ===
    AUTO_UPDATE_ENABLED: bool = Field(
        default=False,
        description="是否开启定时自动检查更新"
    )
    UPDATE_CHECK_INTERVAL: int = Field(
        default=86400,
        description="检查更新的间隔时间 (秒)"
    )
    UPDATE_REMOTE_URL: str = Field(
        default="https://github.com/kellyson520/TG-ONE.git",
        description="远程更新源 (Git Repo 或版本信息 URL)"
    )
    UPDATE_BRANCH: str = Field(
        default="main",
        description="用于更新的 Git 分支"
    )

    # 限流并发控制 (Legacy & New)
    # 限流并发控制
    FORWARD_MAX_CONCURRENCY_GLOBAL: int = Field(default=50)
    FORWARD_MAX_CONCURRENCY_PER_TARGET: int = Field(default=2)
    FORWARD_MAX_CONCURRENCY_PER_PAIR: int = Field(default=1)

    # === 日志推送 (Telegram) ===
    LOG_PUSH_TG_ENABLE: bool = Field(default=False)
    LOG_PUSH_TG_BOT_TOKEN: Optional[str] = Field(default=None)
    LOG_PUSH_TG_CHAT_ID: Optional[Union[int, str]] = Field(default=None)
    LOG_PUSH_TG_LEVEL: str = Field(default="ERROR")
    
    # === Worker 重试策略 ===
    RETRY_BASE_DELAY: float = Field(
        default=1.0,
        description="基础延迟时间（秒）"
    )
    RETRY_MAX_DELAY: float = Field(
        default=3600.0,
        description="最大延迟时间（秒）"
    )
    RETRY_BACKOFF_FACTOR: float = Field(
        default=2.0,
        description="退避因子"
    )
    MAX_RETRIES: int = Field(
        default=5,
        description="最大重试次数"
    )
    
    # === 历史任务进阶配置 ===
    HISTORY_LOCAL_SEEN_LIMIT: int = Field(default=20000)
    HISTORY_BATCH_SIZE: int = Field(default=5)
    HISTORY_FLUSH_EVERY: int = Field(default=20)
    HISTORY_FLUSH_INTERVAL: float = Field(default=5.0)
    AUTO_DOWNGRADE_PROTECTED: bool = Field(default=False)
    HISTORY_POWER_SAVE: bool = Field(default=False)
    HISTORY_SMART_ADAPT: bool = Field(default=True)
    HISTORY_QUEUE_SIZE: int = Field(default=500)
    
    # === 用户与备份配置 ===
    USER_ID: Optional[int] = Field(default=None)
    # === 备份与迁移配置 ===

    MIGRATE_BATCH_SIZE: int = Field(default=5000)
    DATABASE_URL_SQLITE: Optional[str] = Field(default=None)
    DATABASE_URL_TARGET: Optional[str] = Field(default=None)
    
    OS_USERNAME: str = Field(
        default_factory=lambda: os.getenv("USERNAME", "Administrator"),
        description="当前操作系统用户名，用于权限分配"
    )
    
    # === Telegram API 配置 ===
    API_ID: Optional[int] = Field(
        default=None,
        description="Telegram API ID"
    )
    API_HASH: Optional[str] = Field(
        default=None,
        description="Telegram API Hash"
    )
    BOT_TOKEN: Optional[str] = Field(
        default=None,
        description="Telegram Bot Token"
    )
    PHONE_NUMBER: Optional[str] = Field(
        default=None,
        description="Telegram 手机号"
    )

    # === 归档存储与 S3 (DuckDB/Parquet) ===
    ARCHIVE_ROOT: str = Field(
        default="./archive/parquet", 
        description="归档数据根路径 (本地路径或 S3 URL)"
    )
    ARCHIVE_PARQUET_COMPRESSION: str = Field(default="ZSTD")
    ARCHIVE_PARQUET_ROW_GROUP_SIZE: int = Field(default=100000)
    ARCHIVE_QUERY_DEBUG: bool = Field(default=False)
    ARCHIVE_WRITE_CHUNK_SIZE: int = Field(default=200000)
    
    # S3 / AWS 凭据
    AWS_REGION: Optional[str] = Field(default=None)
    S3_REGION: Optional[str] = Field(default=None)
    S3_ENDPOINT: Optional[str] = Field(default=None)
    AWS_ACCESS_KEY_ID: Optional[str] = Field(default=None)
    AWS_SECRET_ACCESS_KEY: Optional[str] = Field(default=None)
    AWS_SESSION_TOKEN: Optional[str] = Field(default=None)
    S3_SSL_ENABLE: bool = Field(default=True)
    
    # DuckDB 性能优化
    DUCKDB_THREADS: int = Field(default=0)
    DUCKDB_MEMORY_LIMIT: Optional[str] = Field(default=None)
    
    # === Bloom Filter 指数配置 ===
    BLOOM_ROOT: str = Field(
        default="./archive/bloom", 
        description="Bloom Filter 数据根路径"
    )
    BLOOM_BITS: int = Field(default=1 << 24)
    BLOOM_HASHES: int = Field(default=7)
    BLOOM_SHARD_BY: str = Field(default="chat")
    BLOOM_CACHE_MAX_ENTRIES: int = Field(default=1024)
    BLOOM_CACHE_TTL_SEC: int = Field(default=300)
    
    # === AI 提供者配置 ===
    OPENAI_API_KEY: Optional[str] = Field(default=None)
    OPENAI_API_BASE: Optional[str] = Field(default=None)
    
    GEMINI_API_KEY: Optional[str] = Field(default=None)
    GEMINI_API_BASE: Optional[str] = Field(default=None)
    
    CLAUDE_API_KEY: Optional[str] = Field(default=None)
    CLAUDE_API_BASE: Optional[str] = Field(default=None)
    
    DEEPSEEK_API_KEY: Optional[str] = Field(default=None)
    DEEPSEEK_API_BASE: Optional[str] = Field(default=None)
    
    GROK_API_KEY: Optional[str] = Field(default=None)
    QWEN_API_KEY: Optional[str] = Field(default=None)
    
    # === 清理和归档配置 ===
    CLEANUP_CRON_TIMES: Union[List[str], str] = Field(
        default=["03:30"],
        description="清理任务执行时间列表"
    )
    AUTO_ARCHIVE_ENABLED: bool = Field(
        default=True,
        description="是否启用自动归档"
    )
    AUTO_GC_ENABLED: bool = Field(
        default=True,
        description="是否启用自动垃圾回收"
    )
    
    # === 转发记录配置 ===
    FORWARD_RECORDER_MODE: str = Field(
        default="summary", 
        description="转发记录模式 (full/summary/off)"
    )
    FORWARD_RECORDER_DIR: Path = Field(
        default=Path("./zhuanfaji"), 
        description="转发记录存储目录"
    )

    # === AI 总结调度配置 ===
    SUMMARY_CONCURRENCY: int = Field(
        default=5, 
        description="并发生成的总结任务数量"
    )
    SUMMARY_BATCH_SIZE: int = Field(
        default=20, 
        description="单次拉取的消息批次大小"
    )
    SUMMARY_BATCH_DELAY: int = Field(
        default=2, 
        description="拉取批次间的延迟（秒）"
    )

    # === 错误通知配置 ===
    ERROR_NOTIFY_THROTTLE_SECONDS: int = Field(
        default=30, 
        description="相同错误的通知节流时间（秒）"
    )

    # === 归档查询配置 ===
    ARCHIVE_COLD_LOOKBACK_DAYS: int = Field(
        default=30, 
        description="归档冷数据查询的回溯天数"
    )

    # 归档保留天数
    HOT_DAYS_SIGN: int = Field(default=60)
    HOT_DAYS_LOG: int = Field(default=30)
    HOT_DAYS_STATS: int = Field(default=180)
    
    # 归档批量大小
    ARCHIVE_BATCH_SIZE: int = Field(default=100000)
    ARCHIVE_LOG_BATCH_SIZE: int = Field(default=200000)
    ARCHIVE_TASK_BATCH_SIZE: int = Field(default=100000)
    ARCHIVE_STATS_BATCH_SIZE: int = Field(default=500000)
    
    # 归档性能与压实
    ARCHIVE_WRITE_PARALLEL: bool = Field(default=True)
    ARCHIVE_WRITE_MAX_WORKERS: int = Field(default=4)
    ARCHIVE_COMPACT_ENABLED: bool = Field(default=False)
    ARCHIVE_COMPACT_MIN_FILES: int = Field(default=10)

    # 垃圾回收 (GC)
    GC_KEEP_DAYS: int = Field(
        default=3,
        description="垃圾回收保留天数"
    )
    GC_TEMP_DIRS: Union[List[str], str] = Field(
        default=["./temp"],
        description="垃圾回收临时目录列表"
    )
    TEMP_GUARD_MAX: int = Field(
        default=5 * 1024**3,  # 5 GiB
        description="临时目录最大大小"
    )
    
    # === 去重与持久化缓存 ===
    DEDUP_PERSIST_TTL_SECONDS: int = Field(
        default=2592000, 
        description="去重记录持久化TTL (默认30天)"
    )
    VIDEO_HASH_PERSIST_TTL_SECONDS: int = Field(
        default=15552000, 
        description="视频哈希持久化TTL (默认180天)"
    )
    
    # === RSS 进阶配置 ===
    RSS_ENABLED: bool = Field(
        default=False,
        description="是否启用RSS功能"
    )
    RSS_SECRET_KEY: Optional[str] = Field(
        default_factory=_load_rss_secret_key,
        description="RSS 密钥"
    )
    RSS_HOST: str = Field(default="127.0.0.1")
    RSS_PORT: int = Field(default=8000)
    RSS_BASE_URL: Optional[str] = Field(default=None)
    RSS_MEDIA_BASE_URL: str = Field(default="")
    RSS_MEDIA_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "rss" / "media"
    )
    RSS_DATA_DIR: Path = Field(
        default_factory=lambda: Path(__file__).resolve().parent.parent.parent / "rss" / "data"
    )
    
    # === Web 服务配置 ===
    WEB_ENABLED: bool = Field(
        default=True,
        description="是否启用Web服务"
    )
    WEB_HOST: str = Field(
        default="0.0.0.0",
        description="Web服务监听地址"
    )
    WEB_PORT: int = Field(
        default=8080,
        description="Web服务监听端口"
    )
    
    # === UI 与分页配置 ===
    PROJECT_NAME: str = Field(default="TG Forwarder RSS")
    DEFAULT_TIMEZONE: str = Field(default="Asia/Shanghai")
    TIMEZONE: str = Field(default="Asia/Shanghai")
    RULES_PER_PAGE: int = Field(default=20)
    PUSH_CHANNEL_PER_PAGE: int = Field(default=10)
    AI_MODELS_PER_PAGE: int = Field(default=10)
    KEYWORDS_PER_PAGE: int = Field(default=50)
    
    # 按钮布局配置
    SUMMARY_TIME_ROWS: int = Field(default=10)
    SUMMARY_TIME_COLS: int = Field(default=6)
    DELAY_TIME_ROWS: int = Field(default=10)
    DELAY_TIME_COLS: int = Field(default=6)
    MEDIA_SIZE_ROWS: int = Field(default=10)
    MEDIA_SIZE_COLS: int = Field(default=6)
    MEDIA_EXTENSIONS_ROWS: int = Field(default=6)
    MEDIA_EXTENSIONS_COLS: int = Field(default=6)
    
    # === 业务规则与 AI ===
    DEFAULT_MAX_MEDIA_SIZE: int = Field(
        default=10,
        description="默认媒体大小限制（MB）"
    )
    DEFAULT_SUMMARY_TIME: str = Field(
        default="07:00",
        description="默认总结时间"
    )
    HISTORY_MESSAGE_LIMIT: int = Field(
        default=0,
        description="历史消息数量限制，0表示无限制"
    )
    DEFAULT_AI_MODEL: str = Field(default="gpt-4o")
    DEFAULT_SUMMARY_PROMPT: str = Field(
        default="请总结以下频道/群组24小时内的消息。"
    )
    DEFAULT_AI_PROMPT: str = Field(
        default="请尊重原意，保持原有格式不变，用简体中文重写下面的内容："
    )
    BOT_MESSAGE_DELETE_TIMEOUT: int = Field(default=300)
    USER_MESSAGE_DELETE_ENABLE: bool = Field(default=False)
    
    # === 并发与性能优化 ===
    FORWARD_CONCURRENCY: int = Field(default=5)
    PROCESSED_GROUP_TTL_SECONDS: int = Field(default=120)
    PROCESSED_GROUP_MAX: int = Field(default=5000)
    VERBOSE_LOG: bool = Field(default=False)
    CLEAR_TEMP_ON_START: bool = Field(default=True)
    DUP_SCAN_PAGE_SIZE: int = Field(default=50)
    # === 去重与持久化增强 ===
    DEDUP_USE_REDIS: bool = Field(default=True)
    DEDUP_USE_MEMORY: bool = Field(default=True)
    DEDUP_BATCH_SIZE: int = Field(default=1000)
    DEDUP_FLUSH_INTERVAL: float = Field(default=3.0)
    DEDUP_DATABASE_URL: Optional[str] = Field(default=None)

    UFB_ENABLED: bool = Field(default=False)
    
    # === 数据库健康检查 ===
    ENABLE_DB_HEALTH_CHECK: bool = Field(
        default=True,
        description="是否在启动时检查数据库完整性"
    )
    ENABLE_DB_AUTO_REPAIR: bool = Field(
        default=True,
        description="检测到损坏时是否尝试自动修复 (VACUUM)"
    )
    
    # === Security / JWT Config ===
    SECRET_KEY: str = Field(
        default_factory=lambda: secrets.token_hex(32),
        description="JWT 密钥"
    )
    JWT_ALGORITHM: str = Field(default="HS256")
    ACCESS_TOKEN_EXPIRE_MINUTES: int = Field(default=30)
    REFRESH_TOKEN_EXPIRE_DAYS: int = Field(default=7)
    MAX_ACTIVE_SESSIONS: int = Field(
        default=10,
        description="每个用户最大允许的活跃会话数"
    )

    # === 通知配置 ===
    ADMIN_IDS: Union[List[int], str] = Field(
        default=[],
        description="管理员 Telegram ID 列表，用于接收系统通知"
    )
    
    # === Worker 动态池配置 ===
    WORKER_MIN_CONCURRENCY: int = Field(
        default=2,
        description="Worker 最小并发数"
    )
    WORKER_MAX_CONCURRENCY: int = Field(
        default=10,
        description="Worker 最大并发数"
    )

    # 模型配置 - Pydantic v2 语法
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
        frozen=False,  # 允许在运行时修改配置
        title="应用配置",
        json_schema_extra={
            "example": {
                "APP_ENV": "development",
                "DEBUG": True,
                "LOG_LEVEL": "INFO"
            }
        }
    )


    @field_validator("CLEANUP_CRON_TIMES", "GC_TEMP_DIRS", "ADMIN_IDS", "LOG_MUTE_LOGGERS", "LOG_MUTE_CATEGORIES", mode="before")
    @classmethod
    def parse_list_fields(cls, v: Any) -> List[Any]:
        if isinstance(v, str):
            import json
            try:
                # 尝试 JSON 解析
                return list(json.loads(v))
            except json.JSONDecodeError:
                # 逗号分隔回退
                return [t.strip() for t in v.split(",") if t.strip()]
        return list(v)
    
    def validate_required(self) -> None:
        """验证极其重要的配置项，若缺失则系统无法基本运行"""
        missing = []
        if not self.API_ID:
            missing.append("API_ID")
        if not self.API_HASH:
            missing.append("API_HASH")
        if not self.BOT_TOKEN:
            missing.append("BOT_TOKEN")
        if not self.PHONE_NUMBER:
            missing.append("PHONE_NUMBER")
        if not self.USER_ID:
            missing.append("USER_ID")
            
        if missing:
            logger.error(
                f"缺少核心环境变量: {', '.join(missing)}。请在 .env 中配置后重新启动。"
            )
            # 在某些 CI 环境下可能不需要立即退出，但对于生产环境必须退出
            if self.APP_ENV == "production":
                raise SystemExit(1)
            else:
                logger.warning("当前非生产环境，尝试降级启动...")
    


# 单例模式获取配置 - 使用lru_cache确保全局只有一个实例
@lru_cache()
def get_settings() -> Settings:
    """获取配置实例，使用lru_cache实现单例模式"""
    return Settings()

# 全局配置实例，方便直接导入使用
settings = get_settings()