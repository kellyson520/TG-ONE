import zlib

import json
import logging
import os
import re
import structlog
import time
from dotenv import find_dotenv, load_dotenv
from logging.handlers import RotatingFileHandler
from pathlib import Path
import contextvars
import uuid

# Global context var for Trace ID
trace_id_var = contextvars.ContextVar("trace_id", default="-")

# 导入 settings 以获取项目根目录
from core.config import settings
from utils.network.log_push import install_log_push_handlers

# Simple redaction keywords
_REDACT_KEYS = {"token", "apikey", "api_key", "authorization", "password", "secret"}

_COMPILED_PATTERNS = []
for _k in _REDACT_KEYS:
    _e = re.escape(_k)
    _COMPILED_PATTERNS.extend(
        [
            (re.compile(rf"({_e}\s*=\s*)([^\s;,]+)", re.IGNORECASE), r"\1***"),
            (re.compile(rf'("{_e}"\s*:\s*")(.*?)(")', re.IGNORECASE), r"\1***\3"),
            (re.compile(rf"('{_e}'\s*:\s*')(.*?)(')", re.IGNORECASE), r"\1***\3"),
            (re.compile(rf"({_e}\s*:\s*)([^,}}\s]+)", re.IGNORECASE), r"\1***"),
        ]
    )


def _redact(text: str) -> str:
    try:
        if not text:
            return text
        masked = text
        for _p, _r in _COMPILED_PATTERNS:
            masked = _p.sub(_r, masked)
        return masked
    except Exception:
        return text


class JsonFormatter(logging.Formatter):
    """JSON 格式化器，支持中文键/是否包含堆栈/自定义时间格式"""

    def __init__(
        self, cn_keys: bool = False, include_traceback: bool = True, datefmt: str = None
    ) -> None:
        super().__init__(datefmt=datefmt)
        self.cn_keys = cn_keys
        self.include_traceback = include_traceback
        self.datefmt = datefmt or "%Y-%m-%dT%H:%M:%S%z"

    def format(self, record: logging.LogRecord) -> str:
        # 中英文键映射
        if self.cn_keys:
            k_time = "时间"
            k_level = "等级"
            k_logger = "记录器"
            k_message = "消息"
            k_process = "进程"
            k_thread = "线程"
            k_cid = "关联ID"
            k_exc = "异常"
        else:
            k_time = "timestamp"
            k_level = "level"
            k_logger = "logger"
            k_message = "message"
            k_process = "process"
            k_thread = "thread"
            k_cid = "correlation_id"
            k_exc = "exc_info"

        payload = {
            k_time: self.formatTime(record, self.datefmt),
            k_level: (
                getattr(record, "levelname_cn", record.levelname)
                if self.cn_keys
                else record.levelname
            ),
            k_logger: record.name,
            k_message: _redact(record.getMessage()),
            k_process: record.process,
            k_thread: record.threadName,
            k_cid: getattr(record, "correlation_id", "-"),
        }
        
        # 增加追踪元数据
        payload["trace_id"] = getattr(record, "correlation_id", "-")
        
        if self.cn_keys:
            payload["模块ID"] = getattr(record, "module_id", "-")
            payload["类ID"] = getattr(record, "class_id", "-")
            payload["方法"] = record.funcName
            payload["行号"] = record.lineno
        else:
            payload["module_id"] = getattr(record, "module_id", "-")
            payload["class_id"] = getattr(record, "class_id", "-")
            payload["func_name"] = record.funcName
            payload["lineno"] = record.lineno

        # 附加异常信息
        if record.exc_info:
            payload[k_exc if self.cn_keys else "exc_info"] = self.formatException(record.exc_info)
        
        return json.dumps(payload, ensure_ascii=False)


class ColorTextFormatter(logging.Formatter):
    """中文彩色文本格式化器（可通过 LOG_COLOR 控制是否着色）。"""

    _LEVEL_CN = {
        "DEBUG": "调试",
        "INFO": "信息",
        "WARNING": "警告",
        "ERROR": "错误",
        "CRITICAL": "严重",
    }
    _COLORS = {
        "DEBUG": "\x1b[90m",  # 灰
        "INFO": "\x1b[32m",  # 绿
        "WARNING": "\x1b[33m",  # 黄
        "ERROR": "\x1b[31m",  # 红
        "CRITICAL": "\x1b[35m",  # 品红
    }
    _RESET = "\x1b[0m"

    def __init__(
        self, use_color: bool = True, datefmt: str | None = None, lang_zh: bool = True
    ) -> None:
        fmt = (
            "【%(asctime)s】[%(correlation_id)s]【%(name)s】%(message)s"
            if lang_zh
            else "%(asctime)s [%(correlation_id)s][%(name)s] %(message)s"
        )
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.use_color = use_color
        self.lang_zh = lang_zh

    def format(self, record: logging.LogRecord) -> str:
        # 中文等级映射
        if self.lang_zh:
            try:
                record.levelname = self._LEVEL_CN.get(
                    record.levelname, record.levelname
                )
            except Exception:
                pass
        out = super().format(record)
        if not self.use_color:
            return out
        # 根据原始英文等级着色（从 levelno 推导）
        try:
            level_en = logging.getLevelName(record.levelno)
            color = self._COLORS.get(level_en)
            return f"{color}{out}{self._RESET}" if color else out
        except Exception:
            return out


