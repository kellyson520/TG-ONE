import asyncio
import json
import logging
import sys
from pathlib import Path
from typing import Optional, Tuple, Dict
from datetime import datetime

from core.config import settings
from services.system_service import guard_service
from services.update_checker import UpdateCheckerMixin, OFFICIAL_REPO
from services.update_executor import UpdateExecutorMixin, MAX_HTTP_UPDATE_DOWNLOAD_BYTES

logger = logging.getLogger(__name__)

EXIT_CODE_UPDATE = 10


class UpdateService(UpdateCheckerMixin, UpdateExecutorMixin):
    """
    高可靠性联网更新服务 (Advanced UpdateService)
    参考成熟方案：支持网络预检、原子更新、依赖自动同步及回滚保护。
    """

    def __init__(self):
        self._git_available = self._check_git_installed()
        self._is_git_repo = self._git_available and (settings.BASE_DIR / ".git").exists()
        self._stop_event = asyncio.Event()
        self._is_updating = False
        self._state_file = settings.BASE_DIR / "data" / "update_state.json"
        self._bus = None
        self._lifecycle = None
        self._tasksList = []
        self._state_file.parent.mkdir(parents=True, exist_ok=True)

    def set_lifecycle(self, lifecycle):
        self._lifecycle = lifecycle

    def set_bus(self, bus):
        self._bus = bus
        logger.debug("UpdateService 事件总线已注入")

    async def _emit_event(self, name: str, data: dict):
        if self._bus:
            await self._bus.publish(name, data)
        else:
            logger.debug(f"事件总线不可用，事件 {name} 已尝试缓存（尚未实现）")

    def _check_git_installed(self) -> bool:
        import shutil
        return shutil.which("git") is not None

    async def get_current_version(self) -> str:
        if self._is_git_repo:
            try:
                process = await asyncio.create_subprocess_exec(
                    "git", "rev-parse", "--short", "HEAD",
                    cwd=str(settings.BASE_DIR), stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
                )
                out, _ = await process.communicate()
                if process.returncode == 0:
                    sha = out.decode().strip()
                    if sha: return sha
            except Exception as e:
                logger.warning(f"获取 Git 当前版本失败，降级读取状态文件: {e}")
        state = self._get_state()
        return state.get("current_version", "unknown")[:8]

    def _get_state(self) -> Dict:
        if self._state_file.exists():
            try:
                return json.loads(self._state_file.read_text())
            except Exception as e:
                logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
        return {}

    def _save_state(self, state: Dict):
        try:
            self._state_file.write_text(json.dumps(state, indent=4))
        except Exception as e:
            logger.error(f"保存更新状态失败: {e}")

    async def trigger_update(self, target_version: str = "origin/main"):
        try:
            logger.info(f"🛡️ [更新] 正在启动更新序列 (目标: {target_version})...")
            from services.backup_service import backup_service
            code_backup = await backup_service.backup_code(label="update_pre")
            db_backup = await backup_service.backup_db(label="update_pre")
            if code_backup:
                logger.info(f"✅ [更新] 代码备份: {code_backup.name}")
            else:
                logger.warning("⚠️ [更新] 代码备份失败，更新后无法回滚代码")
            if db_backup:
                logger.info(f"✅ [更新] 数据库备份: {db_backup.name}")
            if not self._git_available or not self._is_git_repo:
                logger.warning("⚠️ [更新] 检测到非 Git 环境，将先行执行 HTTP 代码同步...")
                success, msg = await self.perform_update(target_version)
                if not success:
                    raise RuntimeError(f"HTTP 更新同步失败: {msg}")
                logger.info("✅ [更新] HTTP 代码同步完成。")
            state = {
                "status": "processing", "start_time": datetime.now().isoformat(),
                "code_backup": str(code_backup) if code_backup else None,
                "db_backup": str(db_backup) if db_backup else None,
                "version": target_version
            }
            lock_file = settings.BASE_DIR / "data" / "UPDATE_LOCK.json"
            lock_file.parent.mkdir(parents=True, exist_ok=True)
            with open(lock_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            await self._emit_event("SYSTEM_ALERT", {"message": f"🚀 系统更新已触发 (目标: {target_version})，正在准备环境并重启..."})
            if self._lifecycle:
                self._lifecycle.shutdown(EXIT_CODE_UPDATE)
            else:
                sys.exit(EXIT_CODE_UPDATE)
        except SystemExit:
            raise
        except Exception as e:
            logger.error(f"❌ [更新] 准备工作失败: {e}", exc_info=True)
            lock_file = settings.BASE_DIR / "data" / "UPDATE_LOCK.json"
            if lock_file.exists():
                lock_file.unlink()
            raise RuntimeError("更新准备失败")

    async def request_rollback(self):
        try:
            logger.critical("🚑 [更新] 收到手动回滚请求，正在准备环境...")
            state = {"status": "rollback_requested", "start_time": datetime.now().isoformat(), "version": "rollback"}
            lock_file = settings.BASE_DIR / "data" / "UPDATE_LOCK.json"
            lock_file.parent.mkdir(parents=True, exist_ok=True)
            with open(lock_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            await self._emit_event("SYSTEM_ALERT", {"message": "🚑 系统紧急回滚已触发，正在重启恢复..."})
            if self._lifecycle:
                self._lifecycle.shutdown(EXIT_CODE_UPDATE)
            else:
                sys.exit(EXIT_CODE_UPDATE)
        except SystemExit:
            raise
        except Exception as e:
            logger.error(f"❌ [回滚] 请求失败: {e}")
            raise RuntimeError("回滚请求失败")

    async def post_update_bootstrap(self):
        lock_file = settings.BASE_DIR / "data" / "UPDATE_LOCK.json"
        if not lock_file.exists():
            return
        logger.info("🔧 [更新] 检测到未完成的更新。正在执行后置更新任务...")
        try:
            with open(lock_file, "r", encoding="utf-8") as f:
                state = json.load(f)
            logger.info("⚙️ [更新] 正在应用数据库迁移...")
            alembic_ini = settings.BASE_DIR / "alembic.ini"
            if alembic_ini.exists():
                try:
                    process = await asyncio.create_subprocess_exec(
                        "alembic", "upgrade", "head",
                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=str(settings.BASE_DIR)
                    )
                    stdout, stderr = await process.communicate()
                    if process.returncode != 0:
                        err_msg = (stderr or stdout).decode(encoding='utf-8', errors='ignore')
                        logger.error(f"🔥 [更新] 数据库迁移失败 (Code: {process.returncode}):\n{err_msg}")
                        if "already exists" in err_msg.lower() or "table" in err_msg.lower():
                            logger.warning("⚠️ [更新] 检测到表已存在的迁移冲突，尝试自动修复...")
                            fix_script = settings.BASE_DIR / "scripts" / "ops" / "fix_alembic_state.py"
                            if fix_script.exists():
                                try:
                                    fix_process = await asyncio.create_subprocess_exec(
                                        sys.executable, str(fix_script),
                                        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=str(settings.BASE_DIR)
                                    )
                                    fix_stdout, fix_stderr = await fix_process.communicate()
                                    if fix_process.returncode == 0:
                                        logger.info("✅ [更新] Alembic 状态修复成功，重新执行迁移...")
                                        retry_process = await asyncio.create_subprocess_exec(
                                            "alembic", "upgrade", "head",
                                            stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE, cwd=str(settings.BASE_DIR)
                                        )
                                        retry_stdout, retry_stderr = await retry_process.communicate()
                                        if retry_process.returncode == 0:
                                            logger.info("✅ [更新] 数据库迁移成功（修复后重试）。")
                                        else:
                                            retry_err = (retry_stderr or retry_stdout).decode(encoding='utf-8', errors='ignore')
                                            logger.error(f"🔥 [更新] 修复后重试仍失败: {retry_err}")
                                            if state.get("db_backup"):
                                                self._rollback_db(state["db_backup"])
                                    else:
                                        fix_err = (fix_stderr or fix_stdout).decode(encoding='utf-8', errors='ignore')
                                        logger.error(f"❌ [更新] Alembic 状态修复失败: {fix_err}")
                                        if state.get("db_backup"):
                                            self._rollback_db(state["db_backup"])
                                except Exception as fix_e:
                                    logger.error(f"❌ [更新] 执行修复脚本时异常: {fix_e}")
                                    if state.get("db_backup"):
                                        self._rollback_db(state["db_backup"])
                            else:
                                logger.error(f"❌ [更新] 修复脚本不存在: {fix_script}")
                                if state.get("db_backup"):
                                    self._rollback_db(state["db_backup"])
                        else:
                            if state.get("db_backup"):
                                self._rollback_db(state["db_backup"])
                    else:
                        logger.info("✅ [更新] 数据库迁移成功。")
                        health_ok, health_msg = await self._run_system_health_check()
                        if not health_ok:
                            logger.error(f"🚑 [更新] 健康检查失败: {health_msg}")
                        else:
                            logger.info("✅ [更新] 更新后的健康检查已通过。")
                except Exception as e:
                    logger.error(f"🔥 [更新] 执行 Alembic 迁移时发生异常: {e}")
                    if state.get("db_backup"):
                        self._rollback_db(state["db_backup"])
            else:
                logger.warning("⚠️ [更新] 未发现 alembic.ini，跳过数据库迁移。")
        except Exception as e:
            logger.error(f"❌ [更新] 引导任务失败: {e}")
        finally:
            try:
                verify_lock = settings.BASE_DIR / "data" / "UPDATE_VERIFYING.json"
                if lock_file.exists():
                    import shutil
                    shutil.move(str(lock_file), str(verify_lock))
                    logger.info("✅ [更新] 数据库后置引导完成，已切换至稳定性观察模式。")
            except Exception as e:
                logger.error(f"切换更新锁状态失败: {e}")
                if lock_file.exists(): lock_file.unlink()

    def _rollback_db(self, backup_path: str):
        logger.warning(f"⏪ [更新] 正在从备份回滚数据库: {backup_path}...")
        try:
            import shutil
            backup_file = Path(backup_path)
            db_file = Path(settings.DB_PATH)
            if not db_file.is_absolute():
                db_file = settings.BASE_DIR / db_file
            if backup_file.exists():
                shutil.copy2(backup_file, db_file)
                logger.info("✅ [更新] 数据库回滚完成。")
            else:
                logger.error("☠️ [更新] 数据库备份文件丢失！")
        except Exception as e:
            logger.critical(f"☠️ [更新] 严重错误：数据库回滚失败: {e}")

    def _read_external_signal_status(self, lock_file: Path) -> Optional[str]:
        try:
            content = json.loads(lock_file.read_text(encoding='utf-8'))
            return content.get("status")
        except json.JSONDecodeError as e:
            logger.warning(f"外部更新信号文件损坏，已忽略本轮信号: path={lock_file}, error={e}")
        except Exception as e:
            logger.warning(f"读取外部更新信号失败，已忽略本轮信号: path={lock_file}, error={e}")
        return None

    async def start_periodic_check(self):
        from services.exception_handler import exception_handler
        t1 = exception_handler.create_task(self._watch_external_signals(), name="update_signal_watcher")
        self._tasksList.append(t1)
        if not settings.AUTO_UPDATE_ENABLED:
            logger.info("自动更新功能已关闭 (仅响应手动/外部指令)。")
            return
        logger.info(f"自动更新已开启，检查间隔: {settings.UPDATE_CHECK_INTERVAL} 秒")
        t2 = exception_handler.create_task(self._run_periodic_update_check(), name="periodic_update_check")
        self._tasksList.append(t2)

    async def _watch_external_signals(self):
        lock_file = settings.BASE_DIR / "data" / "UPDATE_LOCK.json"
        logger.info("📡 [UpdateService] 外部信号监听器已就绪")
        while not self._stop_event.is_set():
            try:
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=5.0)
                    break
                except asyncio.TimeoutError:
                    logger.debug("外部更新信号等待超时，继续轮询: timeout=5.0s")
                if not lock_file.exists():
                    continue
                try:
                    status = self._read_external_signal_status(lock_file)
                    if status in ["processing", "rollback_requested"]:
                        logger.warning(f"📡 [UpdateService] 检测到外部更新信号 (Status: {status})，正在进行受控重启...")
                        is_closing = False
                        if self._lifecycle and self._lifecycle.stop_event.is_set():
                            is_closing = True
                        if not is_closing:
                            await self._emit_event("SYSTEM_ALERT", {"message": "📡 检测到外部更新指令，系统正在重启以应用变更..."})
                        if self._lifecycle:
                            self._lifecycle.shutdown(EXIT_CODE_UPDATE)
                        else:
                            sys.exit(EXIT_CODE_UPDATE)
                        break
                except SystemExit:
                    raise
                except Exception as e:
                    logger.warning(f"处理外部更新信号失败，已继续监听: path={lock_file}, error={e}")
            except SystemExit:
                raise
            except Exception as e:
                logger.error(f"信号监听异常: {type(e).__name__}: {e}")
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=10.0)
                    break
                except asyncio.TimeoutError:
                    logger.debug("外部更新信号异常退避等待超时，恢复监听: timeout=10.0s")

    async def _run_periodic_update_check(self):
        while not self._stop_event.is_set():
            try:
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=settings.UPDATE_CHECK_INTERVAL)
                    break
                except asyncio.TimeoutError:
                    logger.debug("周期更新检查等待超时，开始本轮检查: timeout=%ss", settings.UPDATE_CHECK_INTERVAL)
                if not await self._check_network():
                    logger.debug("网络连接异常，跳过本次更新检查。")
                    continue
                has_update, remote_ver = await self.check_for_updates(force=False)
                if has_update:
                    logger.info(f"🆕 [更新] 发现新版本 (目标: {remote_ver})，正在启动高可靠执行逻辑...")
                    success, msg = await self.perform_update()
                    if success:
                        logger.info("✅ [更新] 原子同步完成，正在触发智能重启...")
                        guard_service.trigger_restart()
                    else:
                        logger.error(f"❌ [更新] 核心流程失败: {msg}")
            except Exception as e:
                logger.error(f"更新监控运行出错: {e}")
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=3600)
                    break
                except asyncio.TimeoutError:
                    logger.debug("周期更新异常退避等待超时，恢复检查: timeout=3600s")

    async def verify_update_health(self):
        if hasattr(self, "_health_checked_in_this_process"):
            return
        self._health_checked_in_this_process = True
        state = self._get_state()
        status = state.get("status")
        if status == "shell_failed":
            logger.error(f"❌ [更新] Shell 更新失败: {state.get('error')}")
            await self._emit_event("ERROR_SYSTEM", {"module": "Update", "error": state.get("error", "未知 Shell 错误")})
            state["status"] = "failed_processed"
            self._save_state(state)
            return
        if status == "critical_failed":
            logger.critical(f"☠️ [更新] 关键性故障: {state.get('error')}")
            await self._emit_event("ERROR_SYSTEM", {"module": "Update", "error": f"🚨 严重更新事故: {state.get('error', '未知错误')}"})
            state["status"] = "failed_processed"
            self._save_state(state)
            return
        if status == "restarting":
            fail_count = state.get("fail_count", 0) + 1
            state["fail_count"] = fail_count
            if fail_count >= 3:
                logger.critical(f"😱 [警告] 系统在更新后连续 {fail_count} 次启动失败！正在尝试紧急回滚至上个稳定版本...")
                success, msg = await self.rollback()
                if success:
                    state["status"] = "rolled_back"
                    state["fail_count"] = 0
                    self._save_state(state)
                    await self._emit_event("ERROR_SYSTEM", {"module": "Update", "error": f"系统更新后多次启动失败，已触发紧急回滚。"})
                    from services.system_service import guard_service
                    guard_service.trigger_restart()
                return
            self._save_state(state)
            logger.warning(f"⏳ [更新] 系统正处于观察期 (尝试 {fail_count}/3)。若 60s 后仍运行正常将标记更新成功。")
            asyncio.create_task(self._stabilize_after_delay(60))

    async def _stabilize_after_delay(self, seconds: int):
        await asyncio.sleep(seconds)
        state = self._get_state()
        if state.get("status") == "restarting":
            logger.info("💪 [更新] 系统已稳定运行超过 60s，更新验证成功。")
            state["status"] = "stable"
            state["fail_count"] = 0
            self._save_state(state)
            await self._emit_event("SYSTEM_ALERT", {"message": f"🎉 系统已稳定运行，更新任务最终确认完成。当前版本: {state.get('current_version', '未知')}"})

    def stop(self):
        self._stop_event.set()
        for t in self._tasksList:
            if not t.done():
                t.cancel()
        self._tasksList.clear()
        logger.info("UpdateService 任务已清理")


update_service = UpdateService()
