"""
统一日志工具类
用于减少重复的日志记录代码，提供标准化的日志格式和功能
"""

import functools
import zlib
from contextlib import contextmanager
from datetime import datetime

import json
import logging
import os
import time
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional, Union
import contextvars

# 导入 ContextVar
from utils.core.log_config import trace_id_var

from utils.core.error_handler import handle_errors


class StandardLogger:
    """标准化日志记录器"""

    def __init__(self, name: str, context: Optional[Dict[str, Any]] = None):
        """
        初始化标准化日志器

        Args:
            name: 日志器名称,通常使用模块名
            context: 绑定上下文（可选）
        """
        # 确保 name 是字符串类型
        if not isinstance(name, str):
            name = str(name) if name is not None else "unknown"
        self.name = name
        self.logger = logging.getLogger(name)
        self.module_name = name.split(".")[-1] if "." in name else name
        self.context = context or {}

    def _log(self, level: str, message: str, *args, **kwargs) -> None:
        """统一日志处理，支持上下文和额外参数"""
        standard_params = {"exc_info", "stack_info", "stacklevel", "extra"}

        # 1. 提取标准 logging 参数
        log_kwargs = {k: v for k, v in kwargs.items() if k in standard_params}

        # 2. 提取并清理 extra
        extra = log_kwargs.get("extra", {})
        if extra is None:
            extra = {}
        elif not isinstance(extra, dict):
            # 防止 extra 为非 dict 类型
            extra = {"_extra_data": extra}

        # 3. 合并 bind 的上下文 (bind 的上下文具有较低优先级，会被调用时的 kwargs 覆盖)
        if self.context:
            extra = {**self.context, **extra}

        # 4. 合并此次调用的其他非标准参数 (具有最高优先级)
        other_params = {k: v for k, v in kwargs.items() if k not in standard_params}
        if other_params:
            extra = {**extra, **other_params}

        if extra:
            log_kwargs["extra"] = extra

        # 5. 调用底层 logger
        getattr(self.logger, level.lower())(message, *args, **log_kwargs)

    # 添加标准的logging方法以保持兼容性
    def debug(self, message: str, *args, **kwargs) -> None:
        """标准debug日志方法"""
        self._log("debug", message, *args, **kwargs)

    def info(self, message: str, *args, **kwargs) -> None:
        """标准info日志方法"""
        self._log("info", message, *args, **kwargs)

    def warning(self, message: str, *args, **kwargs) -> None:
        """标准warning日志方法"""
        self._log("warning", message, *args, **kwargs)

    def error(self, message: str, *args, **kwargs) -> None:
        """标准error日志方法"""
        self._log("error", message, *args, **kwargs)

    def critical(self, message: str, *args, **kwargs) -> None:
        """标准critical日志方法"""
        self._log("critical", message, *args, **kwargs)

    def exception(self, message: str, *args, **kwargs) -> None:
        """标准exception日志方法"""
        self._log("exception", message, *args, **kwargs)

    def bind(self, **kwargs) -> "StandardLogger":
        """
        类似 structlog 的 bind 方法，支持设置上下文
        """
        new_context = {**self.context, **kwargs}
        return StandardLogger(self.name, context=new_context)

    def log_operation(
        self,
        operation: str,
        entity_id: Optional[Union[int, str]] = None,
        details: Optional[str] = None,
        level: str = "info",
    ) -> None:
        """
        标准化操作日志

        Args:
            operation: 操作名称
            entity_id: 实体ID（可选）
            details: 详细信息（可选）
            level: 日志级别
        """
        msg = f"[{self.module_name}] {operation}"
        if entity_id:
            msg += f" [ID: {entity_id}]"
        if details:
            msg += f" - {details}"

        self._log(level, msg)

    def log_error(
        self,
        operation: str,
        error: Exception,
        entity_id: Optional[Union[int, str]] = None,
        context: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        标准化错误日志

        Args:
            operation: 操作名称
            error: 异常对象
            entity_id: 实体ID（可选）
            context: 上下文信息（可选）
        """
        msg = f"[{self.module_name}] {operation} 失败"
        if entity_id:
            msg += f" [ID: {entity_id}]"
        msg += f": {str(error)}"

        if context:
            context_str = json.dumps(context, ensure_ascii=False, default=str)
            msg += f" | 上下文: {context_str}"

        self._log("error", msg)

    def log_performance(
        self,
        operation: str,
        duration: float,
        entity_count: Optional[int] = None,
        details: Optional[str] = None,
    ) -> None:
        """
        标准化性能日志

        Args:
            operation: 操作名称
            duration: 执行时间（秒）
            entity_count: 处理的实体数量（可选）
            details: 详细信息（可选）
        """
        msg = f"[{self.module_name}] {operation} 性能"
        msg += f" | 耗时: {duration:.3f}s"

        if entity_count is not None:
            msg += f" | 处理数量: {entity_count}"
            if duration > 0:
                rate = entity_count / duration
                msg += f" | 处理速率: {rate:.1f}/s"

        if details:
            msg += f" | {details}"

        level = "warning" if duration > 5.0 else "info"
        self._log(level, msg)

    def log_data_flow(
        self,
        stage: str,
        data_count: int,
        data_type: str = "条目",
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        标准化数据流日志

        Args:
            stage: 处理阶段
            data_count: 数据数量
            data_type: 数据类型描述
            metadata: 元数据信息（可选）
        """
        msg = f"[{self.module_name}] {stage} | {data_count} {data_type}"

        if metadata:
            for key, value in metadata.items():
                msg += f" | {key}: {value}"

        self._log("info", msg)

    def log_user_action(
        self,
        user_id: Union[int, str],
        action: str,
        target: Optional[str] = None,
        result: str = "成功",
    ) -> None:
        """
        标准化用户行为日志

        Args:
            user_id: 用户ID
            action: 用户行为
            target: 操作目标（可选）
            result: 操作结果
        """
        msg = f"[{self.module_name}] 用户行为 | 用户: {user_id} | 行为: {action}"
        if target:
            msg += f" | 目标: {target}"
        msg += f" | 结果: {result}"

        self._log("info", msg)

    def log_system_state(
        self, component: str, state: str, metrics: Optional[Dict[str, Any]] = None
    ) -> None:
        """
        标准化系统状态日志

        Args:
            component: 组件名称
            state: 状态描述
            metrics: 相关指标（可选）
        """
        msg = f"[{self.module_name}] 系统状态 | {component}: {state}"

        if metrics:
            for key, value in metrics.items():
                msg += f" | {key}: {value}"

        self._log("info", msg)

    def log_api_call(
        self,
        api_name: str,
        duration: float,
        status: str = "成功",
        request_size: Optional[int] = None,
        response_size: Optional[int] = None,
    ) -> None:
        """
        标准化API调用日志

        Args:
            api_name: API名称
            duration: 调用时间
            status: 调用状态
            request_size: 请求大小（可选）
            response_size: 响应大小（可选）
        """
        msg = f"[{self.module_name}] API调用 | {api_name} | {status} | 耗时: {duration:.3f}s"

        if request_size is not None:
            msg += f" | 请求: {request_size}B"
        if response_size is not None:
            msg += f" | 响应: {response_size}B"

        level = "warning" if duration > 2.0 or status != "成功" else "info"
        self._log(level, msg)


class PerformanceLogger:
    """性能监控日志器"""

    def __init__(self, logger: StandardLogger):
        """
        初始化性能日志器

        Args:
            logger: 标准日志器实例
        """
        self.logger = logger
        self.start_times: Dict[str, float] = {}

    def start_timer(self, operation_id: str) -> None:
        """
        开始计时

        Args:
            operation_id: 操作标识
        """
        self.start_times[operation_id] = time.time()

    def end_timer(
        self,
        operation_id: str,
        operation_name: str,
        entity_count: Optional[int] = None,
        details: Optional[str] = None,
    ) -> float:
        """
        结束计时并记录日志

        Args:
            operation_id: 操作标识
            operation_name: 操作名称
            entity_count: 处理实体数量（可选）
            details: 详细信息（可选）

        Returns:
            执行时长（秒）
        """
        if operation_id not in self.start_times:
            self.logger.log_error(
                "性能监控", ValueError(f"未找到操作 {operation_id} 的开始时间")
            )
            return 0.0

        duration = time.time() - self.start_times[operation_id]
        del self.start_times[operation_id]

        self.logger.log_performance(operation_name, duration, entity_count, details)
        return duration

    def log_memory_usage(
        self, operation: str, before_mb: float, after_mb: float
    ) -> None:
        """
        记录内存使用情况

        Args:
            operation: 操作名称
            before_mb: 操作前内存（MB）
            after_mb: 操作后内存（MB）
        """
        diff = after_mb - before_mb
        msg = f"{operation} 内存使用 | 前: {before_mb:.1f}MB | 后: {after_mb:.1f}MB | 变化: {diff:+.1f}MB"
        self.logger.log_operation(msg, level="debug")


class StructuredLogger:
    """结构化日志器"""

    def __init__(self, logger: StandardLogger):
        """
        初始化结构化日志器

        Args:
            logger: 标准日志器实例
        """
        self.logger = logger

    def log_event(
        self,
        event_type: str,
        event_data: Dict[str, Any],
        user_id: Optional[Union[int, str]] = None,
    ) -> None:
        """
        记录结构化事件

        Args:
            event_type: 事件类型
            event_data: 事件数据
            user_id: 用户ID（可选）
        """
        event = {
            "timestamp": datetime.now().isoformat(),
            "event_type": event_type,
            "data": event_data,
        }

        if user_id:
            event["user_id"] = user_id

        # 格式化为可读的JSON
        event_json = json.dumps(event, ensure_ascii=False, indent=2, default=str)
        self.logger.info(f"事件记录:\n{event_json}")

    def log_business_metrics(
        self, metrics: Dict[str, Union[int, float]], period: str = "实时"
    ) -> None:
        """
        记录业务指标

        Args:
            metrics: 业务指标字典
            period: 统计周期
        """
        metrics_data = {
            "timestamp": datetime.now().isoformat(),
            "period": period,
            "metrics": metrics,
        }

        metrics_json = json.dumps(metrics_data, ensure_ascii=False, indent=2)
        self.logger.info(f"业务指标:\n{metrics_json}")


def get_logger(name: str) -> StandardLogger:
    """
    获取标准日志器实例

    Args:
        name: 模块名称

    Returns:
        StandardLogger实例
    """
    if not isinstance(name, str):
        name = str(name) if name is not None else "unknown"
    return StandardLogger(name)


def get_performance_logger(name: str) -> PerformanceLogger:
    """
    获取性能日志器实例

    Args:
        name: 模块名称

    Returns:
        PerformanceLogger实例
    """
    standard_logger = get_logger(name)
    return PerformanceLogger(standard_logger)


def get_structured_logger(name: str) -> StructuredLogger:
    """
    获取结构化日志器实例

    Args:
        name: 模块名称

    Returns:
        StructuredLogger实例
    """
    standard_logger = get_logger(name)
    return StructuredLogger(standard_logger)


# 性能监控装饰器
def log_performance(
    operation_name: str = None,
    log_args: bool = False,
    log_result: bool = False,
    threshold_seconds: float = 1.0,
):
    """
    性能监控装饰器

    Args:
        operation_name: 操作名称（默认使用函数名）
        log_args: 是否记录参数
        log_result: 是否记录返回值
        threshold_seconds: 性能警告阈值（秒）
    """

    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__ or __name__)
            perf_logger = PerformanceLogger(logger)
            
            # ContextVar 注入 Trace ID (若不存在)
            token = None
            if trace_id_var.get() == "-":
                token = trace_id_var.set(uuid.uuid4().hex[:8])

            op_name = operation_name or func.__name__
            operation_id = f"{func.__module__}.{func.__name__}_{id(func)}"

            # 记录开始
            if log_args:
                logger.log_operation(
                    f"{op_name} 开始", details=f"参数: args={args}, kwargs={kwargs}"
                )
            else:
                logger.log_operation(f"{op_name} 开始")

            perf_logger.start_timer(operation_id)

            try:
                result = await func(*args, **kwargs)
                duration = perf_logger.end_timer(operation_id, op_name)

                # 性能警告
                if duration > threshold_seconds:
                    logger.log_operation(
                        f"{op_name} 性能警告",
                        details=f"执行时间 {duration:.3f}s 超过阈值 {threshold_seconds}s",
                        level="warning",
                    )

                if log_result:
                    logger.log_operation(f"{op_name} 完成", details=f"返回值: {result}")
                else:
                    logger.log_operation(f"{op_name} 完成")

                return result

            except Exception as e:
                perf_logger.end_timer(operation_id, f"{op_name} (失败)")
                logger.log_error(op_name, e)
                raise
            finally:
                if token:
                    trace_id_var.reset(token)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__ or __name__)

            op_name = operation_name or func.__name__
            
            # ContextVar 注入 Trace ID (若不存在)
            token = None
            if trace_id_var.get() == "-":
                token = trace_id_var.set(uuid.uuid4().hex[:8])
            
            start_time = time.time()

            if log_args:
                logger.log_operation(
                    f"{op_name} 开始", details=f"参数: args={args}, kwargs={kwargs}"
                )
            else:
                logger.log_operation(f"{op_name} 开始")

            try:
                result = func(*args, **kwargs)
                duration = time.time() - start_time

                logger.log_performance(op_name, duration)

                if duration > threshold_seconds:
                    logger.log_operation(
                        f"{op_name} 性能警告",
                        details=f"执行时间 {duration:.3f}s 超过阈值 {threshold_seconds}s",
                        level="warning",
                    )

                if log_result:
                    logger.log_operation(f"{op_name} 完成", details=f"返回值: {result}")
                else:
                    logger.log_operation(f"{op_name} 完成")

                return result

            except Exception as e:
                duration = time.time() - start_time
                logger.log_performance(f"{op_name} (失败)", duration)
                logger.log_error(op_name, e)
                raise
            finally:
                if token:
                    trace_id_var.reset(token)

        # 根据函数类型返回对应的包装器
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# 用户行为记录装饰器
def log_user_action(action_name: str = None, extract_user_id: callable = None):
    """
    用户行为记录装饰器

    Args:
        action_name: 行为名称（默认使用函数名）
        extract_user_id: 从参数中提取用户ID的函数
    """

    def decorator(func):
        @functools.wraps(func)
        async def async_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__ or __name__)

            # ContextVar 注入 Trace ID (若不存在)
            token = None
            if trace_id_var.get() == "-":
                token = trace_id_var.set(uuid.uuid4().hex[:8])

            action = action_name or func.__name__
            user_id = None

            if extract_user_id:
                try:
                    user_id = extract_user_id(*args, **kwargs)
                except Exception as e:
                    logger.log_error("提取用户ID", e)

            try:
                result = await func(*args, **kwargs)
                logger.log_user_action(user_id or "未知", action, result="成功")
                return result
            except Exception as e:
                logger.log_user_action(
                    user_id or "未知", action, result=f"失败: {str(e)}"
                )
                raise
            finally:
                if token:
                    trace_id_var.reset(token)

        @functools.wraps(func)
        def sync_wrapper(*args, **kwargs):
            logger = get_logger(func.__module__ or __name__)
            
            # ContextVar 注入 Trace ID (若不存在)
            token = None
            if trace_id_var.get() == "-":
                token = trace_id_var.set(uuid.uuid4().hex[:8])

            action = action_name or func.__name__
            user_id = None

            if extract_user_id:
                try:
                    user_id = extract_user_id(*args, **kwargs)
                except Exception as e:
                    logger.log_error("提取用户ID", e)

            try:
                result = func(*args, **kwargs)
                logger.log_user_action(user_id or "未知", action, result="成功")
                return result
            except Exception as e:
                logger.log_user_action(
                    user_id or "未知", action, result=f"失败: {str(e)}"
                )
                raise
            finally:
                if token:
                    trace_id_var.reset(token)

        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator


# 全局日志器缓存
_logger_cache: Dict[str, StandardLogger] = {}


def get_cached_logger(name: str) -> StandardLogger:
    """
    获取缓存的日志器实例

    Args:
        name: 模块名称

    Returns:
        缓存的StandardLogger实例
    """
    if not isinstance(name, str):
        name = str(name) if name is not None else "unknown"
    if name not in _logger_cache:
        _logger_cache[name] = StandardLogger(name)
    return _logger_cache[name]


# 便捷函数
def log_startup(module_name: str, version: str = None, config: Dict[str, Any] = None):
    """记录模块启动信息"""
    logger = get_cached_logger(module_name)
    msg = f"{module_name} 启动"
    if version:
        msg += f" | 版本: {version}"
    if config:
        msg += f" | 配置: {json.dumps(config, ensure_ascii=False, default=str)}"
    logger.log_system_state("启动", msg)


def log_shutdown(module_name: str, cleanup_info: Dict[str, Any] = None):
    """记录模块关闭信息"""
    logger = get_cached_logger(module_name)
    msg = f"{module_name} 关闭"
    if cleanup_info:
        msg += (
            f" | 清理信息: {json.dumps(cleanup_info, ensure_ascii=False, default=str)}"
        )
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
    """若是长ID则截断显示，用于日志优化"""
    s = str(val)
    if len(s) > length:
        return "..." + s[-length:]
    return s