class _ContextFilter(logging.Filter):
    """Inject correlation_id if present in record.extra or env."""

    def filter(self, record: logging.LogRecord) -> bool:
        cid = trace_id_var.get()
        if cid == "-":
            cid = getattr(record, "correlation_id", None)
            if cid is None:
                cid = os.getenv("CORRELATION_ID", "-")
        
        setattr(record, "correlation_id", cid)
        mid = getattr(record, "module_id", None)
        if mid in (None, "-"):
            try:
                name = record.name or ""
                mid_val = zlib.crc32(name.encode("utf-8")) & 0xFFFF
                setattr(record, "module_id", mid_val)
                mid = mid_val
            except Exception:
                setattr(record, "module_id", "-")
                mid = "-"
        cid2 = getattr(record, "class_id", None)
        if cid2 in (None, "-"):
            try:
                name = record.name or ""
                parts = name.split(".")
                last = parts[-1] if parts else ""
                if last and last[:1].isupper():
                    key = name
                    val = zlib.crc32(key.encode("utf-8")) & 0xFFFF
                    setattr(record, "class_id", val)
                else:
                    setattr(record, "class_id", mid)
            except Exception:
                setattr(record, "class_id", mid)
        return True


class _DropTelethonNoiseFilter(logging.Filter):
    """过滤 Telethon 高频噪声日志（如 updates 差异通知）。"""

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # 精准屏蔽: telethon.client.updates 的差异刷新信息
            if record.name.startswith("telethon.client.updates"):
                msg = record.getMessage()
                if "Got difference for channel" in msg:
                    return False
            return True
        except Exception:
            return True


class _ChineseLevelFilter(logging.Filter):
    """将 levelname 映射为中文（仅供文本/中文 JSON 使用）"""

    _MAP = {
        "DEBUG": "调试",
        "INFO": "信息",
        "WARNING": "警告",
        "ERROR": "错误",
        "CRITICAL": "严重",
    }

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            record.levelname_cn = self._MAP.get(record.levelname, record.levelname)
        except Exception:
            record.levelname_cn = record.levelname
        return True


class _SelectiveFilter(logging.Filter):
    """
    选择性过滤 INFO/DEBUG 级别的冗余日志，仅保留关键日志。

    环境变量：
      - LOG_KEY_ONLY: true/false；为 true 时默认丢弃 INFO/DEBUG（除非匹配允许白名单）
      - LOG_MUTE_LOGGERS: 以逗号分隔的 logger 前缀列表；匹配的 INFO/DEBUG 将被丢弃
      - LOG_DROP_PATTERNS: 以分号分隔的正则；匹配的 INFO/DEBUG 将被丢弃
      - LOG_ALLOW_PATTERNS: 以分号分隔的正则；当 LOG_KEY_ONLY=true 时，仅允许匹配的 INFO/DEBUG 通过
    """

    def __init__(self) -> None:
        super().__init__()
        self.key_only = os.getenv("LOG_KEY_ONLY", "false").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        # 解析静音 logger 前缀
        mute = os.getenv("LOG_MUTE_LOGGERS", "")
        self.mute_prefixes = [p.strip() for p in mute.split(",") if p.strip()]
        # 解析丢弃/允许的消息正则
        drop_raw = os.getenv("LOG_DROP_PATTERNS", "")
        allow_raw = os.getenv("LOG_ALLOW_PATTERNS", "")
        self.drop_patterns = []
        self.allow_patterns = []
        import re as _re

        for pat in [p.strip() for p in drop_raw.split(";") if p.strip()]:
            try:
                self.drop_patterns.append(_re.compile(pat))
            except Exception:
                pass
        for pat in [p.strip() for p in allow_raw.split(";") if p.strip()]:
            try:
                self.allow_patterns.append(_re.compile(pat))
            except Exception:
                pass

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            # WARNING 及以上一律通过
            if record.levelno >= logging.WARNING:
                return True

            # 仅对 INFO/DEBUG 做过滤
            logger_name = record.name or ""
            message = record.getMessage() or ""

            # 按 logger 前缀静音
            for prefix in self.mute_prefixes:
                if logger_name.startswith(prefix):
                    return False

            # 按丢弃规则过滤
            for pat in self.drop_patterns:
                try:
                    if pat.search(message):
                        return False
                except Exception:
                    continue

            # 仅保留关键日志（白名单）
            if self.key_only and self.allow_patterns:
                for pat in self.allow_patterns:
                    try:
                        if pat.search(message):
                            return True
                    except Exception:
                        continue
                return False

            # 默认放行
            return not self.key_only  # key_only 时默认不放行
        except Exception:
            return True


