"""
TG ONE 统一日志模块 (Core Logging)
整合原 utils/core/log_config.py 和 utils/core/logger_utils.py
遵循 Standard Whitepaper 2.2 和 2.4
"""

import functools
import zlib
import json
import logging
import os
import re
import time
import uuid
from contextlib import contextmanager
from datetime import datetime
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, Optional, Union

import structlog
from dotenv import find_dotenv, load_dotenv

# 导入 settings
from core.config import settings
from services.network.log_push import install_log_push_handlers
# 导入 ContextVar
from core.context import trace_id_var

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
    except Exception as e:
        return text


class JsonFormatter(logging.Formatter):
    """JSON 格式化器"""

    def __init__(
        self, include_traceback: bool = True, datefmt: str = None
    ) -> None:
        super().__init__(datefmt=datefmt)
        self.include_traceback = include_traceback
        self.datefmt = datefmt or "%Y-%m-%dT%H:%M:%S%z"

    def format(self, record: logging.LogRecord) -> str:
        k_time = "timestamp"
        k_level = "level"
        k_logger = "logger"
        k_message = "message"
        k_process = "process"
        k_thread = "thread"
        k_cid = "correlation_id"
        
        payload = {
            k_time: self.formatTime(record, self.datefmt),
            k_level: record.levelname,
            k_logger: record.name,
            k_message: _redact(record.getMessage()),
            k_process: record.process,
            k_thread: record.threadName,
            k_cid: getattr(record, "correlation_id", "-"),
        }
        
        # 增加追踪元数据
        payload["trace_id"] = getattr(record, "correlation_id", "-")
        payload["module_id"] = getattr(record, "module_id", "-")
        payload["class_id"] = getattr(record, "class_id", "-")
        payload["func_name"] = record.funcName
        payload["lineno"] = record.lineno

        # 附加异常信息
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        
        return json.dumps(payload, ensure_ascii=False)


class ColorTextFormatter(logging.Formatter):
    """标准彩色文本格式化器"""

    _COLORS = {
        "DEBUG": "\x1b[90m",  # 灰
        "INFO": "\x1b[32m",  # 绿
        "WARNING": "\x1b[33m",  # 黄
        "ERROR": "\x1b[31m",  # 红
        "CRITICAL": "\x1b[35m",  # 品红
    }
    _RESET = "\x1b[0m"

    def __init__(
        self, use_color: bool = True, datefmt: str | None = None
    ) -> None:
        fmt = "%(asctime)s [%(correlation_id)s][%(levelname)s][%(name)s] %(message)s"
        super().__init__(fmt=fmt, datefmt=datefmt)
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        out = super().format(record)
        if not self.use_color:
            return out
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


