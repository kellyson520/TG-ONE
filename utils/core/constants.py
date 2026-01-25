import os
from dotenv import load_dotenv
from pathlib import Path

# 加载环境变量
load_dotenv()

# 目录配置
BASE_DIR = Path(__file__).parent.parent
TEMP_DIR = os.path.join(BASE_DIR, "temp")

RSS_HOST = os.getenv("RSS_HOST", "127.0.0.1")
RSS_PORT = os.getenv("RSS_PORT", "8000")

# RSS基础URL，如果未设置，则使用请求的URL
RSS_BASE_URL = os.environ.get("RSS_BASE_URL", None)

# RSS媒体文件的基础URL，用于生成媒体链接，如果未设置，则使用请求的URL
RSS_MEDIA_BASE_URL = os.getenv("RSS_MEDIA_BASE_URL", "")

RSS_ENABLED = os.getenv("RSS_ENABLED", "false")

RULES_PER_PAGE = int(os.getenv("RULES_PER_PAGE", 20))

PUSH_CHANNEL_PER_PAGE = int(os.getenv("PUSH_CHANNEL_PER_PAGE", 10))

DEFAULT_TIMEZONE = os.getenv("DEFAULT_TIMEZONE", "Asia/Shanghai")
PROJECT_NAME = os.getenv("PROJECT_NAME", "TG Forwarder RSS")
# RSS相关路径配置
RSS_MEDIA_PATH = os.getenv("RSS_MEDIA_PATH", "./rss/media")

# 转换为绝对路径
RSS_MEDIA_DIR = os.path.abspath(
    os.path.join(BASE_DIR, RSS_MEDIA_PATH)
    if not os.path.isabs(RSS_MEDIA_PATH)
    else RSS_MEDIA_PATH
)

# RSS数据路径
RSS_DATA_PATH = os.getenv("RSS_DATA_PATH", "./rss/data")
RSS_DATA_DIR = os.path.abspath(
    os.path.join(BASE_DIR, RSS_DATA_PATH)
    if not os.path.isabs(RSS_DATA_PATH)
    else RSS_DATA_PATH
)

# 默认AI模型
DEFAULT_AI_MODEL = os.getenv("DEFAULT_AI_MODEL", "gpt-4o")
# 默认AI总结提示词
DEFAULT_SUMMARY_PROMPT = os.getenv(
    "DEFAULT_SUMMARY_PROMPT", "请总结以下频道/群组24小时内的消息。"
)
# 默认AI提示词
DEFAULT_AI_PROMPT = os.getenv(
    "DEFAULT_AI_PROMPT", "请尊重原意，保持原有格式不变，用简体中文重写下面的内容："
)

# 分页配置
MODELS_PER_PAGE = int(os.getenv("AI_MODELS_PER_PAGE", 10))
KEYWORDS_PER_PAGE = int(os.getenv("KEYWORDS_PER_PAGE", 50))

# 按钮布局配置
SUMMARY_TIME_ROWS = int(os.getenv("SUMMARY_TIME_ROWS", 10))
SUMMARY_TIME_COLS = int(os.getenv("SUMMARY_TIME_COLS", 6))

DELAY_TIME_ROWS = int(os.getenv("DELAY_TIME_ROWS", 10))
DELAY_TIME_COLS = int(os.getenv("DELAY_TIME_COLS", 6))

MEDIA_SIZE_ROWS = int(os.getenv("MEDIA_SIZE_ROWS", 10))
MEDIA_SIZE_COLS = int(os.getenv("MEDIA_SIZE_COLS", 6))

MEDIA_EXTENSIONS_ROWS = int(os.getenv("MEDIA_EXTENSIONS_ROWS", 6))
MEDIA_EXTENSIONS_COLS = int(os.getenv("MEDIA_EXTENSIONS_COLS", 6))

LOG_MAX_SIZE_MB = 10
LOG_BACKUP_COUNT = 3

# 默认消息删除时间 (秒)
BOT_MESSAGE_DELETE_TIMEOUT = int(os.getenv("BOT_MESSAGE_DELETE_TIMEOUT", 300))

# 自动删除用户发送的指令消息
USER_MESSAGE_DELETE_ENABLE = os.getenv("USER_MESSAGE_DELETE_ENABLE", "false")

# 是否启用UFB
UFB_ENABLED = os.getenv("UFB_ENABLED", "false")

# 并发度：处理单条消息时并发执行匹配/转发规则的最大并发
FORWARD_CONCURRENCY = int(os.getenv("FORWARD_CONCURRENCY", "5"))

# 媒体组去重：缓存保留秒数与最大容量（超过容量将按 FIFO 移除最早的键）
PROCESSED_GROUP_TTL_SECONDS = int(os.getenv("PROCESSED_GROUP_TTL_SECONDS", "120"))
PROCESSED_GROUP_MAX = int(os.getenv("PROCESSED_GROUP_MAX", "5000"))

# 是否输出高频 Info 日志（如每条消息预览、规则数量）。false 则降为 debug
VERBOSE_LOG = os.getenv("VERBOSE_LOG", "false").lower() in {"1", "true", "yes"}

# 启动时是否清空 ./temp 临时目录
CLEAR_TEMP_ON_START = os.getenv("CLEAR_TEMP_ON_START", "1").lower() in {
    "1",
    "true",
    "yes",
}

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

DUP_SCAN_PAGE_SIZE = int(os.getenv("DUP_SCAN_PAGE_SIZE", "200"))


# 为每个规则生成特定的路径
def get_rule_media_dir(rule_id):
    """获取指定规则的媒体目录"""
    rule_path = os.path.join(RSS_MEDIA_DIR, str(rule_id))
    # 确保目录存在
    os.makedirs(rule_path, exist_ok=True)
    return rule_path


def get_rule_data_dir(rule_id):
    """获取指定规则的数据目录"""
    rule_path = os.path.join(RSS_DATA_DIR, str(rule_id))
    # 确保目录存在
    os.makedirs(rule_path, exist_ok=True)
    return rule_path
