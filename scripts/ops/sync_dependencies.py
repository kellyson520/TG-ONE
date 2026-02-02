
import importlib.metadata
import os
import re
import subprocess
import sys

def sync():
    print("🔍 Checking dependencies...")
    req_file = "requirements.txt"
    if not os.path.exists(req_file):
        print(f"⚠️ {req_file} not found, skipping dependency check.")
        return

    try:
        with open(req_file, "r", encoding="utf-8") as f:
            requirements = [line.strip() for line in f if line.strip() and not line.startswith("#")]
        
        missing = []
        for req in requirements:
            # Handle comments and version specs
            # Regex to extract package name from something like "fastapi==0.128.0" or "pydantic[email]>=2.0"
            match = re.match(r'^([a-zA-Z0-9\-_\[\]]+)', req)
            if not match:
                continue
            
            pkg_name_full = match.group(1)
            # Extract basic package name (no extras like [email])
            pkg_name_base = pkg_name_full.split('[')[0]
            
            try:
                importlib.metadata.version(pkg_name_base)
            except importlib.metadata.PackageNotFoundError:
                missing.append(req)
        
        if missing:
            print(f"📦 Found {len(missing)} missing or outdated dependencies.")
            for m in missing:
                print(f"   - {m}")
            
            print("pailing installation...")
            # Use -i https://pypi.tuna.tsinghua.edu.cn/simple for speed in China
            cmd = [sys.executable, "-m", "pip", "install", "-i", "https://pypi.tuna.tsinghua.edu.cn/simple"] + missing
            subprocess.check_call(cmd)
            print("✅ Dependencies installed successfully.")
        else:
            print("✅ All dependencies are satisfied.")
            
    except Exception as e:
        print(f"❌ Dependency check failed: {e}")
        # Don't exit with 1, let the app try to start anyway if possible
        # unless it's a critical error. 

if __name__ == "__main__":
    sync()
