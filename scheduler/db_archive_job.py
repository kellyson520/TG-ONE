from datetime import datetime, timedelta
import logging
from typing import List, Dict, Any

from models.models import get_session, get_dedup_session, MediaSignature, ErrorLog, RuleLog, TaskQueue, ChatStatistics, RuleStatistics
from repositories.archive_store import write_parquet, compact_small_files
from core.helpers.metrics import ARCHIVE_RUN_TOTAL, ARCHIVE_RUN_SECONDS
from repositories.bloom_index import bloom
from models.models import analyze_database, vacuum_database
from pathlib import Path

logger = logging.getLogger(__name__)

# 确保归档系统初始化
def _ensure_archive_system():
    """确保归档系统已正确初始化"""
    try:
        from repositories.archive_init import init_archive_system
        if not init_archive_system():
            logger.warning("归档系统初始化失败，可能影响功能")
    except Exception as e:
        logger.error(f"归档系统初始化检查失败: {e}")
        logger.debug("归档系统初始化检查失败的详细信息", exc_info=True)

# 在模块加载时进行一次检查
_ensure_archive_system()


from core.config import settings

HOT_DAYS_SIGN = settings.HOT_DAYS_SIGN
HOT_DAYS_LOG = settings.HOT_DAYS_LOG
HOT_DAYS_STATS = settings.HOT_DAYS_STATS


def _to_rows(objs: List[Any], columns: List[str]) -> List[Dict[str, Any]]:
    rows = []
    for o in objs:
        d = {}
        for c in columns:
            d[c] = getattr(o, c, None)
        rows.append(d)
    return rows


