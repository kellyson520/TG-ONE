from typing import Tuple

# 优雅降级：未安装 prometheus_client 时提供空实现，避免启动报错
PROMETHEUS_ENABLED = True
try:
    from prometheus_client import (
        CONTENT_TYPE_LATEST,
        CollectorRegistry,
        Counter,
        Gauge,
        Histogram,
        generate_latest,
    )

    try:
        from prometheus_client import multiprocess  # type: ignore
    except Exception:  # pragma: no cover
        multiprocess = None  # type: ignore
except Exception:  # pragma: no cover
    PROMETHEUS_ENABLED = False

    class _NoopMetric:
        def __init__(self, *args, **kwargs):
            pass

        def labels(self, *args, **kwargs):
            return self

    class _NoopCounter(_NoopMetric):
        def inc(self, *args, **kwargs):
            pass

    class _NoopGauge(_NoopMetric):
        def set(self, *args, **kwargs):
            pass

    class _NoopHistogram(_NoopMetric):
        def observe(self, *args, **kwargs):
            pass

    # 轻量占位实现
    class CollectorRegistry:  # type: ignore
        def __init__(self, *args, **kwargs):
            pass

    def generate_latest(*args, **kwargs):  # type: ignore
        return b""

    CONTENT_TYPE_LATEST = "text/plain; charset=utf-8"  # type: ignore
    Counter = _NoopCounter  # type: ignore
    Gauge = _NoopGauge  # type: ignore
    Histogram = _NoopHistogram  # type: ignore
    multiprocess = None  # type: ignore


# Registry（单进程为默认；如存在多进程目录可启用 multiprocess）
REGISTRY = CollectorRegistry()
if multiprocess is not None:
    try:
        multiprocess.MultiProcessCollector(REGISTRY)  # type: ignore
    except Exception:
        pass


# 基础健康/就绪指标
SERVICE_HEALTH = Gauge(
    "service_health_status",
    "Service health status (1 healthy, 0 unhealthy)",
    registry=REGISTRY,
)
SERVICE_READY = Gauge(
    "service_ready_status",
    "Service readiness status (1 ready, 0 not ready)",
    registry=REGISTRY,
)

SERVICE_HEALTH.set(1)
SERVICE_READY.set(0)


# 归档相关指标
ARCHIVE_RUN_TOTAL = Counter(
    "archive_runs_total", "Archive job runs", ["status"], registry=REGISTRY
)
ARCHIVE_RUN_SECONDS = Histogram(
    "archive_run_seconds", "Archive job duration seconds", registry=REGISTRY
)

# 消息处理指标
MESSAGES_RECEIVED_TOTAL = Counter(
    "messages_received_total", "Messages received", ["source"], registry=REGISTRY
)
MESSAGES_FORWARDED_TOTAL = Counter(
    "messages_forwarded_total", "Messages forwarded", ["route"], registry=REGISTRY
)
MESSAGE_PROCESS_SECONDS = Histogram(
    "message_process_seconds",
    "Message end-to-end processing latency seconds",
    registry=REGISTRY,
)
MESSAGE_FAILURES_TOTAL = Counter(
    "message_failures_total",
    "Message processing failures",
    ["reason"],
    registry=REGISTRY,
)

# 去重指标
DEDUP_HITS_TOTAL = Counter(
    "dedup_hits_total", "Dedup hits", ["method"], registry=REGISTRY
)
DEDUP_QUERIES_TOTAL = Counter(
    "dedup_queries_total", "Dedup queries", ["method"], registry=REGISTRY
)

# 去重检查耗时与决策
DEDUP_CHECK_SECONDS = Histogram(
    "dedup_check_seconds", "Dedup end-to-end check duration seconds", registry=REGISTRY
)
DEDUP_DECISIONS_TOTAL = Counter(
    "dedup_decisions_total", "Dedup decisions", ["result", "method"], registry=REGISTRY
)

# 文本指纹（SimHash）预筛命中与相似度比较次数
DEDUP_FP_HITS_TOTAL = Counter(
    "dedup_fp_hits_total",
    "Dedup fingerprint prefilter hits",
    ["algo"],
    registry=REGISTRY,
)
DEDUP_SIMILARITY_COMPARISONS = Histogram(
    "dedup_similarity_comparisons",
    "Number of exact similarity comparisons per check",
    registry=REGISTRY,
)

# 视频部分哈希耗时
VIDEO_PARTIAL_HASH_SECONDS = Histogram(
    "video_partial_hash_seconds",
    "Video partial hash compute duration seconds",
    registry=REGISTRY,
)

# 视频哈希缓存命中与计算次数
VIDEO_HASH_PCACHE_HITS_TOTAL = Counter(
    "video_hash_pcache_hits_total",
    "Video hash persistent cache hits",
    ["algo"],
    registry=REGISTRY,
)
VIDEO_HASH_COMPUTE_TOTAL = Counter(
    "video_hash_compute_total", "Video hash computed count", ["algo"], registry=REGISTRY
)

# 任务队列指标
TASK_QUEUE_LENGTH = Gauge(
    "task_queue_length", "Task queue length", ["status"], registry=REGISTRY
)

# 转发发送耗时与 FloodWait 观测
FORWARD_SEND_SECONDS = Histogram(
    "forward_send_seconds", "Forward send duration seconds", registry=REGISTRY
)
FORWARD_FLOODWAIT_SECONDS = Histogram(
    "forward_floodwait_seconds", "Observed FloodWait seconds", registry=REGISTRY
)

# 压实（小文件合并）指标
COMPACT_RUN_TOTAL = Counter(
    "archive_compact_runs_total",
    "Archive compaction job runs",
    ["status"],
    registry=REGISTRY,
)
COMPACT_FILES_MERGED_TOTAL = Counter(
    "archive_compact_files_merged_total",
    "Files merged during compaction",
    ["table"],
    registry=REGISTRY,
)
COMPACT_RUN_SECONDS = Histogram(
    "archive_compact_run_seconds",
    "Archive compaction job duration seconds",
    registry=REGISTRY,
)


def set_ready(is_ready: bool) -> None:
    SERVICE_READY.set(1 if is_ready else 0)


def set_health(is_healthy: bool) -> None:
    SERVICE_HEALTH.set(1 if is_healthy else 0)


def generate_metrics() -> Tuple[bytes, str]:
    data = generate_latest(REGISTRY)
    return data, CONTENT_TYPE_LATEST
