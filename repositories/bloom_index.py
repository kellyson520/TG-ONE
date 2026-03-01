import glob
import hashlib
import mmap
import threading

import duckdb
import logging
import os
import time
from typing import Any, Dict, List, Optional, Tuple

try:
    import xxhash

    _HAS_XXHASH = True
except ImportError:
    _HAS_XXHASH = False

logger = logging.getLogger(__name__)


from core.config import settings

# 全局配置映射
BLOOM_ROOT = str(settings.BLOOM_ROOT)
BLOOM_BITS = settings.BLOOM_BITS
BLOOM_HASHES = settings.BLOOM_HASHES
BLOOM_SHARD_BY = settings.BLOOM_SHARD_BY

_CACHE_MAX_ENTRIES = settings.BLOOM_CACHE_MAX_ENTRIES
_CACHE_TTL_SEC = settings.BLOOM_CACHE_TTL_SEC


def _ensure_dir(path: str) -> None:
    """确保目录存在，如果创建失败则记录错误"""
    try:
        os.makedirs(path, exist_ok=True)
        logger.debug(f"确保目录存在: {path}")
    except Exception as e:
        logger.error(f"创建目录失败 {path}: {e}")
        logger.debug("创建目录失败详细信息", exc_info=True)
        raise


def _bitfile_path(table: str, shard_key: str) -> str:
    safe = str(shard_key).replace(os.sep, "_")
    return os.path.join(BLOOM_ROOT, table, f"{safe}.bf")


def _hashes(value: str, k: int, m: int) -> List[int]:
    # ✅ 优化方案：使用 xxHash + Double Hashing
    if _HAS_XXHASH:
        data = value.encode("utf-8", errors="ignore")
        # 计算两个基础哈希 (64bit)
        h1 = xxhash.xxh64(data, seed=0).intdigest()
        h2 = xxhash.xxh64(data, seed=1).intdigest()

        positions = []
        for i in range(k):
            # Double Hashing 公式
            pos = (h1 + i * h2) % m
            positions.append(pos)
        return positions

    # ❌ 原有回退逻辑 (保留用于未安装 xxhash 的情况)
    positions: List[int] = []
    v = value.encode("utf-8", errors="ignore")
    for i in range(k):
        h = hashlib.sha256(v + str(i).encode()).digest()
        # 取前8字节为整数
        n = int.from_bytes(h[:8], "big")
        positions.append(n % m)
    return positions


