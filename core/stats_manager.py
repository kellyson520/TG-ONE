
import json
import os
import time
import logging
import asyncio
from typing import Dict, Any, Optional
from datetime import datetime
from core.config import settings

logger = logging.getLogger(__name__)

class StatsManager:
    """
    负责系统生命周期内统计数据的持久化。
    使用原子写入 (Atomic Write) 策略，确保在高并发或断电情况下数据不丢失。
    """
    
    def __init__(self):
        # 数据根目录下的 stats 子目录
        self.stats_dir = settings.DATA_ROOT / "stats"
        self.stats_file = self.stats_dir / "lifetime_stats.json"
        self._ensure_dir()
        
    def _ensure_dir(self):
        if not self.stats_dir.exists():
            try:
                self.stats_dir.mkdir(parents=True, exist_ok=True)
            except Exception as e:
                logger.error(f"Failed to create stats directory {self.stats_dir}: {e}")

    def _load_stats(self) -> Dict[str, Any]:
        """加载现有统计数据，若文件不存在或损坏则返回默认结构"""
        default_stats = {
            "meta": {
                "version": "1.0",
                "deployment_start_date": datetime.utcnow().isoformat(),
                "last_updated": None
            },
            "lifetime_totals": {
                "tasks_cleaned": 0,          # 已清理（物理删除）的任务数
                "logs_cleaned": 0,           # 已清理的日志条目数
                "db_maintenance_count": 0    # 执行维护任务的次数
            },
            "history": [] # 最近 N 次清理记录
        }
        
        if not self.stats_file.exists():
            return default_stats
            
        try:
            with open(self.stats_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
                # 简单的 Schema 兼容性检查
                if "lifetime_totals" not in data:
                    data["lifetime_totals"] = default_stats["lifetime_totals"]
                return data
        except Exception as e:
            logger.warning(f"Failed to load stats file {self.stats_file}, using default. Error: {e}")
            return default_stats

    def _save_stats(self, stats: Dict[str, Any]):
        """原子写入统计数据"""
        try:
            # 更新元数据
            stats["meta"]["last_updated"] = datetime.utcnow().isoformat()
            
            # 1. 写入临时文件
            temp_file = self.stats_file.with_suffix('.tmp')
            with open(temp_file, 'w', encoding='utf-8') as f:
                json.dump(stats, f, indent=2, ensure_ascii=False)
                f.flush()
                # 2. 强制刷盘 (Fsync)
                os.fsync(f.fileno())
                
            # 3. 原子替换
            os.replace(temp_file, self.stats_file)
            
        except Exception as e:
            logger.error(f"Failed to save stats to {self.stats_file}: {e}")

    def record_cleanup(self, tasks_removed: int = 0, logs_removed: int = 0):
        """记录一次清理操作"""
        if tasks_removed == 0 and logs_removed == 0:
            return

        try:
            stats = self._load_stats()
            
            # 更新总数
            stats["lifetime_totals"]["tasks_cleaned"] = stats["lifetime_totals"].get("tasks_cleaned", 0) + tasks_removed
            stats["lifetime_totals"]["logs_cleaned"] = stats["lifetime_totals"].get("logs_cleaned", 0) + logs_removed
            stats["lifetime_totals"]["db_maintenance_count"] = stats["lifetime_totals"].get("db_maintenance_count", 0) + 1
            
            # 添加历史记录 (保留最近 50 条)
            entry = {
                "date": datetime.utcnow().isoformat(),
                "tasks_removed": tasks_removed,
                "logs_removed": logs_removed
            }
            if "history" not in stats:
                stats["history"] = []
                
            stats["history"].insert(0, entry)
            if len(stats["history"]) > 50:
                stats["history"] = stats["history"][:50]
                
            self._save_stats(stats)
            logger.info(f"Statistics persisted: +{tasks_removed} tasks, +{logs_removed} logs cleaned.")
            
        except Exception as e:
            logger.error(f"Error recording cleanup stats: {e}")

    async def async_record_cleanup(self, tasks_removed: int = 0, logs_removed: int = 0):
        """异步接口 (在 ThreadPoolExecutor 中运行以免阻塞事件循环)"""
        await asyncio.to_thread(self.record_cleanup, tasks_removed, logs_removed)

# 全局单例
stats_manager = StatsManager()
