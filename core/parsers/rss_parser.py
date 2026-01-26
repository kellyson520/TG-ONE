import logging
import time
from dataclasses import dataclass, field
from typing import List, Optional, Tuple
from datetime import datetime
import email.utils

logger = logging.getLogger(__name__)

@dataclass
class FeedEntry:
    title: str
    link: str
    id: str  # Unique ID (GUID for RSS, ID for Atom)
    published: Optional[datetime] = None
    content: str = ""
    author: str = ""

@dataclass
class ParsedFeed:
    title: str
    entries: List[FeedEntry] = field(default_factory=list)
    version: str = "unknown"

class RSSParser:
    """
    通用 RSS/Atom 解析器
    优先使用 feedparser (如果安装)，否则使用内置 xml.etree (Zero-Dependency Fallback)
    """

    def __init__(self):
        self.use_fallback = False
        try:
            import feedparser
            self.feedparser = feedparser
            logger.info("使用 feedparser 进行 RSS 解析")
        except ImportError:
            self.use_fallback = True
            import xml.etree.ElementTree as ET
            self.ET = ET
            logger.warning("未检测到 feedparser，使用内置 xml.etree 进行 RSS 解析 (功能受限)")

    def parse(self, content: str) -> Optional[ParsedFeed]:
        if not self.use_fallback:
            return self._parse_with_feedparser(content)
        else:
            try:
                return self._parse_with_xml(content)
            except Exception as e:
                logger.error(f"XML 解析失败: {e}")
                return None

    def _parse_with_feedparser(self, content: str) -> ParsedFeed:
        feed = self.feedparser.parse(content)
        parsed_feed = ParsedFeed(title=feed.feed.get('title', 'Unknown Feed'))
        
        for entry in feed.entries:
            # 尝试解析时间
            pub_date = None
            if hasattr(entry, 'published_parsed') and entry.published_parsed:
                pub_date = datetime.fromtimestamp(time.mktime(entry.published_parsed))
            elif hasattr(entry, 'updated_parsed') and entry.updated_parsed:
                pub_date = datetime.fromtimestamp(time.mktime(entry.updated_parsed))

            parsed_feed.entries.append(FeedEntry(
                title=entry.get('title', ''),
                link=entry.get('link', ''),
                id=entry.get('id', entry.get('link', '')), # Fallback to link if ID missing
                published=pub_date,
                content=entry.get('summary', entry.get('description', '')),
                author=entry.get('author', '')
            ))
        
        parsed_feed.version = feed.version
        return parsed_feed

    def _parse_with_xml(self, content: str) -> ParsedFeed:
        """
        简单的 XML 解析回退方案
        支持 RSS 2.0 和 Atom 1.0 的常用字段
        """
        root = self.ET.fromstring(content)
        tag = root.tag.lower()
        
        if 'rss' in tag:
            return self._parse_rss2(root)
        elif 'feed' in tag: # Atom
            return self._parse_atom(root)
        else:
            raise ValueError(f"不支持的 Feed 格式: {tag}")

    def _parse_rss2(self, root) -> ParsedFeed:
        channel = root.find('channel')
        if channel is None:
            raise ValueError("Invalid RSS: missing channel")
            
        feed_title = channel.findtext('title', 'Unknown Feed')
        parsed_feed = ParsedFeed(title=feed_title, version="rss2.0")
        
        for item in channel.findall('item'):
            title = item.findtext('title', '')
            link = item.findtext('link', '')
            guid = item.findtext('guid')
            if not guid:
                guid = link # Fallback
            
            description = item.findtext('description', '')
            author = item.findtext('author', '')
            
            # 解析 RFC 822 日期
            pub_date_str = item.findtext('pubDate')
            pub_date = None
            if pub_date_str:
                try:
                    # 使用 email.utils 解析 RFC 822
                    ts = email.utils.mktime_tz(email.utils.parsedate_tz(pub_date_str))
                    pub_date = datetime.fromtimestamp(ts)
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse RSS2 date '{pub_date_str}': {e}")
                    pass

            parsed_feed.entries.append(FeedEntry(
                title=title,
                link=link,
                id=guid,
                published=pub_date,
                content=description,
                author=author
            ))
            
        return parsed_feed

    def _parse_atom(self, root) -> ParsedFeed:
        # Atom 通常有命名空间，稍微麻烦一点
        # 这里做一个简单的忽略命名空间的处理 (Hack for simplicity)
        # 更好的做法是正确处理 NS，但为了代码可读性和兼容性，这里简化处理
        
        # 辅助函数：查找带命名空间的标签
        ns = ''
        if '}' in root.tag:
            ns = root.tag.split('}')[0] + '}'

        title = root.findtext(f'{ns}title', 'Unknown Feed')
        parsed_feed = ParsedFeed(title=title, version="atom")
        
        for entry in root.findall(f'{ns}entry'):
            title = entry.findtext(f'{ns}title', '')
            
            # Link 往往是属性
            link_node = entry.find(f'{ns}link')
            link = link_node.attrib.get('href', '') if link_node is not None else ''
            
            id_val = entry.findtext(f'{ns}id')
            if not id_val:
                id_val = link
                
            content = entry.findtext(f'{ns}content', '')
            if not content:
                content = entry.findtext(f'{ns}summary', '')
                
            author_node = entry.find(f'{ns}author')
            author = author_node.findtext(f'{ns}name', '') if author_node is not None else ''

            # Atom 使用 ISO 8601
            updated_str = entry.findtext(f'{ns}updated')
            pub_date = None
            if updated_str:
                try:
                    pub_date = datetime.fromisoformat(updated_str.replace('Z', '+00:00'))
                except (ValueError, TypeError) as e:
                    logger.warning(f"Failed to parse Atom date '{updated_str}': {e}")
                    pass
            
            parsed_feed.entries.append(FeedEntry(
                title=title,
                link=link,
                id=id_val,
                published=pub_date,
                content=content,
                author=author
            ))

        return parsed_feed

# 全局单例
rss_parser = RSSParser()
