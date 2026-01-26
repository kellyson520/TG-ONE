import os
from dotenv import load_dotenv
from pathlib import Path
import logging
import sys
from utils.core.constants import RSS_HOST, RSS_PORT,DEFAULT_TIMEZONE,PROJECT_NAME
# 添加项目根目录到系统路径
sys.path.append(str(Path(__file__).resolve().parent.parent.parent.parent))

# 导入统一的常�?
from utils.core.constants import RSS_MEDIA_DIR, RSS_MEDIA_PATH, RSS_DATA_DIR, get_rule_media_dir, get_rule_data_dir

# 加载环境变量
load_dotenv()

class Settings:
    PROJECT_NAME: str = PROJECT_NAME
    HOST: str = RSS_HOST
    PORT: int = RSS_PORT
    TIMEZONE: str = DEFAULT_TIMEZONE
    # 数据存储路径
    BASE_DIR = Path(__file__).resolve().parent.parent.parent.parent
    DATA_PATH = RSS_DATA_DIR
    
    # 使用统一的媒体路径常�?
    RSS_MEDIA_PATH = RSS_MEDIA_PATH
    MEDIA_PATH = RSS_MEDIA_DIR
    
    
    # 获取规则特定路径的方�?
    @classmethod
    def get_rule_media_path(cls, rule_id):
        """获取指定规则的媒体目�?""
        return get_rule_media_dir(rule_id)
        
    @classmethod
    def get_rule_data_path(cls, rule_id):
        """获取指定规则的数据目�?""
        return get_rule_data_dir(rule_id)
    
    # 确保目录存在
    def __init__(self):
        os.makedirs(self.DATA_PATH, exist_ok=True)
        os.makedirs(self.MEDIA_PATH, exist_ok=True)
        logger = logging.getLogger(__name__)
        logger.info(f"RSS数据路径: {self.DATA_PATH}")
        logger.info(f"RSS媒体路径: {self.MEDIA_PATH}")

settings = Settings() 