def archive_once() -> None:
    """执行一次归档，将超期热数据落到 Parquet，并从 SQLite 删除。"""
    cutoff_sign = (datetime.utcnow() - timedelta(days=HOT_DAYS_SIGN)).isoformat()
    cutoff_log = (datetime.utcnow() - timedelta(days=HOT_DAYS_LOG)).isoformat()
    cutoff_stats = (datetime.utcnow() - timedelta(days=HOT_DAYS_STATS)).isoformat()
    import time
    start = time.time()
    status = 'success'
    
    logger.info(f"开始执行归档任务: cutoff_sign={cutoff_sign}, cutoff_log={cutoff_log}, cutoff_stats={cutoff_stats}")

    with get_dedup_session() as session:
        # 1) media_signatures
        try:
            batch = settings.ARCHIVE_BATCH_SIZE
            logger.debug(f"查询 MediaSignature 数据，批次大小: {batch}")
            sigs = session.query(MediaSignature).filter(
                (MediaSignature.last_seen != None) & (MediaSignature.last_seen < cutoff_sign)
                | ((MediaSignature.last_seen == None) & (MediaSignature.created_at < cutoff_sign))
            ).limit(batch).all()
            logger.info(f"查询到 {len(sigs)} 条 MediaSignature 记录待归档")
            
            if sigs:
                rows = _to_rows(sigs, [
                    'chat_id','signature','file_id','content_hash','message_id','created_at','updated_at',
                    'count','media_type','file_size','file_name','mime_type','duration','width','height','last_seen'
                ])
                logger.debug(f"转换为行数据完成，共 {len(rows)} 行")
                
                # 可选并发写：按 chat_id 分片并发
                try:
                    import concurrent.futures
                    use_parallel = settings.ARCHIVE_WRITE_PARALLEL
                    logger.debug(f"并发写入设置: {use_parallel}")
                except Exception as e:
                    logger.warning(f"检查并发写入设置时出错: {e}")
                    use_parallel = False
                    
                if use_parallel:
                    from collections import defaultdict
                    grouped = defaultdict(list)
                    for r in rows:
                        grouped[str(r.get('chat_id','global'))].append(r)
                    max_workers = settings.ARCHIVE_WRITE_MAX_WORKERS
                    logger.debug(f"使用并发写入，最大工作线程数: {max_workers}")
                    
                    success_rows = []
                    with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as ex:
                        # 将 partition 和 rows 对应起来，以便在失败时知道哪些数据写成功了
                        future_to_rows = {ex.submit(write_parquet, 'media_signatures', part_rows, datetime.utcnow()): part_rows for part_rows in grouped.values()}
                        for fut in concurrent.futures.as_completed(future_to_rows):
                            try:
                                result = fut.result()
                                if result:
                                    success_rows.extend(future_to_rows[fut])
                                    logger.debug(f"并发分块写入成功: {result}")
                                else:
                                    logger.warning("并发分块写入返回为空，该分块将保留在 SQLite")
                            except Exception as we:
                                logger.warning(f"并发写入失败（该分块数据保留）: {we}")
                                logger.debug("并发写入失败详细信息", exc_info=True)
                    
                    # 重新构建待删除的 IDs
                    rows_to_delete = success_rows
                else:
                    logger.debug("使用顺序写入")
                    result = write_parquet('media_signatures', rows, datetime.utcnow())
                    if result:
                        logger.debug(f"顺序写入完成: {result}")
                        rows_to_delete = rows
                    else:
                        logger.error("顺序写入失败，跳过本批次删除")
                        rows_to_delete = []
                    
                if not rows_to_delete:
                    logger.info("没有任何写入成功的记录，跳过删除步骤")
                else:
                    # 更新 Bloom 索引（仅对写入成功的记录更新）
                    try:
                        logger.debug(f"开始更新 Bloom 索引，处理 {len(rows_to_delete)} 条记录")
                        bloom.add_batch('media_signatures', rows_to_delete, ['signature','content_hash'])
                        logger.debug(f"成功更新Bloom索引")
                    except Exception as be:
                        logger.error(f"Bloom 更新失败: {be}")

                    # 删除
                    logger.debug("开始批量删除已归档记录")
                    ids_to_delete = []
                    sig_to_id = {s.signature: s.id for s in sigs}
                    for r in rows_to_delete:
                        rid = sig_to_id.get(r.get('signature'))
                        if rid:
                            ids_to_delete.append(rid)

                    if ids_to_delete:
                        # 优化：单次 commit 处理所有 chunk
                        deleted_count = 0
                        for chunk_start in range(0, len(ids_to_delete), 1000):
                            chunk = ids_to_delete[chunk_start:chunk_start+1000]
                            count = session.query(MediaSignature).filter(MediaSignature.id.in_(chunk)).delete(synchronize_session=False)
                            deleted_count += count
                        session.commit()
                        logger.info(f"成功迁移并删除 {deleted_count} 条 MediaSignature 记录")
            else:
                logger.info("没有需要归档的 MediaSignature 记录")
        except Exception as e:
            logger.error(f"归档 media_signatures 失败: {e}")
            logger.debug("归档 media_signatures 失败详细信息", exc_info=True)

        # 2) 日志
    with get_session() as session:
        try:
            logger.debug("开始归档 ErrorLog")
            errs = session.query(ErrorLog).filter(ErrorLog.created_at < cutoff_log).limit(settings.ARCHIVE_LOG_BATCH_SIZE).all()
            logger.info(f"查询到 {len(errs)} 条 ErrorLog 记录待归档")
            
            if errs:
                rows = _to_rows(errs, ['level','module','function','message','traceback','context','user_id','rule_id','chat_id','created_at'])
                logger.debug(f"转换为行数据完成，共 {len(rows)} 行")
                
                try:
                    result = write_parquet('error_logs', rows, datetime.utcnow())
                    logger.debug(f"写入 error_logs 完成: {result}")
                except Exception as we:
                    logger.warning(f"写入 error_logs 失败，重试一次: {we}")
                    try:
                        result = write_parquet('error_logs', rows, datetime.utcnow())
                        logger.debug(f"重试写入 error_logs 完成: {result}")
                    except Exception as we2:
                        logger.error(f"写入 error_logs 二次失败，跳过本批删除: {we2}")
                        result = None

                if result:
                    deleted_count = 0
                    ids = [r.id for r in errs]
                    count = session.query(ErrorLog).filter(ErrorLog.id.in_(ids)).delete(synchronize_session=False)
                    deleted_count += count
                    session.commit()
                    logger.info(f"成功从 SQLite 迁移并删除 {deleted_count} 条 ErrorLog 记录")
                else:
                    logger.warning("Parquet 写入未成功，保留 ErrorLog 记录在 SQLite 中")
            else:
                logger.info("没有需要归档的 ErrorLog 记录")
        except Exception as e:
            logger.error(f"归档 error_logs 失败: {e}")
            logger.debug("归档 error_logs 失败详细信息", exc_info=True)

        try:
            logger.debug("开始归档 RuleLog")
            rlogs = session.query(RuleLog).filter(RuleLog.created_at < cutoff_log).limit(settings.ARCHIVE_LOG_BATCH_SIZE).all()
            logger.info(f"查询到 {len(rlogs)} 条 RuleLog 记录待归档")
            
            if rlogs:
                rows = _to_rows(rlogs, ['rule_id','action','source_message_id','target_message_id','result','error_message','processing_time','created_at'])
                logger.debug(f"转换为行数据完成，共 {len(rows)} 行")
                
                try:
                    result = write_parquet('rule_logs', rows, datetime.utcnow())
                    logger.debug(f"写入 rule_logs 完成: {result}")
                except Exception as we:
                    logger.warning(f"写入 rule_logs 失败，重试一次: {we}")
                    try:
                        result = write_parquet('rule_logs', rows, datetime.utcnow())
                        logger.debug(f"重试写入 rule_logs 完成: {result}")
                    except Exception as we2:
                        logger.error(f"写入 rule_logs 二次失败，跳过本批删除: {we2}")
                        result = None

                if result:
                    deleted_count = 0
                    ids = [r.id for r in rlogs]
                    count = session.query(RuleLog).filter(RuleLog.id.in_(ids)).delete(synchronize_session=False)
                    deleted_count += count
                    session.commit()
                    logger.info(f"成功从 SQLite 迁移并删除 {deleted_count} 条 RuleLog 记录")
                else:
                    logger.warning("Parquet 写入未成功，保留 RuleLog 记录在 SQLite 中")
            else:
                logger.info("没有需要归档的 RuleLog 记录")
        except Exception as e:
            logger.error(f"归档 rule_logs 失败: {e}")
            logger.debug("归档 rule_logs 失败详细信息", exc_info=True)

        try:
            logger.debug("开始归档 TaskQueue")
            tasks = session.query(TaskQueue).filter(
                TaskQueue.status.in_(['completed','failed']),
                TaskQueue.completed_at != None,
                TaskQueue.completed_at < cutoff_log
            ).limit(settings.ARCHIVE_TASK_BATCH_SIZE).all()
            logger.info(f"查询到 {len(tasks)} 条 TaskQueue 记录待归档")
            
            if tasks:
                rows = _to_rows(tasks, ['task_type','task_data','status','priority','retry_count','max_retries','scheduled_at','started_at','completed_at','error_message','created_at','updated_at'])
                logger.debug(f"转换为行数据完成，共 {len(rows)} 行")
                
                result = write_parquet('task_queue', rows, datetime.utcnow())
                if result:
                    deleted_count = 0
                    ids = [t.id for t in tasks]
                    count = session.query(TaskQueue).filter(TaskQueue.id.in_(ids)).delete(synchronize_session=False)
                    deleted_count += count
                    session.commit()
                    logger.info(f"成功从 SQLite 迁移并删除 {deleted_count} 条 TaskQueue 记录")
                else:
                    logger.warning("Parquet 写入失败，保留 TaskQueue 记录在 SQLite 中")
            else:
                logger.info("没有需要归档的 TaskQueue 记录")
        except Exception as e:
            logger.error(f"归档 task_queue 失败: {e}")
            logger.debug("归档 task_queue 失败详细信息", exc_info=True)

        # 3) 统计
        try:
            logger.debug("开始归档 ChatStatistics")
            cstats = session.query(ChatStatistics).filter(ChatStatistics.created_at < cutoff_stats).limit(settings.ARCHIVE_STATS_BATCH_SIZE).all()
            logger.info(f"查询到 {len(cstats)} 条 ChatStatistics 记录待归档")
            
            if cstats:
                rows = _to_rows(cstats, ['chat_id','date','message_count','media_count','user_count','forward_count','created_at'])
                logger.debug(f"转换为行数据完成，共 {len(rows)} 行")
                
                result = write_parquet('chat_statistics', rows, datetime.utcnow())
                logger.debug(f"写入 chat_statistics 完成: {result}")
                
                deleted_count = 0
                ids = [c.id for c in cstats]
                result = session.query(ChatStatistics).filter(ChatStatistics.id.in_(ids)).delete(synchronize_session=False)
                deleted_count += result
                session.commit()
                logger.info(f"成功删除 {deleted_count} 条已归档的 ChatStatistics 记录")
            else:
                logger.info("没有需要归档的 ChatStatistics 记录")
        except Exception as e:
            logger.error(f"归档 chat_statistics 失败: {e}")
            logger.debug("归档 chat_statistics 失败详细信息", exc_info=True)

        try:
            logger.debug("开始归档 RuleStatistics")
            rstats = session.query(RuleStatistics).filter(RuleStatistics.created_at < cutoff_stats).limit(settings.ARCHIVE_STATS_BATCH_SIZE).all()
            logger.info(f"查询到 {len(rstats)} 条 RuleStatistics 记录待归档")
            
            if rstats:
                rows = _to_rows(rstats, ['rule_id','date','total_triggered','success_count','filtered_count','error_count','created_at'])
                logger.debug(f"转换为行数据完成，共 {len(rows)} 行")
                
                result = write_parquet('rule_statistics', rows, datetime.utcnow())
                logger.debug(f"写入 rule_statistics 完成: {result}")
                
                deleted_count = 0
                ids = [r.id for r in rstats]
                result = session.query(RuleStatistics).filter(RuleStatistics.id.in_(ids)).delete(synchronize_session=False)
                deleted_count += result
                session.commit()
                logger.info(f"成功删除 {deleted_count} 条已归档的 RuleStatistics 记录")
            else:
                logger.info("没有需要归档的 RuleStatistics 记录")
        except Exception as e:
            logger.error(f"归档 rule_statistics 失败: {e}")
            logger.debug("归档 rule_statistics 失败详细信息", exc_info=True)

    # 数据库优化
    try:
        logger.debug("开始数据库优化")
        analyze_database()
        # 先尝试截断 WAL 再 VACUUM 收缩
        try:
            from sqlalchemy import text
            from core.db_factory import get_engine
            with get_engine().connect() as conn:
                try:
                    logger.debug("尝试 TRUNCATE WAL checkpoint")
                    conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
                except Exception as e:
                    logger.warning(f"TRUNCATE WAL checkpoint 失败，尝试 FULL: {e}")
                    logger.debug("TRUNCATE WAL checkpoint 失败详细信息", exc_info=True)
                    conn.execute(text("PRAGMA wal_checkpoint(FULL)"))
        except Exception as we:
            logger.warning(f"WAL 截断失败（忽略）：{we}")
            logger.debug("WAL 截断失败详细信息", exc_info=True)
        vacuum_database()
        logger.debug("数据库优化完成")
    except Exception as e:
        logger.error(f"数据库优化失败: {e}")
        logger.debug("数据库优化失败详细信息", exc_info=True)
        status = 'error'
    finally:
        duration = time.time() - start
        ARCHIVE_RUN_SECONDS.observe(duration)
        ARCHIVE_RUN_TOTAL.labels(status=status).inc()
        logger.info(f"归档任务完成，耗时: {duration:.2f} 秒，状态: {status}")

    # 可选压实：通过环境变量启用
    try:
        if settings.ARCHIVE_COMPACT_ENABLED:
            logger.debug("开始归档压实")
            for table in ('media_signatures', 'error_logs', 'rule_logs', 'task_queue', 'chat_statistics', 'rule_statistics'):
                res = compact_small_files(table, min_files=settings.ARCHIVE_COMPACT_MIN_FILES)
                if res:
                    logger.info(f"归档压实完成: {table} -> {len(res)} 个分区")
                else:
                    logger.debug(f"归档压实完成: {table} -> 无需要压实的文件")
    except Exception as e:
        logger.warning(f"归档压实过程失败（忽略继续）: {e}")
        logger.debug("归档压实过程失败详细信息", exc_info=True)


