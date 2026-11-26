import logging
from typing import Optional, Tuple


logger = logging.getLogger(__name__)

# 容器内 psutil.virtual_memory() 读的是宿主机总量，不是 cgroup 配额，
# 直接用会把 12GB 的容器算成 800MB 级别，阈值被压到 384MB → 疯狂降速 GC。
# 所以先读 cgroup 的真实上限，读不到再退回 psutil。
_CGROUP_PATHS = (
    "/sys/fs/cgroup/memory.max",                      # cgroup v2
    "/sys/fs/cgroup/memory/memory.limit_in_bytes",    # cgroup v1
)

WARN_RATIO = 0.80
CRIT_RATIO = 0.90


def _coerce_positive_number(value: object) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value <= 0:
        return None
    return float(value)


def _cgroup_limit_bytes() -> Optional[int]:
    for path in _CGROUP_PATHS:
        try:
            with open(path, encoding="utf-8") as fh:
                raw = fh.read().strip()
        except OSError:
            continue
        if not raw or raw == "max":
            continue
        try:
            value = int(raw)
        except ValueError:
            continue
        # 未设限时 v1 会给出一个接近 2^63 的天文数字
        if 0 < value < (1 << 50):
            return value
    return None


def _detect_total_bytes() -> Optional[int]:
    limit = _cgroup_limit_bytes()
    if limit:
        return limit
    try:
        import psutil

        return getattr(psutil.virtual_memory(), "total", None)
    except Exception:
        return None


def resolve_process_memory_thresholds(
    configured_warning_mb: int,
    configured_critical_mb: int,
    *,
    total_memory_bytes: Optional[int] = None,
) -> Tuple[int, int]:
    """按容器真实内存配额给出 RSS 水位：80% 警告、90% 硬顶。"""
    try:
        if total_memory_bytes is None:
            total_memory_bytes = _detect_total_bytes()

        total_bytes = _coerce_positive_number(total_memory_bytes)
        if total_bytes is None:
            return int(configured_warning_mb), int(configured_critical_mb)

        total_mb = int(total_bytes / 1024 / 1024)
        ratio_warning = int(total_mb * WARN_RATIO)
        ratio_critical = int(total_mb * CRIT_RATIO)

        # 只有当配置值落在合理区间（总量的一半到 95%）时才采信，
        # 否则说明那是给 800MB 小鸡写的默认值，直接忽略。
        def _honor(configured: int, fallback: int) -> int:
            value = int(configured or 0)
            if total_mb * 0.50 <= value <= total_mb * 0.95:
                return value
            return fallback

        warning = _honor(configured_warning_mb, ratio_warning)
        critical = _honor(configured_critical_mb, ratio_critical)
        if critical <= warning:
            critical = min(int(total_mb * 0.95), warning + 256)

        logger.info(
            "内存阈值: total=%dMB warning=%dMB critical=%dMB (configured=%s/%s)",
            total_mb, warning, critical, configured_warning_mb, configured_critical_mb,
        )
        return warning, critical
    except Exception as exc:
        logger.warning("内存阈值动态计算失败，使用配置值: %s", exc)
        return int(configured_warning_mb), int(configured_critical_mb)
