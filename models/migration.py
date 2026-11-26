from sqlalchemy import inspect, text
import logging
from models.chat import Chat
from models.rule import (
    ForwardRule, ForwardMapping, Keyword, ReplaceRule, 
    MediaTypes, MediaExtensions, RuleSync, PushConfig, 
    RSSConfig, RSSPattern
)
from models.user import User, AuditLog, ActiveSession, AccessControlList
from models.stats import ChatStatistics, RuleStatistics, RuleLog
from models.system import SystemConfiguration, ErrorLog, TaskQueue, RSSSubscription
from models.dedup import MediaSignature

logger = logging.getLogger(__name__)

def _get_existing_columns(inspector, table_name):
    """获取表中已存在的列名集合"""
    try:
        return {column['name'] for column in inspector.get_columns(table_name)}
    except Exception as e:
        logger.warning(f"获取表 {table_name} 的列信息失败: {e}")
        return set()


def _add_columns_if_missing(connection, inspector, table_name, columns_map):
    """通用列迁移：检查并添加缺失的列"""
    existing = _get_existing_columns(inspector, table_name)
    for col, sql in columns_map.items():
        if col not in existing:
            try:
                connection.execute(text(sql))
                logger.info(f"已为 {table_name} 添加列: {col}")
            except Exception as e:
                logger.warning(f'添加列 {col} 失败: {e}')


def _verify_connection(engine):
    """验证数据库连接"""
    try:
        with engine.connect():
            pass
    except Exception as e:
        logger.error(f"无法连接到数据库进行迁移: {e}")
        return False
    return True


def _create_missing_tables(engine, existing_tables):
    """创建所有缺失的表"""
    table_creators = [
        ('chats', Chat),
        ('forward_rules', ForwardRule),
        ('keywords', Keyword),
        ('replace_rules', ReplaceRule),
        ('rule_syncs', RuleSync),
        ('users', User),
        ('rss_configs', RSSConfig),
        ('rss_patterns', RSSPattern),
        ('audit_logs', AuditLog),
        ('active_sessions', ActiveSession),
        ('push_configs', PushConfig),
        ('media_signatures', MediaSignature),
        ('forward_mappings', ForwardMapping),
        ('rss_subscriptions', RSSSubscription),
        ('access_control_list', AccessControlList),
    ]
    for table_name, table_class in table_creators:
        if table_name not in existing_tables:
            logger.info(f"创建{table_name}表...")
            table_class.__table__.create(engine, checkfirst=True)

    new_tables = {
        'chat_statistics': ChatStatistics,
        'rule_statistics': RuleStatistics, 
        'rule_logs': RuleLog,
        'system_configurations': SystemConfiguration,
        'error_logs': ErrorLog,
        'task_queue': TaskQueue,
    }
    for table_name, table_class in new_tables.items():
        if table_name not in existing_tables:
            logger.info(f"创建{table_name}表...")
            table_class.__table__.create(engine, checkfirst=True)


