
import subprocess
import sys

def sync():
    print("🔍 Syncing dependencies with uv...")
    req_file = "requirements.txt"
    try:
        # 使用 uv 直接同步依赖，比手动解析更可靠且快速
        # 指定 --python 确保安装到当前环境
        cmd = [
            "uv", "pip", "install", 
            "-r", req_file, 
            "--python", sys.executable,
            "--index-url", "https://pypi.tuna.tsinghua.edu.cn/simple"
        ]
        
        print(f"Exec: {' '.join(cmd)}")
        subprocess.check_call(cmd)
        print("✅ Dependencies synced successfully.")
            
    except Exception as e:
        print(f"❌ Dependency sync failed: {e}")
        # Non-critical for dev tools? But usually critical for startup.
        sys.exit(1)

if __name__ == "__main__":
    sync()
