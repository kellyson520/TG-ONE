import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional, Tuple
from datetime import datetime

from core.config import settings
from services.update_checker import _redact_url

logger = logging.getLogger(__name__)

MAX_HTTP_UPDATE_DOWNLOAD_BYTES = 50 * 1024 * 1024


class UpdateExecutorMixin:
    """更新执行与回滚相关方法"""

    async def perform_update(self, target_version: Optional[str] = None) -> Tuple[bool, str]:
        if self._is_updating:
            return False, "并发锁: 更新已在进行中"
        self._is_updating = True
        try:
            if self._git_available and self._is_git_repo:
                return await self._perform_git_update()
            else:
                return await self._perform_http_update(target_version)
        finally:
            self._is_updating = False

    async def _perform_git_update(self) -> Tuple[bool, str]:
        try:
            current_proc = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "HEAD",
                cwd=str(settings.BASE_DIR), stdout=asyncio.subprocess.PIPE
            )
            c_out, _ = await current_proc.communicate()
            prev_version = c_out.decode().strip()
            req_hash_before = self._get_file_hash(settings.BASE_DIR / "requirements.txt")
            process = await asyncio.create_subprocess_exec(
                "git", "reset", "--hard", f"origin/{settings.UPDATE_BRANCH}",
                cwd=str(settings.BASE_DIR), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            if process.returncode != 0:
                return False, f"Git 同步失败: {stderr.decode()}"
            req_hash_after = self._get_file_hash(settings.BASE_DIR / "requirements.txt")
            if req_hash_before != req_hash_after:
                logger.info("📦 [更新] 检测到依赖文件变更，正在静默同步库...")
                dep_success = await self._sync_dependencies()
                if not dep_success:
                    logger.warning("⚠️ 依赖同步失败，建议手动检查 requirements.txt 以免系统启动失败。")
            new_proc = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "HEAD",
                cwd=str(settings.BASE_DIR), stdout=asyncio.subprocess.PIPE
            )
            n_out, _ = await new_proc.communicate()
            current_id = n_out.decode().strip()
            state = self._get_state()
            state.update({
                "status": "restarting", "prev_version": prev_version,
                "current_version": current_id, "timestamp": datetime.now().isoformat(), "fail_count": 0
            })
            self._save_state(state)
            return True, "Git 代码原子同步完成"
        except Exception as e:
            return False, f"Git 更新执行异常: {e}"

    async def _resolve_http_final_version(self, version: str) -> str:
        try:
            import httpx
            repo_path = settings.UPDATE_REMOTE_URL.replace("https://github.com/", "").replace(".git", "")
            async with httpx.AsyncClient(timeout=5.0) as client:
                r = await client.get(f"https://api.github.com/repos/{repo_path}/commits/{version}")
                if r.status_code == 200:
                    return r.json().get("sha", version)
        except Exception as e:
            logger.warning(f"解析远端 HTTP 更新版本失败，使用请求版本: version={version}, error={e}")
        return version

    async def _perform_http_update(self, target_version: Optional[str] = None) -> Tuple[bool, str]:
        try:
            import httpx
            import zipfile
            import shutil
            import io
            version = target_version or settings.UPDATE_BRANCH
            if version.startswith("origin/"):
                version = version.replace("origin/", "", 1)
            repo_path = settings.UPDATE_REMOTE_URL.replace("https://github.com/", "").replace(".git", "")
            if len(version) >= 7 and all(c in "0123456789abcdef" for c in version.lower()):
                zip_url = f"https://github.com/{repo_path}/archive/{version}.zip"
            else:
                zip_url = f"https://github.com/{repo_path}/archive/refs/heads/{version}.zip"
            if not await self._cross_verify_sha(version[:8], version):
                return False, f"安全校验失败: 版本 {version[:8]} 未在官方仓库验证通过"
            logger.info("正在从 HTTP 下载更新包: %s", _redact_url(zip_url))
            download_timeout = httpx.Timeout(connect=10.0, read=30.0, write=10.0, pool=5.0)
            async with httpx.AsyncClient(timeout=download_timeout, follow_redirects=True) as client:
                async with client.stream("GET", zip_url) as resp:
                    if resp.status_code != 200:
                        return False, f"下载失败 ({resp.status_code})"
                    content_type = resp.headers.get("content-type", "")
                    if "zip" not in content_type and "octet-stream" not in content_type:
                        return False, f"下载内容类型异常: {content_type}"
                    zip_data = io.BytesIO()
                    downloaded = 0
                    async for chunk in resp.aiter_bytes():
                        downloaded += len(chunk)
                        if downloaded > MAX_HTTP_UPDATE_DOWNLOAD_BYTES:
                            return False, "下载文件超过大小限制"
                        zip_data.write(chunk)
                    zip_data.seek(0)
            from services.backup_service import backup_service
            backup_path = await backup_service.backup_code(label="pre_http_update")
            state = self._get_state()
            prev_version = state.get("current_version", "未知")
            with zipfile.ZipFile(zip_data) as z:
                root_dir = z.namelist()[0].split('/')[0]
                for member in z.namelist():
                    if '..' in member or member.startswith('/') or '\\' in member:
                        logger.warning(f"⚠️ [安全拦截] 检测到非法文件路径: {member}")
                        continue
                    if member == root_dir + '/' or not member.startswith(root_dir + '/'):
                        continue
                    filename = member.replace(root_dir + '/', '', 1)
                    if not filename: continue
                    if any(filename.startswith(p) for p in [".env", "data/", "db/", "logs/", "temp/", ".git/"]):
                        continue
                    base_dir = settings.BASE_DIR.resolve()
                    target_path = (base_dir / filename).resolve()
                    try:
                        target_path.relative_to(base_dir)
                    except ValueError:
                        logger.warning(f"⚠️ [安全拦截] 更新文件目标路径越界: {filename}")
                        continue
                    if member.endswith('/'):
                        target_path.mkdir(parents=True, exist_ok=True)
                        continue
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    for i in range(3):
                        try:
                            with z.open(member) as source:
                                with open(target_path, "wb") as f:
                                    shutil.copyfileobj(source, f)
                            break
                        except PermissionError:
                            if i == 2:
                                logger.error(f"无法写入文件 (被占用): {filename}")
                                raise
                            await asyncio.sleep(0.5)
            final_version = await self._resolve_http_final_version(version)
            try:
                state.update({
                    "status": "restarting", "prev_version": prev_version,
                    "backup_file": str(backup_path) if backup_path else None,
                    "current_version": final_version, "timestamp": datetime.now().isoformat(), "fail_count": 0
                })
                self._save_state(state)
            except Exception as e:
                logger.error(f"保存更新状态失败: {e}")
            return True, f"HTTP 增量更新同步完成 (Version: {final_version[:8]})"
        except Exception as e:
            return False, f"HTTP 更新异常: {e}"
        finally:
            self._is_updating = False

    def _get_file_hash(self, path: Path) -> str:
        if not path.exists():
            return ""
        import hashlib
        try:
            return hashlib.md5(path.read_bytes()).hexdigest()
        except Exception:
            return ""

    async def _sync_dependencies(self) -> bool:
        try:
            cmd = ["uv", "pip", "install", "--python", sys.executable, "-r", "requirements.txt"]
            process = await asyncio.create_subprocess_exec(
                *cmd, cwd=str(settings.BASE_DIR),
                stdout=asyncio.subprocess.DEVNULL, stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            return process.returncode == 0
        except Exception:
            return False

    async def rollback(self) -> Tuple[bool, str]:
        state = self._get_state()
        from services.backup_service import backup_service
        if self._git_available and self._is_git_repo:
            prev = state.get("prev_version")
            if not prev:
                return False, "未找到有效的 Git 版本记录"
            logger.critical(f"🚑 [回滚] Git Reset 至: {prev[:8]}...")
            process = await asyncio.create_subprocess_exec(
                "git", "reset", "--hard", prev, cwd=str(settings.BASE_DIR)
            )
            await process.wait()
            if process.returncode == 0:
                for f in ["UPDATE_LOCK.json", "UPDATE_VERIFYING.json"]:
                    lock_f = settings.BASE_DIR / "data" / f
                    if lock_f.exists(): lock_f.unlink()
            return process.returncode == 0, f"Git 回滚至 {prev[:8]}"
        else:
            code_backup = state.get("code_backup")
            if not code_backup:
                return False, "未找到可用的代码备份文件"
            logger.critical(f"🚑 [回滚] 正在还原代码: {Path(code_backup).name}...")
            success, msg = await backup_service.restore(code_backup)
            if success:
                for f in ["UPDATE_LOCK.json", "UPDATE_VERIFYING.json"]:
                    lock_f = settings.BASE_DIR / "data" / f
                    if lock_f.exists(): lock_f.unlink()
            return success, msg

    async def list_local_backups(self) -> list[dict]:
        from services.backup_service import backup_service
        return await backup_service.list_backups()

    async def restore_from_backup(self, backup_path: str) -> Tuple[bool, str]:
        from services.backup_service import backup_service
        return await backup_service.restore(backup_path)
