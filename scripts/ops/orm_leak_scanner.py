
import ast
import os
import sys

def get_service_files(root_dir):
    service_files = []
    for root, dirs, files in os.walk(root_dir):
        for file in files:
            if file.endswith(".py") and "services" in root:
                service_files.append(os.path.join(root, file))
    return service_files

class ORMLeakVisitor(ast.NodeVisitor):
    def __init__(self, filename):
        self.filename = filename
        self.leaks = []
        self.current_class = None

    def visit_ClassDef(self, node):
        self.current_class = node.name
        self.generic_visit(node)
        self.current_class = None

    def visit_FunctionDef(self, node):
        if not self.current_class or not self.current_class.endswith("Service"):
            return
        
        # Skip private methods
        if node.name.startswith("_"):
            return

        # Check return type annotation
        if node.returns:
            return_type = self._get_annotation_name(node.returns)
            if self._is_orm_model(return_type):
                self.leaks.append(f"{self.filename}:{node.lineno} Method '{node.name}' returns ORM Model '{return_type}'")

    def _get_annotation_name(self, node):
        if isinstance(node, ast.Name):
            return node.id
        elif isinstance(node, ast.Attribute):
            return f"{self._get_annotation_name(node.value)}.{node.attr}"
        elif isinstance(node, ast.Subscript): # List[Model]
            return self._get_annotation_name(node.slice)
        elif isinstance(node, ast.Tuple): # Union[Model, None]
             return ", ".join([self._get_annotation_name(e) for e in node.elts])
        return ""

    def _is_orm_model(self, type_name):
        # Heuristic: names starting with known patterns or import checks
        # But simple heuristic: if it looks like a model name (e.g. User, Rule, Message) and NOT a Schema/DTO
        # This is tricky without resolving imports.
        # Strict rule: Services usually return "DTO", "Schema", "dict", "bool", "int", "str", "None"
        # Suspicious: "User", "ForwardRule", "Chat", "Message"
        
        suspicious_models = {
            "User", "ForwardRule", "Chat", "Message", "Channel", "Log",
            "active_session", "APIKey", "SourceChannel", "TargetChannel"
        }
        
        # Split by dots/brackets
        parts = type_name.replace("List[", "").replace("Optional[", "").replace("Union[", "").replace("]", "").split(",")
        for part in parts:
            clean_part = part.strip().split(".")[-1] # Get Use from models.User
            if clean_part in suspicious_models:
                return True
        return False

def scan_services(root_dir):
    service_files = get_service_files(root_dir)
    total_leaks = 0
    print(f"Scanning {len(service_files)} service files for ORM leaks...")
    
    for file_path in service_files:
        try:
            with open(file_path, "r", encoding="utf-8") as f:
                tree = ast.parse(f.read())
            visitor = ORMLeakVisitor(file_path)
            visitor.visit(tree)
            
            for leak in visitor.leaks:
                print(leak)
                total_leaks += 1
        except Exception as e:
            print(f"Error parsing {file_path}: {e}")

    if total_leaks == 0:
        print("✅ No obvious ORM leaks found in Service layer return hints.")
    else:
        print(f"❌ Found {total_leaks} potential ORM leaks.")
        sys.exit(1)

if __name__ == "__main__":
    scan_services(os.getcwd())
