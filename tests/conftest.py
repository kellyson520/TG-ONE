"""
测试全局 conftest.py
采用延迟加载策略，避免在模块导入时阻塞测试收集
"""
import sys
import os
import logging
from pathlib import Path

# 确保项目根目录在 sys.path 最前面
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)

# ============================================================
# PHASE 0: 预导入关键包 & Patch 核心基础设施
# ============================================================
def _patch_database_engine_early():
    """迫使数据库引擎在任何业务代码导入前被 Patch"""
    try:
        import models.models
        import core.db_factory
        from sqlalchemy import create_engine
        from sqlalchemy.ext.asyncio import create_async_engine
        from sqlalchemy.pool import StaticPool
        
        # 使用共享缓存的命名内存数据库，确保 sync 和 async 共享同一个 DB
        test_url_sync = "sqlite:///file:testdb_early?mode=memory&cache=shared&uri=true"
        test_url_async = "sqlite+aiosqlite:///file:testdb_early?mode=memory&cache=shared&uri=true"
        
        sync_engine = create_engine(
            test_url_sync,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool
        )
        
        # 预先创建所有表
        models.models.Base.metadata.create_all(sync_engine)
        
        def mock_get_engine(): return sync_engine
        def mock_get_async_engine(readonly=False):
            return create_async_engine(
                test_url_async, 
                echo=False, 
                connect_args={"check_same_thread": False},
                poolclass=StaticPool
            )
        
        core.db_factory.get_engine = mock_get_engine
        core.db_factory.get_async_engine = mock_get_async_engine
        core.db_factory.DbFactory.get_engine = mock_get_engine
        core.db_factory.DbFactory.get_async_engine = mock_get_async_engine
        return True
    except Exception as e:
        print(f"CRITICAL: Failed early engine patch: {e}")
        return False

# 立即执行 Patch
_engine_patched_early = _patch_database_engine_early()

try:
    import web_admin  # noqa: F401
except ImportError as e:
    print(f"WARNING: Failed to pre-import web_admin: {e}")

from unittest.mock import MagicMock
import unittest.mock

# ============================================================
# PHASE 1: Mock 缺失的 C 扩展库 (在任何导入之前)
# ============================================================
for lib in ["rapidfuzz", "numba", "duckdb", "pyarrow", "uvloop", "pandas", "apprise"]:
    sys.modules[lib] = MagicMock()
    sys.modules[f"{lib}.fuzz"] = MagicMock()

# Mock 缺失的底层工具 (更新路径以匹配重构后的 fastapi_app.py)
for m in ["core.helpers.realtime_stats", "services.network.bot_heartbeat", "core.helpers.env_config"]:
    sys.modules[m] = unittest.mock.MagicMock()

# Mock decorator 类的工具
def mock_decorator(*args, **kwargs):
    def wrapper(f):
        return f
    return wrapper

mock_err = unittest.mock.MagicMock()
mock_err.handle_errors = mock_decorator
mock_err.log_execution = mock_decorator
sys.modules["core.helpers.error_handler"] = mock_err

# ============================================================
# PHASE 2: Mock 核心配置 (settings)
# ============================================================
mock_settings = MagicMock()
mock_settings.DATABASE_URL = "sqlite+aiosqlite:///:memory:"
mock_settings.APP_ENV = "testing"
mock_settings.DEFAULT_MAX_MEDIA_SIZE = 100
mock_settings.RSS_SECRET_KEY = "test_secret"
mock_settings.DEFAULT_SUMMARY_TIME = "20:00"
mock_settings.DB_POOL_SIZE = 5
mock_settings.DB_MAX_OVERFLOW = 10
mock_settings.DB_ECHO = False
mock_settings.DB_POOL_TIMEOUT = 30
mock_settings.DB_POOL_RECYCLE = 3600
mock_settings.DB_POOL_PRE_PING = True
mock_settings.DB_PATH = "db/test_forward.db"
mock_settings.RSS_ENABLED = False
mock_settings.RSS_MEDIA_DIR = Path("./temp_rss_media")
mock_settings.USER_MESSAGE_DELETE_ENABLE = False
mock_settings.BOT_MESSAGE_DELETE_TIMEOUT = 300
mock_settings.DB_DIR = Path("./temp_test_db")
if not mock_settings.DB_DIR.exists():
    mock_settings.DB_DIR.mkdir(parents=True, exist_ok=True)

# JWT Settings
mock_settings.SECRET_KEY = "test_jwt_secret"
mock_settings.ALGORITHM = "HS256"
mock_settings.ACCESS_TOKEN_EXPIRE_MINUTES = 30
mock_settings.REFRESH_TOKEN_EXPIRE_DAYS = 7

