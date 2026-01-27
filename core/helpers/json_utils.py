"""
JSON工具封装，优先使用orjson提供极速序列化
"""

import json
import logging

logger = logging.getLogger(__name__)

try:
    import orjson

    _HAS_ORJSON = True

    def dumps(obj, default=None, option=None, sort_keys=False, **kwargs):
        """
        orjson.dumps returns bytes, so we decode to str to match json.dumps behavior
        """
        opts = option or (orjson.OPT_NON_STR_KEYS)
        if sort_keys:
            opts |= orjson.OPT_SORT_KEYS
        return orjson.dumps(obj, default=default, option=opts).decode("utf-8")

    def dumps_bytes(obj, default=None, option=None):
        return orjson.dumps(obj, default=default, option=option)

    def loads(s):
        return orjson.loads(s)

    JSONDecodeError = orjson.JSONDecodeError

except ImportError:
    _HAS_ORJSON = False
    
    def dumps(obj, **kwargs):
        kwargs.setdefault('ensure_ascii', False)
        return json.dumps(obj, **kwargs)

    def dumps_bytes(obj, **kwargs):
        return json.dumps(obj, **kwargs).encode('utf-8')

    def loads(s, **kwargs):
        return json.loads(s, **kwargs)

    JSONDecodeError = json.JSONDecodeError

# 兼容旧代码的命名
json_dumps = dumps
json_loads = loads
export_json_dumps = dumps
export_json_loads = loads
