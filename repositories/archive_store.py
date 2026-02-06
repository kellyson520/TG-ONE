from core.helpers.lazy_import import LazyImport
duckdb = LazyImport("duckdb")
import logging
import os
import glob
import shutil
import tempfile
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)
from typing import Any, Dict, List, Optional, Tuple

from core.config import settings

# 归档根路径
ARCHIVE_ROOT = str(settings.ARCHIVE_ROOT)

# Parquet 写入选项
_PARQUET_COMPRESSION = settings.ARCHIVE_PARQUET_COMPRESSION.upper()
_ROW_GROUP_SIZE_INT = settings.ARCHIVE_PARQUET_ROW_GROUP_SIZE
_QUERY_DEBUG = settings.ARCHIVE_QUERY_DEBUG


def _ensure_dir(path: str) -> None:
    """确保目录存在，如果创建失败则记录错误"""
    try:
        os.makedirs(path, exist_ok=True)
        logger.debug(f"确保目录存在: {path}")
    except Exception as e:
        logger.error(f"创建目录失败 {path}: {e}")
        logger.debug("创建目录失败详细信息", exc_info=True)
        raise


def _configure_httpfs_and_s3(con: "duckdb.DuckDBPyConnection") -> None:
    """按需启用 httpfs 并配置 S3 访问。
    通过环境变量传入凭据：
      - AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY / AWS_SESSION_TOKEN
      - AWS_REGION or S3_REGION
      - S3_ENDPOINT (可选，兼容 MinIO 等)
    """
    try:
        logger.debug("安装并加载 httpfs 扩展")
        con.execute("INSTALL httpfs; LOAD httpfs;")
    except Exception as e:
        logger.warning(f"安装或加载 httpfs 扩展失败: {e}")
        logger.debug("安装或加载 httpfs 扩展失败详细信息", exc_info=True)
        return
    # 仅当归档根为 S3/HTTP(S) 时设置参数
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
        # 区域
        region = settings.AWS_REGION or settings.S3_REGION
        if region:
            logger.debug(f"设置 S3 区域: {region}")
            con.execute(f"SET s3_region='{region}';")
        # endpoint（如 MinIO）
        endpoint = settings.S3_ENDPOINT
        if endpoint:
            logger.debug(f"设置 S3 endpoint: {endpoint}")
            con.execute(f"SET s3_endpoint='{endpoint}';")
        # 凭据
        ak = settings.AWS_ACCESS_KEY_ID
        sk = settings.AWS_SECRET_ACCESS_KEY
        st = settings.AWS_SESSION_TOKEN
        if ak and sk:
            logger.debug("设置 S3 访问密钥")
            con.execute(f"SET s3_access_key_id='{ak}';")
            con.execute(f"SET s3_secret_access_key='{sk}';")
        if st:
            logger.debug("设置 S3 会话令牌")
            con.execute(f"SET s3_session_token='{st}';")
        # 允许 SSL 验证开关（默认开启）
        verify = settings.S3_SSL_ENABLE
        logger.debug(f"设置 S3 SSL 验证: {verify}")
        con.execute(f"SET s3_use_ssl={'true' if verify else 'false'};")
    except Exception as e:
        logger.warning(f"S3 配置失败: {e}")
        logger.debug("S3 配置失败详细信息", exc_info=True)


def _partition_path(table: str, dt: datetime) -> str:
    year = dt.strftime("%Y")
    month = dt.strftime("%m")
    day = dt.strftime("%d")
    # 兼容对象存储/URL 风格根路径（如 s3://bucket/prefix）
    if ARCHIVE_ROOT.startswith("s3://") or "://" in ARCHIVE_ROOT:
        base = ARCHIVE_ROOT.rstrip("/")
        return f"{base}/{table}/year={year}/month={month}/day={day}"
    return os.path.join(
        ARCHIVE_ROOT, table, f"year={year}", f"month={month}", f"day={day}"
    )


