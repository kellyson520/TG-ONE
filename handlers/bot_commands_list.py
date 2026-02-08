from telethon.tl.types import BotCommand

BOT_COMMANDS = [
    # --- 基础与导航 ---
    BotCommand(command="start", description="启动机器人"),
    BotCommand(command="menu", description="唤起主菜单 (GUI)"),
    BotCommand(command="help", description="查看完整帮助文档"),
    BotCommand(command="admin", description="系统管理面板"),
    BotCommand(command="cancel", description="取消当前操作/退出模式"),

    # --- 优先级队列 (QoS) ---
    BotCommand(command="vip", description="设置当前群组优先级"),
    BotCommand(command="queue_status", description="查看队列拥塞状态"),

    # --- 规则管理 (核心) ---
    BotCommand(command="settings", description="管理当前会话规则 (s)"),
    BotCommand(command="bind", description="绑定新转发规则"),
    BotCommand(command="switch", description="切换当前管理的规则"),
    BotCommand(command="list_rule", description="列出所有转发规则"),
    BotCommand(command="copy_rule", description="复制规则配置"),
    BotCommand(command="delete_rule", description="删除指定规则"),
    BotCommand(command="clear_all", description="清空当前规则所有配置"),

    # --- 关键字管理 (当前规则) ---
    BotCommand(command="add", description="添加关键字 (a)"),
    BotCommand(command="add_regex", description="添加正则关键字 (ar)"),
    BotCommand(command="list_keyword", description="列出关键字列表"),
    BotCommand(command="remove_keyword", description="删除关键字 (rk)"),
    BotCommand(command="remove_keyword_by_id", description="按ID删除关键字"),
    BotCommand(command="clear_all_keywords", description="清空所有关键字"),
    BotCommand(command="clear_all_keywords_regex", description="清空正则关键字"),
    BotCommand(command="copy_keywords", description="从其他规则导入关键字"),
    BotCommand(command="copy_keywords_regex", description="从其他规则导入正则"),

    # --- 批量/全局关键字操作 ---
    BotCommand(command="add_all", description="添加关键字到所有规则"),
    BotCommand(command="add_regex_all", description="添加正则到所有规则"),
    BotCommand(command="remove_all_keyword", description="从所有规则删除关键字"),

    # --- 替换规则管理 ---
    BotCommand(command="replace", description="添加替换规则 (r)"),
    BotCommand(command="replace_all", description="添加替换到所有规则"),
    BotCommand(command="list_replace", description="列出替换规则"),
    BotCommand(command="remove_replace", description="删除替换规则"),
    BotCommand(command="clear_all_replace", description="清空所有替换规则"),
    BotCommand(command="copy_replace", description="从其他规则导入替换"),

    # --- 数据导入/导出 ---
    BotCommand(command="import_excel", description="导入Excel配置 (推荐)"),
    BotCommand(command="export_keyword", description="导出关键字"),
    BotCommand(command="export_replace", description="导出替换规则"),
    BotCommand(command="import_keyword", description="导入关键字文件"),
    BotCommand(command="import_regex_keyword", description="导入正则文件"),
    BotCommand(command="import_replace", description="导入替换文件"),

    # --- 媒体与下载 ---
    BotCommand(command="download", description="开启下载模式"),
    BotCommand(command="set_duration", description="设置视频时长限制"),
    BotCommand(command="set_resolution", description="设置分辨率限制"),
    BotCommand(command="set_size", description="设置文件大小限制"),
    BotCommand(command="video_cache_stats", description="视频缓存统计"),
    BotCommand(command="video_cache_clear", description="清理视频缓存"),

    # --- 统计与去重 ---
    BotCommand(command="forward_stats", description="转发数据统计"),
    BotCommand(command="forward_search", description="搜索转发记录"),
    BotCommand(command="dedup", description="开关去重功能"),
    BotCommand(command="dedup_scan", description="扫描当前会话重复消息"),

    # --- UFB (统一转发绑定) ---
    BotCommand(command="ufb_bind", description="绑定 UFB 域名"),
    BotCommand(command="ufb_unbind", description="解绑 UFB 域名"),
    BotCommand(command="ufb_item_change", description="切换 UFB 配置项"),

    # --- 搜索功能 ---
    BotCommand(command="search", description="搜索消息"),
    BotCommand(command="search_bound", description="在绑定频道搜索"),
    BotCommand(command="search_public", description="搜索公开频道"),
    BotCommand(command="search_all", description="全局聚合搜索"),

    # --- 运维与系统 ---
    BotCommand(command="update", description="检查更新/升级系统"),
    BotCommand(command="rollback", description="紧急回滚版本"),
    BotCommand(command="system_status", description="查看系统资源状态"),
    BotCommand(command="changelog", description="查看更新日志"),
    BotCommand(command="logs", description="查看系统日志"),
    BotCommand(command="download_logs", description="下载系统日志文件"),
    BotCommand(command="db_info", description="数据库概览"),
    BotCommand(command="db_health", description="数据库健康检查"),
    BotCommand(command="db_backup", description="立即备份数据库"),
    BotCommand(command="db_optimize", description="数据库真空优化"),
    BotCommand(command="delete_rss_user", description="删除 RSS 用户"),
]
