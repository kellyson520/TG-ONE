import sys
import os
import argparse
import subprocess
import time
import re
from typing import List, Tuple

try:
    from tqdm import tqdm
    HAS_TQDM = True
except ImportError:
    HAS_TQDM = False
    print("⚠️ 提示: 安装 tqdm 可获得更好的进度显示 (pip install tqdm)")

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
            stderr=subprocess.STDOUT,  # 将 stderr 重定向到 stdout
            text=True,
            encoding='utf-8', 
            errors='replace'
        )
        # 由于 stderr 已重定向到 stdout，返回空字符串作为 stderr
        return result.returncode, result.stdout, ""
    except FileNotFoundError:
        return 127, "", f"找不到命令: {cmd[0]}"

def print_step(name: str, step: int = 0, total: int = 0):
    """打印步骤信息，带进度提示"""
    print(f"\n{'='*60}")
    if step > 0 and total > 0:
        progress = f"[{step}/{total}]"
        percentage = f"({step*100//total}%)"
        print(f"🔄 {progress} {percentage} 正在执行: {name}")
    else:
        print(f"🔄 正在执行: {name}")
    print(f"{'='*60}")

def print_success(message: str):
    """打印成功信息"""
    print(f"✅ {message}")

def print_error(message: str):
    """打印错误信息"""
    print(f"❌ {message}")

def print_warning(message: str):
    """打印警告信息"""
    print(f"⚠️ {message}")

def check_architecture(root_dir: str, step: int = 0, total: int = 0) -> bool:
    """执行架构守卫检查"""
    print_step("架构守卫 (分层与依赖)", step, total)
    # Updated to find arch_guard in the same directory as local_ci.py
    script_dir = os.path.dirname(os.path.abspath(__file__))
    script_path = os.path.join(script_dir, "arch_guard.py")
    if not os.path.exists(script_path):
        print_error("未找到 scripts/arch_guard.py!")
        return False
    
    start_time = time.time()
    code, out, err = run_command([sys.executable, script_path], cwd=root_dir)
    elapsed = time.time() - start_time
    
    print(out)
    if code != 0:
        print_error(f"架构检查失败，错误码 {code} (耗时: {elapsed:.2f}s)")
        print(err)
        return False
    
    print_success(f"架构检查通过 (耗时: {elapsed:.2f}s)")
    return True

