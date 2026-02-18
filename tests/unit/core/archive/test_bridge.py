"""
P6-1/P6-2: UnifiedQueryBridge 单元测试 + 集成测试
覆盖：热冷联合查询、降级逻辑、query_aggregate、空冷库处理
"""
import pytest
import os
import sys
import glob
import tempfile
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch, AsyncMock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', '..'))

from core.archive.bridge import UnifiedQueryBridge


# ─────────────────────────────────────────────
# UnifiedQueryBridge 单元测试
# ─────────────────────────────────────────────

class TestUnifiedQueryBridgeUnit:

    @pytest.fixture
    def bridge(self):
        with patch("core.archive.bridge.settings") as mock_settings:
            mock_settings.DB_PATH = "sqlite+aiosqlite:///data/db/forward.db"
            mock_settings.ARCHIVE_QUERY_DEBUG = False
            with patch("repositories.archive_store.ARCHIVE_ROOT", "/tmp/archive"):
                b = UnifiedQueryBridge()
                b.db_path = "data/db/forward.db"
                b.archive_root = "/tmp/archive"
                return b

    def test_get_connection_lazy_init(self, bridge):
        """_get_connection 应懒初始化 DuckDB 连接"""
        assert bridge._con is None
        with patch("core.archive.bridge.duckdb") as mock_duckdb:
            mock_con = MagicMock()
            mock_duckdb.connect.return_value = mock_con
            con = bridge._get_connection()
            assert con is mock_con
            assert bridge._con is mock_con
            # 第二次调用应复用同一连接
            con2 = bridge._get_connection()
            assert con2 is mock_con
            mock_duckdb.connect.assert_called_once()

    @pytest.mark.asyncio
    async def test_query_unified_hot_only_when_no_cold(self, bridge):
        """当没有 Parquet 文件时，应仅查询热数据"""
        bridge.archive_root = "/nonexistent/path"

        mock_con = MagicMock()
        mock_con.execute.return_value = mock_con
        mock_con.fetchall.return_value = [(1, "test")]
        mock_con.description = [("id",), ("name",)]
        bridge._con = mock_con

        with patch("glob.glob", return_value=[]):  # 没有 Parquet 文件
            result = await bridge.query_unified("task_queue", "1=1", [], limit=10)

        # 应该只查询 SQLite（不包含 UNION ALL）
        call_args = mock_con.execute.call_args[0][0]
        assert "UNION ALL" not in call_args
        assert "sqlite_scan" in call_args

    @pytest.mark.asyncio
    async def test_query_unified_fallback_on_error(self, bridge):
        """联合查询失败时应降级为仅热数据查询"""
        mock_con = MagicMock()
        # 第一次调用（联合查询）抛出异常
        # 第二次调用（仅热数据）成功
        mock_con.execute.side_effect = [
            Exception("Parquet read error"),
            mock_con
        ]
        mock_con.fetchall.return_value = [(1, "test")]
        mock_con.description = [("id",)]
        bridge._con = mock_con

        with patch("glob.glob", return_value=["/some/file.parquet"]):
            result = await bridge.query_unified("task_queue", "1=1", [], limit=10)

        # 降级后应该成功返回结果
        assert isinstance(result, list)

    @pytest.mark.asyncio
    async def test_query_unified_use_hot_only(self, bridge):
        """use_cold=False 时应只查询热数据"""
        mock_con = MagicMock()
        mock_con.execute.return_value = mock_con
        mock_con.fetchall.return_value = []
        mock_con.description = []
        bridge._con = mock_con

        await bridge.query_unified("task_queue", "1=1", [], use_hot=True, use_cold=False)

        call_args = mock_con.execute.call_args[0][0]
        assert "UNION ALL" not in call_args
        assert "sqlite_scan" in call_args

    @pytest.mark.asyncio
    async def test_query_unified_use_cold_only(self, bridge):
        """use_hot=False 时应只查询冷数据"""
        mock_con = MagicMock()
        mock_con.execute.return_value = mock_con
        mock_con.fetchall.return_value = []
        mock_con.description = []
        bridge._con = mock_con

        with patch("glob.glob", return_value=["/fake.parquet"]):
            await bridge.query_unified("task_queue", "1=1", [], use_hot=False, use_cold=True)

        call_args = mock_con.execute.call_args[0][0]
        assert "sqlite_scan" not in call_args
        assert "read_parquet" in call_args

    @pytest.mark.asyncio
    async def test_query_unified_both_disabled_returns_empty(self, bridge):
        """use_hot=False, use_cold=False 时应返回空列表"""
        result = await bridge.query_unified("task_queue", "1=1", [], use_hot=False, use_cold=False)
        assert result == []

    @pytest.mark.asyncio
    async def test_get_task_detail_found(self, bridge):
        """get_task_detail 找到记录时应返回字典"""
        mock_con = MagicMock()
        mock_con.execute.return_value = mock_con
        mock_con.fetchall.return_value = [(42, "forward", "completed")]
        mock_con.description = [("id",), ("task_type",), ("status",)]
        bridge._con = mock_con

        with patch("glob.glob", return_value=[]):
            result = await bridge.get_task_detail(42)

        assert result is not None
        assert result["id"] == 42
        assert result["task_type"] == "forward"

    @pytest.mark.asyncio
    async def test_get_task_detail_not_found(self, bridge):
        """get_task_detail 找不到记录时应返回 None"""
        mock_con = MagicMock()
        mock_con.execute.return_value = mock_con
        mock_con.fetchall.return_value = []
        mock_con.description = []
        bridge._con = mock_con

        with patch("glob.glob", return_value=[]):
            result = await bridge.get_task_detail(99999)

        assert result is None

    @pytest.mark.asyncio
    async def test_list_tasks_with_filters(self, bridge):
        """list_tasks 应正确传递 status 和 task_type 过滤条件"""
        mock_con = MagicMock()
        mock_con.execute.return_value = mock_con
        mock_con.fetchall.return_value = []
        mock_con.description = []
        bridge._con = mock_con

        with patch("glob.glob", return_value=[]):
            await bridge.list_tasks(status="completed", task_type="forward")

        call_args = mock_con.execute.call_args[0][0]
        assert "status = ?" in call_args
        assert "task_type = ?" in call_args

    @pytest.mark.asyncio
    async def test_query_aggregate_no_cold_data(self, bridge):
        """query_aggregate 在没有冷数据时应仅查询热数据"""
        bridge.archive_root = "/nonexistent"

        mock_con = MagicMock()
        mock_con.execute.return_value = mock_con
        mock_con.fetchall.return_value = [(10,)]
        mock_con.description = [("count",)]
        bridge._con = mock_con

        with patch("glob.glob", return_value=[]):
            sql = "SELECT COUNT(*) as count FROM {table}"
            result = await bridge.query_aggregate("rule_logs", sql)

        assert isinstance(result, list)