def _migrate_core_table_columns(connection, inspector):
    """迁移核心表的列：media_signatures, chats, chat_statistics, forward_rules, users, task_queue"""
    media_signatures_columns = {
        'count': 'ALTER TABLE media_signatures ADD COLUMN count INTEGER DEFAULT 1',
        'media_type': 'ALTER TABLE media_signatures ADD COLUMN media_type VARCHAR',
        'file_size': 'ALTER TABLE media_signatures ADD COLUMN file_size INTEGER',
        'file_name': 'ALTER TABLE media_signatures ADD COLUMN file_name VARCHAR',
        'mime_type': 'ALTER TABLE media_signatures ADD COLUMN mime_type VARCHAR',
        'duration': 'ALTER TABLE media_signatures ADD COLUMN duration INTEGER',
        'width': 'ALTER TABLE media_signatures ADD COLUMN width INTEGER',
        'height': 'ALTER TABLE media_signatures ADD COLUMN height INTEGER',
        'last_seen': 'ALTER TABLE media_signatures ADD COLUMN last_seen VARCHAR',
        'updated_at': 'ALTER TABLE media_signatures ADD COLUMN updated_at VARCHAR',
        'file_id': 'ALTER TABLE media_signatures ADD COLUMN file_id VARCHAR',
        'content_hash': 'ALTER TABLE media_signatures ADD COLUMN content_hash VARCHAR'
    }
    _add_columns_if_missing(connection, inspector, 'media_signatures', media_signatures_columns)
    logger.info('已检查 media_signatures 表结构')

    chats_columns = {
        'chat_type': 'ALTER TABLE chats ADD COLUMN chat_type VARCHAR',
        'username': 'ALTER TABLE chats ADD COLUMN username VARCHAR',
        'created_at': 'ALTER TABLE chats ADD COLUMN created_at VARCHAR',
        'updated_at': 'ALTER TABLE chats ADD COLUMN updated_at VARCHAR', 
        'is_active': 'ALTER TABLE chats ADD COLUMN is_active BOOLEAN DEFAULT 1',
        'member_count': 'ALTER TABLE chats ADD COLUMN member_count INTEGER',
        'description': 'ALTER TABLE chats ADD COLUMN description VARCHAR'
    }
    _add_columns_if_missing(connection, inspector, 'chats', chats_columns)

    chat_stats_columns = {
        'saved_traffic_bytes': 'ALTER TABLE chat_statistics ADD COLUMN saved_traffic_bytes INTEGER DEFAULT 0'
    }
    _add_columns_if_missing(connection, inspector, 'chat_statistics', chat_stats_columns)

    forward_rules_columns = {
        'created_at': 'ALTER TABLE forward_rules ADD COLUMN created_at VARCHAR',
        'updated_at': 'ALTER TABLE forward_rules ADD COLUMN updated_at VARCHAR',
        'created_by': 'ALTER TABLE forward_rules ADD COLUMN created_by VARCHAR',
        'priority': 'ALTER TABLE forward_rules ADD COLUMN priority INTEGER DEFAULT 0',
        'description': 'ALTER TABLE forward_rules ADD COLUMN description VARCHAR',
        'message_count': 'ALTER TABLE forward_rules ADD COLUMN message_count INTEGER DEFAULT 0',
        'last_used': 'ALTER TABLE forward_rules ADD COLUMN last_used VARCHAR',
        'daily_limit': 'ALTER TABLE forward_rules ADD COLUMN daily_limit INTEGER',
        'rate_limit': 'ALTER TABLE forward_rules ADD COLUMN rate_limit INTEGER',
        'webhook_url': 'ALTER TABLE forward_rules ADD COLUMN webhook_url VARCHAR',
        'custom_config': 'ALTER TABLE forward_rules ADD COLUMN custom_config VARCHAR',
        'allow_delete_source_on_dedup': 'ALTER TABLE forward_rules ADD COLUMN allow_delete_source_on_dedup BOOLEAN DEFAULT 0',
        'message_thread_id': 'ALTER TABLE forward_rules ADD COLUMN message_thread_id INTEGER',
        'enable_duration_filter': 'ALTER TABLE forward_rules ADD COLUMN enable_duration_filter BOOLEAN DEFAULT 0',
        'min_duration': 'ALTER TABLE forward_rules ADD COLUMN min_duration INTEGER DEFAULT 0',
        'max_duration': 'ALTER TABLE forward_rules ADD COLUMN max_duration INTEGER DEFAULT 0',
        'enable_resolution_filter': 'ALTER TABLE forward_rules ADD COLUMN enable_resolution_filter BOOLEAN DEFAULT 0',
        'min_width': 'ALTER TABLE forward_rules ADD COLUMN min_width INTEGER DEFAULT 0',
        'max_width': 'ALTER TABLE forward_rules ADD COLUMN max_width INTEGER DEFAULT 0',
        'min_height': 'ALTER TABLE forward_rules ADD COLUMN min_height INTEGER DEFAULT 0',
        'max_height': 'ALTER TABLE forward_rules ADD COLUMN max_height INTEGER DEFAULT 0',
        'enable_file_size_range': 'ALTER TABLE forward_rules ADD COLUMN enable_file_size_range BOOLEAN DEFAULT 0',
        'min_file_size': 'ALTER TABLE forward_rules ADD COLUMN min_file_size INTEGER DEFAULT 0',
        'max_file_size': 'ALTER TABLE forward_rules ADD COLUMN max_file_size INTEGER DEFAULT 0',
        'is_save_to_local': 'ALTER TABLE forward_rules ADD COLUMN is_save_to_local BOOLEAN DEFAULT 0',
        'unique_key': 'ALTER TABLE forward_rules ADD COLUMN unique_key VARCHAR',
        'grouped_id': 'ALTER TABLE forward_rules ADD COLUMN grouped_id VARCHAR'
    }
    _add_columns_if_missing(connection, inspector, 'forward_rules', forward_rules_columns)

    users_columns = {
        'email': 'ALTER TABLE users ADD COLUMN email VARCHAR',
        'telegram_id': 'ALTER TABLE users ADD COLUMN telegram_id VARCHAR',
        'is_active': 'ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1',
        'is_admin': 'ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0',
        'created_at': 'ALTER TABLE users ADD COLUMN created_at VARCHAR',
        'last_login': 'ALTER TABLE users ADD COLUMN last_login VARCHAR',
        'login_count': 'ALTER TABLE users ADD COLUMN login_count INTEGER DEFAULT 0',
        'totp_secret': 'ALTER TABLE users ADD COLUMN totp_secret VARCHAR',
        'is_2fa_enabled': 'ALTER TABLE users ADD COLUMN is_2fa_enabled BOOLEAN DEFAULT 0',
        'backup_codes': 'ALTER TABLE users ADD COLUMN backup_codes VARCHAR',
        'last_otp_token': 'ALTER TABLE users ADD COLUMN last_otp_token VARCHAR',
        'last_otp_at': 'ALTER TABLE users ADD COLUMN last_otp_at VARCHAR'
    }
    _add_columns_if_missing(connection, inspector, 'users', users_columns)

    task_queue_columns = {
        'done_count': 'ALTER TABLE task_queue ADD COLUMN done_count INTEGER DEFAULT 0',
        'total_count': 'ALTER TABLE task_queue ADD COLUMN total_count INTEGER DEFAULT 0',
        'forwarded_count': 'ALTER TABLE task_queue ADD COLUMN forwarded_count INTEGER DEFAULT 0',
        'filtered_count': 'ALTER TABLE task_queue ADD COLUMN filtered_count INTEGER DEFAULT 0',
        'failed_count': 'ALTER TABLE task_queue ADD COLUMN failed_count INTEGER DEFAULT 0',
        'last_message_id': 'ALTER TABLE task_queue ADD COLUMN last_message_id INTEGER',
        'source_chat_id': 'ALTER TABLE task_queue ADD COLUMN source_chat_id VARCHAR',
        'target_chat_id': 'ALTER TABLE task_queue ADD COLUMN target_chat_id VARCHAR',
        'unique_key': 'ALTER TABLE task_queue ADD COLUMN unique_key VARCHAR',
        'grouped_id': 'ALTER TABLE task_queue ADD COLUMN grouped_id VARCHAR',
        'next_retry_at': 'ALTER TABLE task_queue ADD COLUMN next_retry_at TIMESTAMP',
        'locked_until': 'ALTER TABLE task_queue ADD COLUMN locked_until TIMESTAMP',
        'error_log': 'ALTER TABLE task_queue ADD COLUMN error_log TEXT',
        'progress': 'ALTER TABLE task_queue ADD COLUMN progress INTEGER DEFAULT 0',
        'speed': 'ALTER TABLE task_queue ADD COLUMN speed VARCHAR'
    }
    _add_columns_if_missing(connection, inspector, 'task_queue', task_queue_columns)
    logger.info('已更新所有表的新字段')


