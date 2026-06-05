import logging
import asyncio
from typing import Dict, List, Optional, Any
from sqlalchemy import select, delete, func, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.dialects.sqlite import insert

from core.db_factory import DbFactory
from models.hotword import HotRawStats, HotPeriodStats, HotConfig

logger = logging.getLogger(__name__)

class HotwordRepository:
    """
    热词持久化层：使用 hotwords.db (SQLite) 替代原有小文件方案。
    支持高性能 UPSERT 操作与批量聚合。
    """
    
    def __init__(self):
        self.session_factory = DbFactory.get_hotword_session_factory()

    async def save_temp_counts(self, channel: str, counts: Dict[str, Dict[str, Any]]):
        """
        异步 UPSERT 写入原始统计数据。
        counts 格式: { word: {"f": frequency, "u": user_increment} }
        """
        async with self.session_factory() as session:
            try:
                # 采用 SQLite 批处理 UPSERT (Insert or Update)
                for word, meta in counts.items():
                    stmt = insert(HotRawStats).values(
                        channel=channel,
                        word=word,
                        score=meta.get("f", 0.0),
                        unique_users=meta.get("u", 0)
                    ).on_conflict_do_update(
                        index_elements=['channel', 'word'],
                        set_={
                            "score": HotRawStats.score + meta.get("f", 0.0),
                            "unique_users": HotRawStats.unique_users + meta.get("u", 0)
                        }
                    )
                    await session.execute(stmt)
                await session.commit()
            except Exception as e:
                await session.rollback()
                logger.error(f"Hotword DB Save Error ({channel}): {e}")

    async def load_rankings(self, channel: str, filename_or_period: str) -> Dict[str, Any]:
        """
        读取榜单数据。
        为了兼容旧代码，这里解析 filename_or_period。
        如果是 'channel_temp.json' -> 读取 HotRawStats
        如果是 'channel_day_xxx.json' -> 读取 HotPeriodStats
        """
        async with self.session_factory() as session:
            if "_temp" in filename_or_period:
                # 读取实时表
                stmt = select(HotRawStats).where(HotRawStats.channel == channel)
                result = await session.execute(stmt)
                return {r.word: {"f": r.score, "u": r.unique_users} for r in result.scalars()}
            else:
                # 解析周期
                period = "day" if "day" in filename_or_period else "month" if "month" in filename_or_period else "year"
                # 简单实现：这里需要 date_key，如果 filename_or_period 包含日期则提取
                import re
                date_match = re.search(r'\d{4,8}', filename_or_period)
                date_key = date_match.group(0) if date_match else "current"
                
                stmt = select(HotPeriodStats).where(
                    HotPeriodStats.channel == channel,
                    HotPeriodStats.period == period,
                    HotPeriodStats.date_key == date_key
                )
                result = await session.execute(stmt)
                return {r.word: {"f": r.score, "u": r.user_count} for r in result.scalars()}

    async def get_channel_dirs(self) -> List[str]:
        """获取所有有数据的频道 (DB 版本)"""
        async with self.session_factory() as session:
            stmt = select(HotRawStats.channel).distinct()
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def load_config(self, name: str) -> Dict[str, float]:
        """从 DB 加载配置项"""
        async with self.session_factory() as session:
            stmt = select(HotConfig).where(HotConfig.name == name)
            result = await session.execute(stmt)
            cfg = result.scalar_one_or_none()
            if not cfg: return {}
            
            data = cfg.data
            if isinstance(data, list):
                return {k: 1.0 for k in data}
            
            # 容错处理：处理 {"terms": {"description": "...", "terms": {...}}} 这种结构
            content = data.get("terms", {}) if isinstance(data, dict) else {}
            if isinstance(content, dict):
                # 优先提取嵌套的 terms 字典，否则使用当前字典
                target = content.get("terms", content) if isinstance(content.get("terms"), dict) else content
                # 过滤非数值字段 (如 description)
                return {str(k): float(v) for k, v in target.items() if isinstance(v, (int, float, str)) and self._is_float(v) and str(k) != "description"}
            return {}

    def _is_float(self, val):
        try:
            float(val)
            return True
        except:
            return False

    async def save_config(self, name: str, data: Any) -> bool:
        """保存配置到 DB"""
        async with self.session_factory() as session:
            try:
                # 转换 set 为 list 以便 JSON 序列化
                if isinstance(data, (set, list)):
                    final_data = list(data)
                else:
                    final_data = {"terms": data}
                
                stmt = insert(HotConfig).values(
                    name=name,
                    data=final_data
                ).on_conflict_do_update(
                    index_elements=['name'],
                    set_={"data": final_data}
                )
                await session.execute(stmt)
                await session.commit()
                return True
            except Exception as e:
                logger.error(f"Hotword Config Save Error ({name}): {e}")
                return False

    async def move_temp_to_daily(self, date_key: str, semaphore: asyncio.Semaphore):
        """将 hot_raw_stats 中的数据归档到 hot_period_stats (day 级)"""
        channels = await self.get_channel_dirs()
        for channel in channels:
            async with semaphore:
                async with self.session_factory() as session:
                    try:
                        # 1. 读取该频道所有 temp 数据
                        stmt = select(HotRawStats).where(HotRawStats.channel == channel)
                        result = await session.execute(stmt)
                        rows = result.scalars().all()
                        
                        if not rows: continue
                        
                        # 2. 批量插入到 period 统计表
                        for row in rows:
                            new_row = HotPeriodStats(
                                channel=channel,
                                word=row.word,
                                period='day',
                                date_key=date_key,
                                score=row.score,
                                user_count=row.unique_users
                            )
                            session.add(new_row)
                        
                        # 3. 清空该频道的 raw 数据 (原子操作)
                        await session.execute(delete(HotRawStats).where(HotRawStats.channel == channel))
                        await session.commit()
                        logger.info(f"Archived daily hotwords for channel: {channel}")
                    except Exception as e:
                        await session.rollback()
                        logger.error(f"Archive Daily Error ({channel}): {e}")
                await asyncio.sleep(0.05) # Jitter

    async def summarize_period(self, source_period: str, target_period: str, source_date_pattern: str, target_date_key: str, semaphore: asyncio.Semaphore):
        """跨周期聚合 (如 day -> month)"""
        channels = await self.get_channel_dirs_from_period(source_period, source_date_pattern)
        for channel in channels:
            async with semaphore:
                async with self.session_factory() as session:
                    try:
                        # 聚合逻辑：同一频道下的同一词在 source_date_pattern 范围内的总和
                        # 简单实现：SELECT word, SUM(score), SUM(user_count) ...
                        stmt = select(
                            HotPeriodStats.word, 
                            func.sum(HotPeriodStats.score).label("total_score"),
                            func.sum(HotPeriodStats.user_count).label("total_users")
                        ).where(
                            HotPeriodStats.channel == channel,
                            HotPeriodStats.period == source_period,
                            HotPeriodStats.date_key.like(f"{source_date_pattern}%")
                        ).group_by(HotPeriodStats.word)
                        
                        result = await session.execute(stmt)
                        for word, s, u in result.all():
                            new_row = HotPeriodStats(
                                channel=channel,
                                word=word,
                                period=target_period,
                                date_key=target_date_key,
                                score=s,
                                user_count=u
                            )
                            session.add(new_row)
                        await session.commit()
                    except Exception as e:
                        await session.rollback()
                        logger.error(f"Summarize Period Error ({channel}): {e}")
                await asyncio.sleep(0.1)

    async def get_channel_dirs_from_period(self, period: str, date_pattern: str) -> List[str]:
        async with self.session_factory() as session:
            stmt = select(HotPeriodStats.channel).where(
                HotPeriodStats.period == period,
                HotPeriodStats.date_key.like(f"{date_pattern}%")
            ).distinct()
            result = await session.execute(stmt)
            return list(result.scalars().all())

    async def atomic_rename(self, src: Any, dst: Any):
        """废弃：由 move_temp_to_daily 替代"""
        pass