def check_flake8(root_dir: str, step: int = 0, total: int = 0) -> bool:
    """执行与 GitHub Actions 一致的 Flake8 检查"""
    print_step("代码质量 (GitHub Flake8 Mode)", step, total)
    start_time = time.time()
    
    # 1. Critical Errors (GitHub: Stop build if there are Python syntax errors or undefined names)
    # 对应: flake8 . --count --select=E9,F63,F7,F82 --show-source --statistics --exclude=...
    print("👉 阶段 1: 检查严重错误 (语法错误, 未定义名称)...")
    
    # 排除目录列表（与 GitHub CI 和 .flake8 保持一致）
    # 注意：engine.py 和 new_menu_callback.py 因文件过大或逻辑过于复杂导致 mccabe 溢出，必须排除
    exclude_dirs = ".git,__pycache__,.venv,venv,env,build,dist,*.egg-info,tests/temp,.agent/temp,archive,alembic,services/dedup/engine.py,handlers/button/callback/new_menu_callback.py"
    
    cmd_critical = [
        sys.executable, "-m", "flake8", ".",
        "--count",
        "--select=E9,F63,F7,F82",
        "--show-source",
        "--statistics",
        f"--exclude={exclude_dirs}"
    ]
    
    code, out, err = run_command(cmd_critical, cwd=root_dir)
    
    # 检查致命错误（即使返回码可能不正确）
    # 注意：Flake8 可能将错误输出到 stdout 或 stderr
    fatal_errors = [
        'RecursionError',
        'ValueError: source code string cannot contain null bytes',
        'SystemExit',
        'KeyboardInterrupt',
        'MemoryError'
    ]
    
    has_fatal_error = False
    combined_output = (out or "") + (err or "")
    for fatal_error in fatal_errors:
        if fatal_error in combined_output:
            has_fatal_error = True
            print_error(f"检测到致命错误: {fatal_error}")
            if fatal_error == 'RecursionError':
                print_warning("💡 提示: RecursionError 通常是由于某个函数圈复杂度过高。")
                print_warning("💡 建议: 使用 '--jobs 1 --verbose' 找出出错的文件并将其加入 exclude 列表。")
            break

    
    # 输出结果
    if out: print(out)
    if err: print(err)
    
    # 判断失败条件：返回码非0 或 存在致命错误
    if code != 0 or has_fatal_error:
        elapsed = time.time() - start_time
        print_error(f"GitHub Flake8 Critical Check 失败 (耗时: {elapsed:.2f}s)")
        if has_fatal_error:
            print("💡 检测到致命异常，这会导致 GitHub CI 构建失败。")
            print("💡 建议: 检查并修复导致异常的文件（可能是圈复杂度过高或文件损坏）。")
        else:
            print("💡 这些错误会导致 GitHub CI 构建失败，必须修复。")
        return False

    # 2. Warnings (GitHub: exit-zero treats all errors as warnings)
    # 对应: flake8 . --count --exit-zero --max-complexity=10 --max-line-length=127 --statistics --exclude=...
    print("\n👉 阶段 2: 检查代码风格与复杂度 (仅供参考)...")
    cmd_warning = [
        sys.executable, "-m", "flake8", ".",
        "--count",
        "--exit-zero",
        "--max-complexity=10",
        "--max-line-length=127",
        "--statistics",
        f"--exclude={exclude_dirs}"
    ]
    
    # 我们忽略这里的返回值，因为它带有 exit-zero，且 GitHub Action 不会因此失败
    # 但我们打印输出供开发者参考
    # 注意：即使遇到 RecursionError 也不应该导致 CI 失败（这只是警告阶段）
    code_w, out_w, err_w = run_command(cmd_warning, cwd=root_dir)
    
    # 检查是否有 RecursionError（仅警告，不失败）
    if 'RecursionError' in (out_w or ""):
        print_warning("检测到复杂度检查时的 RecursionError（某些文件过于复杂）")
        print_warning("这不影响 CI 通过，但建议后续重构相关文件")
    elif out_w:
        print(out_w)
    if err_w: print(err_w)
    
    elapsed = time.time() - start_time
    print_success(f"GitHub Flake8 检查通过 (耗时: {elapsed:.2f}s)")
    return True


def get_test_count(root_dir: str, targets: List[str] = []) -> int:
    """获取测试用例总数，用于进度条展示"""
    cmd = [sys.executable, "-m", "pytest", "--collect-only", "-q"] + targets
    # Use run_command but silented if possible
    try:
        result = subprocess.run(
            cmd, 
            cwd=root_dir,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding='utf-8', 
            errors='replace'
        )
        out = result.stdout
        # Match strings like "627 tests collected", "627 collected" or "collected 627 items"
        match = re.search(r"(\d+) (?:tests )?collected|collected (\d+) (?:tests )?item", out)
        if match:
            count = match.group(1) or match.group(2)
            return int(count)
    except Exception:
        pass
    return 0

def kill_residual_pytest():
    """清理残留的 pytest 进程"""
    if sys.platform == "win32":
        try:
            # 仅清理非当前进程创建的残留进程
            subprocess.run(["taskkill", "/F", "/IM", "pytest.exe", "/T"], capture_output=True)
            subprocess.run(["taskkill", "/F", "/IM", "python.exe", "/FI", "WINDOWTITLE eq pytest*", "/T"], capture_output=True)
        except Exception:
            pass

def get_memory_usage() -> float:
    """获取程序当前内存占用 (MB)"""
    try:
        import psutil
        process = psutil.Process(os.getpid())
        return process.memory_info().rss / (1024 * 1024)
    except ImportError:
        return 0.0