def _create_performance_indexes(connection, engine):
    """创建性能优化索引并清理重复数据"""
    indexes = [
        'CREATE INDEX IF NOT EXISTS idx_media_signatures_chat_signature ON media_signatures(chat_id, signature)',
        'CREATE INDEX IF NOT EXISTS idx_media_signatures_chat_count ON media_signatures(chat_id, count)',
        'CREATE INDEX IF NOT EXISTS idx_forward_rules_source_enabled ON forward_rules(source_chat_id, enable_rule)',
        'CREATE INDEX IF NOT EXISTS idx_forward_rules_target ON forward_rules(target_chat_id)',
        'CREATE INDEX IF NOT EXISTS idx_keywords_rule_type ON keywords(rule_id, is_regex, is_blacklist)',
        'CREATE INDEX IF NOT EXISTS idx_rss_configs_rule_enabled ON rss_configs(rule_id, enable_rss)',
        'CREATE INDEX IF NOT EXISTS idx_push_configs_rule_enabled ON push_configs(rule_id, enable_push_channel)',
        'CREATE INDEX IF NOT EXISTS idx_replace_rules_rule ON replace_rules(rule_id)',
        'CREATE INDEX IF NOT EXISTS idx_chats_type_active ON chats(chat_type, is_active)',
        'CREATE INDEX IF NOT EXISTS idx_forward_rules_priority ON forward_rules(priority DESC)',
        'CREATE INDEX IF NOT EXISTS idx_forward_rules_created_at ON forward_rules(created_at)',
        'CREATE INDEX IF NOT EXISTS idx_media_signatures_type_size ON media_signatures(media_type, file_size)',
        'CREATE INDEX IF NOT EXISTS idx_media_signatures_last_seen ON media_signatures(last_seen)',
        'CREATE INDEX IF NOT EXISTS idx_rule_logs_action_created ON rule_logs(action, created_at)',
        'CREATE INDEX IF NOT EXISTS idx_rule_logs_rule_created ON rule_logs(rule_id, created_at)',
        'CREATE INDEX IF NOT EXISTS idx_rule_statistics_date ON rule_statistics(date)',
        'CREATE INDEX IF NOT EXISTS idx_chat_statistics_date ON chat_statistics(date)',
        'CREATE INDEX IF NOT EXISTS idx_error_logs_level_created ON error_logs(level, created_at)',
        'CREATE INDEX IF NOT EXISTS idx_task_queue_status_priority ON task_queue(status, priority DESC)',
        # [Optimization] 增加复合索引：状态+调度时间+优先级+创建时间，彻底覆盖 fetch_next 查询路径
        'CREATE INDEX IF NOT EXISTS idx_task_queue_fetch_bundle ON task_queue(status, scheduled_at, priority DESC, created_at)',
        'CREATE INDEX IF NOT EXISTS idx_task_queue_scheduled ON task_queue(scheduled_at)',
        'CREATE INDEX IF NOT EXISTS idx_task_queue_locked_until ON task_queue(locked_until)',
        'CREATE INDEX IF NOT EXISTS idx_task_queue_type_status ON task_queue(task_type, status)',
        'CREATE INDEX IF NOT EXISTS idx_task_queue_type_id_desc ON task_queue(task_type, id DESC)',
        'CREATE UNIQUE INDEX IF NOT EXISTS idx_system_config_key ON system_configurations(key)',
        'CREATE UNIQUE INDEX IF NOT EXISTS idx_task_queue_unique_key ON task_queue(unique_key)',
        'CREATE INDEX IF NOT EXISTS idx_task_queue_grouped_id ON task_queue(grouped_id)',
        'CREATE INDEX IF NOT EXISTS idx_task_queue_next_retry ON task_queue(next_retry_at)'
    ]

    _cleanup_duplicate_data(connection)
    _create_indexes_with_upgrade(connection, indexes)
    logger.info('已创建所有性能优化索引')


