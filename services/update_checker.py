import asyncio
import logging
import urllib.parse
from typing import Tuple, Optional

from core.config import settings

logger = logging.getLogger(__name__)

OFFICIAL_REPO = "kellyson520/TG-ONE"


def _redact_url(url: str) -> str:
    parsed = urllib.parse.urlsplit(url)
    if not parsed.netloc:
        return url
    netloc = parsed.hostname or ""
    if parsed.port:
        netloc = f"{netloc}:{parsed.port}"
    return urllib.parse.urlunsplit((parsed.scheme, netloc, parsed.path, "", ""))


class UpdateCheckerMixin:
    """版本检查与安全验证相关方法"""

    async def check_for_updates(self, force: bool = False) -> Tuple[bool, str]:
        if not force and not self._is_target_of_gray_release():
            return False, "未命中灰度策略"
        if not self._verify_repo_safety(settings.UPDATE_REMOTE_URL):
            return False, "仓库地址未通过安全验证 (非 HTTPS 或非 GitHub)"
        check_result = False
        check_msg = ""
        remote_sha_candidate = ""
        if self._git_available and self._is_git_repo:
            check_result, check_msg = await self._check_via_git()
            remote_sha_candidate = check_msg if check_result else ""
        else:
            check_result, check_msg = await self._check_via_http()
            remote_sha_candidate = check_msg if check_result else ""
        if check_result and remote_sha_candidate:
            is_valid_sha = await self._cross_verify_sha(remote_sha_candidate)
            if not is_valid_sha:
                logger.critical(f"🚨 [安全阻断] 检测到 SHA 指纹不匹配！远程版本 {remote_sha_candidate} 未在官方仓库 {OFFICIAL_REPO} 验证通过。")
                return False, "安全校验失败：版本指纹与官方源不符"
        return check_result, check_msg

    def _is_target_of_gray_release(self) -> bool:
        if settings.UPDATE_CANARY_PROBABILITY >= 1.0:
            return True
        if settings.UPDATE_CANARY_PROBABILITY <= 0.0:
            return False
        import hashlib
        seed_base = f"update_gray_{settings.USER_ID or 'anon'}"
        seed = hashlib.md5(seed_base.encode()).hexdigest()
        val = int(seed[:8], 16) / 0xFFFFFFFF
        return val <= settings.UPDATE_CANARY_PROBABILITY

    async def _cross_verify_sha(self, sha_short: str, version_ref: Optional[str] = None) -> bool:
        try:
            import httpx
            ref = version_ref or settings.UPDATE_BRANCH
            api_url = f"https://api.github.com/repos/{OFFICIAL_REPO}/commits/{ref}"
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                resp = await client.get(api_url)
                if resp.status_code == 200:
                    official_sha = resp.json().get("sha", "")
                    sha_s = sha_short.strip().lower()
                    official_s = official_sha[:len(sha_s)].strip().lower()
                    if official_s and sha_s == official_s:
                        return True
                    if ref.lower().startswith(sha_s):
                        return True
                    logger.warning(f"交叉验证不一致: 待校验={sha_s}, 官方API结果={official_s} (Ref: {ref})")
                    return False
                else:
                    logger.warning(f"交叉验证跳过: 无法连接官方 API ({resp.status_code})")
                    return True
        except Exception as e:
            logger.warning(f"交叉验证异常: {e}")
            return True

    def _verify_repo_safety(self, url: str) -> bool:
        try:
            parsed = urllib.parse.urlparse(url)
            if parsed.scheme != "https":
                logger.warning("⚠️ [安全警报] 拒绝使用非加密协议更新: %s", _redact_url(url))
                return False
            hostname = parsed.hostname or ""
            if hostname != "github.com":
                logger.warning("⚠️ [安全提示] 更新源非 GitHub 官方域: %s", hostname)
            normalized_url = parsed.path.lstrip("/")
            if normalized_url.endswith(".git"):
                normalized_url = normalized_url[:-4]
            if normalized_url != OFFICIAL_REPO:
                logger.warning("⚠️ [安全提示] 正在使用非官方仓库更新: %s (官方: %s)", _redact_url(url), OFFICIAL_REPO)
            return True
        except Exception as e:
            logger.warning("更新仓库来源校验失败: %s", e)
            return False

    async def _check_via_git(self) -> Tuple[bool, str]:
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "fetch", "--quiet", "origin", settings.UPDATE_BRANCH,
                cwd=str(settings.BASE_DIR), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            try:
                await asyncio.wait_for(process.wait(), timeout=30)
            except asyncio.TimeoutError:
                if process:
                    try:
                        process.kill()
                    except Exception as e:
                        logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
                return False, "网络获取超时"
            check_proc = await asyncio.create_subprocess_exec(
                "git", "rev-list", f"HEAD..origin/{settings.UPDATE_BRANCH}", "--count",
                cwd=str(settings.BASE_DIR), stdout=asyncio.subprocess.PIPE
            )
            out, _ = await check_proc.communicate()
            behind_count = int(out.decode().strip() or 0)
            remot_proc = await asyncio.create_subprocess_exec(
                "git", "rev-parse", f"origin/{settings.UPDATE_BRANCH}",
                cwd=str(settings.BASE_DIR), stdout=asyncio.subprocess.PIPE
            )
            r_out, _ = await remot_proc.communicate()
            remot_id = r_out.decode().strip()
            if behind_count > 0:
                return True, remot_id[:8]
            local_proc = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "HEAD",
                cwd=str(settings.BASE_DIR), stdout=asyncio.subprocess.PIPE
            )
            l_out, _ = await local_proc.communicate()
            return False, l_out.decode().strip()[:8]
        except Exception as e:
            return False, f"Git 检查失败: {e}"

    async def _check_via_http(self) -> Tuple[bool, str]:
        try:
            import httpx
            repo_path = settings.UPDATE_REMOTE_URL.replace("https://github.com/", "").replace(".git", "")
            api_url = f"https://api.github.com/repos/{repo_path}/commits/{settings.UPDATE_BRANCH}"
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(api_url)
                if resp.status_code == 200:
                    remote_sha = resp.json().get("sha", "")
                    local_sha = await self.get_current_version()
                    if remote_sha and remote_sha[:8].lower() != local_sha[:8].lower():
                        return True, remote_sha[:8]
                    return False, local_sha[:8]
                else:
                    return False, f"HTTP 请求失败 ({resp.status_code})"
        except Exception as e:
            return False, f"HTTP 检查异常: {e}"

    async def get_update_history(self, limit: int = 10) -> list[dict]:
        from datetime import datetime
        if not self._is_git_repo:
            current_ver = await self.get_current_version()
            if current_ver != "unknown":
                state = self._get_state()
                return [{"sha": current_ver, "short_sha": current_ver[:8], "author": "System", "timestamp": state.get("timestamp", datetime.now().isoformat()), "message": "Current version (Standard Mode)"}]
            return []
        try:
            process = await asyncio.create_subprocess_exec(
                "git", "log", f"-n", str(limit), "--pretty=format:%H|%an|%at|%s",
                cwd=str(settings.BASE_DIR), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
            )
            out, err = await process.communicate()
            if process.returncode != 0:
                logger.error(f"Git 日志获取失败: {err.decode()}")
                return []
            lines = out.decode('utf-8', errors='ignore').strip().split('\n')
            history = []
            for line in lines:
                if not line or '|' not in line: continue
                parts = line.split('|', 3)
                if len(parts) < 4: continue
                sha, author, timestamp, msg = parts
                history.append({"sha": sha, "short_sha": sha[:8], "author": author, "timestamp": datetime.fromtimestamp(int(timestamp)).isoformat(), "message": msg})
            return history
        except Exception as e:
            logger.error(f"获取更新历史失败: {e}")
            return []

    async def _run_system_health_check(self) -> Tuple[bool, str]:
        try:
            try:
                from repositories.health_check import DatabaseHealthManager
                db_path = settings.DB_DIR / "forward.db"
                manager = DatabaseHealthManager(str(db_path))
                if not manager.check_health():
                    return False, "数据库完整性校验未通过"
            except Exception as e:
                logger.warning("数据库健康检查执行失败，降级为文件存在性检查: %s", e)
                if not (settings.DB_DIR / "forward.db").exists():
                    return False, "数据库文件丢失"
            if not await self._check_network():
                return False, "网络连通性异常"
            if not (settings.BASE_DIR / "main.py").exists():
                return False, "核心文件丢失: main.py"
            return True, "系统运行正常"
        except Exception as e:
            return False, f"健康检查异常: {e}"

    async def _check_network(self) -> bool:
        try:
            import socket
            loop = asyncio.get_running_loop()
            try:
                await loop.run_in_executor(None, lambda: socket.gethostbyname("github.com"))
                return True
            except Exception as e:
                logger.warning("更新网络预检 DNS 解析失败: %s", e)
                return False
        except Exception as e:
            logger.error("更新网络预检执行失败: %s", e, exc_info=True)
            return False
