from typing import List, Dict, Any, Optional, Union
import logging
from datetime import datetime, timedelta
from core.helpers.lazy_import import LazyImport
duckdb = LazyImport("duckdb")
from core.config import settings
from repositories.archive_store import ARCHIVE_ROOT, _configure_httpfs_and_s3

logger = logging.getLogger(__name__)

class UnifiedQueryBridge:
    """热冷统一查询桥接器，使用 DuckDB 联邦查询 SQLite 和 Parquet。"""

    def __init__(self):
        self.db_path = str(settings.DB_PATH.replace("sqlite+aiosqlite:///", "")).replace("\\", "/")
        self.archive_root = str(ARCHIVE_ROOT).replace("\\", "/")
        self._con = None

    def _get_connection(self):
        if self._con is None:
            self._con = duckdb.connect(database=':memory:')
            # 配置 S3/HTTP 访问
            _configure_httpfs_and_s3(self._con)
            # 安装并加载 sqlite 扩展
            self._con.execute("INSTALL sqlite; LOAD sqlite;")
        return self._con

    async def query_aggregate(
        self,
        table_name: str,
        sql_template: str,
        params: List[Any] = None,
        use_hot: bool = True,
        use_cold: bool = True
    ) -> List[Dict[str, Any]]:
        """跨热冷数据库执行聚合查询 (如 COUNT, SUM)"""
        con = self._get_connection()
        params = params or []
        
        sqlite_table = f"sqlite_scan('{self.db_path}', '{table_name}')"
        parquet_path = f"{self.archive_root}/{table_name}/**/*.parquet"
        
        # 确定可用数据源
        has_cold = False
        if use_cold:
            if self.archive_root.startswith("s3://") or "://" in self.archive_root:
                has_cold = True
            else:
                import glob
                if glob.glob(parquet_path, recursive=True):
                    has_cold = True
        
        if not use_hot and not has_cold:
            # 如果请求了冷库但没有文件，且没请求热库，直接返回空
            if use_cold and not use_hot:
                return []
            # 如果既没请求热库也没请求冷库
            if not use_hot and not use_cold:
                return []
            # 其他情况（如只请求了热库但 use_hot=False，其实已经包含在上面了）
            return []

        combined_table = ""
        if use_hot and has_cold:
            combined_table = f"(SELECT * FROM {sqlite_table} UNION ALL BY NAME SELECT * FROM read_parquet('{parquet_path}', union_by_name=true))"
        elif use_hot:
            combined_table = sqlite_table
        elif has_cold:
            combined_table = f"read_parquet('{parquet_path}', union_by_name=true)"
        
        final_query = sql_template.replace("{table}", combined_table)
        
        try:
            if settings.ARCHIVE_QUERY_DEBUG:
                logger.debug(f"[UnifiedQueryBridge] Aggregate SQL: {final_query} | Params: {params}")
            
            res = con.execute(final_query, params).fetchall()
            cols = [desc[0] for desc in con.description]
            return [dict(zip(cols, row)) for row in res]
        except Exception as e:
            logger.error(f"[UnifiedQueryBridge] 聚合查询失败: {e}", exc_info=True)
            # 降级：如果联合查询失败，尝试仅热数据 (仅当允许热数据且之前尝试过联合查询时)
            if use_cold and use_hot and has_cold:
                logger.info("[UnifiedQueryBridge] 聚合联合查询失败，降级为仅热数据...")
                return await self.query_aggregate(table_name, sql_template, params, use_hot=True, use_cold=False)
            return []

    async def query_unified(
        self,
        table_name: str,
        where_sql: str = "1=1",
        params: List[Any] = None,
        limit: int = 50,
        offset: int = 0,
        order_by: str = "created_at DESC",
        use_hot: bool = True,
        use_cold: bool = True
    ) -> List[Dict[str, Any]]:
        """基础统一查询 (复用 query_aggregate)"""
        sql = f"SELECT * FROM {{table}} WHERE {where_sql} ORDER BY {order_by} LIMIT {limit} OFFSET {offset}"
        return await self.query_aggregate(table_name, sql, params, use_hot, use_cold)

    async def get_task_detail(self, task_id: int) -> Optional[Dict[str, Any]]:
        """获取任务详情 (跨热冷)"""
        res = await self.query_unified("task_queue", "id = ?", [task_id], limit=1)
        return res[0] if res else None

    async def list_tasks(self, status: str = None, task_type: str = None, limit: int = 50, offset: int = 0) -> List[Dict[str, Any]]:
        """列表查询任务 (跨热冷)"""
        where_clauses = ["1=1"]
        params = []
        if status:
            where_clauses.append("status = ?")
            params.append(status)
        if task_type:
            where_clauses.append("task_type = ?")
            params.append(task_type)
            
        return await self.query_unified("task_queue", " AND ".join(where_clauses), params, limit, offset)

    async def list_audit_logs(
        self, 
        user_id: int = None, 
        action: str = None, 
        limit: int = 50, 
        offset: int = 0
    ) -> List[Dict[str, Any]]:
        """列表查询审计日志 (跨热冷)"""
        where_clauses = ["1=1"]
        params = []
        if user_id:
            where_clauses.append("user_id = ?")
            params.append(user_id)
        if action:
            where_clauses.append("action = ?")
            params.append(action)
            
        return await self.query_unified(
            "audit_logs", 
            " AND ".join(where_clauses), 
            params, 
            limit, 
            offset, 
            order_by="timestamp DESC"
        )
