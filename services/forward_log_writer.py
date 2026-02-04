"""
转发日志批量写入服务 (Forward Log Batch Writer)

高性能日志写入:
- 批量 INSERT (每 100 条或每 5 秒)
- 异步队列缓冲
- 自动归档策略

创建于: 2026-01-11
Phase H.5: 转发日志存档优化
"""
import asyncio
import logging
from datetime import datetime
from typing import Dict, List, Optional
from collections import deque
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


@dataclass
class ForwardLogEntry:
    """转发日志条目"""
    rule_id: int
    source_chat_id: str
    target_chat_id: str
    source_message_id: int
    target_message_id: Optional[int] = None
    action: str = "forward"  # forward, filter, error
    result: str = "success"  # success, filtered, failed
    source_chat_title: Optional[str] = None
    target_chat_title: Optional[str] = None
    filter_hit: Optional[str] = None  # 命中的过滤器
    ai_modified: bool = False
    processing_time_ms: int = 0
    error_message: Optional[str] = None
    metadata: Dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)


class ForwardLogBatchWriter:
    """
    转发日志批量写入器
    
    功能:
    1. 异步队列缓冲
    2. 批量写入 (100 条或 5 秒)
    3. 写入失败自动重试
    4. 统计信息
    
    使用:
        from services.forward_log_writer import forward_log_writer
        
        # 添加日志条目
        await forward_log_writer.log(ForwardLogEntry(
            rule_id=1,
            source_chat_id="-100123456",
            target_chat_id="-100789012",
            source_message_id=100
        ))
        
        # 或者使用简化接口
        await forward_log_writer.log_forward(
            rule_id=1,
            source_chat_id="-100123456",
            target_chat_id="-100789012",
            source_message_id=100,
            target_message_id=200
        )
    """
    
    # 批量写入阈值
    BATCH_SIZE = 100
    # 刷新间隔 (秒)
    FLUSH_INTERVAL = 5.0
    # 最大重试次数
    MAX_RETRIES = 3
    
    def __init__(self):
        self._queue: deque = deque(maxlen=10000)  # 最大缓冲 10000 条
        self._lock = asyncio.Lock()
        self._running = False
        self._flush_task: Optional[asyncio.Task] = None
        self._stats = {
            "total_logged": 0,
            "total_written": 0,
            "total_failed": 0,
            "batch_writes": 0,
            "queue_overflow": 0
        }
    
    async def start(self):
        """启动批量写入服务"""
        if self._running:
            return
        self._running = True
        self._flush_task = asyncio.create_task(self._flush_loop())
        logger.info("ForwardLogBatchWriter started")
    
    async def stop(self):
        """停止服务 (刷新剩余日志)"""
        self._running = False
        if self._flush_task:
            self._flush_task.cancel()
            try:
                await self._flush_task
            except asyncio.CancelledError as e:
                logger.debug(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
        # 刷新剩余日志
        await self._flush()
        logger.info(f"ForwardLogBatchWriter stopped. Stats: {self._stats}")
    
    async def log(self, entry: ForwardLogEntry):
        """添加日志条目到队列"""
        async with self._lock:
            if len(self._queue) >= self._queue.maxlen:
                self._stats["queue_overflow"] += 1
                # 队列满时丢弃最旧的
                self._queue.popleft()
            self._queue.append(entry)
            self._stats["total_logged"] += 1
        
        # 达到批量阈值立即刷新
        if len(self._queue) >= self.BATCH_SIZE:
            asyncio.create_task(self._flush())
    
    async def log_forward(
        self,
        rule_id: int,
        source_chat_id: str,
        target_chat_id: str,
        source_message_id: int,
        target_message_id: Optional[int] = None,
        source_chat_title: Optional[str] = None,
        target_chat_title: Optional[str] = None,
        processing_time_ms: int = 0,
        ai_modified: bool = False,
        filter_hit: Optional[str] = None,
        result: str = "success",
        error_message: Optional[str] = None
    ):
        """简化的转发日志接口"""
        entry = ForwardLogEntry(
            rule_id=rule_id,
            source_chat_id=str(source_chat_id),
            target_chat_id=str(target_chat_id),
            source_message_id=source_message_id,
            target_message_id=target_message_id,
            action="forward" if result == "success" else ("filter" if result == "filtered" else "error"),
            result=result,
            source_chat_title=source_chat_title,
            target_chat_title=target_chat_title,
            filter_hit=filter_hit,
            ai_modified=ai_modified,
            processing_time_ms=processing_time_ms,
            error_message=error_message
        )
        await self.log(entry)
    
    async def _flush_loop(self):
        """定时刷新循环"""
        while self._running:
            try:
                await asyncio.sleep(self.FLUSH_INTERVAL)
                if self._queue:
                    await self._flush()
            except asyncio.CancelledError:
                break
            except Exception as e:
                logger.error(f"Flush loop error: {e}")
    
    async def _flush(self):
        """刷新队列到数据库"""
        async with self._lock:
            if not self._queue:
                return
            
            # 取出当前批次
            batch = []
            while self._queue and len(batch) < self.BATCH_SIZE:
                batch.append(self._queue.popleft())
        
        if not batch:
            return
        
        # 批量写入
        success = await self._batch_insert(batch)
        
        if success:
            self._stats["total_written"] += len(batch)
            self._stats["batch_writes"] += 1
        else:
            self._stats["total_failed"] += len(batch)
            # 写入失败，放回队列末尾 (最多重试一次)
            async with self._lock:
                for entry in batch[:50]:  # 只保留部分避免死循环
                    if len(self._queue) < self._queue.maxlen:
                        self._queue.append(entry)
    
    async def _batch_insert(self, batch: List[ForwardLogEntry]) -> bool:
        """批量插入到数据库"""
        try:
            from core.container import container
            
            async with container.db.session() as session:
                from models.models import RuleLog
                
                logs = []
                for entry in batch:
                    log = RuleLog(
                        rule_id=entry.rule_id,
                        action=entry.action,
                        source_message_id=entry.source_message_id,
                        target_message_id=entry.target_message_id,
                        result=entry.result,
                        error_message=entry.error_message,
                        processing_time=entry.processing_time_ms,
                        created_at=entry.timestamp.isoformat()
                    )
                    logs.append(log)
                
                session.add_all(logs)
                await session.commit()
            
            logger.debug(f"Batch inserted {len(batch)} forward logs")
            return True
            
        except Exception as e:
            logger.error(f"Batch insert failed: {e}")
            return False
    
    def get_stats(self) -> Dict:
        """获取统计信息"""
        return {
            **self._stats,
            "queue_size": len(self._queue),
            "queue_capacity": self._queue.maxlen,
            "batch_size": self.BATCH_SIZE,
            "flush_interval": self.FLUSH_INTERVAL
        }
    
    def get_queue_size(self) -> int:
        """获取当前队列大小"""
        return len(self._queue)


# 全局单例
forward_log_writer = ForwardLogBatchWriter()
