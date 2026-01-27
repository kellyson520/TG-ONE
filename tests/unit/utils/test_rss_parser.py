import unittest
from datetime import datetime
from core.parsers.rss_parser import rss_parser, FeedEntry

class TestRSSParser(unittest.TestCase):
    def test_xml_fallback_rss2(self):
        """测试 XML Fallback 解析 RSS 2.0"""
        rss_content = """<?xml version="1.0" encoding="UTF-8" ?>
<rss version="2.0">
<channel>
  <title>Test Feed</title>
  <link>http://www.example.com</link>
  <description>Test Description</description>
  <item>
    <title>Test Item 1</title>
    <link>http://www.example.com/item1</link>
    <description>Content 1</description>
    <guid>guid-1</guid>
    <pubDate>Mon, 06 Sep 2021 16:45:00 +0000</pubDate>
  </item>
</channel>
</rss>"""
        
        feed = rss_parser.parse(rss_content)
        self.assertIsNotNone(feed)
        self.assertEqual(feed.title, "Test Feed")
        self.assertEqual(feed.version, "rss2.0")
        self.assertEqual(len(feed.entries), 1)
        
        entry = feed.entries[0]
        self.assertEqual(entry.title, "Test Item 1")
        self.assertEqual(entry.link, "http://www.example.com/item1")
        self.assertEqual(entry.id, "guid-1")
        # Check date (approximate)
        self.assertIsInstance(entry.published, datetime)

    def test_xml_fallback_atom(self):
        """测试 XML Fallback 解析 Atom"""
        atom_content = """<?xml version="1.0" encoding="utf-8"?>
<feed xmlns="http://www.w3.org/2005/Atom">
  <title>Test Atom Feed</title>
  <entry>
    <title>Atom Entry</title>
    <link href="http://example.org/2003/12/13/atom03"/>
    <id>urn:uuid:1225c695-cfb8-4ebb-aaaa-80da344efa6a</id>
    <updated>2003-12-13T18:30:02Z</updated>
    <summary>Some text.</summary>
  </entry>
</feed>"""

        feed = rss_parser.parse(atom_content)
        self.assertIsNotNone(feed)
        self.assertEqual(feed.title, "Test Atom Feed")
        self.assertEqual(feed.version, "atom")
        self.assertEqual(len(feed.entries), 1)
        
        entry = feed.entries[0]
        self.assertEqual(entry.title, "Atom Entry")
        self.assertEqual(entry.id, "urn:uuid:1225c695-cfb8-4ebb-aaaa-80da344efa6a")