def save_error_report(content: str, root_dir: str):
    """保存错误报告到临时文件，供 AI 分析"""
    temp_dir = os.path.join(root_dir, "tests", "temp")
    os.makedirs(temp_dir, exist_ok=True)
    report_path = os.path.join(temp_dir, "ci_error_report.log")
    
    # 简单的过滤整理
    filtered_lines = []
    capture = False
    lines = content.splitlines()
    
    failures = []
    errors = []
    
    timestamp = time.strftime("%Y-%m-%d %H:%M:%S")
    
    for line in lines:
        # 捕获失败摘要
        if line.startswith("FAILED ") or line.startswith("ERROR "):
             # FAILED tests/xxx.py::test_xxx - AssertionError...
             parts = line.split(" - ", 1)
             if len(parts) > 0:
                 failures.append(parts[0])
        
        # 捕获详细 Traceback 区域
        if "= FAILURES =" in line or "= ERRORS =" in line:
            capture = True
            filtered_lines.append(f"\n--- {line.strip(' =')} ---\n")
            continue
        
        if capture:
            # 停止捕获条件
            if "= short test summary info =" in line or line.startswith("=========="):
                capture = False
                continue
            
            # 过滤掉一些不重要的行
            if not line.strip(): continue
            # 简单去重或保留关键行 (这里保留缩进的行通常是代码或Traceback)
            filtered_lines.append(line)

    summary_text = [
        f"CI 错误分析报告 - {timestamp}",
        "=" * 50,
        f"总计失败: {len(failures)}",
        "失败用例清单:"
    ] + [f"- {f}" for f in failures] + [
        "=" * 50,
        "详细堆栈跟踪 (已过滤):"
    ] + filtered_lines
    
    try:
        with open(report_path, "w", encoding="utf-8") as f:
            f.write("\n".join(summary_text))
        print_error(f"错误详情已导出至: {report_path}")
        print_warning("💡 建议: 请让 AI 查看此文件以修复错误。")
    except Exception as e:
        print_error(f"保存错误报告失败: {e}")

