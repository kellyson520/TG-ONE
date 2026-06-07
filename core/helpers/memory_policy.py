import logging
from typing import Optional, Tuple


logger = logging.getLogger(__name__)


def _coerce_positive_number(value: object) -> Optional[float]:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    if value <= 0:
        return None
    return float(value)


def resolve_process_memory_thresholds(
    configured_warning_mb: int,
    configured_critical_mb: int,
    *,
    total_memory_bytes: Optional[int] = None,
) -> Tuple[int, int]:
    """Return conservative process RSS thresholds for small VPS/container hosts."""
    try:
        if total_memory_bytes is None:
            import psutil

            total_memory_bytes = getattr(psutil.virtual_memory(), "total", None)

        total_bytes = _coerce_positive_number(total_memory_bytes)
        if total_bytes is None:
            return int(configured_warning_mb), int(configured_critical_mb)

        total_mb = total_bytes / 1024 / 1024
        dynamic_warning = max(256, int(total_mb * 0.45))
        dynamic_critical = max(dynamic_warning + 128, int(total_mb * 0.70))

        warning = min(int(configured_warning_mb), dynamic_warning)
        critical = min(int(configured_critical_mb), dynamic_critical)
        if critical <= warning:
            critical = warning + 128

        return warning, critical
    except Exception as exc:
        logger.warning("内存阈值动态计算失败，使用配置值: %s", exc)
        return int(configured_warning_mb), int(configured_critical_mb)
