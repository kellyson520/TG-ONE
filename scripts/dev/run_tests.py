
import sys
import os
import subprocess
import time
from datetime import datetime

# ----------------------------------------------------------------------
# TG ONE Standard Test Runner
# ----------------------------------------------------------------------
# 此脚本封装了 pytest，实现了以下目标：
# 1. 自动重定向输出流到 tests/temp/reports/，保持控制台整洁。
# 2. 强制将 Pytest 缓存和覆盖率文件存放于 tests/temp/ 下，不污染根目录。
# 3. 自动打印测试摘要和报告路径。
# ----------------------------------------------------------------------

REPORTS_DIR = os.path.join("tests", "temp", "reports")
MAX_REPORTS = 20

def ensure_dirs():
    """Ensure necessary directories exist."""
    os.makedirs(REPORTS_DIR, exist_ok=True)
    os.makedirs(os.path.join("tests", "temp"), exist_ok=True)

def cleanup_old_reports():
    """Keep only the latest MAX_REPORTS reports."""
    try:
        reports = [
            os.path.join(REPORTS_DIR, f) 
            for f in os.listdir(REPORTS_DIR) 
            if os.path.isfile(os.path.join(REPORTS_DIR, f))
        ]
        reports.sort(key=os.path.getmtime)
        
        while len(reports) > MAX_REPORTS:
            os.remove(reports.pop(0))
    except Exception as e:
        print(f"⚠️ Warning: Failed to cleanup old reports: {e}")

def run_pytest(args):
    """Run pytest with given arguments and capture output."""
    ensure_dirs()
    cleanup_old_reports()
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    # 构建命令
    cmd = [sys.executable, "-m", "pytest"] + args
    
    # 生成报告文件名
    # 尝试从参数中提取测试文件名作为描述
    desc = "all"
    for arg in args:
        if arg.endswith(".py") or "::" in arg:
            desc = os.path.basename(arg).replace(".py", "").replace("::", "_")
            break
            
    report_file = os.path.join(REPORTS_DIR, f"test_run_{timestamp}_{desc}.log")
    
    print(f"🚀 Running tests: {' '.join(args)}")
    print(f"📝 Logging to: {report_file}")
    
    start_time = time.time()
    
    # 强制将 stdout/stderr 写入文件同时也输出到控制台（tee行为）
    # 但由于 Agent 希望不污染，我们主要依靠文件，只在控制台输出简洁信息？
    # 不，Agent 需要看测试结果判断下一步。所以我们还是需要输出到控制台。
    # 我们的目标是 "平常的测试输出报告也要这样做"，即生成文件的同时（且是标准化位置），控制台照常。
    
    with open(report_file, "w", encoding="utf-8") as f:
        f.write(f"Command: {' '.join(cmd)}\n")
        f.write(f"Time: {datetime.now()}\n")
        f.write("-" * 60 + "\n\n")
        
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT, # Redirect stderr to stdout
            text=True,
            encoding='utf-8',
            errors='replace',
            cwd=os.getcwd(),
            bufsize=1
        )
        
        full_output = []
        
        try:
            while True:
                line = process.stdout.readline()
                if not line and process.poll() is not None:
                    break
                
                if line:
                    # Print to console
                    sys.stdout.write(line)
                    sys.stdout.flush()
                    
                    # Write to file
                    f.write(line)
                    f.flush()
                    
                    full_output.append(line)
                    
            process.wait()
            code = process.returncode
            
        except KeyboardInterrupt:
            process.kill()
            f.write("\n\n[Aborted by user]\n")
            print("\n🛑 Test run aborted.")
            return 1
            
    elapsed = time.time() - start_time
    
    # 打印页脚
    print("\n" + "="*60)
    if code == 0:
        print(f"✅ Tests Passed in {elapsed:.2f}s")
    else:
        print(f"❌ Tests Failed in {elapsed:.2f}s")
    print(f"📄 Report saved: {report_file}")
    print("="*60)
    
    return code

if __name__ == "__main__":
    # Remove script name from args
    pytest_args = sys.argv[1:]
    if not pytest_args:
        # Default to standard unit tests if no args provided?
        # Or just pass nothing to pytest (which usually runs everything)
        pass
        
    sys.exit(run_pytest(pytest_args))
