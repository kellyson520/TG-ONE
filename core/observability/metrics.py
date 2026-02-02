try:
    from prometheus_client import Counter, Histogram, Gauge, Info
    from prometheus_client import REGISTRY, PROCESS_COLLECTOR, PLATFORM_COLLECTOR, GC_COLLECTOR
    HAS_PROMETHEUS = True
except ImportError:
    HAS_PROMETHEUS = False
    # Dummy classes for when prometheus is missing
    class DummyMetric:
        def __init__(self, *args, **kwargs): pass
        def labels(self, *args, **kwargs): return self
        def inc(self, *args, **kwargs): pass
        def set(self, *args, **kwargs): pass
        def observe(self, *args, **kwargs): pass
    Counter = Histogram = Gauge = Info = DummyMetric
    REGISTRY = None

# --- Web Metrics ---
HTTP_REQUESTS_TOTAL = Counter(
    "http_requests_total",
    "Total number of HTTP requests",
    ["method", "endpoint", "status"]
)

HTTP_REQUEST_DURATION_SECONDS = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration in seconds",
    ["method", "endpoint"],
    buckets=(0.01, 0.05, 0.1, 0.5, 1.0, 5.0, 10.0, float("inf"))
)

# --- Business Metrics ---
FORWARD_OPERATIONS_TOTAL = Counter(
    "forward_operations_total",
    "Total number of forward operations",
    ["status", "source_type"]
)

FORWARD_LATENCY_SECONDS = Histogram(
    "forward_latency_seconds",
    "Time taken to forward a message",
    ["source_type"],
    buckets=(0.1, 0.5, 1.0, 2.0, 5.0, 10.0, 30.0, float("inf"))
)

# --- Infrastructure Metrics ---
DB_CONNECTION_POOL_SIZE = Gauge(
    "db_connection_pool_size",
    "Current number of active database connections",
    ["state"]  # 'active', 'idle'
)

TELEGRAM_CLIENT_STATUS = Gauge(
    "telegram_client_status",
    "Status of the Telegram client (1=connected, 0=disconnected)"
)

SYSTEM_DISK_USAGE_PERCENT = Gauge(
    "system_disk_usage_percent",
    "Disk usage percentage of the volume where the app resides"
)

QUEUE_SIZE = Gauge(
    "task_queue_size",
    "Number of tasks currently in the queue"
)

class MetricsManager:
    """
    Central manager for updating gauges and other non-counter metrics.
    """
    
    @staticmethod
    def track_request(method: str, endpoint: str, status: int):
        HTTP_REQUESTS_TOTAL.labels(method=method, endpoint=endpoint, status=status).inc()

    @staticmethod
    def observe_request_duration(method: str, endpoint: str, duration: float):
        HTTP_REQUEST_DURATION_SECONDS.labels(method=method, endpoint=endpoint).observe(duration)

    @staticmethod
    def track_forward(status: str, source_type: str = "channel"):
        FORWARD_OPERATIONS_TOTAL.labels(status=status, source_type=source_type).inc()

    @staticmethod
    def update_db_pool_stats(checked_in: int, checked_out: int):
        DB_CONNECTION_POOL_SIZE.labels(state="idle").set(checked_in)
        DB_CONNECTION_POOL_SIZE.labels(state="active").set(checked_out)

    @staticmethod
    def set_telegram_status(is_connected: bool):
        TELEGRAM_CLIENT_STATUS.set(1 if is_connected else 0)

    @staticmethod
    def set_queue_size(size: int):
        QUEUE_SIZE.set(size)

metrics_manager = MetricsManager()