class _CategoryFilter(logging.Filter):
    """按类别静音部分 INFO/DEBUG 日志。"""

    def __init__(self) -> None:
        super().__init__()
        raw = os.getenv("LOG_MUTE_CATEGORIES", "")
        self.categories = {c.strip() for c in raw.split(",") if c.strip()}
        # 预设类别映射 → logger 前缀
        self.map = {
            "db": [
                "models.",
                "utils.db_",
                "utils.query_",
                "utils.db_optimization_suite",
                "utils.db_monitor",
                "scheduler.db_archive_job",
            ],
            "cache": ["utils.unified_cache", "utils.query_optimizer"],
            "scheduler": ["scheduler."],
            "telethon": ["telethon"],
            "rss": ["rss."],
            "api": ["handlers.", "controllers.", "services."],
        }

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if record.levelno >= logging.WARNING:
                return True
            name = record.name or ""
            for cat in self.categories:
                for prefix in self.map.get(cat, []):
                    if name.startswith(prefix):
                        return False
            return True
        except Exception:
            return True


class _GlobalDropFilter(logging.Filter):
    """
    全局丢弃匹配指定正则的日志（适用于所有级别）。
    环境变量：LOG_GLOBAL_DROP_PATTERNS=pat1;pat2
    """

    def __init__(self) -> None:
        super().__init__()
        raw = os.getenv("LOG_GLOBAL_DROP_PATTERNS", "")
        self.patterns = []
        import re as _re

        for pat in [p.strip() for p in raw.split(";") if p.strip()]:
            try:
                self.patterns.append(_re.compile(pat))
            except Exception:
                pass

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if not self.patterns:
                return True
            msg = record.getMessage() or ""
            for pat in self.patterns:
                try:
                    if pat.search(msg):
                        return False
                except Exception:
                    continue
            return True
        except Exception:
            return True


class _ConsolidatedFilter(logging.Filter):
    """
    合并过滤器：关键日志保留/前缀静音/类别静音/消息丢弃/白名单/全局丢弃/Telethon降噪。
    目标：减少冗余过滤器配置，统一从 env 控制。
    """

    def __init__(self) -> None:
        super().__init__()
        # 基本开关
        self.key_only = os.getenv("LOG_KEY_ONLY", "true").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        # 前缀静音
        self.mute_prefixes = [
            p.strip() for p in os.getenv("LOG_MUTE_LOGGERS", "").split(",") if p.strip()
        ]
        # 类别静音
        self.mute_categories = {
            c.strip()
            for c in os.getenv("LOG_MUTE_CATEGORIES", "").split(",")
            if c.strip()
        }
        self.category_map = {
            "db": [
                "models.",
                "utils.db_",
                "utils.query_",
                "utils.db_optimization_suite",
                "utils.db_monitor",
                "scheduler.db_archive_job",
            ],
            "cache": ["utils.unified_cache", "utils.query_optimizer"],
            "scheduler": ["scheduler."],
            "telethon": ["telethon"],
            "rss": ["rss."],
            "api": ["handlers.", "controllers.", "services."],
        }
        # 模式
        import re as _re

        self.drop_patterns = [
            self._compile(_re, p)
            for p in os.getenv("LOG_DROP_PATTERNS", "").split(";")
            if p.strip()
        ]
        self.allow_patterns = [
            self._compile(_re, p)
            for p in os.getenv("LOG_ALLOW_PATTERNS", "").split(";")
            if p.strip()
        ]
        self.global_drop_patterns = [
            self._compile(_re, p)
            for p in os.getenv("LOG_GLOBAL_DROP_PATTERNS", "").split(";")
            if p.strip()
        ]

    @staticmethod
    def _compile(_re, pat: str):
        try:
            return _re.compile(pat)
        except Exception:
            return None

    def _match_any(self, patterns, text: str) -> bool:
        for pat in patterns:
            if not pat:
                continue
            try:
                if pat.search(text):
                    return True
            except Exception:
                continue
        return False

    def _is_telethon_noise(self, record: logging.LogRecord) -> bool:
        if not (record.name or "").startswith("telethon.client.updates"):
            return False
        try:
            return "Got difference for channel" in (record.getMessage() or "")
        except Exception:
            return False

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            name = record.name or ""
            message = record.getMessage() or ""

            # 全局丢弃（任何级别）
            if self._is_telethon_noise(record) or self._match_any(
                self.global_drop_patterns, message
            ):
                return False

            # 前缀静音（任何级别）
            for prefix in self.mute_prefixes:
                if name.startswith(prefix):
                    return False

            # 类别静音（任何级别）
            for cat in self.mute_categories:
                for prefix in self.category_map.get(cat, []):
                    if name.startswith(prefix):
                        return False

            # 自定义丢弃规则（任何级别）
            if self._match_any(self.drop_patterns, message):
                return False

            # 严重级别默认放行
            if record.levelno >= logging.WARNING:
                return True

            # INFO/DEBUG 关键白名单
            if self.key_only:
                if self.allow_patterns:
                    return self._match_any(self.allow_patterns, message)
                return False

            return True
        except Exception:
            return True