def write_parquet(
    table: str, rows: List[Dict[str, Any]], partition_dt: Optional[datetime] = None
) -> str:
    logger.debug(f"开始写入 Parquet 文件: table={table}, rows={len(rows)}")

    if not rows:
        logger.debug("没有数据需要写入")
        return ""
    if partition_dt is None:
        partition_dt = datetime.utcnow()
    out_dir = _partition_path(table, partition_dt)
    logger.debug(f"输出目录: {out_dir}")
    _ensure_dir(out_dir)

    # 如数据量过大，分块写入以降低峰值内存占用
    chunk_size = settings.ARCHIVE_WRITE_CHUNK_SIZE

    if len(rows) > chunk_size:
        logger.debug(f"数据量 {len(rows)} 超过分块大小 {chunk_size}，进行分块写入")
        start = 0
        chunk_index = 0
        while start < len(rows):
            end = min(start + chunk_size, len(rows))
            logger.debug(f"写入分块 {chunk_index}: {start}-{end}")
            _write_parquet_chunk(out_dir, rows[start:end])
            start = end
            chunk_index += 1
        # 校验至少生成了一个 parquet 文件
        try:
            import glob as _glob

            files = _glob.glob(os.path.join(out_dir, "*.parquet"))
            logger.debug(f"生成的 Parquet 文件: {len(files)} 个")
            if not files:
                logger.error("未生成任何 Parquet 文件")
                return ""
        except Exception as e:
            logger.error(f"校验 Parquet 文件时出错: {e}")
            logger.debug("校验 Parquet 文件详细信息", exc_info=True)
            return ""
        logger.debug(f"分块写入完成，输出目录: {out_dir}")
        return out_dir

    import random
    fname = f"part-{int(datetime.utcnow().timestamp())}-{int(datetime.utcnow().microsecond)}-{os.getpid()}-{random.randint(1000, 9999)}.parquet"
    out_file = os.path.normpath(os.path.join(out_dir, fname))
    
    # 策略：先写入系统临时目录，再移动到目标目录
    temp_fd, local_tmp_path = tempfile.mkstemp(suffix=".parquet.tmp")
    os.close(temp_fd)
    
    safe_tmp_path = local_tmp_path.replace("\\", "/").replace("'", "''")
    logger.debug(f"输出文件: {out_file}, 临时文件: {local_tmp_path}, DuckDB 路径: {safe_tmp_path}")

    try:
        con = duckdb.connect(database=":memory:")
        try:
            logger.debug("配置 DuckDB 连接")
            # 提升并行与扩展性：启用多核并行、向量化、内存限制与临时目录
            try:
                threads = settings.DUCKDB_THREADS
                logger.debug(f"设置 DuckDB 线程数: {threads}")
                con.execute(f"PRAGMA threads={max(1, threads)}")
            except Exception as e:
                logger.warning(f"设置 DuckDB 线程数时出错: {e}")
                logger.debug("设置 DuckDB 线程数详细信息", exc_info=True)
            try:
                mem_limit = settings.DUCKDB_MEMORY_LIMIT
                if mem_limit:
                    logger.debug(f"设置 DuckDB 内存限制: {mem_limit}")
                    con.execute(f"PRAGMA memory_limit='{mem_limit}'")
            except Exception as e:
                logger.warning(f"设置 DuckDB 内存限制时出错: {e}")
                logger.debug("设置 DuckDB 内存限制详细信息", exc_info=True)
            # S3/httpfs 支持（如需直接写云存储，由上层传入 s3 路径）
            _configure_httpfs_and_s3(con)

            # 方案A：优先使用 pandas DataFrame，最稳定
            try:
                logger.debug(f"使用 pandas DataFrame 写入 Parquet: {safe_tmp_path}")
                import pandas as pd  # type: ignore

                df = pd.DataFrame(rows)
                con.register("df_rows", df)
                try:
                    if os.path.exists(local_tmp_path):
                        os.remove(local_tmp_path)
                    con.execute(
                        f"COPY df_rows TO '{safe_tmp_path}' (FORMAT PARQUET, COMPRESSION {_PARQUET_COMPRESSION}, ROW_GROUP_SIZE {_ROW_GROUP_SIZE_INT})"
                    )
                except Exception as e:
                    logger.warning(
                        f"使用 pandas DataFrame 写入 Parquet 时出错: {e}，尝试不指定压缩参数"
                    )
                    logger.debug(
                        "使用 pandas DataFrame 写入 Parquet 详细信息", exc_info=True
                    )
                    logger.debug(f"使用 pandas DataFrame 写入 Parquet (无压缩参数): {safe_tmp_path}")
                    if os.path.exists(local_tmp_path):
                        os.remove(local_tmp_path)
                    con.execute(f"COPY df_rows TO '{safe_tmp_path}' (FORMAT PARQUET)")
            except Exception as e:
                logger.warning(
                    f"使用 pandas DataFrame 时出错: {e}，尝试 DuckDB Python 对象扫描"
                )
                logger.debug("使用 pandas DataFrame 详细信息", exc_info=True)
                # 方案B：DuckDB Python 对象扫描
                try:
                    logger.debug("尝试使用 DuckDB Python 对象扫描")
                    con.execute("CREATE TABLE t AS SELECT * FROM rows", {"rows": rows})
                except Exception as e:
                    logger.warning(
                        f"使用 DuckDB Python 对象扫描时出错: {e}，尝试以 JSON 推断"
                    )
                    logger.debug("使用 DuckDB Python 对象扫描详细信息", exc_info=True)
                    # 方案C：以 JSON 推断
                    import json

                    logger.debug("尝试使用 JSON 推断")
                    con.execute(
                        "CREATE TABLE t AS SELECT * FROM read_json_auto(?)",
                        [json.dumps(rows)],
                    )
                try:
                    logger.debug(f"使用 DuckDB 写入 Parquet: {safe_tmp_path}")
                    if os.path.exists(local_tmp_path):
                        os.remove(local_tmp_path)
                    con.execute(
                        f"COPY t TO '{safe_tmp_path}' (FORMAT PARQUET, COMPRESSION {_PARQUET_COMPRESSION}, ROW_GROUP_SIZE {_ROW_GROUP_SIZE_INT})"
                    )
                except Exception as e:
                    logger.warning(
                        f"使用 DuckDB 写入 Parquet 时出错: {e}，尝试不指定压缩参数"
                    )
                    logger.debug("使用 DuckDB 写入 Parquet 详细信息", exc_info=True)
                    logger.debug(f"使用 DuckDB 写入 Parquet (无压缩参数): {safe_tmp_path}")
                    if os.path.exists(local_tmp_path):
                        os.remove(local_tmp_path)
                    con.execute(f"COPY t TO '{safe_tmp_path}' (FORMAT PARQUET)")
        finally:
            logger.debug("关闭 DuckDB 连接")
            con.close()

        # 如果临时文件仍然存在，移动它。
        # 注意：某些版本的 DuckDB 可能会在 COPY 时自己创建文件，
        # 我们之前用 mkstemp 创建了空文件，如果 DuckDB 报错没有写入，
        # 则可能会留下 0 字节文件。
        if os.path.exists(local_tmp_path) and os.path.getsize(local_tmp_path) == 0:
            logger.warning(f"检测到 0 字节临时文件: {local_tmp_path}, 视为写入失败")
            raise IOError("DuckDB COPY produced 0-byte file")

        # 移动临时文件到目标位置
        try:
            logger.debug(f"移动文件: {local_tmp_path} -> {out_file}")
            shutil.move(local_tmp_path, out_file)
        except Exception as e:
            logger.error(f"移动文件失败: {e}")
            raise e
        
        # 检查输出文件
        if not os.path.exists(out_file):
            raise IOError(f"目标文件不存在: {out_file}")

        logger.debug(f"写入 Parquet 文件完成: {out_dir}")
        return out_dir

    except Exception as e:
        # 全局异常捕获，清理残留的临时文件
        if 'local_tmp_path' in locals() and os.path.exists(local_tmp_path):
            try:
                logger.debug(f"发生异常，清理产生的临时文件: {local_tmp_path}")
                os.remove(local_tmp_path)
            except Exception as cleanup_error:
                logger.warning(f"清理临时文件失败: {cleanup_error}")
        
        if isinstance(e, IOError) and "目标文件不存在" in str(e):
             return "" # Return empty string on specific known failure if expected
        
        # 重新抛出异常以便上层感知
        raise e



