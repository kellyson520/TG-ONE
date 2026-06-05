"""
JSON工具封装，优先使用orjson提供极速序列化
"""

import json
import logging

logger = logging.getLogger(__name__)

from typing import Any, Union, Optional, cast

try:
    import orjson
    _HAS_ORJSON = True

    def dumps(obj: Any, default: Optional[Any] = None, option: Optional[int] = None, sort_keys: bool = False, **kwargs: Any) -> str:
        """
        orjson.dumps returns bytes, so we decode to str to match json.dumps behavior
        """
        opts = option or (orjson.OPT_NON_STR_KEYS)
        if sort_keys:
            opts |= orjson.OPT_SORT_KEYS
        return cast(str, orjson.dumps(obj, default=default, option=opts).decode("utf-8"))

    def dumps_bytes(obj: Any, default: Optional[Any] = None, option: Optional[int] = None, **kwargs: Any) -> bytes:
        return cast(bytes, orjson.dumps(obj, default=default, option=option or 0))

    def loads(s: Union[str, bytes, bytearray], **kwargs: Any) -> Any:
        return orjson.loads(s)

    JSONDecodeError = orjson.JSONDecodeError

except ImportError:
    _HAS_ORJSON = False
    
    def dumps(obj: Any, default: Optional[Any] = None, option: Optional[int] = None, sort_keys: bool = False, **kwargs: Any) -> str:
        kwargs.setdefault('ensure_ascii', False)
        if sort_keys:
            kwargs['sort_keys'] = True
        if default:
            kwargs['default'] = default
        # option argument is ignored in json fallback
        return json.dumps(obj, **kwargs)

    def dumps_bytes(obj: Any, default: Optional[Any] = None, option: Optional[int] = None, **kwargs: Any) -> bytes:
        # Pass default if present (json.dumps handles it via kwargs usually or named arg)
        # We need to construct kwargs for json.dumps
        d = kwargs.copy()
        if default:
            d['default'] = default
        # option ignored
        return json.dumps(obj, **d).encode('utf-8')

    def loads(s: Union[str, bytes, bytearray], **kwargs: Any) -> Any:
        return json.loads(s, **kwargs)

    JSONDecodeError = json.JSONDecodeError

# 兼容旧代码的命名
json_dumps = dumps
json_loads = loads
export_json_dumps = dumps
export_json_loads = loads