def run_tests(root_dir: str, test_targets: List[str], step: int = 0, total: int = 0) -> bool:
    """运行测试。若提供目标则针对性运行，否则全量并发运行 (-n 3)。"""
    
    # 启动前先清理残留
    kill_residual_pytest()
    
    # 检查内存墙
    mem = get_memory_usage()
    if mem > 1500: # 1.5GB 警告
        print_warning(f"当前内存占用较高: {mem:.2f}MB (系统限制 2GB)")

    cmd = [sys.executable, "-m", "pytest"]
    
    # 默认过滤项：排除性能、压力和慢速测试
    default_filters = ["not stress and not slow and not performance"]
    
    if test_targets:
        print_step(f"针对性测试: {', '.join(test_targets)}", step, total)
        for target in test_targets:
            if not os.path.exists(os.path.join(root_dir, target)):
                print_error(f"未找到测试文件: {target}")
                return False
        cmd.extend(test_targets)
        # 针对性测试时不开启并发，提高稳定性
    else:
        print_step("全量测试 (负载限制: 3)", step, total)
        cmd.extend(["-n", "3", "-m", default_filters[0]])
        # 排除性能目录
        if os.path.exists(os.path.join(root_dir, "tests/performance")):
             cmd.extend(["--ignore", "tests/performance"])

    # 性能与交互优化
    # 改回 --tb=short 以捕获必要的堆栈信息供分析
    # --maxfail=10: 失败过多自动停止
    cmd.extend(["-v", "--tb=short", "--maxfail=10"])

    print(f"🔄 正在启动 Pytest: {' '.join(cmd)}")
    start_time = time.time()
    
    out = ""
    code = 0

    if HAS_TQDM:
        # 获取预估总数
        count_args = test_targets if test_targets else ["-m", default_filters[0]]
        # 排除性能目录的计数
        if not test_targets and os.path.exists(os.path.join(root_dir, "tests/performance")):
             count_args.extend(["--ignore", "tests/performance"])
             
        test_count = get_test_count(root_dir, count_args)
        
        if test_count > 0:
            pbar = tqdm(total=test_count, desc="🧪 收集测试中...", unit="test", leave=True)
            
            process = None
            try:
                # Use a larger buffer to prevent pipe deadlock
                process = subprocess.Popen(
                    cmd,
                    cwd=root_dir,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.STDOUT,
                    text=True,
                    encoding='utf-8',
                    errors='replace',
                    bufsize=1, # Line buffered for real-time progress
                    creationflags=subprocess.CREATE_NEW_PROCESS_GROUP if sys.platform == "win32" else 0
                )
                
                full_output = []
                regex_normal = re.compile(r"^(.+?)::.*? (?:PASSED|FAILED|SKIPPED|ERROR|XPASS|XFAIL)")
                regex_xdist = re.compile(r"^\[gw\d+\]\s+\[\s*\d+%\].*?\s+(?:PASSED|FAILED|SKIPPED|ERROR|XPASS|XFAIL)\s+(.+?)::")
                
                # 守护机制：如果 30 秒内没有任何输出，且还在运行，可能挂起
                last_output_time = time.time()
                timeout_limit = 300 # 5分钟总限时 (单个文件)
                if not test_targets:
                    timeout_limit = 600 # 10分钟全量限时
                
                no_output_limit = 60 # 60秒无响应限时

                # Note: iter(readline) can still block if there is a long task but no newline.
                # However, pytest workers output per test completion.
                while True:
                    line = process.stdout.readline()
                    if not line and process.poll() is not None:
                        break
                    
                    if line:
                        last_output_time = time.time()
                        full_output.append(line)
                        
                        found = False
                        file_name = None
                        
                        match = regex_normal.search(line)
                        if match:
                            file_name = match.group(1)
                            found = True
                        else:
                            match = regex_xdist.search(line)
                            if match:
                                file_name = match.group(1)
                                found = True
                        
                        if found:
                            if file_name:
                                short_name = os.path.basename(file_name)
                                pbar.set_description(f"🧪 执行中: {short_name}")
                            pbar.update(1)
                    else:
                        # Check for hangs
                        now = time.time()
                        if now - last_output_time > no_output_limit:
                            raise TimeoutError(f"测试由于超过 {no_output_limit}s 无输出被中止。")
                        if now - start_time > timeout_limit:
                            raise TimeoutError(f"测试由于达到总限时 {timeout_limit}s 被中止。")
                        time.sleep(0.1) # Avoid busy wait
                
                process.stdout.close()
                code = process.wait()
                out = "".join(full_output)
            except KeyboardInterrupt:
                if process:
                    if sys.platform == "win32":
                        subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
                    else:
                        process.kill()
                pbar.close()
                print_error("\n用户取消测试。")
                sys.exit(1)
            except TimeoutError as te:
                if process:
                    if sys.platform == "win32":
                         subprocess.run(["taskkill", "/F", "/T", "/PID", str(process.pid)], capture_output=True)
                    else:
                         process.kill()
                pbar.close()
                print_error(f"\n❌ {te}")
                return False
            except Exception as e:
                if process:
                    process.kill()
                print_error(f"运行测试时发生错误: {e}")
                return False
            finally:
                pbar.close()
        else:
            # If count failed or 0, run normally
            code, out, err = run_command(cmd, cwd=root_dir)
            if err: out += "\nSTDERR:\n" + err
    else:
        # No tqdm, run normally
        code, out, err = run_command(cmd, cwd=root_dir)
        if err: out += "\nSTDERR:\n" + err

    elapsed = time.time() - start_time
    
    if code != 0:
        # Show last 20 lines of output if it failed to provide context
        lines = out.splitlines()
        print("\n".join(lines[-20:] if len(lines) > 20 else lines))
        print_error(f"测试失败 (耗时: {elapsed:.2f}s, 状态码: {code})")
        # Save detailed report
        save_error_report(out, root_dir)
        return False
    else:
        print_success(f"所有测试通过 (耗时: {elapsed:.2f}s)")
    return True
    elapsed = time.time() - start_time
    
    # Only print full output if it's small or there's an error
    # For CI, usually we want to see what happened, but if it passed we can be brief
    if code != 0:
        print(out)
        print(err)
        print_error(f"测试失败 (耗时: {elapsed:.2f}s)")
        return False
    else:
        # Print a summary of failures if any, or just success
        if "FAILED" in out or "ERROR" in out:
             print(out) # Still print if some tests failed even if code is somehow 0 (unlikely)
        
        print_success(f"所有测试通过 (耗时: {elapsed:.2f}s)")
    return True