def _write_parquet_chunk(out_dir: str, rows: List[Dict[str, Any]]) -> None:
    logger.debug(f"写入 Parquet 分块: out_dir={out_dir}, rows={len(rows)}")

    if not rows:
        logger.debug("没有数据需要写入")
        return
    import random
    fname = f"part-{int(datetime.utcnow().timestamp())}-{int(datetime.utcnow().microsecond)}-{os.getpid()}-{random.randint(1000, 9999)}.parquet"
    out_file = os.path.normpath(os.path.join(out_dir, fname))
    
    # 策略：先写入系统临时目录，再移动到目标目录
    temp_fd, local_tmp_path = tempfile.mkstemp(suffix=".parquet.tmp")
    os.close(temp_fd)
    
    safe_tmp_path = local_tmp_path.replace("\\", "/").replace("'", "''")
    logger.debug(f"输出文件: {out_file}, 临时文件: {local_tmp_path}, DuckDB 路径: {safe_tmp_path}")

    try:
        con = duckdb.connect(database=":memory:")

        try:
            logger.debug("配置 DuckDB 连接")
            try:
                threads = settings.DUCKDB_THREADS
                logger.debug(f"设置 DuckDB 线程数: {threads}")
                con.execute(f"PRAGMA threads={max(1, threads)}")
            except Exception as e:
                logger.warning(f"设置 DuckDB 线程数时出错: {e}")
                logger.debug("设置 DuckDB 线程数详细信息", exc_info=True)
            _configure_httpfs_and_s3(con)
            try:
                logger.debug("创建表并插入数据")
                con.execute("CREATE TABLE t AS SELECT * FROM rows", {"rows": rows})
            except Exception as e:
                logger.warning(f"创建表并插入数据时出错: {e}，尝试以 JSON 推断")
                logger.debug("创建表并插入数据详细信息", exc_info=True)
                import json

                con.execute(
                    "CREATE TABLE t AS SELECT * FROM read_json_auto(?)", [json.dumps(rows)]
                )

            logger.debug(f"写入 Parquet 文件: {safe_tmp_path}")
            con.execute(
                f"COPY t TO '{safe_tmp_path}' (FORMAT PARQUET, COMPRESSION {_PARQUET_COMPRESSION}, ROW_GROUP_SIZE {_ROW_GROUP_SIZE_INT})"
            )
        except Exception as e:
            logger.warning(f"写入 Parquet 文件时出错: {e}，尝试不指定压缩参数")
            logger.debug("写入 Parquet 文件详细信息", exc_info=True)
            try:
                logger.debug(f"写入 Parquet 文件 (无压缩参数): {safe_tmp_path}")
                con.execute(f"COPY t TO '{safe_tmp_path}' (FORMAT PARQUET)")
            except Exception as e:
                logger.error(f"写入 Parquet 文件也失败: {e}")
                logger.debug("写入 Parquet 文件详细信息", exc_info=True)
                raise e
        finally:
            logger.debug("关闭 DuckDB 连接")
            con.close()

        try:
            logger.debug(f"移动临时文件: {local_tmp_path} -> {out_file}")
            shutil.move(local_tmp_path, out_file)
        except Exception as e:
            logger.error(f"移动文件失败: {e}")
            if os.path.exists(local_tmp_path):
                os.remove(local_tmp_path)
            raise e

        logger.debug(f"写入 Parquet 分块完成: {out_file}")

    except Exception:
        # 全局异常捕获，清理残留的临时文件
        if 'local_tmp_path' in locals() and os.path.exists(local_tmp_path):
            try:
                logger.debug(f"发生异常，清理产生的临时文件: {local_tmp_path}")
                os.remove(local_tmp_path)
            except Exception as cleanup_error:
                logger.warning(f"清理临时文件失败: {cleanup_error}")
        raise