# ─────────────────────────────────────────────
# UnifiedQueryBridge 集成测试（真实 DuckDB + Parquet）
# ─────────────────────────────────────────────

class TestUnifiedQueryBridgeIntegration:
    """使用真实 DuckDB 和临时 Parquet 文件的集成测试"""

    @pytest.fixture
    def temp_archive(self, tmp_path):
        return str(tmp_path / "archive")

    @pytest.fixture
    def temp_sqlite(self, tmp_path):
        """创建临时 SQLite 数据库"""
        import sqlite3
        db_path = str(tmp_path / "test.db")
        conn = sqlite3.connect(db_path)
        conn.execute("""
            CREATE TABLE rule_logs (
                id INTEGER PRIMARY KEY,
                rule_id INTEGER,
                action TEXT,
                created_at TEXT
            )
        """)
        # 插入热数据（近 3 天）
        new_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        for i in range(5):
            conn.execute("INSERT INTO rule_logs VALUES (?, ?, ?, ?)",
                         (i + 1, 1, "forward", new_time))
        conn.commit()
        conn.close()
        return db_path

    @pytest.fixture
    def cold_parquet(self, temp_archive):
        """创建冷数据 Parquet 文件"""
        from repositories.archive_store import write_parquet
        old_time = (datetime.now() - timedelta(days=10)).strftime("%Y-%m-%d %H:%M:%S")
        rows = [{"id": 100 + i, "rule_id": 1, "action": "forward", "created_at": old_time}
                for i in range(3)]
        with patch("repositories.archive_store.ARCHIVE_ROOT", temp_archive):
            write_parquet("rule_logs", rows, datetime.now() - timedelta(days=10))
        return temp_archive

    @pytest.mark.asyncio
    async def test_query_cold_parquet_data(self, cold_parquet):
        """应能从 Parquet 文件查询冷数据"""
        import duckdb
        parquet_files = glob.glob(
            os.path.join(cold_parquet, "rule_logs", "**", "*.parquet"), recursive=True
        )
        assert len(parquet_files) > 0, "冷数据 Parquet 文件应存在"

        con = duckdb.connect(":memory:")
        count = con.execute(
            f"SELECT COUNT(*) FROM read_parquet('{parquet_files[0]}')"
        ).fetchone()[0]
        con.close()
        assert count == 3, f"冷数据应有 3 条，实际: {count}"

    @pytest.mark.asyncio
    async def test_hot_cold_union_query(self, temp_sqlite, cold_parquet):
        """热冷联合查询应返回两个数据源的合并结果"""
        import duckdb
        parquet_pattern = os.path.join(cold_parquet, "rule_logs", "**", "*.parquet").replace("\\", "/")

        con = duckdb.connect(":memory:")
        con.execute("INSTALL sqlite; LOAD sqlite;")

        db_path_safe = temp_sqlite.replace("\\", "/")
        sql = f"""
            SELECT COUNT(*) as total FROM (
                SELECT id FROM sqlite_scan('{db_path_safe}', 'rule_logs')
                UNION ALL
                SELECT id FROM read_parquet('{parquet_pattern}', union_by_name=true)
            )
        """
        result = con.execute(sql).fetchone()[0]
        con.close()

        # 热数据 5 条 + 冷数据 3 条 = 8 条
        assert result == 8, f"联合查询应返回 8 条记录，实际: {result}"
