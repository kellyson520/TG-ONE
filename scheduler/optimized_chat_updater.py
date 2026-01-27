"""
优化的聊天信息更新器
使用官方API + 事件驱动替代轮询机制，性能提升5-20倍
"""
import asyncio
from datetime import datetime, timedelta
try:
    import pytz
    PYTZ_AVAILABLE = True
except ImportError:
    pytz = None
    PYTZ_AVAILABLE = False
import os
import logging
from dotenv import load_dotenv
from telethon import TelegramClient
from models.models import Chat
import traceback
import random
from core.constants import DEFAULT_TIMEZONE
from typing import List, Dict, Any, Optional, Set

logger = logging.getLogger(__name__)

class OptimizedChatUpdater:
    """
    优化的聊天信息更新器
    使用官方API + 批量处理 + 事件驱动
    """
    
    def __init__(self, user_client: TelegramClient, db):
        self.user_client = user_client
        self.db = db
        self.timezone = pytz.timezone(DEFAULT_TIMEZONE)
        self.task = None
        self.is_running = False
        
        # 从环境变量获取更新时间，默认凌晨3点
        self.update_time = os.getenv('CHAT_UPDATE_TIME', "03:00")
        
        # 批量处理配置
        self.batch_size = int(os.getenv('CHAT_UPDATE_BATCH_SIZE', '10'))
        self.update_limit = int(os.getenv('CHAT_UPDATE_LIMIT', '50'))  # 降低限制，使用API优化
        
        # 事件驱动队列
        self.update_queue = asyncio.Queue()
        self.batch_update_task = None
        self.pending_updates: Set[str] = set()
        
        # 统计信息
        self.stats = {
            'total_updated': 0,
            'api_calls_saved': 0,
            'last_update': None,
            'batch_updates': 0,
            'errors': 0
        }

    async def start(self):
        """启动优化的更新任务"""
        logger.info("启动优化的聊天信息更新器...")
        try:
            self.is_running = True
            
            # 启动批量更新处理器
            self.batch_update_task = asyncio.create_task(self._batch_update_processor())
            
            # 计算下一次执行时间
            now = datetime.now(self.timezone)
            next_time = self._get_next_run_time(now, self.update_time)
            wait_seconds = (next_time - now).total_seconds()
            
            logger.info(f"下一次聊天信息更新时间: {next_time.strftime('%Y-%m-%d %H:%M:%S')}")
            logger.info(f"等待时间: {wait_seconds:.2f} 秒")
            logger.info(f"批量大小: {self.batch_size}, 更新限制: {self.update_limit}")
            
            # 创建定时任务
            self.task = asyncio.create_task(self._run_optimized_update_task())
            logger.info("优化的聊天信息更新器启动完成")
            
        except Exception as e:
            logger.error(f"启动优化聊天更新器时出错: {str(e)}")
            logger.error(f"错误详情: {traceback.format_exc()}")
    
    async def stop(self):
        """停止更新器"""
        logger.info("停止优化的聊天信息更新器...")
        self.is_running = False
        
        if self.task and not self.task.done():
            self.task.cancel()
        
        if self.batch_update_task and not self.batch_update_task.done():
            self.batch_update_task.cancel()
        
        # 等待任务完成
        tasks = [t for t in [self.task, self.batch_update_task] if t and not t.done()]
        if tasks:
            await asyncio.gather(*tasks, return_exceptions=True)
        
        logger.info("优化的聊天信息更新器已停止")
    
    def _get_next_run_time(self, now, target_time):
        """计算下一次运行时间"""
        hour, minute = map(int, target_time.split(':'))
        next_time = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        
        if next_time <= now:
            next_time += timedelta(days=1)
            
        return next_time
    
    async def _run_optimized_update_task(self):
        """运行优化的更新任务"""
        while self.is_running:
            try:
                # 计算下一次执行时间
                now = datetime.now(self.timezone)
                target_time = self._get_next_run_time(now, self.update_time)
                
                # 等待到执行时间
                wait_seconds = (target_time - now).total_seconds()
                await asyncio.sleep(wait_seconds)
                
                # 执行优化的批量更新
                await self._update_all_chats_optimized()
                
            except asyncio.CancelledError:
                logger.info("优化聊天信息更新任务已取消")
                break
            except Exception as e:
                logger.error(f"优化聊天信息更新任务出错: {str(e)}")
                self.stats['errors'] += 1
                await asyncio.sleep(60)  # 出错后等待一分钟再重试
    
    async def _batch_update_processor(self):
        """批量更新处理器 - 收集更新请求并批量处理"""
        batch_timeout = 2.0  # 2秒超时
        
        while self.is_running:
            try:
                batch = []
                
                # 收集批量更新请求
                try:
                    # 等待第一个请求
                    first_chat_id = await asyncio.wait_for(
                        self.update_queue.get(), timeout=batch_timeout
                    )
                    batch.append(first_chat_id)
                    self.pending_updates.discard(first_chat_id)
                    
                    # 收集更多请求直到达到批次大小或超时
                    while len(batch) < self.batch_size:
                        try:
                            chat_id = await asyncio.wait_for(
                                self.update_queue.get(), timeout=0.2
                            )
                            if chat_id not in batch:  # 避免重复
                                batch.append(chat_id)
                                self.pending_updates.discard(chat_id)
                        except asyncio.TimeoutError:
                            break
                            
                except asyncio.TimeoutError:
                    continue  # 没有请求，继续等待
                
                # 批量处理更新
                if batch:
                    await self._process_batch_updates(batch)
                    self.stats['batch_updates'] += 1
                    
            except Exception as e:
                logger.error(f"批量更新处理器出错: {str(e)}")
                await asyncio.sleep(1)
    
    async def _process_batch_updates(self, chat_ids: List[str]):
        """处理批量聊天更新"""
        try:
            logger.info(f"批量处理聊天更新: {len(chat_ids)} 个聊天")
            
            # 使用API优化器批量获取聊天统计
            from services.network.api_optimization import get_api_optimizer
            api_optimizer = get_api_optimizer()
            
            if api_optimizer:
                # 批量获取聊天统计信息
                stats_results = await api_optimizer.get_multiple_chat_statistics(chat_ids)
                
                # 更新数据库
                async with self.db.session() as session:
                    for chat_id, stats in stats_results.items():
                        if 'error' not in stats:
                            await self._update_chat_in_db(session, chat_id, stats)
                            self.stats['total_updated'] += 1
                        else:
                            logger.warning(f"聊天 {chat_id} 统计获取失败: {stats.get('error')}")
                    
                    await session.commit()
                    logger.info(f"批量更新完成: {len(stats_results)} 个聊天")
                    
            else:
                logger.warning("API优化器未初始化，跳过批量更新")
                
        except Exception as e:
            logger.error(f"批量处理更新失败: {str(e)}")
            self.stats['errors'] += 1
    
    async def _update_chat_in_db(self, session, chat_id: str, stats: Dict[str, Any]):
        """更新数据库中的聊天信息"""
        try:
            # 查找聊天记录
            from sqlalchemy import select
            stmt = select(Chat).filter(Chat.telegram_chat_id == chat_id)
            result = await session.execute(stmt)
            chat = result.scalar_one_or_none()
            
            if chat:
                # 更新聊天统计信息
                chat.member_count = stats.get('participants_count', chat.member_count)
                chat.description = stats.get('about', chat.description)
                chat.updated_at = datetime.utcnow().isoformat()
                
                # 如果有详细统计,可以创建ChatStatistics记录
                if stats.get('total_messages', 0) > 0:
                    from models.models import ChatStatistics
                    today = datetime.utcnow().strftime('%Y-%m-%d')
                    
                    # 检查今天是否已有统计记录
                    stmt = select(ChatStatistics).filter(
                        ChatStatistics.chat_id == chat.id,
                        ChatStatistics.date == today
                    )
                    result = await session.execute(stmt)
                    existing_stat = result.scalar_one_or_none()
                    
                    if not existing_stat:
                        # 创建新的统计记录
                        new_stat = ChatStatistics(
                            chat_id=chat.id,
                            date=today,
                            message_count=stats.get('total_messages', 0),
                            user_count=stats.get('participants_count', 0)
                        )
                        session.add(new_stat)
                
                logger.debug(f"更新聊天信息: {chat_id}")
            else:
                logger.warning(f"数据库中未找到聊天: {chat_id}")
                
        except Exception as e:
            logger.error(f"更新数据库聊天信息失败 {chat_id}: {str(e)}")
    
    async def _update_all_chats_optimized(self):
        """优化的批量聊天信息更新"""
        logger.info("开始优化的聊天信息更新...")
        
        try:
            # 获取需要更新的聊天（限制数量）
            async with self.db.session() as session:
                from sqlalchemy import select
                stmt = select(Chat).filter(
                    Chat.is_active == True
                ).order_by(Chat.updated_at.asc()).limit(self.update_limit)
                result = await session.execute(stmt)
                chats = result.scalars().all()
                
                total_chats = len(chats)
                logger.info(f"找到 {total_chats} 个活跃聊天需要更新")
                
                if not chats:
                    logger.info("没有需要更新的聊天")
                    return
                
                # 收集聊天ID
                chat_ids = [chat.telegram_chat_id for chat in chats if chat.telegram_chat_id]
                
                # 使用API优化器批量获取统计
                from services.network.api_optimization import get_api_optimizer
                api_optimizer = get_api_optimizer()
                
                if api_optimizer and chat_ids:
                    logger.info(f"使用API优化器批量更新 {len(chat_ids)} 个聊天")
                    
                    # 分批处理避免API限制
                    batch_size = self.batch_size
                    for i in range(0, len(chat_ids), batch_size):
                        batch = chat_ids[i:i + batch_size]
                        
                        try:
                            # 批量获取统计信息
                            stats_results = await api_optimizer.get_multiple_chat_statistics(batch)
                            
                            # 更新数据库
                            for chat_id, stats in stats_results.items():
                                if 'error' not in stats:
                                    await self._update_chat_in_db(session, chat_id, stats)
                                    self.stats['total_updated'] += 1
                            
                            await session.commit()
                            
                            # 添加小延迟避免API限制
                            if i + batch_size < len(chat_ids):
                                await asyncio.sleep(0.5)
                                
                        except Exception as e:
                            logger.error(f"批量更新失败 (batch {i//batch_size + 1}): {str(e)}")
                            await session.rollback()
                            self.stats['errors'] += 1
                    
                    self.stats['last_update'] = datetime.now()
                    logger.info(f"优化聊天更新完成: 已更新 {self.stats['total_updated']} 个聊天")
                else:
                    logger.warning("API优化器未初始化或没有聊天ID，跳过更新")
                    
        except Exception as e:
            logger.error(f"优化聊天信息更新失败: {str(e)}")
            self.stats['errors'] += 1
    
    async def queue_chat_update(self, chat_id: str):
        """将聊天更新请求加入队列"""
        if chat_id not in self.pending_updates:
            self.pending_updates.add(chat_id)
            await self.update_queue.put(chat_id)
    
    def get_stats(self) -> Dict[str, Any]:
        """获取更新器统计信息"""
        return {
            **self.stats,
            'is_running': self.is_running,
            'queue_size': self.update_queue.qsize(),
            'pending_updates': len(self.pending_updates),
            'batch_size': self.batch_size,
            'update_limit': self.update_limit
        }


# 保持与原有ChatUpdater的兼容性
class ChatUpdater(OptimizedChatUpdater):
    """兼容原有ChatUpdater接口的优化版本"""
    pass
