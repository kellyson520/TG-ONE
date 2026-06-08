import logging
import asyncio
import re
from typing import Dict, List, Any
from sqlalchemy import select, delete, func, text
from sqlalchemy.dialects.sqlite import insert

from core.db_factory import DbFactory
from models.hotword import HotRawStats, HotPeriodStats, HotConfig

logger = logging.getLogger(__name__)

_PERIOD_FILE_RE = re.compile(r"(?:^|_)(day|month|year)_(\d{4,8})(?:\.json)?$")
_PERIOD_DATE_LENGTHS = {
    "day": {8},
    "month": {6},
    "year": {4},
}

class HotwordRepository:
    """
    热词持久化层：使用 hotwords.db (SQLite) 替代原有小文件方案。
    支持高性能 UPSERT 操作与批量聚合。
    """
    
    def __init__(self):
        self.session_factory = DbFactory.get_hotword_session_factory()

    def _parse_period_key(self, filename_or_period: str) -> tuple[str, str]:
        """Parse the trailing period/date token without inspecting channel names."""
        value = str(filename_or_period or "")
        match = _PERIOD_FILE_RE.search(value)
        if match:
            period, date_key = match.groups()
            if len(date_key) in _PERIOD_DATE_LENGTHS[period]:
                return period, date_key

        if value in _PERIOD_DATE_LENGTHS:
            return value, "current"
        return "day", "current"

    def _is_temp_key(self, filename_or_period: str) -> bool:
        """Detect temp ranking keys by suffix only, not by channel name contents."""
        value = str(filename_or_period or "")
        return value in {"_temp", "temp"} or value.endswith("_temp") or value.endswith("_temp.json")

    async def save_temp_counts(self, channel: str, counts: Dict[str, Dict[str, Any]]):
        """
        异步 UPSERT 写入原始统计数据。
        counts 格式: { word: {"f": frequency, "u": user_increment} }
        """
        rows = [
            {
                "channel": channel,
                "word": word,
                "score": meta.get("f", 0.0),
                "unique_users": meta.get("u", 0),
            }
            for word, meta in counts.items()
            if word
        ]
        if not rows:
            return True

        async with self.session_factory() as session:
            try:
                # 采用 SQLite 批量 UPSERT，避免每个词一次 SQL 导致写锁放大。
                stmt = insert(HotRawStats).values(rows)
                excluded = stmt.excluded
                stmt = stmt.on_conflict_do_update(
                    index_elements=['channel', 'word'],
                    set_={
                        "score": HotRawStats.score + excluded.score,
                        "unique_users": HotRawStats.unique_users + excluded.unique_users,
                    }
                )
                await session.execute(stmt)
                await session.commit()
                return True
            except Exception as e:
                await session.rollback()
                logger.error(f"Hotword DB Save Error ({channel}): {e}")
                return False

    async def load_rankings(self, channel: str, filename_or_period: str) -> Dict[str, Any]:
        """
        读取榜单数据。
        为了兼容旧代码，这里解析 filename_or_period。
        如果是 'channel_temp.json' -> 读取 HotRawStats
        如果是 'channel_day_xxx.json' -> 读取 HotPeriodStats
        """
        async with self.session_factory() as session:
            if self._is_temp_key(filename_or_period):
                # 读取实时表
                stmt = select(HotRawStats).where(HotRawStats.channel == channel)
                result = await session.execute(stmt)
                return {r.word: {"f": r.score, "u": r.unique_users} for r in result.scalars()}
            else:
                period, date_key = self._parse_period_key(filename_or_period)
                
                stmt = select(
                    HotPeriodStats.word,
                    func.sum(HotPeriodStats.score).label("score"),
                    func.sum(HotPeriodStats.user_count).label("user_count"),
                ).where(
                    HotPeriodStats.channel == channel,
                    HotPeriodStats.period == period,
                    HotPeriodStats.date_key == date_key
                ).group_by(HotPeriodStats.word)
                result = await session.execute(stmt)
                return {word: {"f": score or 0.0, "u": user_count or 0} for word, score, user_count in result.all()}

    async def get_channel_dirs(self) -> List[str]:
        """获取所有有数据的频道 (DB 版本)"""
        async with self.session_factory() as session:
            stmt = select(HotRawStats.channel).distinct()
            result = await session.execute(stmt)
            channels = set(result.scalars().all())

            stmt = select(HotPeriodStats.channel).distinct()
            result = await session.execute(stmt)
            channels.update(result.scalars().all())

            return sorted(channels)

    async def load_global_day_snapshot(self, date_key: str) -> tuple[Dict[str, Any], Dict[str, List[float]], int]:
        """
        批量读取 global/day 所需的频道分布。

        语义与逐频道 _load_period_data(channel, "day") 保持一致：
        - 有当日归档或 raw 的频道，使用当日归档 + raw。
        - 当日没有数据的频道，回退到该频道最近一次 day 归档。
        """
        async with self.session_factory() as session:
            raw_channels_result = await session.execute(
                select(HotRawStats.channel).where(HotRawStats.channel != "global").distinct()
            )
            period_channels_result = await session.execute(
                select(HotPeriodStats.channel).where(HotPeriodStats.channel != "global").distinct()
            )
            all_channels = set(raw_channels_result.scalars().all())
            all_channels.update(period_channels_result.scalars().all())

            current_result = await session.execute(
                select(
                    HotPeriodStats.channel,
                    HotPeriodStats.word,
                    HotPeriodStats.score,
                    HotPeriodStats.user_count,
                ).where(
                    HotPeriodStats.channel != "global",
                    HotPeriodStats.period == "day",
                    HotPeriodStats.date_key == date_key,
                )
            )
            current_rows = current_result.all()

            raw_result = await session.execute(
                select(
                    HotRawStats.channel,
                    HotRawStats.word,
                    HotRawStats.score,
                    HotRawStats.unique_users,
                ).where(HotRawStats.channel != "global")
            )
            raw_rows = raw_result.all()

            active_channels = {row[0] for row in current_rows}
            active_channels.update(row[0] for row in raw_rows)

            latest_result = await session.execute(
                text(
                    """
                    SELECT h.channel, h.word, h.score, h.user_count
                    FROM hot_period_stats h
                    JOIN (
                        SELECT channel, MAX(date_key) AS latest_date
                        FROM hot_period_stats
                        WHERE channel != 'global' AND period = 'day'
                        GROUP BY channel
                    ) latest
                      ON latest.channel = h.channel
                     AND latest.latest_date = h.date_key
                    WHERE h.channel != 'global' AND h.period = 'day'
                    """
                )
            )
            latest_rows = latest_result.all()

        channel_word_meta: Dict[str, Dict[str, Dict[str, Any]]] = {}

        def _add_row(channel: str, word: str, score: float, user_count: int) -> None:
            stats = channel_word_meta.setdefault(channel, {})
            entry = stats.setdefault(word, {"f": 0.0, "u": 0})
            entry["f"] += float(score or 0.0)
            entry["u"] += int(user_count or 0)

        for channel, word, score, user_count in current_rows:
            _add_row(channel, word, score, user_count)
        for channel, word, score, user_count in raw_rows:
            _add_row(channel, word, score, user_count)
        for channel, word, score, user_count in latest_rows:
            if channel not in active_channels:
                _add_row(channel, word, score, user_count)

        global_word_meta: Dict[str, Dict[str, Any]] = {}
        word_ch_freq: Dict[str, List[float]] = {}
        for ch_data in channel_word_meta.values():
            for word, meta in ch_data.items():
                f = meta["f"]
                word_ch_freq.setdefault(word, []).append(f)
                gm = global_word_meta.setdefault(word, {"f": 0.0, "u": 0})
                gm["f"] += f
                gm["u"] += meta["u"]

        return global_word_meta, word_ch_freq, len(all_channels)

    async def load_period_summary(self, channel: str, period: str, date_prefix: str) -> Dict[str, Any]:
        """按 date_key 前缀聚合周期数据，用于当前月/年实时榜单。"""
        async with self.session_factory() as session:
            stmt = select(
                HotPeriodStats.word,
                func.sum(HotPeriodStats.score).label("score"),
                func.sum(HotPeriodStats.user_count).label("user_count"),
            ).where(
                HotPeriodStats.channel == channel,
                HotPeriodStats.period == period,
                HotPeriodStats.date_key.like(f"{date_prefix}%"),
            ).group_by(HotPeriodStats.word)
            result = await session.execute(stmt)
            return {word: {"f": score or 0.0, "u": user_count or 0} for word, score, user_count in result.all()}

    async def load_latest_period(self, channel: str, period: str) -> Dict[str, Any]:
        """读取指定频道最近一次归档周期，避免当前周期尚未聚合时榜单为空。"""
        async with self.session_factory() as session:
            stmt = (
                select(HotPeriodStats.date_key)
                .where(
                    HotPeriodStats.channel == channel,
                    HotPeriodStats.period == period,
                )
                .order_by(HotPeriodStats.date_key.desc())
                .limit(1)
            )
            result = await session.execute(stmt)
            date_key = result.scalar_one_or_none()

        if not date_key:
            return {}
        return await self.load_period_summary(channel, period, date_key)

    async def load_config(self, name: str) -> Dict[str, float]:
        """从 DB 加载配置项"""
        async with self.session_factory() as session:
            stmt = select(HotConfig).where(HotConfig.name == name)
            result = await session.execute(stmt)
            cfg = result.scalar_one_or_none()
            if not cfg: return {}
            
            data = cfg.data
            if isinstance(data, list):
                return {str(k): 1.0 for k in data}
            
            # 容错处理：处理 {"terms": {"description": "...", "terms": {...}}} 这种结构
            if not isinstance(data, dict):
                return {}

            content = data.get("terms", data)
            if isinstance(content, list):
                return {str(k): 1.0 for k in content}
            if isinstance(content, dict):
                # 优先提取嵌套的 terms 字典，否则使用当前字典
                target = content.get("terms", content) if isinstance(content.get("terms"), dict) else content
                if isinstance(target, list):
                    return {str(k): 1.0 for k in target}
                # 过滤非数值字段 (如 description)
                return {str(k): float(v) for k, v in target.items() if isinstance(v, (int, float, str)) and self._is_float(v) and str(k) != "description"}
            return {}

    def _is_float(self, val):
        try:
            float(val)
            return True
        except (TypeError, ValueError, OverflowError):
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
        async with self.session_factory() as session:
            result = await session.execute(select(HotRawStats.channel).distinct())
            channels = list(result.scalars().all())

        for channel in channels:
            async with semaphore:
                async with self.session_factory() as session:
                    try:
                        # 1. 读取该频道所有 temp 数据。raw 表只保存聚合增量，last_update 是写入时间，
                        #    不是消息发生时间，不能用它做日期分桶。
                        stmt = select(HotRawStats).where(HotRawStats.channel == channel)
                        result = await session.execute(stmt)
                        rows = result.scalars().all()
                        
                        if not rows: continue
                        
                        # 2. 批量 UPSERT 到 period 统计表；重跑或补归档时合并增量，不覆盖已有日榜。
                        archive_rows = [
                            {
                                "channel": channel,
                                "word": row.word,
                                "period": "day",
                                "date_key": date_key,
                                "score": row.score,
                                "user_count": row.unique_users,
                            }
                            for row in rows
                        ]
                        stmt = insert(HotPeriodStats).values(archive_rows)
                        excluded = stmt.excluded
                        stmt = stmt.on_conflict_do_update(
                            index_elements=["channel", "word", "period", "date_key"],
                            set_={
                                "score": HotPeriodStats.score + excluded.score,
                                "user_count": HotPeriodStats.user_count + excluded.user_count,
                            },
                        )
                        await session.execute(stmt)
                        
                        # 3. 只清空已归档的 raw 数据 (原子操作)
                        delete_stmt = delete(HotRawStats).where(HotRawStats.channel == channel)
                        await session.execute(delete_stmt)
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
                        rows = result.all()
                        if not rows:
                            continue

                        await session.execute(
                            delete(HotPeriodStats).where(
                                HotPeriodStats.channel == channel,
                                HotPeriodStats.period == target_period,
                                HotPeriodStats.date_key == target_date_key,
                            )
                        )

                        for word, s, u in rows:
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
