import pytest
import os
from unittest.mock import AsyncMock, patch
from services.config_service import ConfigService
from models.models import SystemConfiguration

@pytest.mark.asyncio
class TestConfigService:
    @pytest.fixture
    def service(self):
        # 使用临时 JSON 路径
        return ConfigService(json_path="tests/temp/settings.json")

    async def test_set_and_get_db(self, service, db):
        # 1. 设置配置
        await service.set("test_key", "test_value", data_type="string")
        
        # 2. 从 DB 获取 (通过 ConfigService 会优先内存缓存)
        # 我们先清空内存缓存验证 DB 逻辑
        service._memory_cache.clear()
        
        val = await service.get("test_key")
        assert val == "test_value"
        
        # 验证数据库内容
        from sqlalchemy import select
        res = await db.execute(select(SystemConfiguration).filter_by(key="test_key"))
        cfg = res.scalar_one()
        assert cfg.value == "test_value"

    async def test_get_data_types(self, service, db):
        # Integer
        await service.set("int_key", 123, data_type="integer")
        assert await service.get("int_key") == 123
        
        # Boolean
        await service.set("bool_key", True, data_type="boolean")
        assert await service.get("bool_key") is True
        
        # JSON
        await service.set("json_key", {"a": 1}, data_type="json")
        assert await service.get("json_key") == {"a": 1}

    async def test_fallback_logic(self, service):
        # 内存 -> DB -> JSON -> Env -> Default
        
        # 1. Env Fallback
        with patch.dict(os.environ, {"ENV_KEY": "env_val"}):
            assert await service.get("ENV_KEY") == "env_val"
        
        # 2. Default Fallback
        assert await service.get("NON_EXIST", default="def") == "def"

    async def test_subscribe_changes(self, service):
        mock_cb = AsyncMock()
        service.subscribe_change(mock_cb)
        
        await service.set("change_key", "new_val")
        
        mock_cb.assert_called_with("change_key", "new_val")

    async def test_get_sync(self, service):
        service._memory_cache["sync_key"] = "sync_val"
        assert service.get_sync("sync_key") == "sync_val"
        
        with patch.dict(os.environ, {"ENV_SYNC": "env_sync_val"}):
            assert service.get_sync("ENV_SYNC") == "env_sync_val"
