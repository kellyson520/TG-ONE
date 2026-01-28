import sys
import os
import argparse
import subprocess
from typing import List, Tuple

# Force UTF-8 output
if sys.stdout and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

def run_command(cmd: List[str], cwd: str = ".") -> Tuple[int, str, str]:
    """Run a command and return returncode, stdout, stderr."""
    try:
        result = subprocess.run(
            cmd, 
            cwd=cwd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8', 
            errors='replace'
        )
        return result.returncode, result.stdout, result.stderr
    except FileNotFoundError:
        return 127, "", f"找不到命令: {cmd[0]}"

def print_step(name: str):
    print(f"\n{'='*60}")
    print(f"🔄 正在执行: {name}")
    print(f"{'='*60}")

def check_architecture(root_dir: str) -> bool:
    print_step("架构守卫 (分层与依赖)")
    # Updated to find arch_guard in the same directory as local_ci.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, "arch_guard.py")
    if not os.path.exists(script_path):
        print("❌ 未找到 scripts/arch_guard.py!")
        return False
        
    code, out, err = run_command([sys.executable, script_path], cwd=root_dir)
    print(out)
    if code != 0:
        print(f"❌ 架构检查失败，错误码 {code}")
        print(err)
        return False
    return True

def check_code_quality(root_dir: str) -> bool:
    print_step("代码质量 (语法、命名、导入)")
    
    # 核心检查目标
    targets = ["src", "core", "services", "handlers", "utils", "web_admin", "models", "listeners"]
    existing_targets = [d for d in targets if os.path.exists(os.path.join(root_dir, d))]
    
    if not existing_targets:
        print("⚠️ 未找到需要检查的源代码目录。")
        return True

    # Flake8 Select Codes:
    # E9: SyntaxError
    # F63: Logic Error (always true etc)
    # F7: Compile Error
    # F82: Undefined Name (F821, F822, F823)
    # F401: Module imported but unused
    # F811: Redefinition of unused name
    # E402: Module level import not at top (Optional, good for clarity)
    critical_selects = "E9,F63,F7,F82,F401,F811"
    
    cmd = [
        sys.executable, "-m", "flake8"
    ] + existing_targets + [
        "--count",
        f"--select={critical_selects}",
        "--show-source",
        "--statistics"
    ]
    
    print(f"正在对以下目录进行严格检查: {', '.join(existing_targets)}")
    code, out, err = run_command(cmd, cwd=root_dir)
    
    # Parse and count errors
    # Flake8 output line format: file:line:col: code message
    error_counts = {}
    lines = out.strip().splitlines()
    for line in lines:
        parts = line.split()
        for part in parts:
            if part.startswith(('E', 'F', 'W')) and part[1:].isdigit():
                # Found a code like F401
                code_key = part.strip(':') 
                error_counts[code_key] = error_counts.get(code_key, 0) + 1
                break

    print(out)
    
    if error_counts:
        print("\n📊 错误统计报告:")
        print(f"{'Code':<8} {'Count':<8} {'Description':<30}")
        print("-" * 50)
        descriptions = {
            'F401': 'Module imported but unused',
            'F811': 'Redefinition of unused name',
            'F821': 'Undefined name',
            'E999': 'Syntax Error',
            # Add others as encountered
        }
        total = 0
        for code_key, count in sorted(error_counts.items(), key=lambda x: x[1], reverse=True):
            desc = descriptions.get(code_key, "Lint Error")
            print(f"{code_key:<8} {count:<8} {desc:<30}")
            total += count
        print("-" * 50)
        print(f"{'Total':<8} {total:<8}\n")

    if code != 0:
        print(err)
        print("❌ 发现严重代码质量问题 (未定义名称、未使用的导入、语法错误)。")
        
        # Suggest auto-fix
        script_dir = os.path.dirname(os.path.abspath(__file__))
        fix_script = os.path.join(script_dir, "fix_lint.py")
        if os.path.exists(fix_script):
            rel_path = os.path.relpath(fix_script, root_dir)
            print(f"\n💡 建议: 检测到可通过脚本修复的 Lint 错误。")
            print(f"   请运行: python {rel_path}")
            
        return False
    
    print("✅ 代码质量检查通过。")
    return True

def run_targeted_test(root_dir: str, test_targets: List[str]) -> bool:
    print_step(f"目标测试: {', '.join(test_targets)}")
    
    if len(test_targets) > 3:
        print(f"⚠️ 超出限制: 您请求了 {len(test_targets)} 个测试文件。")
        print("为防止系统卡顿，请一次最多运行 3 个测试文件。")
        return False
        
    for target in test_targets:
        if not os.path.exists(os.path.join(root_dir, target)):
            print(f"❌ 未找到测试文件: {target}")
            return False

    cmd = [sys.executable, "-m", "pytest"] + test_targets
    
    code, out, err = run_command(cmd, cwd=root_dir)
    
    print(out)
    if code != 0:
        print(err)
        print(f"❌ 测试失败。")
        return False
        
    print("✅ 目标测试通过。")
    return True

def main():
    parser = argparse.ArgumentParser(description="TG ONE 本地 CI 运行器")
    parser.add_argument("--test", "-t", nargs='+', help="要运行的特定测试文件 (最多 3 个)", default=[])
    parser.add_argument("--skip-arch", action="store_true", help="跳过架构检查")
    parser.add_argument("--skip-quality", action="store_true", help="跳过代码质量检查 (flake8)")
    
    args = parser.parse_args()
    root_dir = os.getcwd()

    passes = True
    
    # 1. Architecture
    if not args.skip_arch:
        if not check_architecture(root_dir):
            passes = False
            
    # 2. Code Quality (Strict)
    if passes and not args.skip_quality:
        if not check_code_quality(root_dir):
            passes = False
            
    # 3. Targeted Test
    if passes:
        if args.test:
            if not run_targeted_test(root_dir, args.test):
                passes = False
        else:
            print("\n⚠️ 未提供特定测试目标 (--test)。跳过单元测试。")
            print("💡 最佳实践: 请始终运行与您更改相关的测试文件 (最多 3 个)。")
            print("❌ 禁止运行完整测试套件 (pytest .)，以防止系统卡顿。")

    if passes:
        print("\n✨✨ 本地 CI 通过 - 准备发布 ✨✨")
        sys.exit(0)
    else:
        print("\n🛑 本地 CI 失败 - 请在推送前修复错误 🛑")
        sys.exit(1)

if __name__ == "__main__":
    main()
