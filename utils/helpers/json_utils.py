"""
JSON工具封装，优先使用orjson提供极速序列化
"""

import json

try:
    import orjson

    _HAS_ORJSON = True

    def json_dumps(obj):
        """
        使用orjson序列化对象

        Args:
            obj: 要序列化的对象

        Returns:
            str: 序列化后的JSON字符串
        """
        # orjson.dumps 返回 bytes，需要 decode 为 str 存入数据库 Text 字段
        # option=orjson.OPT_NON_STR_KEYS 允许非字符串键
        return orjson.dumps(obj, option=orjson.OPT_NON_STR_KEYS).decode("utf-8")

    def json_loads(obj):
        """
        使用orjson反序列化对象

        Args:
            obj: 要反序列化的JSON字符串

        Returns:
            反序列化后的对象
        """
        return orjson.loads(obj)

except ImportError:
    _HAS_ORJSON = False
    json_dumps = json.dumps
    json_loads = json.loads

# 导出工具方法
export_json_dumps = json_dumps
export_json_loads = json_loads
