
try:
    import orjson
    
    def dumps(obj, default=None, option=None, sort_keys=False, **kwargs):
        """
        orjson.dumps returns bytes, so we decode to str to match json.dumps behavior
        when used as a direct replacement in some contexts (e.g. logging).
        However, for web frameworks, bytes is often preferred. 
        Here we define a compatible 'dumps' that returns str, 
        but we also expose 'dumps_bytes' for high perf.
        """
        # orjson.OPT_NON_STR_KEYS allows non-string keys in dicts
        # orjson.OPT_INDENT_2 for pretty print if needed (not default)
        
        # We try to mimic standard json.dumps defaults
        opts = option or (orjson.OPT_NON_STR_KEYS)
        
        # Handle sort_keys compatibility
        if sort_keys:
            opts |= orjson.OPT_SORT_KEYS

        return orjson.dumps(obj, default=default, option=opts).decode('utf-8')

    def dumps_bytes(obj, default=None, option=None):
        return orjson.dumps(obj, default=default, option=option)

    def loads(s):
        return orjson.loads(s)

    JSONDecodeError = orjson.JSONDecodeError

except ImportError:
    import json
    
    def dumps(obj, **kwargs):
        # ensure_ascii=False is usually desired default in modern web apps
        kwargs.setdefault('ensure_ascii', False)
        return json.dumps(obj, **kwargs)

    def dumps_bytes(obj, **kwargs):
        return json.dumps(obj, **kwargs).encode('utf-8')

    def loads(s, **kwargs):
        return json.loads(s, **kwargs)

    JSONDecodeError = json.JSONDecodeError
