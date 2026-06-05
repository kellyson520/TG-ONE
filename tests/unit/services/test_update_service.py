import pytest
from unittest.mock import patch, AsyncMock
from services.update_service import UpdateService

@pytest.fixture
def update_service():
    # 使用 Patch 避免初始化时真实检查 .git 和 创建目录
    with patch("pathlib.Path.exists", return_value=True), \
         patch("pathlib.Path.mkdir"):
        service = UpdateService()
        # 强制设置 _is_git_repo 为 True 方便测试
        service._is_git_repo = True
        return service

@pytest.mark.asyncio
async def test_check_network_success(update_service):
    # 模拟 socket.gethostbyname 返回成功
    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(return_value="192.168.1.1")
        assert await update_service._check_network() is True

@pytest.mark.asyncio
async def test_check_network_failure(update_service):
    with patch("asyncio.get_running_loop") as mock_loop:
        mock_loop.return_value.run_in_executor = AsyncMock(side_effect=Exception("DNS Error"))
        assert await update_service._check_network() is False

@pytest.mark.asyncio
async def test_check_for_updates_has_update(update_service):
    mock_fetch = AsyncMock()
    mock_fetch.communicate.return_value = (b"", b"")
    
    mock_local = AsyncMock()
    # git rev-list --count 应该返回一个数字字符串
    mock_local.communicate.return_value = (b"1\n", b"")
    
    mock_remote = AsyncMock()
    mock_remote.communicate.return_value = (b"remote_commit\n", b"")
    
    with patch("asyncio.create_subprocess_exec") as mock_exec, \
         patch.object(update_service, "_check_network", return_value=True), \
         patch.object(update_service, "_cross_verify_sha", return_value=True):
        mock_exec.side_effect = [mock_fetch, mock_local, mock_remote]
        has_update, commit = await update_service.check_for_updates()
        assert has_update is True
        assert commit == "remote_c"

@pytest.mark.asyncio
async def test_perform_update_sets_restarting_state(update_service):
    mock_current = AsyncMock()
    mock_current.communicate.return_value = (b"old_commit\n", b"")
    mock_reset = AsyncMock()
    mock_reset.communicate.return_value = (b"", b"")
    mock_reset.returncode = 0
    
    with patch("asyncio.create_subprocess_exec") as mock_exec, \
         patch.object(update_service, "_get_file_hash", return_value="hash"), \
         patch.object(update_service, "_save_state") as mock_save, \
         patch.object(update_service, "_get_state", return_value={}), \
         patch.object(update_service, "_check_network", return_value=True), \
         patch.object(update_service, "_cross_verify_sha", return_value=True):
        
        mock_exec.side_effect = [mock_current, mock_reset, mock_current]
        
        success, msg = await update_service.perform_update()
        assert success is True
        # 验证 state 被更新为 restarting 且 fail_count 为 0
        mock_save.assert_called()
        saved_state = mock_save.call_args[0][0]
        assert saved_state["status"] == "restarting"
        assert saved_state["fail_count"] == 0

@pytest.mark.asyncio
async def test_verify_update_health_increments_fail(update_service):
    # 模拟处于 restarting 状态，第一次失败
    initial_state = {"status": "restarting", "fail_count": 0}
    with patch.object(update_service, "_get_state", return_value=initial_state), \
         patch.object(update_service, "_save_state") as mock_save, \
         patch("asyncio.create_task") as mock_task:
        
        await update_service.verify_update_health()
        
        mock_save.assert_called()
        saved_state = mock_save.call_args[0][0]
        assert saved_state["fail_count"] == 1
        # 验证启动了稳定化任务
        mock_task.assert_called()

@pytest.mark.asyncio
async def test_verify_update_health_triggers_rollback(update_service):
    # 模拟处于 restarting 状态，已经失败了 2 次，这是第 3 次
    initial_state = {"status": "restarting", "fail_count": 2, "prev_version": "safe_commit"}
    with patch.object(update_service, "_get_state", return_value=initial_state), \
         patch.object(update_service, "_save_state") as mock_save, \
         patch.object(update_service, "rollback", return_value=(True, "ok")) as mock_rollback, \
         patch("services.system_service.guard_service.trigger_restart") as mock_restart:
        
        await update_service.verify_update_health()
        
        # 验证触发了回滚
        mock_rollback.assert_called_once()
        # 验证状态变更为 rolled_back
        mock_save.assert_called()
        last_state = mock_save.call_args[0][0]
        assert last_state["status"] == "rolled_back"
        # 验证触发了重启
        mock_restart.assert_called_once()

@pytest.mark.asyncio
async def test_rollback_execution(update_service):
    mock_reset = AsyncMock()
    mock_reset.wait = AsyncMock(return_value=0)
    mock_reset.returncode = 0
    
    with patch.object(update_service, "_get_state", return_value={"prev_version": "some_hash"}), \
         patch("asyncio.create_subprocess_exec", return_value=mock_reset):
        
        success, msg = await update_service.rollback()
        assert success is True
        assert "some_ha" in msg
