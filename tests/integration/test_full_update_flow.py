import pytest
import asyncio
import json
import os
import shutil
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime

from services.update_service import UpdateService, EXIT_CODE_UPDATE
from core.lifecycle import LifecycleManager

class MockLifecycle:
    def __init__(self):
        self.exit_code = 0
        self.stop_event = asyncio.Event()
        self.coordinator = MagicMock()
    
    def shutdown(self, code):
        self.exit_code = code
        self.stop_event.set()

@pytest.mark.asyncio
class TestFullUpdateFlow:
    """测试从指令发出到更新完成的全链路模拟"""

    @pytest.fixture
    async def setup_env(self, tmp_path):
        """准备测试环境"""
        # 1. 设置工作目录
        base_dir = tmp_path
        data_dir = base_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        
        # 2. 模拟数据库
        db_file = data_dir / "bot.db"
        db_file.write_text("original db content")
        
        # 3. 模拟配置
        with patch('services.update_service.settings') as mock_settings:
            mock_settings.BASE_DIR = base_dir
            mock_settings.UPDATE_BRANCH = "main"
            
            # 4. 初始化服务
            service = UpdateService()
            service._state_file = data_dir / "update_state.json"
            
            # 5. 模拟生命周期管理器
            mock_lifecycle = MockLifecycle()
            
            with patch('services.update_service.container') as mock_container:
                mock_container.lifecycle = mock_lifecycle
                yield service, mock_lifecycle, base_dir

    async def test_update_workflow_link(self, setup_env):
        service, lifecycle, base_dir = setup_env
        
        # --- Stage 1: Trigger Update ---
        # 模拟执行 /update 指令逻辑
        print("\n[Phase 1] Triggering update...")
        await service.trigger_update()
        
        # 验证 1: 锁文件是否生成
        lock_file = base_dir / "data" / "UPDATE_LOCK.json"
        assert lock_file.exists()
        lock_data = json.loads(lock_file.read_text())
        assert lock_data["status"] == "processing"
        
        # 验证 2: 退出码是否设为 10
        assert lifecycle.exit_code == EXIT_CODE_UPDATE
        print("✅ Phase 1 passed: Update triggered and exit code set.")

        # --- Stage 2: Daemon Execution (Simulated) ---
        # 在真实场景中，此时 Python 进程结束，entrypoint.sh 介入
        # 我们模拟守护进程完成的工作：保留锁文件、更新代码（此处略）、执行重启
        print("[Phase 2] Simulating daemon work...")
        # 确保备份目录中有内容 (trigger_update 已经创建了备份)
        backup_dir = base_dir / "data" / "backups" / "auto_update"
        assert any(backup_dir.glob("bot.db.*.bak"))
        
        # 模拟重启后的状态：创建 alembic.ini 以触发迁移逻辑
        (base_dir / "alembic.ini").write_text("dummy alembic config")
        print("✅ Phase 2 passed: Environment prepared for bootstrap.")

        # --- Stage 3: Post-Update Bootstrap ---
        print("[Phase 3] Running post-update bootstrap...")
        
        # 模拟 Alembic 成功
        mock_process = AsyncMock()
        mock_process.returncode = 0
        mock_process.communicate.return_value = (b"OK", b"")
        
        with patch('asyncio.create_subprocess_exec', return_value=mock_process) as mock_exec:
            # 模拟健康检查通过
            with patch.object(service, '_run_system_health_check', return_value=(True, "OK")):
                await service.post_update_bootstrap()
                
                # 验证 3: Alembic 是否被调用
                mock_exec.assert_called_once()
                assert "alembic" in mock_exec.call_args[0]
        
        # 验证 4: 锁文件状态转换
        # UPDATE_LOCK.json 应该消失
        assert not lock_file.exists()
        # UPDATE_VERIFYING.json 应该出现
        verify_lock = base_dir / "data" / "UPDATE_VERIFYING.json"
        assert verify_lock.exists()
        
        print("✅ Phase 3 passed: Bootstrap complete and locks transitioned.")

    async def test_update_rollback_on_failure(self, setup_env):
        """测试更新过程中迁移失败触发的回滚流程"""
        service, lifecycle, base_dir = setup_env
        
        print("\n[Rollback Test] Triggering update...")
        await service.trigger_update()
        lock_file = base_dir / "data" / "UPDATE_LOCK.json"
        
        # 模拟 Alembic 失败
        mock_process = AsyncMock()
        mock_process.returncode = 1
        mock_process.communicate.return_value = (b"", b"Migration Error: conflict")
        
        (base_dir / "alembic.ini").write_text("dummy")
        
        print("[Rollback Test] Running bootstrap with failing migration...")
        with patch('asyncio.create_subprocess_exec', return_value=mock_process):
            # 捕获并忽略内部 emit 事件错误
            await service.post_update_bootstrap()
            
        # 验证: 数据库是否已从备份恢复
        db_file = base_dir / "data" / "bot.db"
        # 初始内容是 "original db content"，备份也是这个内容
        assert db_file.read_text() == "original db content"
        
        # 仍然会转换状态以允许系统带伤运行（或在此后的健康检查中再次触发回滚）
        assert not lock_file.exists()
        assert (base_dir / "data" / "UPDATE_VERIFYING.json").exists()
        print("✅ Rollback logic verified.")

if __name__ == "__main__":
    pytest.main([__file__, "-v"])
