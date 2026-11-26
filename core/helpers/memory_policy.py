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


_ENV_MEMORY_KEYS = ("SERVER_MEMORY", "MEMORY_LIMIT", "CONTAINER_MEMORY_MB")

# 探测失败或探测值荒唐时用的地板（MB）
FALLBACK_WARNING_MB = 1024
FALLBACK_CRITICAL_MB = 2048


def _env_limit_bytes() -> Tuple[Optional[int], Optional[str]]:
    """Pterodactyl/Wings 会把容器内存上限以 MB 注入 SERVER_MEMORY，这比 cgroup 可靠。"""
    import os

    for key in _ENV_MEMORY_KEYS:
        raw = os.environ.get(key)
        if not raw:
            continue
        try:
            mb = float(str(raw).strip())
        except ValueError:
            continue
        if mb > 0:
            return int(mb * 1024 * 1024), key
    return None, None


def _meminfo_total_bytes() -> Optional[int]:
    try:
        with open("/proc/meminfo", encoding="utf-8") as fh:
            for line in fh:
                if line.startswith("MemTotal:"):
                    return int(line.split()[1]) * 1024
    except Exception:
        return None
    return None


def _detect_total_bytes_with_source() -> Tuple[Optional[int], str]:
    """返回 (字节数, 来源)。来源用于日志归因和可信度判断。"""
    cgroup = _cgroup_limit_bytes()
    env_limit, env_key = _env_limit_bytes()

    # [FIX] cgroup 在嵌套容器里偶尔只报出几百 MB（线上就是 480MB），
    # 而面板的权威值是 SERVER_MEMORY。两者差一个数量级时采信环境变量。
    if env_limit and (cgroup is None or env_limit > cgroup * 2):
        return env_limit, env_key or "env"
    if cgroup:
        return cgroup, "cgroup"
    if env_limit:
        return env_limit, env_key or "env"
    try:
        import psutil

        total = getattr(psutil.virtual_memory(), "total", None)
        if total:
            return int(total), "psutil"
    except Exception:
        pass
    meminfo = _meminfo_total_bytes()
    if meminfo:
        return meminfo, "/proc/meminfo(宿主机)"
    return None, "unknown"


def _detect_total_bytes() -> Optional[int]:
    return _detect_total_bytes_with_source()[0]


def resolve_process_memory_thresholds(
    configured_warning_mb: int,
    configured_critical_mb: int,
    *,
    total_memory_bytes: Optional[int] = None,
) -> Tuple[int, int]:
    """按容器真实内存配额给出 RSS 水位：80% 警告、90% 硬顶。"""
    try:
        source = "explicit"
        if total_memory_bytes is None:
            total_memory_bytes, source = _detect_total_bytes_with_source()

        total_bytes = _coerce_positive_number(total_memory_bytes)
        if total_bytes is None:
            # [FIX] 探测不到就别用 384/768 这种给小鸡写的默认值，抬到地板，
            # 否则 300~450MB 的常驻 RSS 会一直踩 Warning、每 10 秒一次 GC。
            warn = max(int(configured_warning_mb or 0), FALLBACK_WARNING_MB)
            crit = max(int(configured_critical_mb or 0), FALLBACK_CRITICAL_MB)
            logger.warning(
                "内存上限探测失败，使用地板阈值 warning=%dMB critical=%dMB", warn, crit
            )
            return warn, crit

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

        # 探测到的总量小于 1GB 时用 WARNING 打出来：容器实际配额远大于此，
        # 阈值就会一直踩线（线上 450MB > 384MB 就是这么来的）。
        log = logger.warning if total_mb < 1024 else logger.info
        log(
            "内存阈值: total=%dMB warning=%dMB critical=%dMB 来源=%s (configured=%s/%s)",
            total_mb, warning, critical, source, configured_warning_mb, configured_critical_mb,
        )
        return warning, critical
    except Exception as exc:
        logger.warning("内存阈值动态计算失败，使用配置值: %s", exc)
        return int(configured_warning_mb), int(configured_critical_mb)
