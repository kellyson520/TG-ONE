import shutil
import sqlite3

import logging
import os
import time
from pathlib import Path

# 获取logger
logger = logging.getLogger(__name__)


def _get_session_file(base: str) -> Path:
    p = Path(base)
    if p.suffix == ".session":
        return p
    return p.with_suffix(".session")


def shutil_move_safe(src, dst):
    """安全移动文件，兼容跨设备"""
    try:
        shutil.move(str(src), str(dst))
    except Exception:
        if Path(src).exists():
            Path(src).replace(dst)


def _backup_and_reset(file: Path) -> None:
    try:
        ts = time.strftime("%Y%m%d_%H%M%S")
        backup_dir = file.parent / "backup"
        backup_dir.mkdir(parents=True, exist_ok=True)

        # 修复文件名生成逻辑，避免累加后缀
        # 始终基于原始文件名，防止出现 user.corrupt.backup.corrupt...
        original_stem = file.stem.split(".")[0]
        backup = backup_dir / f"{original_stem}.corrupt_{ts}{file.suffix}"

        if file.exists():
            logger.warning(f"Backing up corrupt session file to {backup}")
            shutil_move_safe(file, backup)

    except Exception as e:
        logger.error(f"Failed to backup session file: {e}")
        try:
            if file.exists():
                file.unlink()
        except Exception:
            pass

    # 清理残留的 journal/wal/shm 文件
    try:
        for ext in ["-journal", "-wal", "-shm"]:
            f = Path(str(file) + ext)
            if f.exists():
                f.unlink(missing_ok=True)
    except Exception:
        pass

    # 确保文件被删除，让 Telethon 重新创建
    try:
        if file.exists():
            file.unlink()
    except Exception:
        pass


def _integrity_ok(conn: sqlite3.Connection) -> bool:
    try:
        # 增加查询超时，防止因短暂锁定导致的误判
        cur = conn.execute("PRAGMA integrity_check")
        row = cur.fetchone()
        return bool(row and str(row[0]).lower() == "ok")
    except sqlite3.OperationalError as e:
        # 关键修复：如果是数据库被锁定，记录日志但不视为损坏
        # 防止因并发访问或上次未干净退出导致的锁文件残留引发重置
        if "locked" in str(e).lower():
            logger.warning(
                f"Database locked during integrity check (skipping reset): {e}"
            )
            return True
        return False
    except Exception as e:
        logger.error(f"Integrity check error: {e}")
        return False


def ensure_session_ok(base: str) -> bool:
    try:
        file = _get_session_file(base)
        file.parent.mkdir(parents=True, exist_ok=True)

        if not file.exists():
            return True

        # 1. 检查文件大小，0字节文件直接删除，视为无效
        if file.stat().st_size == 0:
            logger.warning(
                f"Session file {file} is empty. Removing it to allow recreation."
            )
            file.unlink()
            return True

        # 2. 尝试连接检查
        try:
            # 增加 timeout 参数到 30秒，给数据库解锁留足时间
            conn = sqlite3.connect(str(file), timeout=30)
            try:
                # 启用 WAL 模式有助于减少锁竞争，但这通常由 Telethon 设置
                # 这里只做检查
                if _integrity_ok(conn):
                    return True

                # 3. 尝试 VACUUM INTO 修复
                logger.warning(
                    f"Session file {file} integrity check failed. Attempting repair..."
                )
                backup_dir = file.parent / "backup"
                backup_dir.mkdir(parents=True, exist_ok=True)

                tmp = file.parent / f"{file.stem}.repair{file.suffix}"

                try:
                    conn.execute(f"VACUUM INTO '{tmp.as_posix()}'")
                    conn.close()  # 必须先关闭连接才能操作原文件

                    # 备份原文件到 backup 目录
                    ts = time.strftime("%Y%m%d_%H%M%S")
                    corrupt_backup = (
                        backup_dir / f"{file.stem}.before_repair_{ts}{file.suffix}"
                    )
                    shutil_move_safe(file, corrupt_backup)

                    # 应用修复后的文件
                    shutil_move_safe(tmp, file)
                    logger.info(f"Session file repaired successfully.")
                    return True
                except Exception as e:
                    logger.error(f"VACUUM repair failed: {e}")
                    if tmp.exists():
                        tmp.unlink()
                    # 确保连接关闭
                    try:
                        conn.close()
                    except:
                        pass
            except Exception:
                # 确保 finally 块能执行
                try:
                    conn.close()
                except:
                    pass
                raise  # 抛出异常进入下面的重置流程

        except sqlite3.OperationalError as e:
            logger.error(f"Cannot connect to sqlite db: {e}")
            if "locked" in str(e).lower():
                return True  # 锁定了就不动它

        # 4. 如果以上步骤失败或检查未通过，执行重置
        logger.warning(
            f"Session file {file} is corrupted and cannot be repaired. Resetting."
        )
        _backup_and_reset(file)
        return True

    except Exception as e:
        logger.error(f"Error ensuring session ok: {e}")
        return False


def ensure_sessions_ok(bases: list[str]) -> bool:
    ok = True
    for b in bases:
        if not ensure_session_ok(b):
            ok = False
    return ok