def garbage_collect_once() -> None:
    """执行一次垃圾清理：清理临时目录中过期文件。"""
    try:
        logger.debug("开始垃圾清理")
        keep_days = settings.GC_KEEP_DAYS
        cutoff = datetime.utcnow() - timedelta(days=max(0, keep_days))
        tmp_dirs = settings.GC_TEMP_DIRS
        if isinstance(tmp_dirs, str):
            tmp_dirs = [p.strip() for p in tmp_dirs.split(',') if p.strip()]
            
        removed = 0
        for d in tmp_dirs:
            p = Path(d)
            if not p.exists():
                logger.debug(f"临时目录不存在: {d}")
                continue
            logger.debug(f"清理临时目录: {d}")
            for item in p.rglob('*'):
                try:
                    if item.is_file():
                        mtime = datetime.utcfromtimestamp(item.stat().st_mtime)
                        if mtime < cutoff:
                            item.unlink(missing_ok=True)
                            removed += 1
                            logger.debug(f"删除过期文件: {item}")
                    elif item.is_dir():
                        # 尝试移除空目录
                        try:
                            next(item.iterdir())
                        except StopIteration:
                            item.rmdir()
                            logger.debug(f"删除空目录: {item}")
                except Exception as e:
                    logger.warning(f"清理文件/目录失败 {item}: {e}")
                    logger.debug("清理文件/目录失败详细信息", exc_info=True)
        logger.info(f"垃圾清理完成，删除文件约 {removed} 个")
    except Exception as e:
        logger.error(f"垃圾清理失败: {e}")
        logger.debug("垃圾清理失败详细信息", exc_info=True)

