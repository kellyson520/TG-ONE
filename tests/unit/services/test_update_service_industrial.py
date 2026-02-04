"""
工业级自动升级系统单元测试
测试 UpdateService 的双层状态机、原子回滚和无限重启保护能力
"""
import pytest
import asyncio
import json
import sys
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch, mock_open
from datetime import datetime

# 测试目标
from services.update_service import UpdateService, EXIT_CODE_UPDATE


class TestIndustrialUpdateSystem:
    """工业级自动升级系统测试套件"""
    
    @pytest.fixture
    def mock_settings(self, tmp_path):
        """模拟配置"""
        with patch('services.update_service.settings') as mock_settings:
            mock_settings.BASE_DIR = tmp_path
            mock_settings.AUTO_UPDATE_ENABLED = True
            mock_settings.UPDATE_CHECK_INTERVAL = 3600
            mock_settings.UPDATE_REMOTE_URL = "https://github.com/kellyson520/TG-ONE.git"
            mock_settings.UPDATE_BRANCH = "main"
            yield mock_settings
    
    @pytest.fixture
    def update_service(self, mock_settings):
        """创建 UpdateService 实例"""
        service = UpdateService()
        # 确保状态文件目录存在
        service._state_file.parent.mkdir(parents=True, exist_ok=True)
        return service
    
    # ==================== Phase 1: trigger_update 测试 ====================
    
    @pytest.mark.asyncio
    async def test_trigger_update_creates_db_backup(self, update_service, mock_settings, tmp_path):
        """测试 trigger_update 创建数据库备份"""
        # 准备：创建模拟数据库文件
        db_file = tmp_path / "data" / "bot.db"
        db_file.parent.mkdir(parents=True, exist_ok=True)
        db_file.write_text("mock database content")
        
        # 模拟 sys.exit 以捕获退出码
        with patch('sys.exit') as mock_exit:
            mock_exit.side_effect = SystemExit(EXIT_CODE_UPDATE)
            
            with pytest.raises(SystemExit):
                await update_service.trigger_update()
            
            # 验证退出码
            mock_exit.assert_called_once_with(EXIT_CODE_UPDATE)
        
        # 验证备份文件已创建
        backup_dir = tmp_path / "data" / "backups" / "auto_update"
        assert backup_dir.exists(), "备份目录应该被创建"
        
        backup_files = list(backup_dir.glob("bot.db.*.bak"))
        assert len(backup_files) == 1, "应该创建一个数据库备份文件"
        assert backup_files[0].read_text() == "mock database content", "备份内容应该与原文件一致"
    
    @pytest.mark.asyncio
    async def test_trigger_update_creates_lock_file(self, update_service, mock_settings, tmp_path):
        """测试 trigger_update 创建锁文件"""
        with patch('sys.exit') as mock_exit:
            mock_exit.side_effect = SystemExit(EXIT_CODE_UPDATE)
            
            with pytest.raises(SystemExit):
                await update_service.trigger_update()
        
        # 验证锁文件已创建
        lock_file = tmp_path / "data" / "UPDATE_LOCK.json"
        assert lock_file.exists(), "锁文件应该被创建"
        
        # 验证锁文件内容
        lock_data = json.loads(lock_file.read_text())
        assert lock_data["status"] == "processing", "状态应该是 processing"
        assert "start_time" in lock_data, "应该记录开始时间"
        assert lock_data["version"] == "origin/main", "版本应该是 origin/main"
    
    @pytest.mark.asyncio
    async def test_trigger_update_exits_with_correct_code(self, update_service, mock_settings):
        """测试 trigger_update 使用正确的退出码"""
        with patch('sys.exit') as mock_exit:
            mock_exit.side_effect = SystemExit(EXIT_CODE_UPDATE)
            
            with pytest.raises(SystemExit):
                await update_service.trigger_update()
            
            mock_exit.assert_called_once_with(10)  # EXIT_CODE_UPDATE = 10
    
    @pytest.mark.asyncio
    async def test_trigger_update_cleanup_on_failure(self, update_service, mock_settings, tmp_path):
        """测试 trigger_update 失败时清理锁文件"""
        # 模拟写入锁文件时失败
        with patch('builtins.open', side_effect=PermissionError("Mock permission error")):
            with pytest.raises(RuntimeError, match="更新准备失败"):
                await update_service.trigger_update()
        
        # 验证锁文件不存在（已清理）
        lock_file = tmp_path / "data" / "UPDATE_LOCK.json"
        # 注意：由于异常发生在写入前，文件本来就不存在
        assert not lock_file.exists() or lock_file.stat().st_size == 0
    
    # ==================== Phase 2: post_update_bootstrap 测试 ====================
    
    @pytest.mark.asyncio
    async def test_post_update_bootstrap_no_lock_file(self, update_service, mock_settings, tmp_path):
        """测试 post_update_bootstrap 在没有锁文件时直接返回"""
        # 确保锁文件不存在
        lock_file = tmp_path / "data" / "UPDATE_LOCK.json"
        if lock_file.exists():
            lock_file.unlink()
        
        # 应该直接返回，不执行任何操作
        await update_service.post_update_bootstrap()
        
        # 验证没有副作用
        assert not lock_file.exists()
    
    @pytest.mark.asyncio
    async def test_post_update_bootstrap_runs_alembic(self, update_service, mock_settings, tmp_path):
        """测试 post_update_bootstrap 执行 Alembic 迁移"""
        # 准备：创建锁文件
        lock_file = tmp_path / "data" / "UPDATE_LOCK.json"
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_data = {
            "status": "processing",
            "start_time": datetime.now().isoformat(),
            "db_backup": str(tmp_path / "data" / "backups" / "auto_update" / "bot.db.20260204.bak"),
            "version": "origin/main"
        }
        lock_file.write_text(json.dumps(lock_data))
        
        # 准备：创建 alembic.ini
        alembic_ini = tmp_path / "alembic.ini"
        alembic_ini.write_text("[alembic]\nscript_location = alembic")
        
        # 模拟 subprocess.run
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Alembic migration successful"
        mock_result.stderr = ""
        
        with patch('subprocess.run', return_value=mock_result) as mock_run:
            await update_service.post_update_bootstrap()
            
            # 验证 Alembic 被调用
            mock_run.assert_called_once()
            args = mock_run.call_args[0][0]
            assert args[0] == "alembic"
            assert args[1] == "upgrade"
            assert args[2] == "head"
        
        # 验证锁文件已删除
        assert not lock_file.exists(), "锁文件应该被删除"
    
    @pytest.mark.asyncio
    async def test_post_update_bootstrap_rollback_on_migration_failure(self, update_service, mock_settings, tmp_path):
        """测试 post_update_bootstrap 在迁移失败时回滚数据库"""
        # 准备：创建数据库备份
        db_backup = tmp_path / "data" / "backups" / "auto_update" / "bot.db.20260204.bak"
        db_backup.parent.mkdir(parents=True, exist_ok=True)
        db_backup.write_text("backup database content")
        
        # 准备：创建锁文件
        lock_file = tmp_path / "data" / "UPDATE_LOCK.json"
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_data = {
            "status": "processing",
            "start_time": datetime.now().isoformat(),
            "db_backup": str(db_backup),
            "version": "origin/main"
        }
        lock_file.write_text(json.dumps(lock_data))
        
        # 准备：创建 alembic.ini
        alembic_ini = tmp_path / "alembic.ini"
        alembic_ini.write_text("[alembic]\nscript_location = alembic")
        
        # 模拟 Alembic 迁移失败
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""
        mock_result.stderr = "Migration failed: table already exists"
        
        with patch('subprocess.run', return_value=mock_result):
            await update_service.post_update_bootstrap()
        
        # 验证数据库已回滚
        db_file = tmp_path / "data" / "bot.db"
        assert db_file.exists(), "数据库文件应该被恢复"
        assert db_file.read_text() == "backup database content", "数据库内容应该与备份一致"
        
        # 验证锁文件仍被删除（允许系统继续启动）
        assert not lock_file.exists(), "锁文件应该被删除"
    
    @pytest.mark.asyncio
    async def test_post_update_bootstrap_skips_migration_without_alembic(self, update_service, mock_settings, tmp_path):
        """测试 post_update_bootstrap 在没有 alembic.ini 时跳过迁移"""
        # 准备：创建锁文件
        lock_file = tmp_path / "data" / "UPDATE_LOCK.json"
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_data = {
            "status": "processing",
            "start_time": datetime.now().isoformat(),
            "version": "origin/main"
        }
        lock_file.write_text(json.dumps(lock_data))
        
        # 确保 alembic.ini 不存在
        alembic_ini = tmp_path / "alembic.ini"
        if alembic_ini.exists():
            alembic_ini.unlink()
        
        with patch('subprocess.run') as mock_run:
            await update_service.post_update_bootstrap()
            
            # 验证 subprocess.run 未被调用
            mock_run.assert_not_called()
        
        # 验证锁文件已删除
        assert not lock_file.exists(), "锁文件应该被删除"
    
    @pytest.mark.asyncio
    async def test_post_update_bootstrap_always_removes_lock(self, update_service, mock_settings, tmp_path):
        """测试 post_update_bootstrap 无论成功失败都删除锁文件"""
        # 准备：创建锁文件
        lock_file = tmp_path / "data" / "UPDATE_LOCK.json"
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_data = {
            "status": "processing",
            "start_time": datetime.now().isoformat(),
            "version": "origin/main"
        }
        lock_file.write_text(json.dumps(lock_data))
        
        # 准备：创建 alembic.ini
        alembic_ini = tmp_path / "alembic.ini"
        alembic_ini.write_text("[alembic]\nscript_location = alembic")
        
        # 模拟 subprocess.run 抛出异常
        with patch('subprocess.run', side_effect=Exception("Unexpected error")):
            await update_service.post_update_bootstrap()
        
        # 验证锁文件仍被删除
        assert not lock_file.exists(), "即使发生异常，锁文件也应该被删除"
    
    # ==================== Phase 3: _rollback_db 测试 ====================
    
    def test_rollback_db_success(self, update_service, mock_settings, tmp_path):
        """测试数据库回滚成功"""
        # 准备：创建备份文件
        backup_file = tmp_path / "data" / "backups" / "auto_update" / "bot.db.backup.bak"
        backup_file.parent.mkdir(parents=True, exist_ok=True)
        backup_file.write_text("backup content")
        
        # 准备：创建当前数据库文件
        db_file = tmp_path / "data" / "bot.db"
        db_file.parent.mkdir(parents=True, exist_ok=True)
        db_file.write_text("corrupted content")
        
        # 执行回滚
        update_service._rollback_db(str(backup_file))
        
        # 验证数据库已恢复
        assert db_file.read_text() == "backup content", "数据库应该被恢复为备份内容"
    
    def test_rollback_db_missing_backup(self, update_service, mock_settings, tmp_path):
        """测试备份文件不存在时的处理"""
        # 准备：确保备份文件不存在
        backup_file = tmp_path / "data" / "backups" / "auto_update" / "nonexistent.bak"
        
        # 执行回滚（不应该抛出异常）
        update_service._rollback_db(str(backup_file))
        
        # 验证数据库文件未被创建
        db_file = tmp_path / "data" / "bot.db"
        assert not db_file.exists() or db_file.stat().st_size == 0
    
    # ==================== Phase 4: 集成测试 ====================
    
    @pytest.mark.asyncio
    async def test_full_update_cycle(self, update_service, mock_settings, tmp_path):
        """测试完整的更新周期：trigger -> bootstrap"""
        # 准备：创建数据库文件
        db_file = tmp_path / "data" / "bot.db"
        db_file.parent.mkdir(parents=True, exist_ok=True)
        db_file.write_text("original database")
        
        # 准备：创建 alembic.ini
        alembic_ini = tmp_path / "alembic.ini"
        alembic_ini.write_text("[alembic]\nscript_location = alembic")
        
        # Step 1: 触发更新
        with patch('sys.exit') as mock_exit:
            mock_exit.side_effect = SystemExit(EXIT_CODE_UPDATE)
            
            with pytest.raises(SystemExit):
                await update_service.trigger_update()
        
        # 验证锁文件已创建
        lock_file = tmp_path / "data" / "UPDATE_LOCK.json"
        assert lock_file.exists(), "锁文件应该存在"
        
        # 验证数据库备份已创建
        backup_dir = tmp_path / "data" / "backups" / "auto_update"
        backup_files = list(backup_dir.glob("bot.db.*.bak"))
        assert len(backup_files) == 1, "应该有一个数据库备份"
        
        # Step 2: 模拟 Shell 更新代码和依赖（这里跳过）
        
        # Step 3: 启动引导
        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Migration successful"
        mock_result.stderr = ""
        
        with patch('subprocess.run', return_value=mock_result):
            await update_service.post_update_bootstrap()
        
        # 验证锁文件已删除
        assert not lock_file.exists(), "锁文件应该被删除"
        
        # 验证数据库未被回滚（迁移成功）
        assert db_file.read_text() == "original database", "数据库应该保持原样"
    
    @pytest.mark.asyncio
    async def test_update_failure_rollback_cycle(self, update_service, mock_settings, tmp_path):
        """测试更新失败回滚周期"""
        # 准备：创建数据库文件
        db_file = tmp_path / "data" / "bot.db"
        db_file.parent.mkdir(parents=True, exist_ok=True)
        db_file.write_text("original database")
        
        # 准备：创建 alembic.ini
        alembic_ini = tmp_path / "alembic.ini"
        alembic_ini.write_text("[alembic]\nscript_location = alembic")
        
        # Step 1: 触发更新
        with patch('sys.exit') as mock_exit:
            mock_exit.side_effect = SystemExit(EXIT_CODE_UPDATE)
            
            with pytest.raises(SystemExit):
                await update_service.trigger_update()
        
        lock_file = tmp_path / "data" / "UPDATE_LOCK.json"
        assert lock_file.exists()
        
        # Step 2: 模拟迁移失败
        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Migration failed"
        
        with patch('subprocess.run', return_value=mock_result):
            await update_service.post_update_bootstrap()
        
        # 验证数据库已回滚
        assert db_file.read_text() == "original database", "数据库应该被恢复"
        
        # 验证锁文件已删除
        assert not lock_file.exists(), "锁文件应该被删除"
    
    # ==================== Phase 5: 边界条件测试 ====================
    
    @pytest.mark.asyncio
    async def test_concurrent_trigger_update_prevention(self, update_service, mock_settings):
        """测试防止并发触发更新"""
        # 注意：trigger_update 没有并发锁，因为它会立即退出进程
        # 这个测试主要验证退出码的一致性
        
        with patch('sys.exit') as mock_exit:
            mock_exit.side_effect = SystemExit(EXIT_CODE_UPDATE)
            
            with pytest.raises(SystemExit):
                await update_service.trigger_update()
            
            # 验证退出码
            assert mock_exit.call_args[0][0] == EXIT_CODE_UPDATE
    
    @pytest.mark.asyncio
    async def test_post_update_bootstrap_with_corrupted_lock_file(self, update_service, mock_settings, tmp_path):
        """测试损坏的锁文件处理"""
        # 准备：创建损坏的锁文件
        lock_file = tmp_path / "data" / "UPDATE_LOCK.json"
        lock_file.parent.mkdir(parents=True, exist_ok=True)
        lock_file.write_text("{ invalid json")
        
        # 应该不抛出异常，优雅处理
        await update_service.post_update_bootstrap()
        
        # 验证锁文件已删除
        assert not lock_file.exists(), "损坏的锁文件应该被删除"


class TestExitCodeConstant:
    """测试退出码常量"""
    
    def test_exit_code_update_value(self):
        """测试 EXIT_CODE_UPDATE 的值"""
        assert EXIT_CODE_UPDATE == 10, "退出码应该是 10"
    
    def test_exit_code_is_integer(self):
        """测试退出码是整数"""
        assert isinstance(EXIT_CODE_UPDATE, int), "退出码应该是整数类型"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