class _ConsolidatedFilter(logging.Filter):
    """
    合并过滤器：关键日志保留/前缀静音/类别静音/消息丢弃/白名单/全局丢弃/Telethon降噪。
    """

    def __init__(self) -> None:
        super().__init__()
        # 基本开关
        self.key_only = os.getenv("LOG_KEY_ONLY", "true").lower() in {"1", "true", "yes", "on"}
        # 前缀静音
        self.mute_prefixes = [
            p.strip() for p in os.getenv("LOG_MUTE_LOGGERS", "").split(",") if p.strip()
        ]
        # 类别静音
        self.mute_categories = {
            c.strip() for c in os.getenv("LOG_MUTE_CATEGORIES", "").split(",") if c.strip()
        }
        self.category_map = {
            "db": ["models.", "repositories_", "utils.query_", "repositories_optimization_suite", "repositories_monitor", "scheduler.db_archive_job"],
            "cache": ["utils.unified_cache", "utils.query_optimizer"],
            "scheduler": ["scheduler."],
            "telethon": ["telethon"],
            "rss": ["rss."],
            "api": ["handlers.", "controllers.", "services."],
        }
        # 模式
        import re as _re

        self.drop_patterns = [
            self._compile(_re, p) for p in os.getenv("LOG_DROP_PATTERNS", "").split(";") if p.strip()
        ]
        self.allow_patterns = [
            self._compile(_re, p) for p in os.getenv("LOG_ALLOW_PATTERNS", "").split(";") if p.strip()
        ]
        self.global_drop_patterns = [
            self._compile(_re, p) for p in os.getenv("LOG_GLOBAL_DROP_PATTERNS", "").split(";") if p.strip()
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
            if self._is_telethon_noise(record) or self._match_any(self.global_drop_patterns, message):
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


class SafeLoggerFactory(structlog.stdlib.LoggerFactory):
    """确保 logger name 永远是字符串"""
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
            structlog.stdlib.LoggerFactory(),
        ],
        context_class=dict,
        logger_factory=SafeLoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def setup_logging():
    """配置日志系统，包括滚动归档"""
    # 优先加载 .env
    try:
        loaded = load_dotenv(find_dotenv(usecwd=True))
        if not loaded:
            alt_path = Path.cwd() / "env"
            if alt_path.exists():
                load_dotenv(dotenv_path=str(alt_path), override=True)
    except Exception as e:
        print(f"Error loading .env: {e}")

    configure_structlog()

    root_logger = logging.getLogger()
    level = os.getenv("LOG_LEVEL", "INFO").upper()
    try:
        root_logger.setLevel(getattr(logging, level, logging.INFO))
    except Exception:
        root_logger.setLevel(logging.INFO)

    log_format = os.getenv("LOG_FORMAT", "text").lower()
    include_tb = os.getenv("LOG_INCLUDE_TRACEBACK", "false").lower() in {"1", "true", "yes", "on"}

    # 移除现有处理器
    for handler in list(root_logger.handlers):
        root_logger.removeHandler(handler)

    # Console Handler
    console_handler = logging.StreamHandler()
    if log_format == "json":
        formatter = JsonFormatter(include_traceback=include_tb)
    else:
        use_color = os.getenv("LOG_COLOR", "true").lower() in {"1", "true", "yes", "on"}
        formatter = ColorTextFormatter(use_color=use_color)
    console_handler.setFormatter(formatter)
    console_handler.addFilter(_ContextFilter())
    console_handler.addFilter(_ConsolidatedFilter())
    root_logger.addHandler(console_handler)

    # File Handler (Rolling & Auto Cleanup)
    log_dir = str(settings.LOG_DIR)
    if log_dir:
        Path(log_dir).mkdir(parents=True, exist_ok=True)
        # 默认 10MB per file, keep 5 backups
        max_bytes = int(os.getenv("LOG_MAX_BYTES", "10485760"))
        backup_count = int(os.getenv("LOG_BACKUP_COUNT", "5"))
        
        file_handler = RotatingFileHandler(
            filename=str(Path(log_dir) / "app.log"),
            maxBytes=max_bytes,
            backupCount=backup_count,
            encoding="utf-8",
        )
        
        if log_format == "json":
            file_formatter = JsonFormatter(include_traceback=include_tb)
        else:
            file_formatter = ColorTextFormatter(use_color=False)
            
        file_handler.setFormatter(file_formatter)
        file_handler.addFilter(_ContextFilter())
        file_handler.addFilter(_ConsolidatedFilter())
        root_logger.addHandler(file_handler)

    # Telethon 日志级别控制
    try:
        telethon_level = os.getenv("TELETHON_LOG_LEVEL", "WARNING").upper()
        logging.getLogger("telethon").setLevel(getattr(logging, telethon_level, logging.WARNING))
    except Exception:
        pass

    # Logger Overrides
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

    # Log Startup
    logger = structlog.get_logger()
    try:
        eff = logging.getLevelName(root_logger.level)
        logger.info(
            "Log system initialized (Core)",
            level=eff,
            format=log_format,
            max_bytes=os.getenv("LOG_MAX_BYTES", "10MB"),
            backup_count=os.getenv("LOG_BACKUP_COUNT", "5")
        )
    except Exception:
        pass

    # Log Push
    try:
        install_log_push_handlers(root_logger)
    except Exception:
        pass

    return root_logger