class BloomIndex:
    def __init__(
        self,
        root: Optional[str] = None,
        bits: Optional[int] = None,
        hashes: Optional[int] = None,
        shard_by: Optional[str] = None,
    ):
        self.root = root or BLOOM_ROOT
        self.bits = bits or BLOOM_BITS
        self.hashes = hashes or BLOOM_HASHES
        self.shard_by = (shard_by or BLOOM_SHARD_BY).lower()
        # 简单 LRU/TTL 缓存：path -> (bits, mtime, last_access_epoch)
        self._cache: Dict[str, Tuple[bytearray, float, float]] = {}
        self._cache_lock = threading.RLock()  # 保护缓存并发访问
        logger.debug(
            f"BloomIndex 初始化: root={self.root}, bits={self.bits}, hashes={self.hashes}, shard_by={self.shard_by}"
        )

    def _prune_cache(self) -> None:
        with self._cache_lock:
            if len(self._cache) <= _CACHE_MAX_ENTRIES:
                return
            # 以 last_access 排序，淘汰最久未使用的一半
            items = sorted(self._cache.items(), key=lambda kv: kv[1][2])
            prune_count = max(1, len(items) // 2)
            logger.debug(
                f"缓存条目数 {len(self._cache)} 超过最大值 {_CACHE_MAX_ENTRIES}，淘汰 {prune_count} 个最旧条目"
            )
            for path, _ in items[:prune_count]:
                self._cache.pop(path, None)

    # Removed _get_mmap as it leaks fd and causes SIGBUS. Inlined into add_values.

    def _load_bitarray(self, table: str, shard_key: str) -> bytearray:
        path = _bitfile_path(table, shard_key)
        logger.debug(f"加载位数组: table={table}, shard_key={shard_key}, path={path}")
        _ensure_dir(os.path.dirname(path))
        bytes_len = (self.bits + 7) // 8

        # 缓存命中且未过期、且底层文件未变化
        now = time.time()
        with self._cache_lock:
            cache_item = self._cache.get(path)
        try:
            file_mtime = os.path.getmtime(path)
            file_exists = True
            logger.debug(f"文件存在，修改时间: {file_mtime}")
        except Exception as e:
            file_mtime = 0.0
            file_exists = False
            logger.debug(f"文件不存在或获取修改时间失败: {e}")

        if cache_item is not None:
            data, cached_mtime, _last_access = cache_item
            logger.debug(
                f"缓存命中: cached_mtime={cached_mtime}, now-last_access={now - _last_access}, file_exists={file_exists}, file_mtime={file_mtime}"
            )
            if (now - _last_access) <= _CACHE_TTL_SEC and (
                not file_exists or cached_mtime == file_mtime
            ):
                # 刷新 last_access
                with self._cache_lock:
                    self._cache[path] = (data, cached_mtime, now)
                logger.debug("使用缓存数据")
                return data

        # 磁盘加载或创建新位图
        if file_exists:
            try:
                logger.debug("从磁盘加载位图")
                with open(path, "rb") as f:
                    data = bytearray(f.read())
                if len(data) < bytes_len:
                    logger.debug(f"文件大小 {len(data)} 小于预期 {bytes_len}，扩展")
                    data.extend(b"\x00" * (bytes_len - len(data)))
                elif len(data) > bytes_len:
                    logger.debug(f"文件大小 {len(data)} 大于预期 {bytes_len}，截断")
                    data = data[:bytes_len]
            except Exception as e:
                logger.error(f"加载位图文件失败: {e}")
                logger.debug("加载位图文件失败详细信息", exc_info=True)
                data = bytearray(bytes_len)
        else:
            logger.debug("文件不存在，创建新的位图")
            data = bytearray(bytes_len)

        # 写入缓存并做容量控制
        with self._cache_lock:
            self._cache[path] = (data, file_mtime, now)
        self._prune_cache()
        logger.debug(f"位数组加载完成，大小: {len(data)}")
        return data

    def _save_bitarray(self, table: str, shard_key: str, bits: bytearray) -> None:
        path = _bitfile_path(table, shard_key)
        logger.debug(
            f"保存位数组: table={table}, shard_key={shard_key}, path={path}, size={len(bits)}"
        )
        _ensure_dir(os.path.dirname(path))
        try:
            with open(path, "wb") as f:
                f.write(bits)
            logger.debug("位数组保存完成")
        except Exception as e:
            logger.error(f"保存位数组文件失败: {e}")
            logger.debug("保存位数组文件失败详细信息", exc_info=True)
            raise
        try:
            mtime = os.path.getmtime(path)
        except Exception as e:
            logger.warning(f"获取文件修改时间失败: {e}")
            logger.debug("获取文件修改时间失败详细信息", exc_info=True)
            mtime = 0.0
        # 同步缓存
        with self._cache_lock:
            self._cache[path] = (bits, mtime, time.time())
        logger.debug("缓存同步完成")

    def _set_bit(self, bits: bytearray, pos: int) -> None:
        byte_index = pos // 8
        bit_index = pos % 8
        old_value = bits[byte_index]
        bits[byte_index] |= 1 << bit_index
        logger.debug(
            f"设置位: pos={pos}, byte_index={byte_index}, bit_index={bit_index}, old_value={old_value:08b}, new_value={bits[byte_index]:08b}"
        )

    def _get_bit(self, bits: bytearray, pos: int) -> bool:
        byte_index = pos // 8
        bit_index = pos % 8
        result = (bits[byte_index] >> bit_index) & 1 == 1
        logger.debug(
            f"获取位: pos={pos}, byte_index={byte_index}, bit_index={bit_index}, value={result}"
        )
        return result

    def _shard(self, row: Dict[str, Any]) -> str:
        if self.shard_by == "chat":
            result = str(row.get("chat_id", "global"))
        else:
            result = "global"
        logger.debug(f"分片: row={row}, result={result}")
        return result

    def add_values(self, table: str, shard_key: str, values: List[str]) -> None:
        logger.debug(
            f"添加值: table={table}, shard_key={shard_key}, values_count={len(values)}"
        )
        
        path = _bitfile_path(table, shard_key)
        _ensure_dir(os.path.dirname(path))
        bytes_len = (self.bits + 7) // 8

        # 确保文件存在且被填满，避免稀疏文件和阶段性为 0 引发 SIGBUS
        if not os.path.exists(path) or os.path.getsize(path) < bytes_len:
            logger.debug(f"文件不存在或大小不足，追加真实零数据: size={bytes_len}")
            # 使用 ab 追加，避免并发时 wb 截断导致另一个线程由于超出文件范围而 SIGBUS
            with open(path, "ab") as f:
                current_size = f.tell()
                if current_size < bytes_len:
                    f.write(b"\x00" * (bytes_len - current_size))

        # 使用 mmap 直接操作文件，使用上下文管理器确保 fd 闭环，防泄漏
        changed = False
        with open(path, "r+b") as f:
            with mmap.mmap(f.fileno(), 0) as mm:
                for val in values:
                    if not val:
                        continue
                    logger.debug(f"处理值: {val}")
                    for pos in _hashes(str(val), self.hashes, self.bits):
                        byte_index = pos // 8
                        bit_index = pos % 8
                        # 读取当前字节值
                        current_byte = mm[byte_index]
                        # 检查位是否已设置
                        if not (current_byte & (1 << bit_index)):
                            # 设置位
                            mm[byte_index] = current_byte | (1 << bit_index)
                            changed = True
                            logger.debug(
                                f"设置位: pos={pos}, byte_index={byte_index}, bit_index={bit_index}, old_value={current_byte:08b}, new_value={mm[byte_index]:08b}"
                            )

        if changed:
            logger.debug("位数组已更新，mmap 自动回写")
        else:
            logger.debug("位数组未发生变化")

        # 清除缓存，确保下次读取时获取最新数据
        path = _bitfile_path(table, shard_key)
        with self._cache_lock:
            self._cache.pop(path, None)
        logger.debug("缓存已清除，确保数据一致性")

    def add_batch(
        self, table: str, rows: List[Dict[str, Any]], fields: List[str]
    ) -> None:
        logger.debug(
            f"批量添加: table={table}, rows_count={len(rows)}, fields={fields}"
        )
        # 分 shard 批量添加
        grouped: Dict[str, List[str]] = {}
        for r in rows:
            shard = self._shard(r)
            for f in fields:
                v = r.get(f)
                if v:
                    grouped.setdefault(shard, []).append(str(v))
        logger.debug(f"分组完成: shards_count={len(grouped)}")
        for shard_key, values in grouped.items():
            self.add_values(table, shard_key, values)

    def probably_contains(self, table: str, shard_key: str, value: str) -> bool:
        path = _bitfile_path(table, shard_key)
        logger.debug(
            f"Bloom索引检查开始: table={table}, shard_key={shard_key}, value={value}, path={path}"
        )
        if not os.path.exists(path):
            logger.debug("Bloom索引文件不存在，检查结果: False")
            return False
        bits = self._load_bitarray(table, shard_key)
        logger.debug(f"加载位数组完成，大小: {len(bits)}")
        for pos in _hashes(str(value), self.hashes, self.bits):
            if not self._get_bit(bits, pos):
                logger.debug(f"Bloom索引检查结果: False (在位置 {pos} 未找到匹配位)")
                return False
        logger.debug("Bloom索引检查结果: True (所有哈希位都匹配)")
        return True

    # ==== 归档重建（媒体签名表）====
    def rebuild_media_signatures(self, archive_root: Optional[str] = None) -> int:
        """从 Parquet 归档重建 media_signatures 的 Bloom 索引。
        返回写入的条目计数（估算）。
        """
        root = archive_root or str(settings.ARCHIVE_ROOT)
        logger.debug(f"重建媒体签名 Bloom 索引: archive_root={root}")
        pattern = os.path.join(
            root, "media_signatures", "year=*", "month=*", "*.parquet"
        )
        logger.debug(f"文件模式: {pattern}")
        files = glob.glob(pattern)
        logger.debug(f"找到 {len(files)} 个文件")
        if not files:
            logger.debug("未找到任何文件")
            return 0
        count = 0
        con = duckdb.connect(database=":memory:")
        try:
            # 分批读取，避免占用过多内存
            # 注意：按文件逐个处理
            for fp in files:
                try:
                    logger.debug(f"处理文件: {fp}")
                    cur = con.execute(
                        "SELECT chat_id, signature, content_hash FROM read_parquet(?) WHERE signature IS NOT NULL OR content_hash IS NOT NULL",
                        [fp],
                    )
                    rows = cur.fetchall()
                    logger.debug(f"查询结果: {len(rows)} 行")
                    if not rows:
                        continue
                    # 组装行格式，复用 add_batch
                    payload: List[Dict[str, Any]] = []
                    for chat_id, signature, content_hash in rows:
                        payload.append(
                            {
                                "chat_id": str(chat_id),
                                "signature": signature,
                                "content_hash": content_hash,
                            }
                        )
                    self.add_batch(
                        "media_signatures", payload, ["signature", "content_hash"]
                    )
                    count += len(rows)
                    logger.debug(f"处理完成，累计处理 {count} 行")
                except Exception as e:
                    logger.error(f"处理文件失败 {fp}: {e}")
                    logger.debug("处理文件失败详细信息", exc_info=True)
                    continue
        finally:
            logger.debug("关闭 DuckDB 连接")
            con.close()
        logger.debug(f"重建完成，总共处理 {count} 行")
        return count


# 全局实例
bloom = BloomIndex()
