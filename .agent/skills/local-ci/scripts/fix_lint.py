import sys
import os
import subprocess
import re
from collections import defaultdict
from typing import List, Dict, Tuple

def run_flake8(root_dir: str) -> List[str]:
    """Running flake8 to detect F401 and F811"""
    cmd = [
        sys.executable, "-m", "flake8",
        root_dir,
        "--select=F401,F811",
        "--format=%(path)s:%(row)d:%(col)d: %(code)s %(text)s"
    ]
    
    # Check if we should ignore any typical folders that might cause confusion?
    # Flake8 usually respects .flake8 or setup.cfg
    
    print(f"🔄 Executing Flake8 scan...")
    result = subprocess.run(
        cmd,
        cwd=root_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
        encoding='utf-8',
        errors='replace'
    )
    return result.stdout.strip().splitlines()

def parse_errors(lines: List[str]) -> Dict[str, List[Tuple[int, str, str]]]:
    errors = defaultdict(list)
    # Match: path:row:col: code message
    pattern = re.compile(r"^(.*?):(\d+):(\d+):\s*(F401|F811)\s*(.*)$")
    
    for line in lines:
        match = pattern.match(line)
        if match:
            path, row, col, code, msg = match.groups()
            errors[path].append((int(row), code, msg))
            
    # Sort by line number DESCENDING so we don't mess up indices when deleting lines
    # (Though we are safer to just map edits first, but simplistic approach is acceptable for now if careful)
    for path in errors:
        errors[path].sort(key=lambda x: x[0], reverse=True)
        
    return errors

def extract_unused_name(code: str, msg: str, line_content: str) -> str:
    """Extract the variable name from the error message."""
    unused_name = None
    
    if code == 'F401':
        # " 'os' imported but unused"
        # " 'models.models.User' imported but unused"
        m = re.search(r"'([^']+)' imported but unused", msg)
        if m:
            full_name = m.group(1)
            # If line is "import X.Y", we might want X.Y or Y depending on import style.
            # We'll try to guess based on what exists in the line.
            
            if "from " in line_content and " import " in line_content:
                # likely "from module import target"
                if "." in full_name:
                     unused_name = full_name.split(".")[-1]
                else:
                     unused_name = full_name
            else:
                 unused_name = full_name
                
    elif code == 'F811':
        # "redefinition of unused 'X' from line N"
        m = re.search(r"redefinition of unused '([^']+)'", msg)
        if m:
            unused_name = m.group(1)
            
    return unused_name

def fix_import_line(line: str, unused_name: str) -> str:
    """
    Remove unused_name from line.
    Returns None if line to be deleted.
    Returns string if modified.
    Returns original string if no change.
    """
    original_line = line
    safe_name = re.escape(unused_name)
    
    # Case 1: "import X as Y" or "from M import X as Y" -> Remove "X as Y"
    # Flake8 reports 'Y' as unused usually? Or X? 
    # If code is "import pandas as pd", and pd is unused, Flake8 says 'pd' imported but unused?
    # Actually F401 says 'pandas' parsed as 'pd' ???
    # Let's assume matches 'as unused_name' 
    
    # 1. Alias pattern: "something as unused_name"
    p_alias = r'[\w\.]+\s+as\s+\b{}\b'.format(safe_name)
    
    # 2. Simple pattern: "unused_name"
    p_simple = r'\b{}\b'.format(safe_name)
    
    target_pattern = None
    if re.search(p_alias, line):
        target_pattern = p_alias
    elif re.search(p_simple, line):
        target_pattern = p_simple
    else:
        # Not found
        return line

    # Removal strategies
    # A: target,
    # B: , target
    # C: target
    
    p_a = r'({})\s*,'.format(target_pattern)
    p_b = r',\s*({})'.format(target_pattern)
    p_c = r'({})'.format(target_pattern)
    
    new_line = line
    count = 0
    
    new_line, n = re.subn(p_a, '', new_line, count=1)
    if n > 0: count = n
    else:
        new_line, n = re.subn(p_b, '', new_line, count=1)
        if n > 0: count = n
        else:
            new_line, n = re.subn(p_c, '', new_line, count=1)
            if n > 0: count = n

    if count == 0:
        return line
        
    stripped = new_line.strip()
    if not stripped:
        return None
        
    # Comments only?
    if stripped.startswith('#'):
        return None
        
    # Hanging import check
    # "import" or "from x import" or "from x import ("
    # We want to preserve checking if parens are empty "()"
    
    # Remove hanging parens if they are empty "()"
    # But be careful if it was "from x import ( )" -> remove line
    # If "from x import ( a )" we keep it.
    
    if re.match(r'^[\s\w\.]*import\s*\(\s*\)\s*$', stripped):
        return None
        
    # If line ends with "import ", it's invalid unless it's a multi-line continuation we just broke?
    # But if we removed the last item, we return None (handled by !stripped)
    
    # Check for "from X import " (empty targets)
    if re.match(r'^\s*from\s+[\w\.]+\s+import\s*$', stripped):
        return None
        
    # Check for "import "
    if re.match(r'^\s*import\s*$', stripped):
        return None

    code_only = new_line.split('#')[0].strip()
    if not code_only:
        return None
        
    if code_only.endswith('('):
         # Checking "from X import (" -> if that was the only content left (meaning we removed everything?)
         # No, if we removed everything, count > 0 would have likely triggered above.
         pass

    return new_line