class StandardLogger:
    """标准化日志记录器 (from logger_utils)"""

    def __init__(self, name: str, context: Optional[Dict[str, Any]] = None):
        if not isinstance(name, str):
            name = str(name) if name is not None else "unknown"
        self.name = name
        self.logger = logging.getLogger(name)
        self.module_name = name.split(".")[-1] if "." in name else name
        self.context = context or {}

    def _log(self, level: str, message: str, *args, **kwargs) -> None:
        standard_params = {"exc_info", "stack_info", "stacklevel", "extra"}
        log_kwargs = {k: v for k, v in kwargs.items() if k in standard_params}
        
        extra = log_kwargs.get("extra", {}) or {}
        if not isinstance(extra, dict):
            extra = {"_extra_data": extra}

        if self.context:
            extra = {**self.context, **extra}

        other_params = {k: v for k, v in kwargs.items() if k not in standard_params}
        if other_params:
            extra = {**extra, **other_params}

        if extra:
            log_kwargs["extra"] = extra

        getattr(self.logger, level.lower())(message, *args, **log_kwargs)

    def debug(self, message: str, *args, **kwargs) -> None: self._log("debug", message, *args, **kwargs)
    def info(self, message: str, *args, **kwargs) -> None: self._log("info", message, *args, **kwargs)
    def warning(self, message: str, *args, **kwargs) -> None: self._log("warning", message, *args, **kwargs)
    def error(self, message: str, *args, **kwargs) -> None: self._log("error", message, *args, **kwargs)
    def critical(self, message: str, *args, **kwargs) -> None: self._log("critical", message, *args, **kwargs)
    def exception(self, message: str, *args, **kwargs) -> None: self._log("exception", message, *args, **kwargs)

    def bind(self, **kwargs) -> "StandardLogger":
        new_context = {**self.context, **kwargs}
        return StandardLogger(self.name, context=new_context)
    
    # 业务日志方法
    def log_operation(self, operation: str, entity_id: Optional[Union[int, str]] = None, details: Optional[str] = None, level: str = "info") -> None:
        msg = f"[{self.module_name}] {operation}"
        if entity_id: msg += f" [ID: {entity_id}]"
        if details: msg += f" - {details}"
        self._log(level, msg)

    def log_error(self, operation: str, error: Exception, entity_id: Optional[Union[int, str]] = None, context: Optional[Dict[str, Any]] = None) -> None:
        msg = f"[{self.module_name}] {operation} 失败"
        if entity_id: msg += f" [ID: {entity_id}]"
        msg += f": {str(error)}"
        if context: msg += f" | 上下文: {json.dumps(context, ensure_ascii=False, default=str)}"
        self._log("error", msg)

    def log_performance(self, operation: str, duration: float, entity_count: Optional[int] = None, details: Optional[str] = None) -> None:
        msg = f"[{self.module_name}] {operation} 性能 | 耗时: {duration:.3f}s"
        if entity_count is not None:
            msg += f" | 处理数量: {entity_count}"
            if duration > 0: msg += f" | 处理速率: {entity_count / duration:.1f}/s"
        if details: msg += f" | {details}"
        level = "warning" if duration > 5.0 else "info"
        self._log(level, msg)
        
    def log_user_action(self, user_id: Union[int, str], action: str, target: Optional[str] = None, result: str = "成功") -> None:
        msg = f"[{self.module_name}] 用户行为 | 用户: {user_id} | 行为: {action}"
        if target: msg += f" | 目标: {target}"
        msg += f" | 结果: {result}"
        self._log("info", msg)

    def log_system_state(self, component: str, state: str, metrics: Optional[Dict[str, Any]] = None) -> None:
        msg = f"[{self.module_name}] 系统状态 | {component}: {state}"
        if metrics:
            for key, value in metrics.items(): msg += f" | {key}: {value}"
        self._log("info", msg)


class PerformanceLogger:
    def __init__(self, logger: StandardLogger):
        self.logger = logger
        self.start_times: Dict[str, float] = {}

    def start_timer(self, operation_id: str) -> None:
        self.start_times[operation_id] = time.time()

    def end_timer(self, operation_id: str, operation_name: str, entity_count: Optional[int] = None, details: Optional[str] = None) -> float:
        if operation_id not in self.start_times:
            self.logger.log_error("性能监控", ValueError(f"未找到操作 {operation_id} 的开始时间"))
            return 0.0
        duration = time.time() - self.start_times[operation_id]
        del self.start_times[operation_id]
        self.logger.log_performance(operation_name, duration, entity_count, details)
        return duration

class StructuredLogger:
    """结构化日志器"""

    def __init__(self, logger: StandardLogger):
        self.logger = logger

    def log_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        user_id: Optional[Union[int, str]] = None,
    ) -> None:
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "data": event_data,
        }
        if user_id:
            event["user_id"] = user_id
        event_json = json.dumps(event, ensure_ascii=False, indent=2, default=str)
        self.logger.info(f"事件记录:\n{event_json}")

    def log_business_metrics(
        self, metrics: Dict[str, Union[int, float]], period: str = "实时"
    ) -> None:
        metrics_data = {
            "timestamp": datetime.now().isoformat(),
            "period": period,
            "metrics": metrics,
        }
        metrics_json = json.dumps(metrics_data, ensure_ascii=False, indent=2)
        self.logger.info(f"业务指标:\n{metrics_json}")


# Cache
_logger_cache: Dict[str, StandardLogger] = {}

def get_logger(name: str) -> StandardLogger:
    if not isinstance(name, str):
        name = str(name) if name is not None else "unknown"
    if name not in _logger_cache:
        _logger_cache[name] = StandardLogger(name)
    return _logger_cache[name]

# Alias for backward compatibility
get_cached_logger = get_logger

def get_performance_logger(name: str) -> PerformanceLogger:
    standard_logger = get_logger(name)
    return PerformanceLogger(standard_logger)

def get_structured_logger(name: str) -> StructuredLogger:
    standard_logger = get_logger(name)
    return StructuredLogger(standard_logger)