class _MessageLocalizationFilter(logging.Filter):
    """
    日志消息本地化过滤器：将常见英文短语/关键词替换为中文。
    仅对属于指定前缀的 logger 生效，避免误伤三方库。

    环境变量：
      - LOG_LOCALIZE_MESSAGES=true/false 是否开启
      - LOG_LOCALIZE_PREFIXES=utils.,controllers.,handlers.,managers.,scheduler.,models.,rss. 逗号分隔
    """

    def __init__(self) -> None:
        super().__init__()
        self.enabled = os.getenv("LOG_LOCALIZE_MESSAGES", "").lower() in {
            "1",
            "true",
            "yes",
            "on",
        }
        # 若未显式开启，但语言为中文，则默认开启
        if not self.enabled and os.getenv("LOG_LANGUAGE", "zh").lower() == "zh":
            self.enabled = True

        raw = os.getenv(
            "LOG_LOCALIZE_PREFIXES",
            "utils.,controllers.,handlers.,managers.,scheduler.,models.,rss.",
        )
        self.prefixes = [p.strip() for p in raw.split(",") if p.strip()]

        # 轻量替换表（仅覆盖常见词，避免长句误翻）
        self.replacements = {
            "initialized": "初始化完成",
            "initialization": "初始化",
            "start": "启动",
            "started": "已启动",
            "stop": "停止",
            "stopped": "已停止",
            "connect": "连接",
            "connected": "已连接",
            "disconnect": "断开连接",
            "disconnected": "已断开",
            "success": "成功",
            "failed": "失败",
            "error": "错误",
            "warning": "警告",
            "retry": "重试",
            "timeout": "超时",
            "archive": "归档",
            "compaction": "压实",
            "bloom": "布隆",
            "cache": "缓存",
            "monitor": "监控",
            "optimize": "优化",
            "performance": "性能",
            "metrics": "指标",
            "query": "查询",
        }

    def _should_localize(self, name: str) -> bool:
        for p in self.prefixes:
            if name.startswith(p):
                return True
        return False

    def filter(self, record: logging.LogRecord) -> bool:
        try:
            if not self.enabled:
                return True
            name = record.name or ""
            if not self._should_localize(name):
                return True
            # 仅在 msg 为字符串时做简单替换
            msg = record.getMessage()
            if not isinstance(msg, str) or not msg:
                return True
            # 避免破坏格式化参数，占位符极少出现在我们自定义日志中
            localized = msg
            try:
                for eng, zh in self.replacements.items():
                    # 小写比较，保留原大小写影响较小
                    localized = localized.replace(eng, zh)
                    localized = localized.replace(eng.capitalize(), zh)
                    localized = localized.replace(eng.upper(), zh)
            except Exception:
                pass
            # 将 record.msg 替换为本地化版本
            record.msg = localized
            record.args = None
            return True
        except Exception:
            return True


class SafeLoggerFactory(structlog.stdlib.LoggerFactory):
    """确保 logger name 永远是字符串，解决 'A logger name must be a string' 错误"""
    def __call__(self, *args, **kwargs):
        if args and args[0] is None:
            args = ("root",) + args[1:]
        elif not args:
            args = ("root",)
        return super().__call__(*args, **kwargs)