def locate_actual_line(lines: List[str], start_idx: int, unused_name: str) -> int:
    """
    Search for the line containing the unused_name starting from start_idx.
    Supports looking forward in a multi-line import block.
    """
    safe_name = re.escape(unused_name)
    # Pattern to find name as a word boundary
    pattern = re.compile(r'\b{}\b'.format(safe_name))
    
    # Look ONLY forward a bit (max 50 lines) to avoid scanning whole file
    limit = min(len(lines), start_idx + 50)
    
    for i in range(start_idx, limit):
        line = lines[i]
        # Ignore comments
        code_part = line.split('#')[0]
        if pattern.search(code_part):
            return i
            
        # If we hit an empty line or dedent that suggests end of block?
        # Python imports can be spaced out. But if we see a new 'import' statement or 'def' or 'class', stop?
        if i > start_idx:
            stripped = line.strip()
            if stripped.startswith(('def ', 'class ', '@', 'if ', 'while ')):
                return -1
                
    return -1

def apply_fixes(root_dir: str, errors: Dict[str, List[Tuple[int, str, str]]]):
    fixed_count = 0
    skipped_count = 0
    files_fixed = 0
    
    for relative_path, file_errors in errors.items():
        file_path = os.path.join(root_dir, relative_path)
        if not os.path.exists(file_path):
            continue
            
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                lines = f.readlines()
        except UnicodeDecodeError:
            print(f"❌ Skipped {relative_path} (encoding)")
            continue

        file_modified = False
        print(f"🔧 Fixing {relative_path} ({len(file_errors)} issues)...")
        
        # We process errors. But since we might change lines (delete lines), indices shift.
        # But we sorted errors descending by line number.
        # However, if we scan FORWARD to find the actual line, we might mess up if multiple errors point to the same block?
        # Descending order is typically safe for deletions below.
        # But if error 1 is line 6 (multi-line) and error 2 is line 6 (multi-line), both point to same block.
        # If we fix one inside the block, it's fine.
        
        # Issue: if we look forward and delete line 10. The next error (processed afterwards but higher line number?)
        # We sorted DESCENDING. So we process line 100 before line 6.
        # If error at line 6 points to content at line 10.
        # We scanned forward from 6 to 10. We modify 10.
        # This is safe because previous operations were at line > 10.
        
        for row, code, msg in file_errors:
            original_idx = row - 1
            if original_idx < 0 or original_idx >= len(lines):
                continue
            
            # 1. Determine unused name
            # We look at the original reported line to guess context?
            # Or just use the message?
            guess_line = lines[original_idx]
            unused_name = extract_unused_name(code, msg, guess_line)
            
            if not unused_name:
                skipped_count += 1
                continue
                
            # 2. Locate actual line
            # Often Flake8 reports start of statement.
            target_idx = locate_actual_line(lines, original_idx, unused_name)
            
            if target_idx == -1:
                # print(f"  Start line: {lines[original_idx].strip()}")
                # print(f"  Could not find '{unused_name}' near line {row}")
                skipped_count += 1
                continue
                
            # 3. Apply fix
            current_line = lines[target_idx]
            new_line = fix_import_line(current_line, unused_name)
            
            if new_line != current_line:
                if new_line is None:
                    lines.pop(target_idx)
                else:
                    lines[target_idx] = new_line
                file_modified = True
                fixed_count += 1
            else:
                skipped_count += 1

        if file_modified:
            with open(file_path, 'w', encoding='utf-8') as f:
                f.writelines(lines)
            files_fixed += 1
            
    print(f"\n✅ Fix complete.")
    print(f"Files Modified: {files_fixed}")
    print(f"Fixed Issues: {fixed_count}")
    print(f"Skipped Issues: {skipped_count}")

def main():
    root_dir = os.getcwd()
    print(f"📂 Scanning {root_dir} for F401/F811 errors...")
    
    output_lines = run_flake8(root_dir)
    errors = parse_errors(output_lines)
    
    if not errors:
        print("🎉 No unused imports or redefinitions found!")
        sys.exit(0)
    
    count = sum(len(e) for e in errors.values())
    print(f"🧐 Found {count} issues in {len(errors)} files.")
    
    apply_fixes(root_dir, errors)

if __name__ == "__main__":
    main()