def query_parquet_duckdb(
    table: str,
    where_sql: str,
    params: List[Any],
    columns: Optional[List[str]] = None,
    limit: Optional[int] = 1,
    order_by: Optional[str] = None,
    distinct: bool = False,
    max_days: Optional[int] = None,
) -> List[Dict[str, Any]]:
    logger.debug(f"查询 Parquet 文件: table={table}")

    if ARCHIVE_ROOT.startswith("s3://") or "://" in ARCHIVE_ROOT:
        base = ARCHIVE_ROOT.rstrip("/")
        pattern = f"{base}/{table}/year=*/month=*/day=*/*.parquet"
    else:
        pattern = os.path.join(
            ARCHIVE_ROOT, table, "year=*", "month=*", "day=*", "*.parquet"
        )
    logger.debug(f"文件模式: {pattern}")
    # DuckDB 需要使用正斜杠路径
    pattern = pattern.replace("\\", "/")

    files_param: Optional[List[str]] = None
    # 限定最近 N 天文件，减少文件扫描
    if max_days and max_days > 0:
        logger.debug(f"限定最近 {max_days} 天的文件")
        try:
            cutoff = datetime.utcnow().date() - timedelta(days=int(max_days) - 1)
            files: List[str] = []
            # 枚举最近 N 天的分区（仅本地/挂载盘可用；S3 由 DuckDB 自行通配）
            if not (ARCHIVE_ROOT.startswith("s3://") or "://" in ARCHIVE_ROOT):
                for d in range(int(max_days)):
                    dt = datetime.utcnow().date() - timedelta(days=d)
                    pdir = os.path.join(
                        ARCHIVE_ROOT,
                        table,
                        f"year={dt.strftime('%Y')}",
                        f"month={dt.strftime('%m')}",
                        f"day={dt.strftime('%d')}",
                    )
                    logger.debug(f"扫描分区目录: {pdir}")
                    files.extend(glob.glob(os.path.join(pdir, "*.parquet")))
                if files:
                    files_param = [f.replace("\\", "/") for f in sorted(files)]
                    logger.debug(f"找到 {len(files_param)} 个文件")
            else:
                logger.debug("使用 S3/HTTP(S) 存储，跳过本地文件扫描")
        except Exception as e:
            logger.error(f"限定文件时出错: {e}")
            logger.debug("限定文件详细信息", exc_info=True)
            files_param = None
    # 若不存在任何归档文件，直接返回空
    if (
        not files_param
        and (not (ARCHIVE_ROOT.startswith("s3://") or "://" in ARCHIVE_ROOT))
        and not glob.glob(pattern)
    ):
        logger.debug("未找到任何归档文件")
        return []
    select_cols = "*" if not columns else ",".join(columns)
    sel_prefix = "SELECT DISTINCT" if distinct else "SELECT"
    if files_param:
        sql = f"{sel_prefix} {select_cols} FROM read_parquet(?) WHERE {where_sql}"
    else:
        sql = f"{sel_prefix} {select_cols} FROM read_parquet('{pattern}') WHERE {where_sql}"
    if order_by:
        sql += f" ORDER BY {order_by}"
    if limit is not None and limit > 0:
        sql += f" LIMIT {int(limit)}"
    logger.debug(f"查询 SQL: {sql}")
    if _QUERY_DEBUG:
        try:
            logger.debug(f"archive query: {sql} params={params}")
        except Exception as e:
            logger.warning(f"记录查询日志时出错: {e}")
            logger.debug("记录查询日志详细信息", exc_info=True)
    con = duckdb.connect(database=":memory:")
    try:
        logger.debug("配置 DuckDB 连接")
        try:
            threads = settings.DUCKDB_THREADS
            logger.debug(f"设置 DuckDB 线程数: {threads}")
            con.execute(f"PRAGMA threads={max(1, threads)}")
        except Exception as e:
            logger.warning(f"设置 DuckDB 线程数时出错: {e}")
            logger.debug("设置 DuckDB 线程数详细信息", exc_info=True)
        try:
            mem_limit = settings.DUCKDB_MEMORY_LIMIT
            if mem_limit:
                logger.debug(f"设置 DuckDB 内存限制: {mem_limit}")
                con.execute(f"PRAGMA memory_limit='{mem_limit}'")
        except Exception as e:
            logger.warning(f"设置 DuckDB 内存限制时出错: {e}")
            logger.debug("设置 DuckDB 内存限制详细信息", exc_info=True)
        _configure_httpfs_and_s3(con)
        if files_param:
            debug_cur = con.execute(f"SELECT * FROM read_parquet(?) LIMIT 3", [files_param])
        else:
            debug_cur = con.execute(f"SELECT * FROM read_parquet('{pattern}') LIMIT 3")
        debug_rows = debug_cur.fetchall()
        logger.debug(f"Parquet 样例数据 (前3条): {debug_rows}")

        logger.debug("执行查询")
        if files_param:
            cur = con.execute(sql, [files_param] + params)
        else:
            cur = con.execute(sql, params)
        rows = cur.fetchall()
        logger.debug(f"查询结果: {len(rows)} 行")
        colnames = [d[0] for d in cur.description]
        result = [dict(zip(colnames, r)) for r in rows]
        logger.debug(f"返回结果: {len(result)} 行")
        return result
    except Exception as e:
        # 归档损坏或其他异常时，返回空避免影响主流程
        logger.error(f"查询 Parquet 文件时出错: {e}")
        logger.debug("查询 Parquet 文件详细信息", exc_info=True)
        if _QUERY_DEBUG:
            try:
                logger.warning(f"archive query failed: {e}")
            except Exception as e:
                logger.warning(f"记录查询失败日志时出错: {e}")
                logger.debug("记录查询失败日志详细信息", exc_info=True)
        return []
    finally:
        logger.debug("关闭 DuckDB 连接")
        con.close()


