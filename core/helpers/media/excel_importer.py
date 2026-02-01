from __future__ import annotations

import io

from typing import List, Tuple
from core.helpers.lazy_import import LazyImport

pd = LazyImport("pandas")


def parse_excel(content: bytes) -> Tuple[List[dict], List[dict]]:
    """解析 Excel 二进制内容，返回 (keywords, replacements)

    约定：
      - Sheet "keywords": 列 rule_id, keyword, is_regex, is_blacklist
      - Sheet "replacements": 列 rule_id, pattern, content
    """
    try:
        # 触发/检查 pandas 是否可用
        _ = pd.DataFrame
    except Exception as e:
        raise RuntimeError("缺少 pandas 依赖，请安装后再试") from e

    buf = io.BytesIO(content)
    xls = pd.ExcelFile(buf)

    keywords: List[dict] = []
    replacements: List[dict] = []

    if "keywords" in xls.sheet_names:
        df = pd.read_excel(xls, "keywords")
        for _, row in df.iterrows():
            keywords.append(
                {
                    "rule_id": int(row.get("rule_id")),
                    "keyword": str(row.get("keyword") or ""),
                    "is_regex": bool(row.get("is_regex")),
                    "is_blacklist": bool(row.get("is_blacklist")),
                }
            )

    if "replacements" in xls.sheet_names:
        df = pd.read_excel(xls, "replacements")
        for _, row in df.iterrows():
            replacements.append(
                {
                    "rule_id": int(row.get("rule_id")),
                    "pattern": str(row.get("pattern") or ""),
                    "content": str(row.get("content") or ""),
                }
            )

    return keywords, replacements