def _cleanup_duplicate_data(connection):
    """在创建唯一索引前清理重复数据"""
    cleanup_sqls = [
        """
        DELETE FROM task_queue 
        WHERE id NOT IN (
            SELECT MIN(id) 
            FROM task_queue 
            GROUP BY unique_key
        ) AND unique_key IS NOT NULL
        """,
        """
        DELETE FROM system_configurations 
        WHERE id NOT IN (
            SELECT MIN(id) 
            FROM system_configurations 
            GROUP BY key
        )
        """
    ]
    for cleanup_sql in cleanup_sqls:
        try:
            connection.execute(text(cleanup_sql))
        except Exception as e:
            logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')


def _create_indexes_with_upgrade(connection, indexes):
    """创建索引，必要时将非唯一索引升级为唯一索引"""
    for sql in indexes:
        try:
            if 'UNIQUE' in sql:
                idx_name = sql.split(' ')[-2] if 'IF NOT EXISTS' not in sql else sql.split(' ')[-3]
                check_sql = f"SELECT sql FROM sqlite_master WHERE name='{idx_name}'"
                res = connection.execute(text(check_sql)).fetchone()
                if res and 'UNIQUE' not in res[0].upper():
                    logger.info(f"升级索引 {idx_name} 为 UNIQUE...")
                    connection.execute(text(f"DROP INDEX {idx_name}"))
            connection.execute(text(sql))
        except Exception as e:
            logger.warning(f"创建索引 {sql[:30]}... 出错: {e}")