def archive_force() -> None:
    """强制归档：忽略保留天数阈值，将当前所有热数据迁移到 Parquet 并从 SQLite 删除，然后执行优化。

    注意：
    - media_signatures: 归档全部记录
    - error_logs / rule_logs: 归档全部记录
    - task_queue: 仅归档 status in (completed, failed) 的记录（避免影响在途任务）
    - chat_statistics / rule_statistics: 归档全部记录
    """
    logger.info("开始强制归档")
    
    with get_session() as session:
        # 通用分批器设置
        batch_size = 100000

        # 1) media_signatures（全量）
        try:
            logger.debug("开始强制归档 MediaSignature")
            last_id = 0
            total_archived = 0
            while True:
                # 分批获取数据
                sigs = session.query(MediaSignature) \
                    .filter(MediaSignature.id > last_id) \
                    .order_by(MediaSignature.id) \
                    .limit(batch_size).all()
                
                if not sigs:
                    break
                
                logger.debug(f"正在处理 {len(sigs)} 条记录，当前最后 ID: {last_id}")
                
                rows = _to_rows(sigs, [
                    'chat_id','signature','file_id','content_hash','message_id','created_at','updated_at',
                    'count','media_type','file_size','file_name','mime_type','duration','width','height','last_seen'
                ])
                
                # 执行写操作
                result = write_parquet('media_signatures', rows, datetime.utcnow())
                if not result:
                    logger.error("强制归档: MediaSignature Parquet 写入失败，跳过该批次")
                    break

                # 处理 Bloom 和删除
                try:
                    bloom.add_batch('media_signatures', rows, ['signature','content_hash'])
                except Exception as be:
                    logger.error(f"强制归档: Bloom 更新失败 (已忽略并继续): {be}")
                    
                # 批量删除（在当前 batch 内使用 chunked delete 以防止锁表）
                ids = [s.id for s in sigs]
                for chunk_start in range(0, len(ids), 2000): # 增加 chunk 大小至 2000
                    chunk = ids[chunk_start:chunk_start+2000]
                    session.query(MediaSignature).filter(MediaSignature.id.in_(chunk)).delete(synchronize_session=False)
                
                session.commit() # 每个 batch 提交一次
                last_id = sigs[-1].id
                total_archived += len(sigs)
            
            logger.info(f"强制归档 MediaSignature 完成，总共处理 {total_archived} 条记录")
        except Exception as e:
            logger.error(f"强制归档 media_signatures 失败: {e}")
            logger.debug("强制归档 media_signatures 失败详细信息", exc_info=True)

        # 2) 错误/规则日志（全量）
        try:
            logger.debug("开始强制归档 ErrorLog")
            last_id = 0
            total_archived = 0
            while True:
                errs = session.query(ErrorLog) \
                    .filter(ErrorLog.id > last_id) \
                    .order_by(ErrorLog.id).limit(batch_size).all()
                if not errs:
                    break
                logger.debug(f"查询到 {len(errs)} 条 ErrorLog 记录，ID 范围: {errs[0].id} - {errs[-1].id}")
                
                rows = _to_rows(errs, ['level','module','function','message','traceback','context','user_id','rule_id','chat_id','created_at'])
                logger.debug(f"转换为行数据完成，共 {len(rows)} 行")
                
                result = write_parquet('error_logs', rows, datetime.utcnow())
                if result:
                    deleted_count = 0
                    ids = [r.id for r in errs]
                    count = session.query(ErrorLog).filter(ErrorLog.id.in_(ids)).delete(synchronize_session=False)
                    deleted_count += count
                    session.commit()
                    logger.info(f"成功迁移并删除 {deleted_count} 条 ErrorLog 记录")
                    last_id = errs[-1].id
                    total_archived += len(errs)
                else:
                    logger.error("强制归档: ErrorLog Parquet 写入失败，停止该表归档")
                    break
                
            logger.info(f"强制归档 ErrorLog 完成，总共处理 {total_archived} 条记录")
        except Exception as e:
            logger.error(f"强制归档 error_logs 失败: {e}")
            logger.debug("强制归档 error_logs 失败详细信息", exc_info=True)

        try:
            logger.debug("开始强制归档 RuleLog")
            last_id = 0
            total_archived = 0
            while True:
                rlogs = session.query(RuleLog) \
                    .filter(RuleLog.id > last_id) \
                    .order_by(RuleLog.id).limit(batch_size).all()
                if not rlogs:
                    break
                logger.debug(f"查询到 {len(rlogs)} 条 RuleLog 记录，ID 范围: {rlogs[0].id} - {rlogs[-1].id}")
                
                rows = _to_rows(rlogs, ['rule_id','action','source_message_id','target_message_id','result','error_message','processing_time','created_at'])
                logger.debug(f"转换为行数据完成，共 {len(rows)} 行")
                
                result = write_parquet('rule_logs', rows, datetime.utcnow())
                if result:
                    deleted_count = 0
                    ids = [r.id for r in rlogs]
                    count = session.query(RuleLog).filter(RuleLog.id.in_(ids)).delete(synchronize_session=False)
                    deleted_count += count
                    session.commit()
                    logger.info(f"成功迁移并删除 {deleted_count} 条 RuleLog 记录")
                    last_id = rlogs[-1].id
                    total_archived += len(rlogs)
                else:
                    logger.error("强制归档: RuleLog Parquet 写入失败，停止该表归档")
                    break
                
            logger.info(f"强制归档 RuleLog 完成，总共处理 {total_archived} 条记录")
        except Exception as e:
            logger.error(f"强制归档 rule_logs 失败: {e}")
            logger.debug("强制归档 rule_logs 失败详细信息", exc_info=True)

        # 任务队列：仅归档完成/失败（忽略时间）
        try:
            logger.debug("开始强制归档 TaskQueue")
            last_id = 0
            total_archived = 0
            while True:
                tasks = session.query(TaskQueue) \
                    .filter(TaskQueue.id > last_id) \
                    .filter(TaskQueue.status.in_(['completed','failed'])) \
                    .order_by(TaskQueue.id).limit(batch_size).all()
                if not tasks:
                    break
                logger.debug(f"查询到 {len(tasks)} 条 TaskQueue 记录，ID 范围: {tasks[0].id} - {tasks[-1].id}")
                
                rows = _to_rows(tasks, ['task_type','task_data','status','priority','retry_count','max_retries','scheduled_at','started_at','completed_at','error_message','created_at','updated_at'])
                logger.debug(f"转换为行数据完成，共 {len(rows)} 行")
                
                result = write_parquet('task_queue', rows, datetime.utcnow())
                if result:
                    deleted_count = 0
                    ids = [t.id for t in tasks]
                    count = session.query(TaskQueue).filter(TaskQueue.id.in_(ids)).delete(synchronize_session=False)
                    deleted_count += count
                    session.commit()
                    logger.info(f"成功迁移并删除 {deleted_count} 条 TaskQueue 记录")
                    last_id = tasks[-1].id
                    total_archived += len(tasks)
                else:
                    logger.error("强制归档: TaskQueue Parquet 写入失败，停止该表归档")
                    break
                
            logger.info(f"强制归档 TaskQueue 完成，总共处理 {total_archived} 条记录")
        except Exception as e:
            logger.error(f"强制归档 task_queue 失败: {e}")
            logger.debug("强制归档 task_queue 失败详细信息", exc_info=True)

        # 3) 统计（全量）
        try:
            logger.debug("开始强制归档 ChatStatistics")
            last_id = 0
            total_archived = 0
            while True:
                cstats = session.query(ChatStatistics) \
                    .filter(ChatStatistics.id > last_id) \
                    .order_by(ChatStatistics.id).limit(batch_size).all()
                if not cstats:
                    break
                logger.debug(f"查询到 {len(cstats)} 条 ChatStatistics 记录，ID 范围: {cstats[0].id} - {cstats[-1].id}")
                
                rows = _to_rows(cstats, ['chat_id','date','message_count','media_count','user_count','forward_count','created_at'])
                logger.debug(f"转换为行数据完成，共 {len(rows)} 行")
                
                result = write_parquet('chat_statistics', rows, datetime.utcnow())
                if result:
                    deleted_count = 0
                    ids = [c.id for c in cstats]
                    count = session.query(ChatStatistics).filter(ChatStatistics.id.in_(ids)).delete(synchronize_session=False)
                    deleted_count += count
                    session.commit()
                    logger.info(f"成功迁移并删除 {deleted_count} 条 ChatStatistics 记录")
                    last_id = cstats[-1].id
                    total_archived += len(cstats)
                else:
                    logger.error("强制归档: ChatStatistics Parquet 写入失败，停止该表归档")
                    break
                
            logger.info(f"强制归档 ChatStatistics 完成，总共处理 {total_archived} 条记录")
        except Exception as e:
            logger.error(f"强制归档 chat_statistics 失败: {e}")
            logger.debug("强制归档 chat_statistics 失败详细信息", exc_info=True)

        try:
            logger.debug("开始强制归档 RuleStatistics")
            last_id = 0
            total_archived = 0
            while True:
                rstats = session.query(RuleStatistics) \
                    .filter(RuleStatistics.id > last_id) \
                    .order_by(RuleStatistics.id).limit(batch_size).all()
                if not rstats:
                    break
                logger.debug(f"查询到 {len(rstats)} 条 RuleStatistics 记录，ID 范围: {rstats[0].id} - {rstats[-1].id}")
                
                rows = _to_rows(rstats, ['rule_id','date','total_triggered','success_count','filtered_count','error_count','created_at'])
                logger.debug(f"转换为行数据完成，共 {len(rows)} 行")
                
                result = write_parquet('rule_statistics', rows, datetime.utcnow())
                if result:
                    deleted_count = 0
                    ids = [r.id for r in rstats]
                    count = session.query(RuleStatistics).filter(RuleStatistics.id.in_(ids)).delete(synchronize_session=False)
                    deleted_count += count
                    session.commit()
                    logger.info(f"成功迁移并删除 {deleted_count} 条 RuleStatistics 记录")
                    last_id = rstats[-1].id
                    total_archived += len(rstats)
                else:
                    logger.error("强制归档: RuleStatistics Parquet 写入失败，停止该表归档")
                    break
                
            logger.info(f"强制归档 RuleStatistics 完成，总共处理 {total_archived} 条记录")
        except Exception as e:
            logger.error(f"强制归档 rule_statistics 失败: {e}")
            logger.debug("强制归档 rule_statistics 失败详细信息", exc_info=True)

    # 数据库优化与WAL截断，确保文件体积实际下降
    try:
        logger.debug("开始数据库优化")
        analyze_database()
        # 先尝试检查点并截断 WAL，随后 VACUUM 收缩主库
        try:
            from sqlalchemy import text
            from core.db_factory import get_engine
            with get_engine().connect() as conn:
                try:
                    logger.debug("尝试 TRUNCATE WAL checkpoint")
                    conn.execute(text("PRAGMA wal_checkpoint(TRUNCATE)"))
                except Exception as e:
                    logger.warning(f"TRUNCATE WAL checkpoint 失败，尝试 FULL: {e}")
                    logger.debug("TRUNCATE WAL checkpoint 失败详细信息", exc_info=True)
                    conn.execute(text("PRAGMA wal_checkpoint(FULL)"))
        except Exception as we:
            logger.warning(f"WAL 截断失败（忽略）：{we}")
            logger.debug("WAL 截断失败详细信息", exc_info=True)
        vacuum_database()
        logger.debug("数据库优化完成")
    except Exception as e:
        logger.error(f"数据库优化失败: {e}")
        logger.debug("数据库优化失败详细信息", exc_info=True)
        
    logger.info("强制归档完成")
