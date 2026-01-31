import os
from pathlib import Path
from typing import Union
from core.config import settings

# 基础目录
BASE_DIR = settings.BASE_DIR
TEMP_DIR = settings.TEMP_DIR

# RSS 配置
RSS_HOST = settings.RSS_HOST
RSS_PORT = settings.RSS_PORT
RSS_BASE_URL = settings.RSS_BASE_URL
RSS_MEDIA_BASE_URL = settings.RSS_MEDIA_BASE_URL
RSS_ENABLED = settings.RSS_ENABLED

# 分页配置
RULES_PER_PAGE = settings.RULES_PER_PAGE
PUSH_CHANNEL_PER_PAGE = settings.PUSH_CHANNEL_PER_PAGE
MODELS_PER_PAGE = settings.AI_MODELS_PER_PAGE
KEYWORDS_PER_PAGE = settings.KEYWORDS_PER_PAGE

# 通用设置
DEFAULT_TIMEZONE = settings.DEFAULT_TIMEZONE
PROJECT_NAME = settings.PROJECT_NAME

# RSS 目录 (绝对路径)
RSS_MEDIA_DIR = str(settings.RSS_MEDIA_DIR)
RSS_DATA_DIR = str(settings.RSS_DATA_DIR)

# AI 默认值
DEFAULT_AI_MODEL = settings.DEFAULT_AI_MODEL
DEFAULT_SUMMARY_PROMPT = settings.DEFAULT_SUMMARY_PROMPT
DEFAULT_AI_PROMPT = settings.DEFAULT_AI_PROMPT

# UI 布局配置
SUMMARY_TIME_ROWS = settings.SUMMARY_TIME_ROWS
SUMMARY_TIME_COLS = settings.SUMMARY_TIME_COLS
DELAY_TIME_ROWS = settings.DELAY_TIME_ROWS
DELAY_TIME_COLS = settings.DELAY_TIME_COLS
MEDIA_SIZE_ROWS = settings.MEDIA_SIZE_ROWS
MEDIA_SIZE_COLS = settings.MEDIA_SIZE_COLS
MEDIA_EXTENSIONS_ROWS = settings.MEDIA_EXTENSIONS_ROWS
MEDIA_EXTENSIONS_COLS = settings.MEDIA_EXTENSIONS_COLS

# 消息与清理
BOT_MESSAGE_DELETE_TIMEOUT = settings.BOT_MESSAGE_DELETE_TIMEOUT
USER_MESSAGE_DELETE_ENABLE = settings.USER_MESSAGE_DELETE_ENABLE
CLEAR_TEMP_ON_START = settings.CLEAR_TEMP_ON_START

# 性能与逻辑
UFB_ENABLED = settings.UFB_ENABLED
FORWARD_CONCURRENCY = settings.FORWARD_CONCURRENCY
PROCESSED_GROUP_TTL_SECONDS = settings.PROCESSED_GROUP_TTL_SECONDS
PROCESSED_GROUP_MAX = settings.PROCESSED_GROUP_MAX
VERBOSE_LOG = settings.VERBOSE_LOG
DUP_SCAN_PAGE_SIZE = settings.DUP_SCAN_PAGE_SIZE

# 菜单标题
AI_SETTINGS_TEXT = """
当前AI提示词：

`{ai_prompt}`

当前总结提示词：

`{summary_prompt}`
"""

# 媒体设置文本
MEDIA_SETTINGS_TEXT = """
媒体设置：

- 纯转发：开启去重后，将对媒体组进行组内预去重并批量转发原消息ID（不下载不上传）。
- 非纯转发：在过滤链中对媒体组筛选与去重后重新组合为相册一次发送（多文件），单文件退化为单发。
- 去重优先使用文件ID，缺失时使用签名兜底，保持原始顺序。
"""
PUSH_SETTINGS_TEXT = """
推送设置：
请前往 https://github.com/caronc/apprise/wiki 查看添加推送配置格式说明
如 `ntfy://ntfy.sh/你的主题名`
"""

# 去重设置文本与参数
DUP_SETTINGS_TEXT = """
去重设置：
 - 开启去重：在目标会话内跳过已存在的相同媒体
 - 扫描会话：手动扫描会话内重复媒体并生成报告
 """

# 为每个规则生成特定的路径
def get_rule_media_dir(rule_id: Union[int, str]) -> str:
    """获取指定规则的媒体目录"""
    rule_path = os.path.join(RSS_MEDIA_DIR, str(rule_id))
    os.makedirs(rule_path, exist_ok=True)
    return rule_path

def get_rule_data_dir(rule_id: Union[int, str]) -> str:
    """获取指定规则的数据目录"""
    rule_path = os.path.join(RSS_DATA_DIR, str(rule_id))
    os.makedirs(rule_path, exist_ok=True)
    return rule_path