def _list_day_partitions(table: str) -> List[str]:
    logger.debug(f"列出日分区: table={table}")
    base = os.path.join(ARCHIVE_ROOT, table)
    pattern = os.path.join(base, "year=*", "month=*", "day=*")
    logger.debug(f"分区模式: {pattern}")
    result = [d for d in glob.glob(pattern) if os.path.isdir(d)]
    logger.debug(f"找到 {len(result)} 个分区")
    return result


def compact_small_files(table: str, min_files: int = 10) -> List[Tuple[str, int]]:
    """将按日分区目录中较多小文件合并为单个 parquet。

    返回列表 [(partition_dir, merged_count), ...]
    """
    logger.debug(f"压实小文件: table={table}, min_files={min_files}")
    results: List[Tuple[str, int]] = []
    partitions = _list_day_partitions(table)
    logger.debug(f"找到 {len(partitions)} 个分区")
    for part_dir in partitions:
        try:
            logger.debug(f"处理分区: {part_dir}")
            # 仅合并小文件（避免重复合并）：只匹配 part- 前缀
            pattern = os.path.join(part_dir, "part-*.parquet")
            small_files = sorted(glob.glob(pattern))
            logger.debug(f"找到 {len(small_files)} 个小文件")
            if len(small_files) < max(1, int(min_files)):
                logger.debug(
                    f"小文件数量 {len(small_files)} 小于最小要求 {min_files}，跳过"
                )
                continue
            out_file = os.path.normpath(os.path.join(
                part_dir, f"compact-{int(datetime.utcnow().timestamp())}-{int(datetime.utcnow().microsecond)}.parquet"
            ))
            
            # 策略：先写入系统临时目录，再移动到目标目录
            temp_fd, local_tmp_path = tempfile.mkstemp(suffix=".parquet.compact.tmp")
            os.close(temp_fd)
            
            safe_tmp_path = local_tmp_path.replace("\\", "/").replace("'", "''")
            logger.debug(f"输出文件: {out_file}, 临时文件: {local_tmp_path}, DuckDB 路径: {safe_tmp_path}")
            con = duckdb.connect(database=":memory:")
            try:
                logger.debug("配置 DuckDB 连接")
                # 使用通配模式仅读取 part-*.parquet，避免把目标 compact 文件读进去
                con.execute(
                    "CREATE TABLE t AS SELECT * FROM read_parquet(?)", [pattern]
                )
                try:
                    logger.debug(f"写入压实文件: {safe_tmp_path}")
                    con.execute(
                        f"COPY t TO '{safe_tmp_path}' (FORMAT PARQUET, COMPRESSION {_PARQUET_COMPRESSION}, ROW_GROUP_SIZE {_ROW_GROUP_SIZE_INT})"
                    )
                except Exception as e:
                    logger.warning(f"写入压实文件时出错: {e}，尝试不指定压缩参数")
                    logger.debug("写入压实文件详细信息", exc_info=True)
                    logger.debug(f"写入压实文件 (无压缩参数): {safe_tmp_path}")
                    con.execute(f"COPY t TO '{safe_tmp_path}' (FORMAT PARQUET)")
            finally:
                logger.debug("关闭 DuckDB 连接")
                con.close()
            # 移动临时文件到目标位置
            try:
                logger.debug(f"移动压实文件: {local_tmp_path} -> {out_file}")
                shutil.move(local_tmp_path, out_file)
            except Exception as e:
                logger.error(f"移动压实文件失败: {e}")
                if os.path.exists(local_tmp_path):
                    os.remove(local_tmp_path)
                continue
            # 删除已合并的小文件
            removed = 0
            for fp in small_files:
                try:
                    logger.debug(f"删除小文件: {fp}")
                    os.remove(fp)
                    removed += 1
                except Exception as e:
                    logger.warning(f"删除小文件失败 {fp}: {e}")
                    logger.debug("删除小文件失败详细信息", exc_info=True)
            logger.debug(f"分区 {part_dir} 压实完成，删除 {removed} 个小文件")
            results.append((part_dir, removed))
        except Exception as e:
            logger.error(f"压实分区失败 {part_dir}: {e}")
            logger.debug("压实分区失败详细信息", exc_info=True)
            continue
    logger.debug(f"压实小文件完成，共处理 {len(results)} 个分区")
    return results
