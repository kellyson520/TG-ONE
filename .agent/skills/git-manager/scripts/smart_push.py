import subprocess
import sys
import math

def run_git(args):
    """Run git command and return output."""
    try:
        return subprocess.check_output(["git"] + args, stderr=subprocess.STDOUT, text=True, encoding='utf-8').strip()
    except subprocess.CalledProcessError as e:
        print(f"Error running git {' '.join(args)}: {e.output}")
        raise

def batch_push(remote="origin", branch="main", batch_size_mb=50):
    """
    Push large repository in batches loosely based on commit history size.
    Note: Since we only have 1 initial commit with many files, we can't really 'batch' commits.
    However, we can try to push with increased buffer settings which we already did.
    
    If the user meant 'batch add and commit', that would be different.
    Since the commit is already made, we will focus on maximizing push success probability.
    """
    
    print(f"🚀 Configuring Git for large push (User: 526839739@qq.com)...")
    
    # 1. Optimize Configs
    configs = [
        ("http.postBuffer", "524288000"), # 500MB
        ("http.lowSpeedLimit", "0"),
        ("http.lowSpeedTime", "999999"),
        ("core.compression", "0"), # Speed up packing
    ]
    
    for key, val in configs:
        run_git(["config", key, val])
        
    print(f"✅ Config optimized. Starting Push...")
    
    # 2. Push with verbose output
    try:
        # Using subprocess.run to stream output to console if possible, but here we capture common errors
        process = subprocess.run(
            ["git", "push", "-u", remote, branch],
            check=False,
            capture_output=True,
            text=True,
            encoding='utf-8' # Force UTF-8 explicitly
        )
        
        if process.returncode == 0:
            print("🎉 Success! Code pushed to GitHub.")
            print(process.stdout)
        else:
            print("❌ Push failed.")
            print(process.stderr)
            
            # Smart Retry Logic for common errors
            if "GH007" in process.stderr:
                print("\n⚠️  Email Privacy Error Detected.")
                print("Please verify your email address is allowed in GitHub Settings > Emails.")
            elif "408" in process.stderr or "RPC failed" in process.stderr:
                print("\n⚠️  Network Timeout Detected.")
                print("Tip: Your internet connection might be unstable for large uploads.")

    except Exception as e:
        print(f"Fatal error: {str(e)}")

if __name__ == "__main__":
    batch_push()
