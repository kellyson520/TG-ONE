from core.helpers.lazy_import import LazyImport
duckdb = LazyImport("duckdb")
import logging
from core.config import settings

logger = logging.getLogger(__name__)


def _duckdb_string_literal(value: str) -> str:
    """Properly escape a value for use inside a DuckDB single-quoted string literal."""
    return "'" + str(value).replace("\\", "\\\\").replace("'", "''") + "'"


def configure_httpfs_and_s3(con: "duckdb.DuckDBPyConnection") -> None:
    """按需启用 httpfs 并配置 S3 访问。"""
    try:
        logger.debug("安装并加载 httpfs 扩展")
        con.execute("INSTALL httpfs; LOAD httpfs;")
    except Exception as e:
        logger.warning(f"安装或加载 httpfs 扩展失败: {e}")
        logger.debug("安装或加载 httpfs 扩展失败详细信息", exc_info=True)
        return
    from repositories.archive_store import ARCHIVE_ROOT
    root = ARCHIVE_ROOT.lower()
    if not (
        root.startswith("s3://")
        or root.startswith("http://")
        or root.startswith("https://")
    ):
        logger.debug("归档根路径不是 S3/HTTP(S)，跳过 S3 配置")
        return
    try:
        logger.debug("配置 S3 访问参数")
        region = settings.AWS_REGION or settings.S3_REGION
        if region:
            logger.debug(f"设置 S3 区域: {region}")
            con.execute(f"SET s3_region={_duckdb_string_literal(region)};")
        endpoint = settings.S3_ENDPOINT
        if endpoint:
            logger.debug(f"设置 S3 endpoint: {endpoint}")
            con.execute(f"SET s3_endpoint={_duckdb_string_literal(endpoint)};")
        ak = settings.AWS_ACCESS_KEY_ID
        sk = settings.AWS_SECRET_ACCESS_KEY
        st = settings.AWS_SESSION_TOKEN
        if ak and sk:
            logger.debug("设置 S3 访问密钥")
            con.execute(f"SET s3_access_key_id={_duckdb_string_literal(ak)};")
            con.execute(f"SET s3_secret_access_key={_duckdb_string_literal(sk)};")
        if st:
            logger.debug("设置 S3 会话令牌")
            con.execute(f"SET s3_session_token={_duckdb_string_literal(st)};")
        verify = settings.S3_SSL_ENABLE
        logger.debug(f"设置 S3 SSL 验证: {verify}")
        con.execute(f"SET s3_use_ssl={'true' if verify else 'false'};")
    except Exception as e:
        logger.warning(f"S3 配置失败: {e}")
        logger.debug("S3 配置失败详细信息", exc_info=True)


def configure_duckdb_resource_limits(
    con: "duckdb.DuckDBPyConnection", context: str
) -> None:
    """按配置限制 DuckDB 资源；失败只降级并记录原因。"""
    try:
        threads = int(settings.DUCKDB_THREADS)
        con.execute(f"PRAGMA threads={max(1, threads)}")
    except Exception as e:
        logger.warning(f"配置 DuckDB 线程数失败: context={context}, error={e}")
        logger.debug("配置 DuckDB 线程数失败详细信息", exc_info=True)

    try:
        mem_limit = settings.DUCKDB_MEMORY_LIMIT
        if mem_limit:
            safe_mem_limit = str(mem_limit).replace("'", "''")
            con.execute(f"PRAGMA memory_limit='{safe_mem_limit}'")
    except Exception as e:
        logger.warning(f"配置 DuckDB 内存限制失败: context={context}, error={e}")
        logger.debug("配置 DuckDB 内存限制失败详细信息", exc_info=True)


# ---------------------------------------------------------------------------
# Shared DuckDB in-memory connection (lazy singleton)
# ---------------------------------------------------------------------------
_duckdb_conn = None


def get_connection() -> "duckdb.DuckDBPyConnection":
    """Return a shared DuckDB in-memory connection, configured once."""
    global _duckdb_conn
    if _duckdb_conn is None:
        _duckdb_conn = duckdb.connect(database=":memory:")
        configure_duckdb_resource_limits(_duckdb_conn, context="shared_connection")
        configure_httpfs_and_s3(_duckdb_conn)
        logger.debug("已创建共享 DuckDB 内存连接")
    return _duckdb_conn
