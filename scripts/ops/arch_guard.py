import ast
import sys
from pathlib import Path

# 定义层级及其定义的包名
LAYERS = {
    "core": "core",
    "repositories": "repositories",
    "services": "services",
    "handlers": "handlers",
    "web_admin": "web_admin",
}

# 禁止的层级依赖关系 (Layer -> Forbids dependency on layer)
FORBIDDEN_DEPENDENCIES = {
    "core": ["services", "handlers", "web_admin", "repositories"],
    "repositories": ["services", "handlers", "web_admin"],
    "services": ["handlers", "web_admin"],
    "models": ["services", "handlers", "web_admin", "repositories", "core"], # base models usually pure
}

def get_layer(path: Path, root: Path) -> str:
    parts = path.relative_to(root).parts
    if not parts:
        return None
    return parts[0]

def check_file(file_path: Path, root: Path):
    layer = get_layer(file_path, root)
    if layer not in FORBIDDEN_DEPENDENCIES:
        return []

    forbidden = FORBIDDEN_DEPENDENCIES[layer]
    violations = []

    try:
        with open(file_path, "r", encoding="utf-8-sig") as f:
            tree = ast.parse(f.read(), filename=str(file_path))
    except Exception as e:
        print(f"Error parsing {file_path}: {e}")
        return []

    for node in ast.iter_child_nodes(tree):
        dep = None
        if isinstance(node, ast.Import):
            for alias in node.names:
                dep = alias.name.split('.')[0]
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                dep = node.module.split('.')[0]
        
        if dep in forbidden:
            violations.append((node.lineno, dep))

    return violations

def main():
    root = Path(__file__).resolve().parent.parent.parent
    violations_found = False

    print(f"🔍 Running Architecture Guard in {root}...")

    # We only scan specific directories
    scan_dirs = ["core", "repositories", "services", "models"]
    
    for d in scan_dirs:
        dir_path = root / d
        if not dir_path.exists():
            continue
            
        for file_path in dir_path.rglob("*.py"):
            layer = get_layer(file_path, root)
            # 允许在 core/__init__.py 中进行某些操作（如果需要），但目前我们保持严格
            
            violations = check_file(file_path, root)
            if violations:
                violations_found = True
                for line, dep in violations:
                    print(f"❌ Violation in {file_path.relative_to(root)} [Layer: {layer}]: Forbidden dependency on '{dep}' at line {line}")

    if violations_found:
        print("\n💥 Architecture check failed!")
        sys.exit(1)
    else:
        print("\n✅ Architecture is compliant.")
        sys.exit(0)

if __name__ == "__main__":
    main()
