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

def migrate_db(engine):
    """数据库迁移函数，确保新字段的添加"""
    inspector = inspect(engine)
    
    # 获取当前数据库中所有表
    existing_tables = inspector.get_table_names()
    
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
                Chat.__table__.create(engine)

            # 如果forward_rules表不存在，创建表
            if 'forward_rules' not in existing_tables:
                logger.info("创建forward_rules表...")
                ForwardRule.__table__.create(engine)

            # 如果keywords表不存在，创建表
            if 'keywords' not in existing_tables:
                logger.info("创建keywords表...")
                Keyword.__table__.create(engine)
            
            # 如果replace_rules表不存在，创建表
            if 'replace_rules' not in existing_tables:
                logger.info("创建replace_rules表...")
                ReplaceRule.__table__.create(engine)

            # 如果rule_syncs表不存在，创建表
            if 'rule_syncs' not in existing_tables:
                logger.info("创建rule_syncs表...")
                RuleSync.__table__.create(engine)


            # 如果users表不存在，创建表
            if 'users' not in existing_tables:
                logger.info("创建users表...")
                User.__table__.create(engine)

            # 如果rss_configs表不存在，创建表
            if 'rss_configs' not in existing_tables:
                logger.info("创建rss_configs表...")
                RSSConfig.__table__.create(engine)
                

            # 如果rss_patterns表不存在，创建表
            if 'rss_patterns' not in existing_tables:
                logger.info("创建rss_patterns表...")
                RSSPattern.__table__.create(engine)

            if 'audit_logs' not in existing_tables:
                logger.info("创建audit_logs表...")
                AuditLog.__table__.create(engine, checkfirst=True)

            if 'active_sessions' not in existing_tables:
                logger.info("创建active_sessions表...")
                ActiveSession.__table__.create(engine)

            # 如果push_configs表不存在，创建表
            if 'push_configs' not in existing_tables:
                logger.info("创建push_configs表...")
                PushConfig.__table__.create(engine)
            # 如果media_signatures表不存在，创建表
            if 'media_signatures' not in existing_tables:
                logger.info("创建media_signatures表...")
                MediaSignature.__table__.create(engine)
                
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
                ForwardMapping.__table__.create(engine)

            # 如果rss_subscriptions表不存在，创建表
            if 'rss_subscriptions' not in existing_tables:
                logger.info("创建rss_subscriptions表...")
                RSSSubscription.__table__.create(engine)

            # 创建ACL表
            if 'access_control_list' not in existing_tables:
                logger.info("创建access_control_list表...")
                AccessControlList.__table__.create(engine)
            
            # 补充现有表的新字段
            try:
                new_columns = [
                    'ALTER TABLE media_signatures ADD COLUMN count INTEGER DEFAULT 1',
                    'ALTER TABLE media_signatures ADD COLUMN media_type VARCHAR',
                    'ALTER TABLE media_signatures ADD COLUMN file_size INTEGER',
                    'ALTER TABLE media_signatures ADD COLUMN file_name VARCHAR',
                    'ALTER TABLE media_signatures ADD COLUMN mime_type VARCHAR',
                    'ALTER TABLE media_signatures ADD COLUMN duration INTEGER',
                    'ALTER TABLE media_signatures ADD COLUMN width INTEGER',
                    'ALTER TABLE media_signatures ADD COLUMN height INTEGER',
                    'ALTER TABLE media_signatures ADD COLUMN last_seen VARCHAR',
                    'ALTER TABLE media_signatures ADD COLUMN updated_at VARCHAR',
                    'ALTER TABLE media_signatures ADD COLUMN file_id VARCHAR',
                    'ALTER TABLE media_signatures ADD COLUMN content_hash VARCHAR'
                ]
                
                for sql in new_columns:
                    try:
                        connection.execute(text(sql))
                    except Exception:
                        pass
                        
                logger.info('已更新 media_signatures 表结构')
            except Exception as e:
                logger.warning(f'更新 media_signatures 表失败: {str(e)}')
            
            try:
                chat_columns = [
                    'ALTER TABLE chats ADD COLUMN chat_type VARCHAR',
                    'ALTER TABLE chats ADD COLUMN username VARCHAR',
                    'ALTER TABLE chats ADD COLUMN created_at VARCHAR',
                    'ALTER TABLE chats ADD COLUMN updated_at VARCHAR', 
                    'ALTER TABLE chats ADD COLUMN is_active BOOLEAN DEFAULT 1',
                    'ALTER TABLE chats ADD COLUMN member_count INTEGER',
                    'ALTER TABLE chats ADD COLUMN description VARCHAR'
                ]
                
                rule_columns = [
                    'ALTER TABLE forward_rules ADD COLUMN created_at VARCHAR',
                    'ALTER TABLE forward_rules ADD COLUMN updated_at VARCHAR',
                    'ALTER TABLE forward_rules ADD COLUMN created_by VARCHAR',
                    'ALTER TABLE forward_rules ADD COLUMN priority INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN description VARCHAR',
                    'ALTER TABLE forward_rules ADD COLUMN message_count INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN last_used VARCHAR',
                    'ALTER TABLE forward_rules ADD COLUMN daily_limit INTEGER',
                    'ALTER TABLE forward_rules ADD COLUMN rate_limit INTEGER',
                    'ALTER TABLE forward_rules ADD COLUMN webhook_url VARCHAR',
                    'ALTER TABLE forward_rules ADD COLUMN custom_config VARCHAR',
                    'ALTER TABLE forward_rules ADD COLUMN allow_delete_source_on_dedup BOOLEAN DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN message_thread_id INTEGER',
                    'ALTER TABLE forward_rules ADD COLUMN enable_duration_filter BOOLEAN DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN min_duration INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN max_duration INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN enable_resolution_filter BOOLEAN DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN min_width INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN max_width INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN min_height INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN max_height INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN enable_file_size_range BOOLEAN DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN min_file_size INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN max_file_size INTEGER DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN is_save_to_local BOOLEAN DEFAULT 0',
                    'ALTER TABLE forward_rules ADD COLUMN unique_key VARCHAR',
                    'ALTER TABLE forward_rules ADD COLUMN grouped_id VARCHAR'
                ]
                
                user_columns = [
                    'ALTER TABLE users ADD COLUMN email VARCHAR',
                    'ALTER TABLE users ADD COLUMN telegram_id VARCHAR',
                    'ALTER TABLE users ADD COLUMN is_active BOOLEAN DEFAULT 1',
                    'ALTER TABLE users ADD COLUMN is_admin BOOLEAN DEFAULT 0',
                    'ALTER TABLE users ADD COLUMN created_at VARCHAR',
                    'ALTER TABLE users ADD COLUMN last_login VARCHAR',
                    'ALTER TABLE users ADD COLUMN login_count INTEGER DEFAULT 0',
                    'ALTER TABLE users ADD COLUMN totp_secret VARCHAR',
                    'ALTER TABLE users ADD COLUMN is_2fa_enabled BOOLEAN DEFAULT 0',
                    'ALTER TABLE users ADD COLUMN backup_codes VARCHAR',
                    'ALTER TABLE users ADD COLUMN last_otp_token VARCHAR',
                    'ALTER TABLE users ADD COLUMN last_otp_at VARCHAR'
                ]
                
                all_columns = chat_columns + rule_columns + user_columns
                for sql in all_columns:
                    try:
                        connection.execute(text(sql))
                    except Exception:
                        pass
                
                taskqueue_new_columns = [
                    'ALTER TABLE task_queue ADD COLUMN done_count INTEGER DEFAULT 0',
                    'ALTER TABLE task_queue ADD COLUMN total_count INTEGER DEFAULT 0',
                    'ALTER TABLE task_queue ADD COLUMN forwarded_count INTEGER DEFAULT 0',
                    'ALTER TABLE task_queue ADD COLUMN filtered_count INTEGER DEFAULT 0',
                    'ALTER TABLE task_queue ADD COLUMN failed_count INTEGER DEFAULT 0',
                    'ALTER TABLE task_queue ADD COLUMN last_message_id INTEGER',
                    'ALTER TABLE task_queue ADD COLUMN source_chat_id VARCHAR',
                    'ALTER TABLE task_queue ADD COLUMN target_chat_id VARCHAR',
                    'ALTER TABLE task_queue ADD COLUMN unique_key VARCHAR',
                    'ALTER TABLE task_queue ADD COLUMN grouped_id VARCHAR',
                    'ALTER TABLE task_queue ADD COLUMN next_retry_at TIMESTAMP',
                    'ALTER TABLE task_queue ADD COLUMN error_log TEXT'
                ]
                for sql in taskqueue_new_columns:
                    try:
                        connection.execute(text(sql))
                    except Exception:
                        pass

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
                    'CREATE INDEX IF NOT EXISTS idx_task_queue_scheduled ON task_queue(scheduled_at)',
                    'CREATE INDEX IF NOT EXISTS idx_task_queue_type_status ON task_queue(task_type, status)',
                    'CREATE INDEX IF NOT EXISTS idx_task_queue_type_id_desc ON task_queue(task_type, id DESC)',
                    'CREATE INDEX IF NOT EXISTS idx_system_config_key ON system_configurations(key)',
                    'CREATE INDEX IF NOT EXISTS idx_task_queue_unique_key ON task_queue(unique_key)',
                    'CREATE INDEX IF NOT EXISTS idx_task_queue_grouped_id ON task_queue(grouped_id)',
                    'CREATE INDEX IF NOT EXISTS idx_task_queue_next_retry ON task_queue(next_retry_at)'
                ]
                
                for sql in indexes:
                    try:
                        connection.execute(text(sql))
                    except Exception:
                        pass
                        
                logger.info('已创建所有性能优化索引')
            except Exception as e:
                logger.warning(f'创建索引时出错: {str(e)}')
            
            if 'media_types' not in existing_tables:
                logger.info("创建media_types表...")
                MediaTypes.__table__.create(engine)
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
                MediaExtensions.__table__.create(engine)
                
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
                except Exception:
                    pass

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
