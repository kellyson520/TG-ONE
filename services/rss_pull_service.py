import asyncio
import logging
from datetime import datetime
from typing import List, Optional

from sqlalchemy import select
from telethon import TelegramClient

from models.models import AsyncSessionManager, RSSSubscription
from utils.network.aimd import AIMDScheduler
from utils.network.timing_wheel import HashedTimingWheel
from utils.network.circuit_breaker import CircuitBreaker, CircuitOpenException
import aiohttp

logger = logging.getLogger(__name__)

class RSSPullService:
    """
    RSS 主动拉取服务 (AIMD 驱动)
    使用 HashedTimingWheel 进行轻量级定时调度
    使用 AIMD 算法根据内容更新频率自动调整拉取间隔
    """
    
    def __init__(self, user_client: TelegramClient, bot_client: TelegramClient):
        self.user_client = user_client
        self.bot_client = bot_client
        # 初始化时间轮：1秒一刻，3600个槽位（支持1小时内的精确调度）
        self.timing_wheel = HashedTimingWheel(tick_ms=1000, slots=3600)
        self.schedulers = {}  # subscription_id -> AIMDScheduler
        self.breakers = {}    # subscription_id -> CircuitBreaker (容灾熔断)
        self._running = False

    async def start(self):
        """启动服务"""
        if self._running:
            return
        
        self._running = True
        await self.timing_wheel.start()
        
        # 加载所有活跃订阅
        async with AsyncSessionManager() as session:
            stmt = select(RSSSubscription).where(RSSSubscription.is_active == True)
            result = await session.execute(stmt)
            subscriptions = result.scalars().all()
            
            for sub in subscriptions:
                await self.schedule_subscription(sub)
        
        logger.info(f"RSS Pull Service 已启动，共计 {len(subscriptions)} 个订阅")

    async def stop(self):
        """停止服务"""
        self._running = False
        await self.timing_wheel.stop()
        logger.info("RSS Pull Service 已停止")

    async def schedule_subscription(self, sub: RSSSubscription):
        """将订阅加入调度轮"""
        # 初始化 AIMD 调度器
        if sub.id not in self.schedulers:
            self.schedulers[sub.id] = AIMDScheduler(
                min_interval=sub.min_interval,
                max_interval=sub.max_interval,
                multiplier=0.5, # 发现更新，间隔减半
                increment=60    # 无更新，间隔增加1分钟
            )
            # 恢复当前间隔
            self.schedulers[sub.id].current_interval = sub.current_interval

        # 计算下次运行延迟
        delay = self.schedulers[sub.id].current_interval
        
        # 添加任务到时间轮
        task_id = f"rss_pull_{sub.id}"
        self.timing_wheel.add_task(
            delay_ms=int(delay * 1000),
            callback=self.pull_task,
            task_id=task_id,
            sub_id=sub.id
        )
        logger.debug(f"[RSS Pull] 订阅 {sub.id} 已排期: {delay:.1f}s 后运行")

    async def pull_task(self, sub_id: int):
        """执行拉取任务并根据结果更新 AIMD"""
        if not self._running:
            return

        has_new_content = False
        try:
            async with AsyncSessionManager() as session:
                sub = await session.get(RSSSubscription, sub_id)
                if not sub or not sub.is_active:
                    return

                # 执行实际拉取逻辑
                has_new_content = await self._do_pull(sub)
                
                # 更新 AIMD 逻辑
                new_interval = self.schedulers[sub_id].update(has_new_content)
                
                # 持久化当前间隔
                sub.current_interval = int(new_interval)
                sub.last_checked = datetime.utcnow().isoformat()
                await session.commit()

                # 重新排期
                await self.schedule_subscription(sub)

        except Exception as e:
            logger.error(f"RSS Pull {sub_id} 任务执行出错: {e}", exc_info=True)
            # 即使出错也重新排期，使用惩罚性延迟或保持现状
            await asyncio.sleep(60)
            if self._running:
                async with AsyncSessionManager() as session:
                    sub = await session.get(RSSSubscription, sub_id)
                    if sub: await self.schedule_subscription(sub)

    async def _do_pull(self, sub: RSSSubscription) -> bool:
        """执行 HTTP 拉取并解析 (核心逻辑) - 接入熔断器保护"""
        logger.info(f"[RSS Pull] 正在拉取: {sub.url}")
        
        # 获取或创建该订阅的熔断器
        if sub.id not in self.breakers:
            self.breakers[sub.id] = CircuitBreaker(
                name=f"rss_pull_{sub.id}", 
                failure_threshold=3, 
                recovery_timeout=300 # 5分钟冷却
            )
        
        try:
            return await self.breakers[sub.id].call(self._do_pull_internal, sub)
        except CircuitOpenException:
            logger.warning(f"[RSS Pull] 订阅 {sub.id} 处于熔断状态，跳过 HTTP 请求")
            return False
        except Exception as e:
            logger.warning(f"[RSS Pull] 拉取失败 {sub.url}: {e}")
            return False

    async def _do_pull_internal(self, sub: RSSSubscription) -> bool:
        """实际的 HTTP 请求逻辑"""
        try:
            async with aiohttp.ClientSession() as session:
                headers = {}
                if sub.last_etag: headers['If-None-Match'] = sub.last_etag
                if sub.last_modified: headers['If-Modified-Since'] = sub.last_modified
                
                async with session.get(sub.url, headers=headers, timeout=30) as resp:
                    if resp.status == 304:
                        logger.debug(f"[RSS Pull] {sub.url} 无变化 (304)")
                        return False
                    
                    if resp.status != 200:
                        logger.warning(f"[RSS Pull] {sub.url} 返回状态码 {resp.status}")
                        return False
                    
                    # 更新 ETag/Modified
                    sub.last_etag = resp.headers.get('ETag')
                    sub.last_modified = resp.headers.get('Last-Modified')
                    
                    text = await resp.text()
                    
                    # 使用 RSSParser 解析
                    from utils.processing.rss_parser import rss_parser
                    parsed_feed = rss_parser.parse(text)
                    
                    if not parsed_feed or not parsed_feed.entries:
                        logger.warning(f"[RSS Pull] 解析失败或空 Feed: {sub.url}")
                        return False

                    # 增量去重
                    new_entries = []
                    last_published = sub.latest_post_date
                    max_published = last_published

                    for entry in parsed_feed.entries:
                        if not entry.published:
                            continue
                        
                        entry_time = entry.published.replace(tzinfo=None) if entry.published.tzinfo else entry.published
                        last_time_naive = last_published.replace(tzinfo=None) if last_published and last_published.tzinfo else (last_published or datetime.min)

                        if entry_time > last_time_naive:
                            new_entries.append(entry)
                            if not max_published or entry_time > (max_published.replace(tzinfo=None) if max_published.tzinfo else max_published):
                                max_published = entry.published

                    if new_entries:
                        logger.info(f"[RSS Pull] 发现 {len(new_entries)} 条新内容")
                        sub.latest_post_date = max_published
                        sub.fail_count = 0 
                        return True
                    else:
                        logger.debug(f"[RSS Pull] 无新内容 (Latest: {last_published})")
                        return False
        except Exception as e:
            raise e # 抛出给上层 breaker 捕获

    def add_new_subscription(self, sub_id: int):
        """当外部添加新订阅时被调用"""
        asyncio.create_task(self._add_sub_worker(sub_id))

    async def _add_sub_worker(self, sub_id: int):
        async with AsyncSessionManager() as session:
            sub = await session.get(RSSSubscription, sub_id)
            if sub:
                await self.schedule_subscription(sub)

    def get_service_stats(self):
        """获取服务运行状态统计"""
        # 计算断路器状态
        open_breakers = sum(1 for b in self.breakers.values() if b.state.name == "OPEN")
        
        # 获取时间轮状态
        wheel_stats = self.timing_wheel.get_stats()
        
        return {
            "is_running": self._running,
            "active_subscriptions": len(self.schedulers),
            "open_breakers": open_breakers,
            "total_breakers": len(self.breakers),
            "timing_wheel": wheel_stats
        }
