import asyncio
import logging
import os
import subprocess
import sys
import json
import urllib.parse
from pathlib import Path
from typing import Optional, Tuple, Dict
from datetime import datetime

from core.config import settings
from services.system_service import guard_service
from core.container import container

logger = logging.getLogger(__name__)

# 官方认证的仓库地址
OFFICIAL_REPO = "kellyson520/TG-ONE"

# 退出码约定
EXIT_CODE_UPDATE = 10  # 请求系统级更新

class UpdateService:
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
        self._tasksList = []  # 管理本服务启动的任务
        
        # 确保数据目录存在
        self._state_file.parent.mkdir(parents=True, exist_ok=True)

    def set_bus(self, bus):
        """注入事件总线"""
        self._bus = bus
        logger.debug("UpdateService 事件总线已注入")

    async def _emit_event(self, name: str, data: dict):
        """触发系统事件"""
        if self._bus:
            await self._bus.publish(name, data)
        else:
            logger.debug(f"事件总线不可用，事件 {name} 已尝试缓存（尚未实现）")

    def _check_git_installed(self) -> bool:
        """检查系统环境中是否安装了 Git"""
        import shutil
        return shutil.which("git") is not None

    async def get_current_version(self) -> str:
        """获取当前系统版本 (Git SHA -> VERSION 文件 -> 状态文件)"""
        if self._is_git_repo:
            try:
                process = await asyncio.create_subprocess_exec(
                    "git", "rev-parse", "--short", "HEAD",
                    cwd=str(settings.BASE_DIR),
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                out, _ = await process.communicate()
                if process.returncode == 0:
                    sha = out.decode().strip()
                    if sha: return sha
            except Exception:
                pass
        
        # 2. 从状态文件读取 (Non-Git Fallback)
        state = self._get_state()
        return state.get("current_version", "unknown")[:8]

    def _get_state(self) -> Dict:
        """从状态文件读取更新历史"""
        if self._state_file.exists():
            try:
                return json.loads(self._state_file.read_text())
            except Exception as e:
                logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')
        return {}

    def _save_state(self, state: Dict):
        """保存更新状态"""
        try:
            self._state_file.write_text(json.dumps(state, indent=4))
        except Exception as e:
            logger.error(f"保存更新状态失败: {e}")

    async def _check_network(self) -> bool:
        """网络预检 (测试 GitHub 连通性)"""
        try:
            import socket
            loop = asyncio.get_running_loop()
            try:
                # 尝试解析地址，测试 DNS 和基础网络
                await loop.run_in_executor(None, lambda: socket.gethostbyname("github.com"))
                return True
            except Exception:
                return False
        except Exception:
            return False

    async def trigger_update(self, target_version: str = "origin/main"):
        """
        [阶段1] 触发更新：分别备份代码+DB -> 写锁 -> 退出进程
        这是工业级双层状态机的第一阶段，由 Python 层执行
        target_version: 可以是 commit SHA, branch name 或 tag
        """
        try:
            logger.info(f"🛡️ [更新] 正在启动更新序列 (目标: {target_version})...")
            
            # 1. 分别备份代码和数据库 (互不影响)
            from .backup_service import backup_service
            code_backup = await backup_service.backup_code(label="update_pre")
            db_backup = await backup_service.backup_db(label="update_pre")
            
            if code_backup:
                logger.info(f"✅ [更新] 代码备份: {code_backup.name}")
            else:
                logger.warning("⚠️ [更新] 代码备份失败，更新后无法回滚代码")
            if db_backup:
                logger.info(f"✅ [更新] 数据库备份: {db_backup.name}")

            # 2. 如果非 Git 环境，先行通过 Python 下载代码
            if not self._git_available or not self._is_git_repo:
                logger.warning("⚠️ [更新] 检测到非 Git 环境，将先行执行 HTTP 代码同步...")
                success, msg = await self.perform_update(target_version)
                if not success:
                    raise RuntimeError(f"HTTP 更新同步失败: {msg}")
                logger.info("✅ [更新] HTTP 代码同步完成。")

            # 3. 写入状态锁 (供 entrypoint.sh 识别)
            state = {
                "status": "processing",
                "start_time": datetime.now().isoformat(),
                "code_backup": str(code_backup) if code_backup else None,
                "db_backup": str(db_backup) if db_backup else None,
                "version": target_version
            }
            
            lock_file = settings.BASE_DIR / "data" / "UPDATE_LOCK.json"
            lock_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(lock_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
            
            await self._emit_event("SYSTEM_ALERT", {"message": f"🚀 系统更新已触发 (目标: {target_version})，正在准备环境并重启..."})
            
            # 4. 退出进程，移交控制权给 entrypoint.sh
            if container.lifecycle:
                container.lifecycle.shutdown(EXIT_CODE_UPDATE)
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
        """
        请求紧急回滚。
        设置锁文件状态为 rollback_requested 并退出，由守护进程接管执行回滚。
        """
        try:
            logger.critical("🚑 [更新] 收到手动回滚请求，正在准备环境...")
            
            # 写锁
            state = {
                "status": "rollback_requested",
                "start_time": datetime.now().isoformat(),
                "version": "rollback"
            }
            lock_file = settings.BASE_DIR / "data" / "UPDATE_LOCK.json"
            lock_file.parent.mkdir(parents=True, exist_ok=True)
            
            with open(lock_file, "w", encoding="utf-8") as f:
                json.dump(state, f, indent=2)
                
            await self._emit_event("SYSTEM_ALERT", {"message": "🚑 系统紧急回滚已触发，正在重启恢复..."})
            if container.lifecycle:
                container.lifecycle.shutdown(EXIT_CODE_UPDATE)
            else:
                sys.exit(EXIT_CODE_UPDATE)
        except SystemExit:
            raise
        except Exception as e:
            logger.error(f"❌ [回滚] 请求失败: {e}")
            raise RuntimeError("回滚请求失败")

    async def post_update_bootstrap(self):
        """
        [阶段2] 启动引导：检查锁 -> DB迁移 -> 清理锁
        """
        lock_file = settings.BASE_DIR / "data" / "UPDATE_LOCK.json"
        if not lock_file.exists():
            return

        logger.info("🔧 [更新] 检测到未完成的更新。正在执行后置更新任务...")
        try:
            with open(lock_file, "r", encoding="utf-8") as f:
                state = json.load(f)

            logger.info("⚙️ [更新] 正在应用数据库迁移...")
            alembic_ini = settings.BASE_DIR / "alembic.ini"
            alembic_dir = settings.BASE_DIR / "alembic"
            if alembic_ini.exists():
                try:
                    process = await asyncio.create_subprocess_exec(
                        "alembic", "upgrade", "head",
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE,
                        cwd=str(settings.BASE_DIR)
                    )
                    stdout, stderr = await process.communicate()
                    
                    if process.returncode != 0:
                        err_msg = (stderr or stdout).decode(encoding='utf-8', errors='ignore')
                        logger.error(f"🔥 [更新] 数据库迁移失败 (Code: {process.returncode}):\n{err_msg}")
                        
                        # 检测是否为"表已存在"错误
                        if "already exists" in err_msg.lower() or "table" in err_msg.lower():
                            logger.warning("⚠️ [更新] 检测到表已存在的迁移冲突，尝试自动修复...")
                            
                            # 运行修复脚本
                            fix_script = settings.BASE_DIR / "scripts" / "ops" / "fix_alembic_state.py"
                            if fix_script.exists():
                                try:
                                    fix_process = await asyncio.create_subprocess_exec(
                                        sys.executable, str(fix_script),
                                        stdout=asyncio.subprocess.PIPE,
                                        stderr=asyncio.subprocess.PIPE,
                                        cwd=str(settings.BASE_DIR)
                                    )
                                    fix_stdout, fix_stderr = await fix_process.communicate()
                                    
                                    if fix_process.returncode == 0:
                                        logger.info("✅ [更新] Alembic 状态修复成功，重新执行迁移...")
                                        
                                        # 重试迁移
                                        retry_process = await asyncio.create_subprocess_exec(
                                            "alembic", "upgrade", "head",
                                            stdout=asyncio.subprocess.PIPE,
                                            stderr=asyncio.subprocess.PIPE,
                                            cwd=str(settings.BASE_DIR)
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
                            # 非"表已存在"错误，直接回滚
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
        """回滚数据库到 .bak 备份"""
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

    async def start_periodic_check(self):
        """启动更新检查服务"""
        # 启动时无需再次验证健康度，main.py 已经执行过一次。
        # await self.verify_update_health()

        # 1. 始终启动: 外部信号监听
        from services.exception_handler import exception_handler
        t1 = exception_handler.create_task(self._watch_external_signals(), name="update_signal_watcher")
        self._tasksList.append(t1)

        # 2. 条件启动: 自动更新检查
        if not settings.AUTO_UPDATE_ENABLED:
            logger.info("自动更新功能已关闭 (仅响应手动/外部指令)。")
            return

        logger.info(f"自动更新已开启，检查间隔: {settings.UPDATE_CHECK_INTERVAL} 秒")
        # 启动周期性检查循环
        t2 = exception_handler.create_task(self._run_periodic_update_check(), name="periodic_update_check")
        self._tasksList.append(t2)

    async def _watch_external_signals(self):
        """监听外部更新信号 (UPDATE_LOCK.json)"""
        lock_file = settings.BASE_DIR / "data" / "UPDATE_LOCK.json"
        logger.info("📡 [UpdateService] 外部信号监听器已就绪")
        
        while not self._stop_event.is_set():
            try:
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=5.0)
                    break 
                except asyncio.TimeoutError:
                    pass

                if not lock_file.exists():
                    continue

                try:
                    content = json.loads(lock_file.read_text(encoding='utf-8'))
                    status = content.get("status")
                    
                    if status in ["processing", "rollback_requested"]:
                        logger.warning(f"📡 [UpdateService] 检测到外部更新信号 (Status: {status})，正在进行受控重启...")
                        
                        # 如果系统已经在关闭流程中，我们只尝试更新退出码，不再发送事件（防止 EventBus 关闭导致的挂起）
                        is_closing = False
                        if container.lifecycle and container.lifecycle.stop_event.is_set():
                            is_closing = True
                            
                        if not is_closing:
                            await self._emit_event("SYSTEM_ALERT", {"message": "📡 检测到外部更新指令，系统正在重启以应用变更..."})
                        
                        if container.lifecycle:
                            container.lifecycle.shutdown(EXIT_CODE_UPDATE)
                        else:
                            sys.exit(EXIT_CODE_UPDATE)
                       
                        # 立即退出监听循环
                        break
                        
                except json.JSONDecodeError:
                    pass
                except SystemExit:
                    raise
                except Exception:
                    pass

            except SystemExit:
                raise
            except Exception as e:
                logger.error(f"信号监听异常: {type(e).__name__}: {e}")
                # Backoff with interruptibility
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=10.0)
                    break
                except asyncio.TimeoutError:
                    pass

    async def _run_periodic_update_check(self):
        """执行周期性自动更新检查"""
        while not self._stop_event.is_set():
            try:
                try:
                    await asyncio.wait_for(self._stop_event.wait(), timeout=settings.UPDATE_CHECK_INTERVAL)
                    break  # Stop signaled
                except asyncio.TimeoutError:
                    pass   # Timeout, continue check

                # 网络检查，不通则跳过本次循环
                if not await self._check_network():
                    logger.debug("网络连接异常，跳过本次更新检查。")
                    continue

                has_update, remote_ver = await self.check_for_updates(force=False)
                if has_update:
                    logger.info(f"🆕 [更新] 发现新版本 (目标: {remote_ver})，正在启动高可靠执行逻辑...")
                    # 注意: 这里调用 perform_update 会直接下载代码并覆盖，
                    # 成功后 guard_service.trigger_restart() 会重启。
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
                    pass

    async def verify_update_health(self):
        """
        验证更新后的系统健康状况。
        如果系统启动后在短时间内崩溃，下次启动会检测并处理连续失败。
        (已增加进程级防抖，确保单词启动回路仅计数一次)
        """
        if hasattr(self, "_health_checked_in_this_process"):
            return
        self._health_checked_in_this_process = True

        state = self._get_state()
        status = state.get("status")
        
        if status == "shell_failed":
            logger.error(f"❌ [更新] Shell 更新失败: {state.get('error')}")
            await self._emit_event("ERROR_SYSTEM", {"module": "Update", "error": state.get("error", "未知 Shell 错误")})
            # 处理完后重置状态，防止重复通知
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
            # 增加失败计数
            fail_count = state.get("fail_count", 0) + 1
            state["fail_count"] = fail_count
            
            if fail_count >= 3:
                logger.critical(f"😱 [警告] 系统在更新后连续 {fail_count} 次启动失败！正在尝试紧急回滚至上个稳定版本...")
                success, msg = await self.rollback()
                if success:
                    # 回滚后重置状态并再次重启
                    state["status"] = "rolled_back"
                    state["fail_count"] = 0
                    self._save_state(state)
                    await self._emit_event("ERROR_SYSTEM", {"module": "Update", "error": f"系统更新后多次启动失败，已触发紧急回滚。"})
                    
                    from services.system_service import guard_service
                    guard_service.trigger_restart()
                return

            self._save_state(state)
            logger.warning(f"⏳ [更新] 系统正处于观察期 (尝试 {fail_count}/3)。若 60s 后仍运行正常将标记更新成功。")
            
            # 异步观察，如果系统坚持运行，则标记为稳定
            asyncio.create_task(self._stabilize_after_delay(60))

    async def _stabilize_after_delay(self, seconds: int):
        """延迟标记系统为稳定状态"""
        await asyncio.sleep(seconds)
        state = self._get_state()
        if state.get("status") == "restarting":
            logger.info("💪 [更新] 系统已稳定运行超过 60s，更新验证成功。")
            state["status"] = "stable"
            state["fail_count"] = 0
            self._save_state(state)
            await self._emit_event("SYSTEM_ALERT", {"message": f"🎉 系统已稳定运行，更新任务最终确认完成。当前版本: {state.get('current_version', '未知')}"})

    async def get_update_history(self, limit: int = 10) -> list[dict]:
        """获取更新历史 (Git commits)"""
        if not self._is_git_repo:
            current_ver = await self.get_current_version()
            if current_ver != "unknown":
                state = self._get_state()
                return [{
                    "sha": current_ver,
                    "short_sha": current_ver[:8],
                    "author": "System",
                    "timestamp": state.get("timestamp", datetime.now().isoformat()),
                    "message": "Current version (Standard Mode)"
                }]
            return []
        
        try:
            # 使用 git log 获取历史
            process = await asyncio.create_subprocess_exec(
                "git", "log", f"-n", str(limit), "--pretty=format:%H|%an|%at|%s",
                cwd=str(settings.BASE_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
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
                history.append({
                    "sha": sha,
                    "short_sha": sha[:8],
                    "author": author,
                    "timestamp": datetime.fromtimestamp(int(timestamp)).isoformat(),
                    "message": msg
                })
            return history
        except Exception as e:
            logger.error(f"获取更新历史失败: {e}")
            return []

    async def _run_system_health_check(self) -> Tuple[bool, str]:
        """执行系统健康检查，确认更新后运行正常"""
        try:
            # 1. 检查数据库
            try:
                from repositories.health_check import DatabaseHealthManager
                db_path = settings.DB_DIR / "forward.db"
                manager = DatabaseHealthManager(str(db_path))
                if not manager.check_health():
                    return False, "数据库完整性校验未通过"
            except Exception:
                # 如果 health_check 导入失败或运行出错，回滚最基础的检查
                if not (settings.DB_DIR / "forward.db").exists():
                    return False, "数据库文件丢失"
            
            # 2. 检查网络
            if not await self._check_network():
                return False, "网络连通性异常"
                
            # 3. 检查基础环境
            if not (settings.BASE_DIR / "main.py").exists():
                return False, "核心文件丢失: main.py"
                
            return True, "系统运行正常"
        except Exception as e:
            return False, f"健康检查异常: {e}"

    async def check_for_updates(self, force: bool = False) -> Tuple[bool, str]:
        """原子检查远程仓库状态"""
        # 0. 灰度发布过滤 (如果是自动触发)
        if not force and not self._is_target_of_gray_release():
            # 注意: 如果是用户通过 Web 手动点更新，应该绕过此检查。
            # 这里先实现逻辑，调用方（start_periodic_check）会隐含受限。
            return False, "未命中灰度策略"

        # 安全检查 1: 验证配置中的 URL 是否合法
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

        # 安全检查 2: 交叉验证 (Cross-Verification)
        # 即使 Git/HTTP 检查成功，也要用官方 API 再次确认该 SHA 是否属于官方仓库
        # 这能防止 .git/config 被篡改指向恶意源
        if check_result and remote_sha_candidate:
            is_valid_sha = await self._cross_verify_sha(remote_sha_candidate)
            if not is_valid_sha:
                logger.critical(f"🚨 [安全阻断] 检测到 SHA 指纹不匹配！远程版本 {remote_sha_candidate} 未在官方仓库 {OFFICIAL_REPO} 验证通过。")
                return False, "安全校验失败：版本指纹与官方源不符"

        return check_result, check_msg

    def _is_target_of_gray_release(self) -> bool:
        """判断当前实例是否命中灰度更新策略 (基于 USER_ID 的确定性随机)"""
        if settings.UPDATE_CANARY_PROBABILITY >= 1.0:
            return True
        if settings.UPDATE_CANARY_PROBABILITY <= 0.0:
            return False
            
        import hashlib
        # 使用 USER_ID 作为种子，确保同一账号在同一版本下的结果一致
        seed_base = f"update_gray_{settings.USER_ID or 'anon'}"
        seed = hashlib.md5(seed_base.encode()).hexdigest()
        val = int(seed[:8], 16) / 0xFFFFFFFF
        
        return val <= settings.UPDATE_CANARY_PROBABILITY

    async def _cross_verify_sha(self, sha_short: str, version_ref: Optional[str] = None) -> bool:
        """
        交叉验证: 这里的逻辑是绝对信任'硬编码'的 OFFICIAL_REPO。
        通过独立的 HTTP 通道访问官方 API，确认 sha_short 是否真实存在于官方仓库中。
        """
        try:
            import httpx
            # 如果提供了具体的引用 (SHA/Tag)，则校验该引用；否则校验默认分支
            ref = version_ref or settings.UPDATE_BRANCH
            api_url = f"https://api.github.com/repos/{OFFICIAL_REPO}/commits/{ref}"
            
            async with httpx.AsyncClient(timeout=5.0, follow_redirects=True) as client:
                resp = await client.get(api_url)
                if resp.status_code == 200:
                    official_sha = resp.json().get("sha", "")
                    # 比对前 N 位
                    sha_s = sha_short.strip().lower()
                    official_s = official_sha[:len(sha_s)].strip().lower()
                    if official_s and sha_s == official_s:
                        return True
                    
                    # 如果 ref 本身就是 SHA，且与返回的 SHA 一致，也判定成功
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
        """验证远程仓库地址的安全性"""
        try:
            parsed = urllib.parse.urlparse(url)
            # 1. 强制 HTTPS
            if parsed.scheme != "https":
                logger.warning(f"⚠️ [安全警报] 拒绝使用非加密协议更新: {url}")
                return False
            
            # 2. 检查是否为 GitHub (目前主要支持 GitHub)
            if parsed.netloc != "github.com":
                logger.warning(f"⚠️ [安全提示] 更新源非 GitHub 官方域: {parsed.netloc}")
                # 暂时允许非 GitHub 但记录警告 (根据用户需求，这里可以更严格)
            
            # 3. 官方仓库比对
            normalized_url = url.replace("https://", "").replace("http://", "")
            if normalized_url.endswith(".git"):
                normalized_url = normalized_url[:-4]
            if normalized_url.startswith("github.com/"):
                 normalized_url = normalized_url[11:]

            if normalized_url != OFFICIAL_REPO:
                logger.warning(f"⚠️ [安全提示] 正在使用非官方仓库更新: {normalized_url} (官方: {OFFICIAL_REPO})")
            
            return True
        except Exception:
            return False

    async def _check_via_git(self) -> Tuple[bool, str]:
        """通过 Git 指令检查更新"""

        try:
            # 执行静默 Fetch 并设置超时
            process = await asyncio.create_subprocess_exec(
                "git", "fetch", "--quiet", "origin", settings.UPDATE_BRANCH,
                cwd=str(settings.BASE_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
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

            # 2. 检查本地是否落后于远程 (检查 HEAD..origin/branch 的提交数)
            # 理由：如果 local_id != remot_id，可能只是本地领先或偏离。
            # 我们仅在本地缺少远程提交时提示更新。
            check_proc = await asyncio.create_subprocess_exec(
                "git", "rev-list", f"HEAD..origin/{settings.UPDATE_BRANCH}", "--count",
                cwd=str(settings.BASE_DIR), stdout=asyncio.subprocess.PIPE
            )
            out, _ = await check_proc.communicate()
            behind_count = int(out.decode().strip() or 0)

            # 获取远程 SHA 用于展示
            remot_proc = await asyncio.create_subprocess_exec(
                "git", "rev-parse", f"origin/{settings.UPDATE_BRANCH}",
                cwd=str(settings.BASE_DIR), stdout=asyncio.subprocess.PIPE
            )
            r_out, _ = await remot_proc.communicate()
            remot_id = r_out.decode().strip()

            if behind_count > 0:
                return True, remot_id[:8]
            
            # 如果不落后（相等、领先或完全分叉但已同步），则显示当前 HEAD
            local_proc = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "HEAD",
                cwd=str(settings.BASE_DIR), stdout=asyncio.subprocess.PIPE
            )
            l_out, _ = await local_proc.communicate()
            return False, l_out.decode().strip()[:8]
        except Exception as e:
            return False, f"Git 检查失败: {e}"

    async def _check_via_http(self) -> Tuple[bool, str]:
        """通过 HTTP API 检查更新 (针对无 Git 环境)"""
        try:
            import httpx
            # 假定 GitHub，获取最新版本的 commit 或者是版本号
            # 这里简单起见，尝试获取主分支的 SHA
            repo_path = settings.UPDATE_REMOTE_URL.replace("https://github.com/", "").replace(".git", "")
            api_url = f"https://api.github.com/repos/{repo_path}/commits/{settings.UPDATE_BRANCH}"
            
            async with httpx.AsyncClient(timeout=10.0) as client:
                resp = await client.get(api_url)
                if resp.status_code == 200:
                    remote_sha = resp.json().get("sha", "")
                    # 对比本地存储的版本
                    local_sha = await self.get_current_version()
                    
                    # 统一对比长度 (8位)
                    if remote_sha and remote_sha[:8].lower() != local_sha[:8].lower():
                        return True, remote_sha[:8]
                    return False, local_sha[:8]
                else:
                    return False, f"HTTP 请求失败 ({resp.status_code})"
        except Exception as e:
            return False, f"HTTP 检查异常: {e}"

    async def perform_update(self, target_version: Optional[str] = None) -> Tuple[bool, str]:
        """执行生产级原子更新流程"""
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
        """执行 Git 更新"""
        try:
            # 1. 记录当前版本
            current_proc = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "HEAD",
                cwd=str(settings.BASE_DIR), stdout=asyncio.subprocess.PIPE
            )
            c_out, _ = await current_proc.communicate()
            prev_version = c_out.decode().strip()

            # 2. 检查依赖文件 (requirements.txt) 哈希值
            req_hash_before = self._get_file_hash(settings.BASE_DIR / "requirements.txt")

            # 3. 执行单向同步 (Hard Reset)
            # 理由：彻底消除任何本地权限或文件意外改动对更新的阻碍
            process = await asyncio.create_subprocess_exec(
                "git", "reset", "--hard", f"origin/{settings.UPDATE_BRANCH}",
                cwd=str(settings.BASE_DIR),
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            stdout, stderr = await process.communicate()
            
            if process.returncode != 0:
                return False, f"Git 同步失败: {stderr.decode()}"

            # 4. 依赖项对齐
            req_hash_after = self._get_file_hash(settings.BASE_DIR / "requirements.txt")
            if req_hash_before != req_hash_after:
                logger.info("📦 [更新] 检测到依赖文件变更，正在静默同步库...")
                dep_success = await self._sync_dependencies()
                if not dep_success:
                    logger.warning("⚠️ 依赖同步失败，建议手动检查 requirements.txt 以免系统启动失败。")

            # 5. 获取更新后的版本 ID 并持久化状态
            new_proc = await asyncio.create_subprocess_exec(
                "git", "rev-parse", "HEAD",
                cwd=str(settings.BASE_DIR), stdout=asyncio.subprocess.PIPE
            )
            n_out, _ = await new_proc.communicate()
            current_id = n_out.decode().strip()

            state = self._get_state()
            state.update({
                "status": "restarting",
                "prev_version": prev_version,
                "current_version": current_id,
                "timestamp": datetime.now().isoformat(),
                "fail_count": 0
            })
            
            self._save_state(state)
            
            return True, "Git 代码原子同步完成"
        except Exception as e:
            return False, f"Git 更新执行异常: {e}"

    async def _perform_http_update(self, target_version: Optional[str] = None) -> Tuple[bool, str]:
        """通过下载压缩包执行 HTTP 更新 (无 Git 环境 fallback)"""
        try:
            import httpx
            import zipfile
            import shutil
            import io

            # 规范化版本号
            version = target_version or settings.UPDATE_BRANCH
            if version.startswith("origin/"):
                version = version.replace("origin/", "", 1)

            repo_path = settings.UPDATE_REMOTE_URL.replace("https://github.com/", "").replace(".git", "")
            
            # GitHub 支持 Branch/Tag 和 SHA 两种 Zip 路径
            if len(version) >= 7 and all(c in "0123456789abcdef" for c in version.lower()):
                # 判定为 Commit SHA
                zip_url = f"https://github.com/{repo_path}/archive/{version}.zip"
            else:
                # 判定为 Branch 或 Tag
                zip_url = f"https://github.com/{repo_path}/archive/refs/heads/{version}.zip"
            
            # [安全] 预下载指纹校验
            if not await self._cross_verify_sha(version[:8], version):
                 return False, f"安全校验失败: 版本 {version[:8]} 未在官方仓库验证通过"

            logger.info(f"正在从 HTTP 下载更新包: {zip_url}")
            # [安全] 限制最大下载大小 (防止炸弹包)
            async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
                resp = await client.get(zip_url)
                if resp.status_code != 200:
                    return False, f"下载失败 ({resp.status_code})"
                
                # 检查内容类型
                content_type = resp.headers.get("content-type", "")
                if "zip" not in content_type and "octet-stream" not in content_type:
                     return False, f"下载内容类型异常: {content_type}"
                
                zip_data = io.BytesIO(resp.content)
                
            # 备份当前版本
            from .backup_service import backup_service
            backup_path = await backup_service.backup_code(label="pre_http_update")
            state = self._get_state()
            prev_version = state.get("current_version", "未知")

            with zipfile.ZipFile(zip_data) as z:
                # GitHub zip 结构通常是: RepoName-BranchName/Files...
                root_dir = z.namelist()[0].split('/')[0]
                
                for member in z.namelist():
                    # [安全] 防止 Zip Slip 漏洞 (路径穿越攻击)
                    if '..' in member or member.startswith('/') or  '\\' in member:
                        logger.warning(f"⚠️ [安全拦截] 检测到非法文件路径: {member}")
                        continue

                    if member == root_dir + '/' or not member.startswith(root_dir + '/'):
                        continue
                    
                    filename = member.replace(root_dir + '/', '', 1)
                    if not filename: continue
                    
                    # 保护排除名单
                    if any(filename.startswith(p) for p in [".env", "data/", "db/", "logs/", "temp/", ".git/"]):
                        continue
                    
                    base_dir = settings.BASE_DIR.resolve()
                    target_path = (base_dir / filename).resolve()
                    try:
                        target_path.relative_to(base_dir)
                    except ValueError:
                        logger.warning(f"⚠️ [安全拦截] 更新文件目标路径越界: {filename}")
                        continue
                    
                    # 如果是目录，创建通过
                    if member.endswith('/'):
                        target_path.mkdir(parents=True, exist_ok=True)
                        continue

                    # 确保父目录存在
                    target_path.parent.mkdir(parents=True, exist_ok=True)
                    
                    # Atomic Write with Retry (Windows Robustness)
                    for i in range(3):
                        try:
                            source = z.open(member)
                            with open(target_path, "wb") as f:
                                shutil.copyfileobj(source, f)
                            break
                        except PermissionError:
                            if i == 2: 
                                logger.error(f"无法写入文件 (被占用): {filename}")
                                # 这里如果失败，可能导致不完整更新。但有了 backup，我们可以回滚。
                                # 暂时继续，或抛出异常触发整体失败？
                                # 考虑到原子性难保证，抛出异常比较安全
                                raise
                            await asyncio.sleep(0.5)
            
            # 持久化版本信息
            # 尝试解析真实 SHA (如果 version 是分支名)
            final_version = version
            try:
                repo_path = settings.UPDATE_REMOTE_URL.replace("https://github.com/", "").replace(".git", "")
                async with httpx.AsyncClient(timeout=5.0) as client:
                    r = await client.get(f"https://api.github.com/repos/{repo_path}/commits/{version}")
                    if r.status_code == 200:
                        final_version = r.json().get("sha", version)
            except Exception:
                pass

            try:
                state.update({
                    "status": "restarting",
                    "prev_version": prev_version,
                    "backup_file": str(backup_path) if backup_path else None,
                    "current_version": final_version,
                    "timestamp": datetime.now().isoformat(),
                    "fail_count": 0
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
        """获取文件 MD5 哈希"""
        if not path.exists():
            return ""
        import hashlib
        try:
            return hashlib.md5(path.read_bytes()).hexdigest()
        except Exception as e:
            return ""

    async def _sync_dependencies(self) -> bool:
        """执行后台依赖安装 (使用 uv 加速)"""
        try:
            # 优先使用 uv
            cmd = ["uv", "pip", "install", "--python", sys.executable, "-r", "requirements.txt"]
            
            process = await asyncio.create_subprocess_exec(
                *cmd,
                cwd=str(settings.BASE_DIR),
                stdout=asyncio.subprocess.DEVNULL,
                stderr=asyncio.subprocess.PIPE
            )
            _, stderr = await process.communicate()
            return process.returncode == 0
        except Exception:
            return False

    async def rollback(self) -> Tuple[bool, str]:
        """执行紧急回滚流程 (支持 Git 和 HTTP)"""
        state = self._get_state()
        from .backup_service import backup_service
        
        # 1. 如果有 Git
        if self._git_available and self._is_git_repo:
            prev = state.get("prev_version")
            if not prev:
                return False, "未找到有效的 Git 版本记录"
            
            logger.critical(f"🚑 [回滚] Git Reset 至: {prev[:8]}...")
            process = await asyncio.create_subprocess_exec(
                "git", "reset", "--hard", prev,
                cwd=str(settings.BASE_DIR)
            )
            await process.wait()
            if process.returncode == 0:
                for f in ["UPDATE_LOCK.json", "UPDATE_VERIFYING.json"]:
                    lock_f = settings.BASE_DIR / "data" / f
                    if lock_f.exists(): lock_f.unlink()
            return process.returncode == 0, f"Git 回滚至 {prev[:8]}"
            
        # 2. 如果是 HTTP 模式 -> 只回滚代码
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
        """列出所有备份 (转发给 BackupService)"""
        from .backup_service import backup_service
        return await backup_service.list_backups()

    async def restore_from_backup(self, backup_path: str) -> Tuple[bool, str]:
        """公开的还原接口 (转发给 BackupService)"""
        from .backup_service import backup_service
        return await backup_service.restore(backup_path)

    def stop(self):
        """停止更新监控并清理任务"""
        self._stop_event.set()
        # 显式取消任务
        for t in self._tasksList:
            if not t.done():
                t.cancel()
        self._tasksList.clear()
        logger.info("UpdateService 任务已清理")

# 全局单例
update_service = UpdateService()