config_mock = MagicMock()
config_mock.settings = mock_settings
try:
    # 尝试获取真实的 Settings 类以供单元测试使用
    import core.config as real_config
    config_mock.Settings = real_config.Settings
except Exception:
    pass
# sys.modules["core.config"] = config_mock  <-- This was breaking core.config.settings_loader imports
import core.config
# Instead of replacing settings, we update the existing object to avoid reference issues
for key, value in mock_settings.__dict__.items():
    if not key.startswith('_') and key.isupper():
        try:
            setattr(core.config.settings, key, value)
        except Exception:
            pass
# Ensure SECRET_KEY and other critical ones are definitely set
core.config.settings.SECRET_KEY = "test_jwt_secret"
core.config.settings.ALGORITHM = "HS256"
core.config.settings.DATABASE_URL = "sqlite+aiosqlite:///file:testdb_early?mode=memory&cache=shared&uri=true"


# # Mock 暂时不需要测试且存在导入错误的业务模块
# for module in [
#     "services.download_service", 
#     "services.worker_service", 
#     "scheduler.summary_scheduler",
#     "scheduler.optimized_chat_updater",
#     "core.helpers.media.media",
#     "core.helpers.tombstone"
# ]:
#     if module not in sys.modules:
#         sys.modules[module] = MagicMock()

# ============================================================
# PHASE 3: 设置环境变量和基础导入
# ============================================================
import asyncio
import pytest

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["APP_ENV"] = "testing"

# ============================================================
# PHASE 4: 延迟加载重量级模块
# 使用函数封装，只在需要时才导入
# ============================================================

# 缓存变量
_container = None
_app = None
_Base = None
_engine_patched = False


def get_container():
    """延迟获取 container 实例"""
    global _container
    if _container is None:
        try:
            from core.container import container
            _container = container
            if hasattr(_container, 'db') and hasattr(_container.db, 'engine'):
                _container.db.engine.echo = False
        except Exception as e:
            logging.warning(f"获取 container 失败: {e}")
            import traceback
            logging.warning(traceback.format_exc())
            _container = MagicMock()
    return _container


def get_app():
    """延迟获取 FastAPI app 实例"""
    global _app
    if _app is None:
        from web_admin.fastapi_app import app
        _app = app
    return _app


def get_base():
    """延迟获取 SQLAlchemy Base"""
    global _Base
    if _Base is None:
        from models.models import Base
        _Base = Base
    return _Base


# ============================================================
# PHASE 5: Pytest Fixtures (使用延迟加载)
# ============================================================

@pytest.fixture(scope="session")
def event_loop():
    """创建事件循环"""
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session")
async def setup_database():
    """
    数据库初始化 fixture
    注意：不再使用 autouse=True，只有需要数据库的测试才会触发
    """
    container = get_container()
    Base = get_base()
    
    if container is None or Base is None:
        logging.warning("跳过数据库初始化 (container 或 Base 不可用)")
        yield
        return
    
    try:
        engine = container.db.engine
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        yield
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.drop_all)
    except Exception as e:
        logging.warning(f"数据库初始化失败: {e}")
        yield


@pytest.fixture
async def clear_data(setup_database):
    """
    清理数据 fixture
    依赖 setup_database，确保数据库已初始化
    """
    yield
    
    container = get_container()
    Base = get_base()
    
    if container is None or Base is None:
        return
    
    try:
        engine = container.db.engine
        async with engine.begin() as conn:
            for table in reversed(Base.metadata.sorted_tables):
                await conn.execute(table.delete())
    except Exception as e:
        logging.warning(f"清理数据失败: {e}")


@pytest.fixture
async def client(setup_database):
    """
    HTTP 客户端 fixture
    依赖 setup_database，确保数据库已初始化
    """
    from httpx import AsyncClient, ASGITransport
    
    app = get_app()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
async def db(setup_database):
    """
    数据库会话 fixture
    依赖 setup_database，确保数据库已初始化
    """
    container = get_container()
    async with container.db.session_factory() as session:
        yield session


@pytest.fixture
def container():
    """Container fixture"""
    return get_container()


# ============================================================
# 向后兼容：暴露变量供旧代码使用
# 注意：这些变量在首次访问时才会初始化
# ============================================================
class _LazyLoader:
    """延迟加载器，避免在模块导入时执行重量级操作"""
    
    @property
    def container(self):
        return get_container()
    
    @property
    def app(self):
        return get_app()
    
    @property
    def Base(self):
        return get_base()


_lazy = _LazyLoader()

# 这些变量仍然可用，但只在首次访问时才初始化
# 使用 __getattr__ 实现延迟加载
def __getattr__(name):
    if name == 'container':
        return get_container()
    elif name == 'app':
        return get_app()
    elif name == 'Base':
        return get_base()
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
