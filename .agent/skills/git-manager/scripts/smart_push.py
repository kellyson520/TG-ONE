import argparse
import subprocess
import sys
import os

def get_git_env():
    """Ensure Git output is in English for consistency and UTF-8 handling."""
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    # Windows-specific: ensure Python uses UTF-8 for IO
    env["PYTHONIOENCODING"] = "utf-8"
    return env

def run_git(args):
    """Run git command and return output."""
    try:
        # Pass env to force consistent output language
        return subprocess.check_output(
            ["git"] + args, 
            stderr=subprocess.STDOUT, 
            text=True, 
            encoding='utf-8',
            env=get_git_env()
        ).strip()
    except subprocess.CalledProcessError as e:
        # Don't exit yet, let caller handle
        raise e

def optimize_configs():
    """Apply optimizations for large repos and unstable networks."""
    configs = [
        ("http.postBuffer", "524288000"), # 500MB
        ("http.lowSpeedLimit", "0"),
        ("http.lowSpeedTime", "999999"),
        ("core.compression", "0"),
    ]
    print("🛠️  正在应用 Git 网络优化配置...")

    for key, val in configs:
        subprocess.run(["git", "config", key, val], check=False, env=get_git_env())

def get_noreply_email(username):
    """Guess GitHub noreply email."""
    # Common format: username@users.noreply.github.com
    # (Older accounts use ID+username, but this is a safe default for new pushes)
    return f"{username}@users.noreply.github.com"

def smart_push(remote="origin", branch="main", privacy_mode=False, force=False):
    optimize_configs()
    
    # 1. Check if we need to fix privacy
    if privacy_mode:
        try:
            user_name = run_git(["config", "user.name"])
            noreply = get_noreply_email(user_name)
            print(f"🔒 隐私保护: 切换邮箱至 {noreply}")
            subprocess.run(["git", "config", "user.email", noreply], check=True, env=get_git_env())
            # Try to amend the last commit to match this new email
            print("✍️  修正最后一次提交的作者信息...")
            subprocess.run(["git", "commit", "--amend", "--reset-author", "--no-edit"], check=False, env=get_git_env())
        except Exception as e:
            print(f"⚠️ 无法自动修复隐私信息: {e}")


    # 2. Push Loop
    print(f"🚀 正在推送到 {remote} 的 {branch} 分支...")

    cmd = ["git", "push", "-u", remote, branch]
    if force:
        cmd.insert(2, "--force")

    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, encoding='utf-8', env=get_git_env())
        
        if proc.returncode == 0:
            print("✅ 推送成功！")
            print(proc.stdout)
            return True
        else:
            err = proc.stderr
            print("❌ 推送失败。")
            print(err)
            
            # Auto-Diagnosis
            if "GH007" in err or "privacy" in err.lower():
                print("\n🚨 [诊断]: GitHub 拒绝了私有邮箱推送。")
                print("👉 建议: 请尝试添加 --privacy-fix 参数重试。")
            elif "408" in err or "RPC failed" in err:
                print("\n🚨 [诊断]: 网络超时。")
                print("👉 已应用网络优化，重试可能成效。")
            elif "fast-forward" in err or "rejected" in err:
                print("\n🚨 [诊断]: 远程分支领先于本地。")
                print("👉 请运行: git pull --rebase")
            return False


    except Exception as e:
        print(f"🔥 严重错误: {e}")
        return False


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Smart Push Wrapper")
    parser.add_argument("--remote", default="origin", help="Remote name")
    parser.add_argument("--branch", default="main", help="Branch name")
    parser.add_argument("--privacy-fix", action="store_true", help="Auto-switch to noreply email")
    parser.add_argument("--force", action="store_true", help="Force push")
    
    args = parser.parse_args()
    
    # If no arguments are provided, use defaults.
    # Args will always be populated with defaults by argparse.
    smart_push(args.remote, args.branch, args.privacy_fix, args.force)
