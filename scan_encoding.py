
import os

def is_suspicious(text):
    # Common mojibake patterns
    # "Ã©" is often 'é' from UTF-8 viewed as Latin-1
    # "ä¸" is often Chinese viewed as Latin-1
    suspicious_substrings = ["Ã©", "Ã¤", "Ã¼", "ä¸", "å", "æ", "è", "ï¿½"]
    
    # Check if file has a lot of these or looks weird.
    # Actually, "å", "æ", "è" are valid characters in some langs, but in a purely Chinese/English project, 
    # seeing "å" followed by other high-bit chars might be mojibake.
    # The most common Chinese mojibake (UTF-8 as Latin-1) results in 3 chars per Chinese char.
    # e.g. '中' (E4 B8 AD) -> 'ä¸' (E4 B8) ...
    
    count = 0
    for s in suspicious_substrings:
        if s in text:
            count += text.count(s)
            
    # Heuristic: if we see 'ï¿½', it's definitely broken (replacement char).
    if "ï¿½" in text:
         return True, "Contains Replacement Char"
         
    # If we see combinations like "ä¸" (common for '中' etc)
    if "ä¸" in text or "å" in text or "æ" in text:
        # Check if it looks like UTF-8 interpreted as Latin-1
        try:
            # If we encode to latin-1 and then decode as utf-8, does it make sense?
            # This is risky as a heuristic for *valid* utf-8 files which actually contain these chars.
            # But in this project context (TG ONE), we expect English + Chinese.
            pass
        except:
            pass
            
    if count > 0:
        return True, f"Suspicious chars count: {count}"
        
    return False, ""

def scan(root_dir):
    print(f"Scanning {root_dir}...")
    issues = []
    
    for root, dirs, files in os.walk(root_dir):
        # Skip hidden and venv
        if '.git' in dirs: dirs.remove('.git')
        if '.agent' in dirs: dirs.remove('.agent')
        if '__pycache__' in dirs: dirs.remove('__pycache__')
        if 'venv' in dirs: dirs.remove('venv')
        if 'node_modules' in dirs: dirs.remove('node_modules')
        
        for file in files:
            if not file.endswith(('.py', '.md', '.txt', '.json', '.yml', '.yaml')):
                continue
                
            path = os.path.join(root, file)
            try:
                with open(path, 'r', encoding='utf-8') as f:
                    content = f.read()
                    suspicious, reason = is_suspicious(content)
                    if suspicious:
                         print(f"SUSPICIOUS: {path} -> {reason}")
                         issues.append((path, 'suspicious', reason))
            except UnicodeDecodeError:
                print(f"NON-UTF8: {path}")
                issues.append((path, 'non-utf8', 'UnicodeDecodeError'))
            except Exception as e:
                print(f"ERROR: {path} -> {e}")

    return issues

if __name__ == "__main__":
    scan(".")
