"""
Metrics API Endpoints
暴露系统性能指标的 REST API
"""
from fastapi import APIRouter, HTTPException
from typing import Dict, Any
import logging

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/metrics", tags=["metrics"])


@router.get("/compression")
async def get_compression_metrics() -> Dict[str, Any]:
    """
    获取压缩服务指标
    
    Returns:
        {
            "compressed_count": int,
            "decompressed_count": int,
            "avg_compression_ratio": float,
            "space_saved_bytes": int,
            "space_saved_percent": float
        }
    """
    try:
        from services.metrics_collector import metrics_collector
        return metrics_collector.get_compression_metrics()
    except Exception as e:
        logger.error(f"Failed to get compression metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/rate_limit")
async def get_rate_limit_metrics() -> Dict[str, Dict[str, Any]]:
    """
    获取限流器指标
    
    Returns:
        {
            "db_writes": {
                "total_requests": int,
                "accepted_requests": int,
                "rejected_requests": int,
                "tokens_available": float,
                "current_rate": float,
                "acceptance_rate": float
            },
            ...
        }
    """
    try:
        from services.metrics_collector import metrics_collector
        return metrics_collector.get_rate_limit_metrics()
    except Exception as e:
        logger.error(f"Failed to get rate limit metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/io_latency")
async def get_io_latency_metrics() -> Dict[str, Dict[str, Any]]:
    """
    获取 I/O 延迟指标
    
    Returns:
        {
            "db_read": {
                "count": int,
                "avg_ms": float,
                "p50_ms": float,
                "p95_ms": float,
                "p99_ms": float
            },
            ...
        }
    """
    try:
        from services.metrics_collector import metrics_collector
        return metrics_collector.get_io_latency_metrics()
    except Exception as e:
        logger.error(f"Failed to get I/O latency metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/system")
async def get_system_metrics() -> Dict[str, Any]:
    """
    获取系统资源指标
    
    Returns:
        {
            "cpu_percent": float,
            "memory_percent": float,
            "memory_available_mb": float,
            "disk_percent": float,
            "disk_free_gb": float,
            "uptime_seconds": float
        }
    """
    try:
        from services.metrics_collector import metrics_collector
        return metrics_collector.get_system_metrics()
    except Exception as e:
        logger.error(f"Failed to get system metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all")
async def get_all_metrics() -> Dict[str, Any]:
    """
    获取所有指标
    
    Returns:
        {
            "timestamp": str,
            "compression": {...},
            "rate_limit": {...},
            "io_latency": {...},
            "system": {...},
            "custom": {...}
        }
    """
    try:
        from services.metrics_collector import metrics_collector
        return metrics_collector.get_all_metrics()
    except Exception as e:
        logger.error(f"Failed to get all metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset")
async def reset_metrics() -> Dict[str, str]:
    """
    重置所有指标统计
    
    Returns:
        {"status": "success", "message": "All metrics reset"}
    """
    try:
        from services.metrics_collector import metrics_collector
        metrics_collector.reset_all()
        return {"status": "success", "message": "All metrics reset"}
    except Exception as e:
        logger.error(f"Failed to reset metrics: {e}")
        raise HTTPException(status_code=500, detail=str(e))