# 性能监控装饰器 (Moved out of class for easy import)
def log_performance(
    operation_name: str = None,
    log_args: bool = False,
    log_result: bool = False,
    threshold_seconds: float = 1.0,
):
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__ or __name__)
            perf_logger = PerformanceLogger(logger)
            token = None
            if trace_id_var.get() == "-":
                token = trace_id_var.set(uuid.uuid4().hex[:8])
            op_name = operation_name or func.__name__
            operation_id = f"{func.__module__}.{func.__name__}_{id(func)}"
            if log_args:
                logger.log_operation(f"{op_name} 开始", details=f"args={args}")
            else:
                logger.log_operation(f"{op_name} 开始")
            perf_logger.start_timer(operation_id)
            try:
                result = await func(*args, **kwargs)
                duration = perf_logger.end_timer(operation_id, op_name)
                if duration > threshold_seconds:
                    logger.log_operation(f"{op_name} 性能警告", details=f"Time: {duration}s", level="warning")
                return result
            except Exception as e:
                perf_logger.end_timer(operation_id, f"{op_name} (Failed)")
                logger.log_error(op_name, e)
                raise
            finally:
                if token: trace_id_var.reset(token)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__ or __name__)
            op_name = operation_name or func.__name__
            token = None
            if trace_id_var.get() == "-":
                token = trace_id_var.set(uuid.uuid4().hex[:8])
            start = time.time()
            if log_args: logger.log_operation(f"{op_name} 开始")
            try:
                result = func(*args, **kwargs)
                duration = time.time() - start
                logger.log_performance(op_name, duration)
                return result
            except Exception as e:
                logger.log_error(op_name, e)
                raise
            finally:
                if token: trace_id_var.reset(token)

        import asyncio
        if asyncio.iscoroutinefunction(func): return async_wrapper
        else: return sync_wrapper
    return decorator

# User Action Decorator
def log_user_action(action_name: str = None, extract_user_id: callable = None):
    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__ or __name__)
            user_id = "unknown"
            if extract_user_id:
                try: user_id = extract_user_id(*args, **kwargs)
                except: pass
            try:
                res = await func(*args, **kwargs)
                logger.log_user_action(user_id, action_name or func.__name__)
                return res
            except Exception as e:
                logger.log_user_action(user_id, action_name or func.__name__, result=str(e))
                raise

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__ or __name__)
            user_id = "unknown"
            if extract_user_id:
                try: user_id = extract_user_id(*args, **kwargs)
                except: pass
            try:
                res = func(*args, **kwargs)
                logger.log_user_action(user_id, action_name or func.__name__)
                return res
            except Exception as e:
                logger.log_user_action(user_id, action_name or func.__name__, result=str(e))
                raise
                
        import asyncio
        if asyncio.iscoroutinefunction(func): return async_wrapper
        else: return sync_wrapper
    return decorator


def log_startup(module_name: str, version: str = None, config: Dict[str, Any] = None):
    logger = get_cached_logger(module_name)
    msg = f"{module_name} 启动"
    if version: msg += f" | 版本: {version}"
    if config: msg += f" | 配置: {json.dumps(config, ensure_ascii=False, default=str)}"
    logger.log_system_state("启动", msg)


def log_shutdown(module_name: str, cleanup_info: Dict[str, Any] = None):
    logger = get_cached_logger(module_name)
    msg = f"{module_name} 关闭"
    if cleanup_info: msg += f" | 清理信息: {json.dumps(cleanup_info, ensure_ascii=False, default=str)}"
    logger.log_system_state("关闭", msg)


_module_id_cache: Dict[str, int] = {}
_class_id_cache: Dict[str, int] = {}


def get_module_id(module_name: str) -> int:
    if module_name in _module_id_cache:
        return _module_id_cache[module_name]
    val = zlib.crc32(module_name.encode("utf-8")) & 0xFFFF
    _module_id_cache[module_name] = val
    return val


def get_class_id(module_name: str, class_name: str) -> int:
    key = f"{module_name}.{class_name}"
    if key in _class_id_cache:
        return _class_id_cache[key]
    val = zlib.crc32(key.encode("utf-8")) & 0xFFFF
    _class_id_cache[key] = val
    return val


def get_logger_with_ids(
    name: str, module_id: Optional[int] = None, class_id: Optional[int] = None
) -> logging.LoggerAdapter:
    base = logging.getLogger(name)
    extra = {}
    if module_id is not None:
        extra["module_id"] = module_id
    if class_id is not None:
        extra["class_id"] = class_id
    return logging.LoggerAdapter(base, extra)


@contextmanager
def correlation_context(cid: Optional[str]):
    token = None
    if cid:
        token = trace_id_var.set(str(cid))
    try:
        yield
    finally:
        if token:
            trace_id_var.reset(token)

def short_id(val: Any, length: int = 6) -> str:
    s = str(val)
    if len(s) > length: return "..." + s[-length:]
    return s
