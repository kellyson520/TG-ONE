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
    except Exception:
        return set()

def migrate_db(engine):
    """数据库迁移函数，确保新字段的添加"""
    inspector = inspect(engine)
    
    # 获取当前数据库中所有表 (结果转为小写以兼容 case-insensitive 检查)
    existing_tables = {t.lower() for t in inspector.get_table_names()}
    
    # 连接数据库
    try:
        connection = engine.connect()
    except Exception as e:
        logger.error(f"无法连接到数据库进行迁移: {e}")
        return

    # 分步骤执行迁移，避免一个错误导致全部失败
    
    # 1. 创建缺失的表
    try:
        with engine.connect() as connection:

            # 如果chats表不存在，创建表
            if 'chats' not in existing_tables:
                logger.info("创建chats表...")
                Chat.__table__.create(engine, checkfirst=True)

            # 如果forward_rules表不存在，创建表
            if 'forward_rules' not in existing_tables:
                logger.info("创建forward_rules表...")
                ForwardRule.__table__.create(engine, checkfirst=True)

            # 如果keywords表不存在，创建表
            if 'keywords' not in existing_tables:
                logger.info("创建keywords表...")
                Keyword.__table__.create(engine, checkfirst=True)
            
            # 如果replace_rules表不存在，创建表
            if 'replace_rules' not in existing_tables:
                logger.info("创建replace_rules表...")
                ReplaceRule.__table__.create(engine, checkfirst=True)

            # 如果rule_syncs表不存在，创建表
            if 'rule_syncs' not in existing_tables:
                logger.info("创建rule_syncs表...")
                RuleSync.__table__.create(engine, checkfirst=True)


            # 如果users表不存在，创建表
            if 'users' not in existing_tables:
                logger.info("创建users表...")
                User.__table__.create(engine, checkfirst=True)

            # 如果rss_configs表不存在，创建表
            if 'rss_configs' not in existing_tables:
                logger.info("创建rss_configs表...")
                RSSConfig.__table__.create(engine, checkfirst=True)
                

            # 如果rss_patterns表不存在，创建表
            if 'rss_patterns' not in existing_tables:
                logger.info("创建rss_patterns表...")
                RSSPattern.__table__.create(engine, checkfirst=True)

            if 'audit_logs' not in existing_tables:
                logger.info("创建audit_logs表...")
                AuditLog.__table__.create(engine, checkfirst=True)

            if 'active_sessions' not in existing_tables:
                logger.info("创建active_sessions表...")
                ActiveSession.__table__.create(engine, checkfirst=True)

            # 如果push_configs表不存在，创建表
            if 'push_configs' not in existing_tables:
                logger.info("创建push_configs表...")
                PushConfig.__table__.create(engine, checkfirst=True)
            # 如果media_signatures表不存在，创建表
            if 'media_signatures' not in existing_tables:
                logger.info("创建media_signatures表...")
                MediaSignature.__table__.create(engine, checkfirst=True)
                
            # 创建新的统计和管理表
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

            # 如果forward_mappings表不存在，创建表
            if 'forward_mappings' not in existing_tables:
                logger.info("创建forward_mappings表...")
                ForwardMapping.__table__.create(engine, checkfirst=True)

            # 如果rss_subscriptions表不存在，创建表
            if 'rss_subscriptions' not in existing_tables:
                logger.info("创建rss_subscriptions表...")
                RSSSubscription.__table__.create(engine, checkfirst=True)

            # 创建ACL表
            if 'access_control_list' not in existing_tables:
                logger.info("创建access_control_list表...")
                AccessControlList.__table__.create(engine, checkfirst=True)
            
            # 补充现有表的新字段
            try:
                media_columns_existing = _get_existing_columns(inspector, 'media_signatures')
                new_columns_map = {
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
                
                for col, sql in new_columns_map.items():
                    if col not in media_columns_existing:
                        try:
                            connection.execute(text(sql))
                            logger.info(f"已为 media_signatures 添加列: {col}")
                        except Exception as e:
                            logger.warning(f'添加列 {col} 失败: {e}')
                        
                logger.info('已检查 media_signatures 表结构')
            except Exception as e:
                logger.warning(f'检查 media_signatures 表失败: {str(e)}')
            
            try:
                chat_columns_existing = _get_existing_columns(inspector, 'chats')
                chat_columns_map = {
                    'chat_type': 'ALTER TABLE chats ADD COLUMN chat_type VARCHAR',
                    'username': 'ALTER TABLE chats ADD COLUMN username VARCHAR',
                    'created_at': 'ALTER TABLE chats ADD COLUMN created_at VARCHAR',
                    'updated_at': 'ALTER TABLE chats ADD COLUMN updated_at VARCHAR', 
                    'is_active': 'ALTER TABLE chats ADD COLUMN is_active BOOLEAN DEFAULT 1',
                    'member_count': 'ALTER TABLE chats ADD COLUMN member_count INTEGER',
                    'description': 'ALTER TABLE chats ADD COLUMN description VARCHAR'
                }
                
                for col, sql in chat_columns_map.items():
                    if col not in chat_columns_existing:
                        try:
                            connection.execute(text(sql))
                            logger.info(f"已为 chats 添加列: {col}")
                        except Exception as e:
                            logger.warning(f'添加列 {col} 失败: {e}')

                # 4.3 补充 chat_statistics 表的新字段
                chat_stats_columns_existing = _get_existing_columns(inspector, 'chat_statistics')
                chat_stats_map = {
                    'saved_traffic_bytes': 'ALTER TABLE chat_statistics ADD COLUMN saved_traffic_bytes INTEGER DEFAULT 0'
                }
                
                for col, sql in chat_stats_map.items():
                    if col not in chat_stats_columns_existing:
                        try:
                            connection.execute(text(sql))
                            logger.info(f"已为 chat_statistics 添加列: {col}")
                        except Exception as e:
                            logger.warning(f'添加列 {col} 失败: {e}')
                
                rule_columns_existing = _get_existing_columns(inspector, 'forward_rules')
                rule_columns_map = {
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
                
                for col, sql in rule_columns_map.items():
                    if col not in rule_columns_existing:
                        try:
                            connection.execute(text(sql))
                            logger.info(f"已为 forward_rules 添加列: {col}")
                        except Exception as e:
                            logger.warning(f'添加列 {col} 失败: {e}')
                
                user_columns_existing = _get_existing_columns(inspector, 'users')
                user_columns_map = {
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
                
                for col, sql in user_columns_map.items():
                    if col not in user_columns_existing:
                        try:
                            connection.execute(text(sql))
                            logger.info(f"已为 users 添加列: {col}")
                        except Exception as e:
                            logger.warning(f'添加列 {col} 失败: {e}')
                
                task_queue_columns_existing = _get_existing_columns(inspector, 'task_queue')
                taskqueue_columns_map = {
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
                    'error_log': 'ALTER TABLE task_queue ADD COLUMN error_log TEXT'
                }
                for col, sql in taskqueue_columns_map.items():
                    if col not in task_queue_columns_existing:
                        try:
                            connection.execute(text(sql))
                            logger.info(f"已为 task_queue 添加列: {col}")
                        except Exception as e:
                            logger.warning(f'添加列 {col} 失败: {e}')

                logger.info('已更新所有表的新字段')
            except Exception as e:
                logger.warning(f'更新表字段失败: {str(e)}')
                
            try:
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
                
                # 在创建唯一索引前，先清理重复数据
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

                for sql in indexes:
                    try:
                        # 检查是否需要从非唯一索引升级到唯一索引
                        if 'UNIQUE' in sql:
                            idx_name = sql.split(' ')[-2] if 'IF NOT EXISTS' not in sql else sql.split(' ')[-3]
                            # 简单的升级逻辑：如果存在且不是唯一的，则先删除
                            # SQLite 不支持 ALTER INDEX，只能先 DROP
                            # 注意：这里我们保守一点，如果失败说明可能已经存在唯一索引或者正在使用
                            check_sql = f"SELECT sql FROM sqlite_master WHERE name='{idx_name}'"
                            res = connection.execute(text(check_sql)).fetchone()
                            if res and 'UNIQUE' not in res[0].upper():
                                logger.info(f"升级索引 {idx_name} 为 UNIQUE...")
                                connection.execute(text(f"DROP INDEX {idx_name}"))
                        
                        connection.execute(text(sql))
                    except Exception as e:
                        logger.warning(f"创建索引 {sql[:30]}... 出错: {e}")
                        
                logger.info('已创建所有性能优化索引')
            except Exception as e:
                logger.warning(f'创建索引时出错: {str(e)}')
            
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
            
            connection.commit()
                
    except Exception as e:
        logger.error(f'迁移过程中出错: {str(e)}')
    
    try:
        with engine.connect() as connection:
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
        rule_logs_new_columns = {'is_result_compressed': 'ALTER TABLE rule_logs ADD COLUMN is_result_compressed BOOLEAN DEFAULT 0'}
        error_logs_new_columns = {'is_traceback_compressed': 'ALTER TABLE error_logs ADD COLUMN is_traceback_compressed BOOLEAN DEFAULT 0'}

        with engine.connect() as connection:
            for column, sql in forward_rules_new_columns.items():
                if column not in forward_rules_columns:
                    try: connection.execute(text(sql)); logger.info(f'已添加列: {column}')
                    except Exception as e: logger.error(f'添加列 {column} 出错: {e}')
            for column, sql in keywords_new_columns.items():
                if column not in keyword_columns:
                    try: connection.execute(text(sql)); logger.info(f'已添加列: {column}')
                    except Exception as e: logger.error(f'添加列 {column} 出错: {e}')
            
            if 'forward_mode' not in forward_rules_columns:
                try: connection.execute(text("ALTER TABLE forward_rules RENAME COLUMN mode TO forward_mode"))
                except Exception as e:
                    logger.warning(f'已忽略预期内的异常: {e}' if 'e' in locals() else '已忽略静默异常')

            # 约束更新 (SQLite 特色)
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

    except Exception as e:
        logger.error(f"迁移终结阶段出错: {e}")
