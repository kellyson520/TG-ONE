import logging
from pathlib import Path
import re
import json

logger = logging.getLogger(__name__)

class FeedService:
    @staticmethod
    def extract_telegram_title_and_content(content: str) -> tuple[str, str]:
        """从Telegram消息中提取标题和内容"""
        if not content:
            logger.info("输入内容为空,返回空标题和内容")
            return "", ""
        try:
            # 读取标题模板配置
            config_path = Path(__file__).parent.parent / 'configs' / 'title_template.json'
            if not config_path.exists():
                logger.warning(f"标题模板配置文件不存在: {config_path}")
                return content[:20], content
                
            with open(config_path, 'r', encoding='utf-8') as f:
                title_config = json.load(f)
            # 遍历每个模式
            for pattern_info in title_config['patterns']:
                pattern_str = pattern_info['pattern']
                pattern_desc = pattern_info['description']
                # 编译正则表达式
                pattern = re.compile(pattern_str, re.MULTILINE)
                # 尝试匹配
                match = pattern.match(content)
                if match:
                    title = FeedService.clean_title(match.group(1))
                    # 获取匹配部分的起始和结束位置
                    start, end = match.span(0)
                    # 提取剩余内容，去除开头的空白字符
                    remaining_content = content[end:].lstrip()
                    return title, remaining_content
                    
            # 如果没有匹配到任何模式，使用前20个字符作为标题
            clean_content = FeedService.clean_content(content)
            clean_content = clean_content.replace('\n', ' ').strip()
            title = clean_content[:20]
            if len(clean_content) > 20:
                title += "..."
            return title, content
        except Exception as e:
            logger.error(f"提取标题和内容时出错: {str(e)}")
            return content[:20], content
            
    @staticmethod
    def clean_title(title: str) -> str:
        """清理标题"""
        if not title: return ""
        return title.strip()
        
    @staticmethod
    def clean_content(content: str) -> str:
        """清理内容"""
        if not content: return ""
        return content.strip()