def main():
    parser = argparse.ArgumentParser(description="TG ONE 本地 CI 运行器")
    # Change --test to accept multiple arguments
    parser.add_argument("--test", "-t", nargs='+', help="指定测试文件运行。若省略，则运行全量测试 (并发限制 3)。", default=[])
    parser.add_argument("--skip-arch", action="store_true", help="跳过架构检查")
    parser.add_argument("--skip-flake", action="store_true", help="跳过 flake8 检查")
    parser.add_argument("--skip-test", action="store_true", help="跳过测试")
    
    args = parser.parse_args()
    root_dir = os.getcwd()

    # 计算总步骤数
    total_steps = 0
    if not args.skip_arch:
        total_steps += 1
    if not args.skip_flake:
        total_steps += 1
    if not args.skip_test:
        total_steps += 1
    
    print("\n" + "="*60)
    print("🚀 TG ONE 本地 CI 开始执行")
    print("="*60)
    print(f"📋 总共 {total_steps} 个检查步骤")
    print(f"📁 工作目录: {root_dir}")
    print("="*60)
    
    passes = True
    current_step = 0
    start_time = time.time()
    results = []
    
    # 1. Architecture
    if not args.skip_arch:
        current_step += 1
        step_start = time.time()
        if not check_architecture(root_dir, current_step, total_steps):
            passes = False
            results.append(("架构检查", False, time.time() - step_start))
        else:
            results.append(("架构检查", True, time.time() - step_start))
            
    # 2. Flake8
    if passes and not args.skip_flake:
        current_step += 1
        step_start = time.time()
        if not check_flake8(root_dir, current_step, total_steps):
            passes = False
            results.append(("代码质量", False, time.time() - step_start))
        else:
            results.append(("代码质量", True, time.time() - step_start))
            
    # 3. Tests
    if passes and not args.skip_test:
        current_step += 1
        step_start = time.time()
        if not run_tests(root_dir, args.test, current_step, total_steps):
            passes = False
            results.append(("测试", False, time.time() - step_start))
        else:
            results.append(("测试", True, time.time() - step_start))

    total_elapsed = time.time() - start_time
    
    # 打印执行摘要
    print("\n" + "="*60)
    print("📊 执行摘要")
    print("="*60)
    print(f"{'步骤':<15} {'状态':<10} {'耗时':<10}")
    print("-"*60)
    for name, success, elapsed in results:
        status = "✅ 通过" if success else "❌ 失败"
        print(f"{name:<15} {status:<10} {elapsed:>6.2f}s")
    print("-"*60)
    print(f"{'总计':<15} {'':<10} {total_elapsed:>6.2f}s")
    print("="*60)

    if passes:
        print("\n✨✨ 本地 CI 通过 - 准备发布 ✨✨")
        print("💡 提示: 您现在可以使用 git-manager 推送代码")
        sys.exit(0)
    else:
        print("\n🛑 本地 CI 失败 - 请在推送前修复错误 🛑")
        sys.exit(1)

if __name__ == "__main__":
    main()

