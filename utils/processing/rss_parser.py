
"""
Redirect buffer to avoid ImportErrors during migration.
This file is deprecated. Please update imports to `core.parsers.rss_parser`.
"""
import warnings
warnings.warn("Importing from utils.processing.rss_parser is deprecated. Use core.parsers.rss_parser instead.", DeprecationWarning, stacklevel=2)

from core.parsers.rss_parser import RSSParser, FeedEntry, ParsedFeed, rss_parser
