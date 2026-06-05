# tests/unit/handlers/conftest.py
"""
Handler 测试专用 conftest
完全禁用全局 conftest 的数据库初始化
"""
import sys
from unittest.mock import MagicMock, AsyncMock

# ============================================================
# 在任何导入之前，Mock 所有可能阻塞的模块
# ============================================================

# Mock C 扩展库和异步库
for lib in ["rapidfuzz", "numba", "duckdb", "pyarrow", "uvloop", "pandas", "apprise", "psutil"]:
    sys.modules[lib] = MagicMock()
    sys.modules[f"{lib}.fuzz"] = MagicMock()

# 异步文件操作
mock_aiofiles = MagicMock()
mock_aiofiles.open = MagicMock(return_value=AsyncMock())
sys.modules["aiofiles"] = mock_aiofiles

# Mock 底层工具
for m in ["core.helpers.realtime_stats", "services.network.bot_heartbeat", "core.helpers.forward_recorder", "core.helpers.env_config"]:
    sys.modules[m] = MagicMock()

# Mock error handler
mock_err = MagicMock()
mock_err.handle_errors = lambda *a, **k: (lambda f: f)
mock_err.log_execution = lambda *a, **k: (lambda f: f)
sys.modules["core.helpers.error_handler"] = mock_err

# Mock settings 函数
_mock_settings = MagicMock()
_mock_settings.load_ai_models = MagicMock(return_value=[])
_mock_settings.load_delay_times = MagicMock(return_value=[])
_mock_settings.load_max_media_size = MagicMock(return_value=[])
_mock_settings.load_media_extensions = MagicMock(return_value=[])
_mock_settings.load_summary_times = MagicMock(return_value=[])
sys.modules['core.config.settings_loader'] = _mock_settings

# Mock core.config
mock_config_settings = MagicMock()
mock_config_settings.DATABASE_URL = "sqlite:///:memory:"
mock_config_settings.APP_ENV = "testing"
mock_config_settings.DEFAULT_MAX_MEDIA_SIZE = 100
mock_config_settings.RSS_SECRET_KEY = "test_secret"
mock_config_settings.DEFAULT_SUMMARY_TIME = "20:00"
mock_config_settings.DB_POOL_SIZE = 5
mock_config_settings.DB_MAX_OVERFLOW = 10
mock_config_settings.DB_ECHO = False
mock_config = MagicMock()
mock_config.settings = mock_config_settings
sys.modules["core.config"] = mock_config

# Mock 业务模块
for module in [
    "services.download_service", 
    "services.worker_service", 
    "scheduler.summary_scheduler",
    "scheduler.optimized_chat_updater",
    "core.helpers.media.media",
    "middlewares.loader",
    "middlewares.dedup", 
    "middlewares.download",
    "middlewares.sender",
    "middlewares.filter",
    "middlewares.ai",
    "core.helpers.tombstone"
]:
    if module not in sys.modules:
        sys.modules[module] = MagicMock()

# Mock container (完全禁用)
mock_container = MagicMock()
mock_container.db = MagicMock()
# session() 返回一个 AsyncMock，它自带 __aenter__/__aexit__
mock_container.db.session = MagicMock(return_value=AsyncMock())
mock_container.db.engine = MagicMock()
mock_container.user_client = AsyncMock()
mock_container.bot_client = AsyncMock()
# 补全 repository/service 的 mock, 默认设为 AsyncMock 以防止 await 错误
mock_container.rule_repo = AsyncMock()
mock_container.task_repo = AsyncMock()
mock_container.user_repo = AsyncMock()
mock_container.rule_management_service = AsyncMock()
mock_container.rule_query_service = AsyncMock()

sys.modules["core.container"] = MagicMock()
sys.modules["core.container"].container = mock_container
sys.modules["core.container"].get_container = lambda: mock_container

# Mock web_admin 完全禁用 FastAPI 初始化
sys.modules["web_admin"] = MagicMock()
sys.modules["web_admin.fastapi_app"] = MagicMock()
sys.modules["web_admin.fastapi_app"].app = MagicMock()

import pytest


# 覆盖全局 conftest 的 fixtures
@pytest.fixture(scope="session")
def event_loop():
    """事件循环 fixture"""
    import asyncio
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
def setup_database():
    """禁用数据库初始化"""
    yield


@pytest.fixture
def clear_data():
    """禁用数据清理"""
    yield


@pytest.fixture
def client():
    """禁用 HTTP 客户端"""
    yield MagicMock()


@pytest.fixture
def db():
    """禁用数据库会话"""
    yield AsyncMock()