def configure_structlog():
    """配置 structlog 以对接标准 logging 系统"""
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            # 关键：将 structlog 处理后的日志转交给标准 logging 的 handler
            structlog.stdlib.LoggerFactory(),
        ],
        context_class=dict,
        logger_factory=SafeLoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def setup_logging():
    """
    配置日志系统：
    - LOG_LEVEL: 日志级别（默认 INFO）
    - LOG_FORMAT: json | text（默认 text）
    - LOG_DIR/LOG_MAX_BYTES/LOG_BACKUP_COUNT: 可选文件日志
    """
    # 优先加载 .env；若不存在则兼容加载同目录下的 'env' 文件
    try:
        loaded = load_dotenv(find_dotenv(usecwd=True))
        if not loaded:
            # 兼容非隐藏文件名 'env'
            alt_path = Path.cwd() / "env"
            if alt_path.exists():
                load_dotenv(dotenv_path=str(alt_path), override=True)
    except Exception:
        # 保底不抛出
        pass

    # 设置 structlog 配置
    configure_structlog()

    root_logger = logging.getLogger()

    level = os.getenv("LOG_LEVEL", "INFO").upper()
    try:
        root_logger.setLevel(getattr(logging, level, logging.INFO))
    except Exception:
        root_logger.setLevel(logging.INFO)

    # 语言与格式
    lang = os.getenv("LOG_LANGUAGE", "zh").lower()
    log_format = os.getenv("LOG_FORMAT", "text").lower()
    cn_keys = (
        os.getenv("LOG_CN_KEYS", "true").lower() in {"1", "true", "yes", "on"}
        or lang == "zh"
    )
    include_tb = os.getenv("LOG_INCLUDE_TRACEBACK", "false").lower() in {
        "1",
        "true",
        "yes",
        "on",
    }

    # 移除所有已存在的处理器，重新配置
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    # 添加控制台处理器
    console_handler = logging.StreamHandler()
    if log_format == "json":
        formatter = logging.Formatter("%(message)s")
    else:
        use_color = os.getenv("LOG_COLOR", "true").lower() in {"1", "true", "yes", "on"}
        formatter = ColorTextFormatter(use_color=use_color, lang_zh=(lang == "zh"))
    console_handler.setFormatter(formatter)
    console_handler.addFilter(_ContextFilter())
    console_handler.addFilter(_ConsolidatedFilter())
    console_handler.addFilter(_MessageLocalizationFilter())
    root_logger.addHandler(console_handler)

    # 添加文件处理器（如果配置了）
    log_dir = str(settings.LOG_DIR)
    if log_dir:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            filename=str(Path(log_dir) / "app.log"),
            maxBytes=int(os.getenv("LOG_MAX_BYTES", "10485760")),
            backupCount=int(os.getenv("LOG_BACKUP_COUNT", "5")),
            encoding="utf-8",
        )
        if log_format == "json":
            file_formatter = logging.Formatter("%(message)s")
        else:
            file_formatter = ColorTextFormatter(use_color=False, lang_zh=(lang == "zh"))
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(_ContextFilter())
        file_handler.addFilter(_ConsolidatedFilter())
        file_handler.addFilter(_MessageLocalizationFilter())
        root_logger.addHandler(file_handler)

    # 降低 Telethon 日志级别（可通过环境变量 TELETHON_LOG_LEVEL 控制，默认 WARNING）
    try:
        telethon_level = os.getenv("TELETHON_LOG_LEVEL", "WARNING").upper()
        logging.getLogger("telethon").setLevel(
            getattr(logging, telethon_level, logging.WARNING)
        )
    except Exception:
        pass

    # 应用按 logger 的级别覆盖（LOG_LEVEL_OVERRIDES=telethon=ERROR,sqlalchemy=WARNING）
    try:
        overrides = os.getenv("LOG_LEVEL_OVERRIDES", "").split(",")
        for item in overrides:
            item = item.strip()
            if not item or "=" not in item:
                continue
            name, lvl = item.split("=", 1)
            name = name.strip()
            lvl = lvl.strip().upper()
            if name:
                logging.getLogger(name).setLevel(getattr(logging, lvl, logging.WARNING))
    except Exception:
        pass

    # 启动时打印一次生效的日志配置（中文）
    logger = structlog.get_logger()
    try:
        eff = logging.getLevelName(root_logger.level)
        telethon_level = os.getenv("TELETHON_LOG_LEVEL", "WARNING").upper()
        logger.info(
            "日志系统已初始化",
            level=eff,
            env_level=level,
            format=log_format,
            language=lang,
            telethon_level=telethon_level,
        )
    except Exception:
        pass

    # 统一日志推送（如配置）
    try:
        install_log_push_handlers(root_logger)
    except Exception:
        pass

    return root_logger
