from typing import Dict, Callable, Optional, Tuple

class RadixNode:
    def __init__(self, path: str = ""):
        self.path = path
        self.children: Dict[str, 'RadixNode'] = {}
        self.handler: Optional[Callable] = None
        self.param_name: Optional[str] = None
        self.is_wildcard = False

class RadixRouter:
    """
    Radix Tree 路由实现
    用于 Telegram Callback 路径的高效分发。
    支持路径参数，如 "rule:{id}:edit"
    """
    def __init__(self):
        self.root = RadixNode()

    def add_route(self, path: str, handler: Callable):
        """添加路由"""
        node = self.root
        parts = path.split(':')
        
        for i, part in enumerate(parts):
            if not part: continue
            
            # 检查是否为参数位
            if part.startswith('{') and part.endswith('}'):
                param_name = part[1:-1]
                if '*' in node.children:
                    node = node.children['*']
                else:
                    new_node = RadixNode('*')
                    new_node.param_name = param_name
                    new_node.is_wildcard = True
                    node.children['*'] = new_node
                    node = new_node
            else:
                if part not in node.children:
                    node.children[part] = RadixNode(part)
                node = node.children[part]
        
        node.handler = handler

    def match(self, path: str) -> Tuple[Optional[Callable], Dict[str, str]]:
        """匹配路由并提取参数"""
        parts = path.split(':')
        node = self.root
        params = {}
        
        for part in parts:
            if not part: continue
            
            if part in node.children:
                node = node.children[part]
            elif '*' in node.children:
                node = node.children['*']
                params[node.param_name] = part
            else:
                return None, {}
        
        return node.handler, params

    def build_from_dict(self, handlers_dict: Dict[str, Callable]):
        """从字典批量构建"""
        for path, handler in handlers_dict.items():
            self.add_route(path, handler)
