import ctypes
import gc
import platform
import tempfile

import asyncio
import logging
import os
import time
from typing import Callable, Any, Dict, List

# 尝试引入高性能序列化
try:
    import orjson as json
except ImportError:
    import json

from core.config import settings

logger = logging.getLogger(__name__)


class TombstoneManager:
    def __init__(self) -> None:
        self._managed_objects: List[Dict[str, Any]] = []
        self._is_frozen = False
        self._tombstone_path = str(settings.TEMP_DIR / "tombstone_state.bin")
        # ✅ 新增：并发锁，防止同时冻结和复苏
        self._lock = asyncio.Lock()
        # ✅ 新增：冷却时间，防止频繁冻结（例如冻结后至少保持 5 分钟不再次冻结）
        self._last_freeze_time: float = 0.0
        self._freeze_cooldown = 300

        # 创建目录
        os.makedirs(os.path.dirname(self._tombstone_path), exist_ok=True)

        # 加载 libc 以调用 malloc_trim (Linux 专属内存释放神器)
        self._libc = None
        if platform.system() == "Linux":
            try:
                self._libc = ctypes.CDLL("libc.so.6")
            except Exception as e:
                logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')

    def register(
        self, name: str, get_state_func: Callable[[], Any], restore_state_func: Callable[[Any], None]
    ) -> None:
        """注册需要被管理的组件"""
        self._managed_objects.append(
            {"name": name, "get": get_state_func, "restore": restore_state_func}
        )

    def force_release_memory(self) -> None:
        """强制归还系统内存 (核心黑科技)"""
        # 1. Python 层垃圾回收
        gc.collect()
        # 2. C 语言层归还物理内存 (类似 iOS 的压后台行为)
        if self._libc:
            try:
                # malloc_trim(0) 告诉系统把所有未使用的堆内存归还给 OS
                self._libc.malloc_trim(0)
                logger.debug("已执行 malloc_trim 释放物理内存")
            except Exception as e:
                logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')

    def _write_to_disk(self, state_dump: Dict[str, Any]) -> None:
        """同步的磁盘写入逻辑，供线程池调用"""
        dirname = os.path.dirname(self._tombstone_path)
        os.makedirs(dirname, exist_ok=True)

        # 创建临时文件
        fd, temp_path = tempfile.mkstemp(dir=dirname)
        try:
            payload = json.dumps(state_dump)
            if isinstance(payload, str):
                payload = payload.encode("utf-8")

            with os.fdopen(fd, "wb") as f:
                f.write(payload)
            # 原子移动
            os.replace(temp_path, self._tombstone_path)
        except Exception:
            try:
                os.unlink(temp_path)
            except FileNotFoundError:
                logger.debug("墓碑临时文件已不存在，跳过清理: path=%s", temp_path)
            raise

    async def freeze(self) -> None:
        """安全冻结"""
        # ✅ 检查冷却时间
        if time.time() - self._last_freeze_time < self._freeze_cooldown:
            return

        # ✅ 加锁，确保原子操作
        if self._lock.locked():
            return

        async with self._lock:
            if self._is_frozen:
                return

            logger.info("❄️ 触发墓碑机制：正在安全冻结状态...")
            state_dump = {}

            try:
                # 1. 获取状态
                for obj in self._managed_objects:
                    try:
                        data = obj["get"]()
                        if data:
                            state_dump[obj["name"]] = data
                    except Exception as e:
                        logger.error(f"冻结组件 {obj['name']} 失败: {e}")
                        # 如果获取状态失败，中止冻结，防止数据丢失
                        return

                # 2. ✅ 原子写入 (Atomic Write) 使用线程池避免阻塞
                # 先写入临时文件，再重命名，杜绝文件损坏风险
                if state_dump:
                    loop = asyncio.get_running_loop()
                    await loop.run_in_executor(None, self._write_to_disk, state_dump)

                self._is_frozen = True
                self._last_freeze_time = time.time()

                # 3. 释放内存
                del state_dump
                self.force_release_memory()
                logger.info("❄️ 墓碑化完成")

            except Exception as e:
                logger.error(f"❌ 墓碑化严重错误: {e}")
                # 发生错误时，确保不标记为 frozen，避免逻辑死锁
                self._is_frozen = False

    async def resurrect(self) -> None:
        """安全复苏"""
        # ✅ 加锁
        async with self._lock:
            if not self._is_frozen:
                return

            logger.info("🔥 正在从墓碑复苏...")
            try:
                if os.path.exists(self._tombstone_path):
                    with open(self._tombstone_path, "rb") as f:
                        # 增加容错：如果文件损坏，捕获异常
                        try:
                            state_dump = json.loads(f.read())
                        except Exception:
                            logger.error("❌ 墓碑文件损坏，状态丢失！将重置为空状态。")
                            state_dump = {}

                    for obj in self._managed_objects:
                        name = obj["name"]
                        if name in state_dump:
                            try:
                                obj["restore"](state_dump[name])
                            except Exception as e:
                                logger.error(f"复苏组件 {name} 失败: {e}")

                    del state_dump

                self._is_frozen = False
                logger.info("🔥 复苏完成")

            except Exception as e:
                logger.error(f"❌ 复苏失败: {e}")
                # 即使失败也要标记为非冻结，否则程序会卡死在“尝试复苏”的循环里
                self._is_frozen = False


# 全局实例
tombstone = TombstoneManager()