def _migrate_media_type_tables(connection, engine, existing_tables, inspector):
    """创建media_types和media_extensions表并迁移数据"""
    if 'media_types' not in existing_tables:
        logger.info("创建media_types表...")
        MediaTypes.__table__.create(connection)
        forward_rules_columns = {column['name'] for column in inspector.get_columns('forward_rules')}
        if 'selected_media_types' in forward_rules_columns:
            logger.info("迁移媒体类型数据...")
            rules = connection.execute(text("SELECT id, selected_media_types FROM forward_rules WHERE selected_media_types IS NOT NULL"))
            for rule in rules:
                rule_id, selected_types = rule
                if selected_types:
                    connection.execute(
                        text("INSERT INTO media_types (rule_id, photo, document, video, audio, voice) VALUES (:r, :p, :d, :v, :a, :vo)"),
                        {'r': rule_id, 'p': 'photo' in selected_types, 'd': 'document' in selected_types, 'v': 'video' in selected_types, 'a': 'audio' in selected_types, 'vo': 'voice' in selected_types}
                    )
    if 'media_extensions' not in existing_tables:
        logger.info("创建media_extensions表...")
        MediaExtensions.__table__.create(connection)


def _migrate_extended_columns(engine):
    """迁移扩展列：AI、总结、RSS等高级功能字段"""
    inspector = inspect(engine)
    forward_rules_columns = {column['name'] for column in inspector.get_columns('forward_rules')}
    keyword_columns = {column['name'] for column in inspector.get_columns('keywords')}
    rss_sub_columns = {column['name'] for column in inspector.get_columns('rss_subscriptions')}
    rss_configs_columns = {column['name'] for column in inspector.get_columns('rss_configs')}
    rule_logs_columns = {column['name'] for column in inspector.get_columns('rule_logs')}
    error_logs_columns = {column['name'] for column in inspector.get_columns('error_logs')}

    forward_rules_new_columns = {
        'is_ai': 'ALTER TABLE forward_rules ADD COLUMN is_ai BOOLEAN DEFAULT FALSE',
        'ai_model': 'ALTER TABLE forward_rules ADD COLUMN ai_model VARCHAR DEFAULT NULL',
        'ai_prompt': 'ALTER TABLE forward_rules ADD COLUMN ai_prompt VARCHAR DEFAULT NULL',
        'ai_persona': 'ALTER TABLE forward_rules ADD COLUMN ai_persona TEXT DEFAULT NULL',
        'is_summary': 'ALTER TABLE forward_rules ADD COLUMN is_summary BOOLEAN DEFAULT FALSE',
        'summary_time': 'ALTER TABLE forward_rules ADD COLUMN summary_time VARCHAR DEFAULT "07:00"',
        'summary_prompt': 'ALTER TABLE forward_rules ADD COLUMN summary_prompt VARCHAR DEFAULT NULL',
        'is_delete_original': 'ALTER TABLE forward_rules ADD COLUMN is_delete_original BOOLEAN DEFAULT FALSE',
        'is_original_sender': 'ALTER TABLE forward_rules ADD COLUMN is_original_sender BOOLEAN DEFAULT FALSE',
        'is_original_time': 'ALTER TABLE forward_rules ADD COLUMN is_original_time BOOLEAN DEFAULT FALSE',
        'is_keyword_after_ai': 'ALTER TABLE forward_rules ADD COLUMN is_keyword_after_ai BOOLEAN DEFAULT FALSE',
        'add_mode': 'ALTER TABLE forward_rules ADD COLUMN add_mode VARCHAR DEFAULT "BLACKLIST"',
        'enable_rule': 'ALTER TABLE forward_rules ADD COLUMN enable_rule BOOLEAN DEFAULT TRUE',
        'is_top_summary': 'ALTER TABLE forward_rules ADD COLUMN is_top_summary BOOLEAN DEFAULT TRUE',
        'is_filter_user_info': 'ALTER TABLE forward_rules ADD COLUMN is_filter_user_info BOOLEAN DEFAULT FALSE',
        'enable_delay': 'ALTER TABLE forward_rules ADD COLUMN enable_delay BOOLEAN DEFAULT FALSE',
        'delay_seconds': 'ALTER TABLE forward_rules ADD COLUMN delay_seconds INTEGER DEFAULT 5',
        'handle_mode': 'ALTER TABLE forward_rules ADD COLUMN handle_mode VARCHAR DEFAULT "FORWARD"',
        'enable_comment_button': 'ALTER TABLE forward_rules ADD COLUMN enable_comment_button BOOLEAN DEFAULT FALSE',
        'enable_media_type_filter': 'ALTER TABLE forward_rules ADD COLUMN enable_media_type_filter BOOLEAN DEFAULT FALSE',
        'enable_media_size_filter': 'ALTER TABLE forward_rules ADD COLUMN enable_media_size_filter BOOLEAN DEFAULT FALSE',
        'max_media_size': f'ALTER TABLE forward_rules ADD COLUMN max_media_size INTEGER DEFAULT 10',
        'is_send_over_media_size_message': 'ALTER TABLE forward_rules ADD COLUMN is_send_over_media_size_message BOOLEAN DEFAULT TRUE',
        'enable_extension_filter': 'ALTER TABLE forward_rules ADD COLUMN enable_extension_filter BOOLEAN DEFAULT FALSE',
        'extension_filter_mode': 'ALTER TABLE forward_rules ADD COLUMN extension_filter_mode VARCHAR DEFAULT "BLACKLIST"',
        'enable_reverse_blacklist': 'ALTER TABLE forward_rules ADD COLUMN enable_reverse_blacklist BOOLEAN DEFAULT FALSE',
        'enable_reverse_whitelist': 'ALTER TABLE forward_rules ADD COLUMN enable_reverse_whitelist BOOLEAN DEFAULT FALSE',
        'only_rss': 'ALTER TABLE forward_rules ADD COLUMN only_rss BOOLEAN DEFAULT FALSE',
        'enable_sync': 'ALTER TABLE forward_rules ADD COLUMN enable_sync BOOLEAN DEFAULT FALSE',
        'userinfo_template': 'ALTER TABLE forward_rules ADD COLUMN userinfo_template VARCHAR DEFAULT "**{name}**"',
        'time_template': 'ALTER TABLE forward_rules ADD COLUMN time_template VARCHAR DEFAULT "{time}"',
        'original_link_template': 'ALTER TABLE forward_rules ADD COLUMN original_link_template VARCHAR DEFAULT "原始连接：{original_link}"',
        'enable_push': 'ALTER TABLE forward_rules ADD COLUMN enable_push BOOLEAN DEFAULT FALSE',
        'enable_only_push': 'ALTER TABLE forward_rules ADD COLUMN enable_only_push BOOLEAN DEFAULT FALSE',
        'media_allow_text': 'ALTER TABLE forward_rules ADD COLUMN media_allow_text BOOLEAN DEFAULT FALSE',
        'enable_ai_upload_image': 'ALTER TABLE forward_rules ADD COLUMN enable_ai_upload_image BOOLEAN DEFAULT FALSE',
        'force_pure_forward': 'ALTER TABLE forward_rules ADD COLUMN force_pure_forward BOOLEAN DEFAULT FALSE',
        'enable_dedup': 'ALTER TABLE forward_rules ADD COLUMN enable_dedup BOOLEAN DEFAULT FALSE',
        'required_sender_id': 'ALTER TABLE forward_rules ADD COLUMN required_sender_id VARCHAR',
        'required_sender_regex': 'ALTER TABLE forward_rules ADD COLUMN required_sender_regex VARCHAR',
        'is_save_to_local': 'ALTER TABLE forward_rules ADD COLUMN is_save_to_local BOOLEAN DEFAULT FALSE',
    }

    keywords_new_columns = {'is_blacklist': 'ALTER TABLE keywords ADD COLUMN is_blacklist BOOLEAN DEFAULT TRUE'}
    rss_sub_new_columns = {'latest_post_date': 'ALTER TABLE rss_subscriptions ADD COLUMN latest_post_date TIMESTAMP', 'fail_count': 'ALTER TABLE rss_subscriptions ADD COLUMN fail_count INTEGER DEFAULT 0'}
    rss_configs_new_columns = {'is_description_compressed': 'ALTER TABLE rss_configs ADD COLUMN is_description_compressed BOOLEAN DEFAULT 0', 'is_prompt_compressed': 'ALTER TABLE rss_configs ADD COLUMN is_prompt_compressed BOOLEAN DEFAULT 0'}
    rule_logs_new_columns = {
        'message_text': 'ALTER TABLE rule_logs ADD COLUMN message_text TEXT',
        'message_type': 'ALTER TABLE rule_logs ADD COLUMN message_type VARCHAR',
        'processing_time': 'ALTER TABLE rule_logs ADD COLUMN processing_time INTEGER',
        'details': 'ALTER TABLE rule_logs ADD COLUMN details TEXT',
        'is_result_compressed': 'ALTER TABLE rule_logs ADD COLUMN is_result_compressed BOOLEAN DEFAULT 0'
    }
    error_logs_new_columns = {'is_traceback_compressed': 'ALTER TABLE error_logs ADD COLUMN is_traceback_compressed BOOLEAN DEFAULT 0'}

    with engine.connect() as connection:
        _apply_column_migrations(connection, forward_rules_columns, forward_rules_new_columns)
        _apply_column_migrations(connection, keyword_columns, keywords_new_columns)
        _apply_column_migrations(connection, rss_sub_columns, rss_sub_new_columns)
        _apply_column_migrations(connection, rss_configs_columns, rss_configs_new_columns)
        _apply_column_migrations(connection, rule_logs_columns, rule_logs_new_columns)
        _apply_column_migrations(connection, error_logs_columns, error_logs_new_columns)

        if 'forward_mode' not in forward_rules_columns:
            try: connection.execute(text("ALTER TABLE forward_rules RENAME COLUMN mode TO forward_mode"))
            except Exception as e:
                logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')

        _update_keywords_unique_constraint(connection, engine)


