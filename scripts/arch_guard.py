
import ast
import os
import sys

# Force UTF-8 output for Windows consoles to support emojis
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

# Define layering rules: Key component -> Forbidden imports
# Format: "component_dir": ["forbidden_component_1", "forbidden_component_2"]
RULES = {
    "repositories": ["services", "handlers", "web_admin"],
    "utils": ["services", "repositories", "models", "handlers", "web_admin", "core"],
    # Core Container/Bootstrap needs to import everything to wire the app, so we allow it.
    # However, strict helpers should not depend on business logic.
    "core/helpers": ["services", "repositories", "handlers", "web_admin"],
    
    "services": ["handlers", "web_admin"], # Services should not depend on UI/Controllers
    "models": ["services", "repositories", "handlers", "web_admin", "core"], # Models are pure data structure
}

def get_project_files(root_dir):
    files_to_check = []
    for root, dirs, files in os.walk(root_dir):
        if "venv" in root or ".git" in root or "__pycache__" in root:
            continue
        for file in files:
            if file.endswith(".py"):
                files_to_check.append(os.path.join(root, file))
    return files_to_check

def check_imports(file_path, root_dir):
    # Determine which component this file belongs to
    # Determine which component this file belongs to
    rel_path = os.path.relpath(file_path, root_dir).replace("\\", "/")
    component = None
    
    # Check strict subdirectories first (Rule keys must use forward slashes)
    if rel_path.startswith("core/helpers"):
        component = "core/helpers"
    else:
        # Top level components
        parts = rel_path.split("/")
        if len(parts) > 0 and parts[0] in RULES:
            component = parts[0]

    if not component:
        return []

    forbidden = RULES.get(component, [])
    violations = []
    
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            tree = ast.parse(f.read())
            
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    msg = _check_import(alias.name, forbidden)
                    if msg: violations.append((node.lineno, msg))
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    msg = _check_import(node.module, forbidden)
                    if msg: violations.append((node.lineno, msg))
                    
    except Exception as e:
        # print(f"Error parsing {file_path}: {e}")
        pass
        
    return violations

def _check_import(module_name, forbidden_list):
    # module_name could be "services.user_service" or "models"
    parts = module_name.split(".")
    if not parts: return None
    
    top_level = parts[0]
    if top_level in forbidden_list:
        return f"Imports '{module_name}' which is forbidden for this component."
    return None

def main():
    root_dir = os.getcwd()
    print(f"Scanning for architecture violations in {root_dir}...")
    
    violations_count = 0
    files = get_project_files(root_dir)
    
    for file_path in files:
        violations = check_imports(file_path, root_dir)
        if violations:
            print(f"\n📄 {os.path.relpath(file_path, root_dir)}")
            for lineno, msg in violations:
                print(f"  Line {lineno}: ❌ {msg}")
                violations_count += 1
                
    if violations_count == 0:
        print("\n✅ Architecture verification passed! No layering violations found.")
        sys.exit(0)
    else:
        print(f"\n❌ Found {violations_count} architecture violations.")
        sys.exit(1)

if __name__ == "__main__":
    main()