def _apply_column_migrations(connection, existing_columns, new_columns_map):
    """应用列迁移：仅添加不存在的列"""
    for column, sql in new_columns_map.items():
        if column not in existing_columns:
            try: connection.execute(text(sql)); logger.info(f'已添加列: {column}')
            except Exception as e: logger.error(f'添加列 {column} 出错: {e}')


def _update_keywords_unique_constraint(connection, engine):
    """更新keywords表的唯一约束"""
    result = connection.execute(text("SELECT name FROM sqlite_master WHERE type='index' AND name='unique_rule_keyword_is_regex_is_blacklist'"))
    if not result.fetchone():
        try:
            with engine.begin() as conn:
                conn.execute(text("CREATE TABLE keywords_temp (id INTEGER PRIMARY KEY AUTOINCREMENT, rule_id INTEGER, keyword TEXT, is_regex BOOLEAN, is_blacklist BOOLEAN)"))
                conn.execute(text("INSERT INTO keywords_temp (rule_id, keyword, is_regex, is_blacklist) SELECT rule_id, keyword, is_regex, is_blacklist FROM keywords"))
                conn.execute(text("DROP TABLE keywords"))
                conn.execute(text("ALTER TABLE keywords_temp RENAME TO keywords"))
                conn.execute(text("CREATE UNIQUE INDEX unique_rule_keyword_is_regex_is_blacklist ON keywords (rule_id, keyword, is_regex, is_blacklist)"))
        except Exception as e: logger.error(f"更新约束出错: {e}")


def migrate_db(engine):
    """数据库迁移函数，确保新字段的添加"""
    inspector = inspect(engine)
    existing_tables = {t.lower() for t in inspector.get_table_names()}

    if not _verify_connection(engine):
        return

    try:
        with engine.connect() as connection:
            _create_missing_tables(engine, existing_tables)

            try:
                _migrate_core_table_columns(connection, inspector)
            except Exception as e:
                logger.warning(f'更新表字段失败: {str(e)}')

            try:
                _create_performance_indexes(connection, engine)
            except Exception as e:
                logger.warning(f'创建索引时出错: {str(e)}')

            _migrate_media_type_tables(connection, engine, existing_tables, inspector)
            connection.commit()
    except Exception as e:
        logger.error(f'迁移过程中出错: {str(e)}')

    try:
        _migrate_extended_columns(engine)
    except Exception as e:
        logger.error(f"迁移终结阶段出错: {e}")
