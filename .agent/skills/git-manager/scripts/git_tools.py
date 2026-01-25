import argparse
import subprocess
import sys
import re
from datetime import datetime
from typing import List, Dict

def run_git(args: List[str]) -> str:
    """运行 git 命令并返回输出结果。"""
    try:
        result = subprocess.check_output(["git"] + args, stderr=subprocess.STDOUT, text=True, encoding='utf-8')
        return result.strip()
    except subprocess.CalledProcessError as e:
        print(f"执行 git 命令出错 {' '.join(args)}: {e.output}")
        sys.exit(1)
    except FileNotFoundError:
        print("错误: 未找到 'git' 命令。请安装 Git 并确保将其添加到 PATH 环境变量中。")
        sys.exit(1)

def get_current_branch():
    return run_git(["rev-parse", "--abbrev-ref", "HEAD"])

def generate_changelog(since_tag: str = None, output_file: str = "CHANGELOG.md"):
    """
    基于 Conventional Commits 规范从 git 历史生成变更日志。
    """
    range_spec = f"{since_tag}..HEAD" if since_tag else "HEAD"
    
    # 获取日志格式: hash|author|date|message
    logs = run_git(["log", range_spec, "--pretty=format:%h|%an|%ad|%s", "--date=short"]).splitlines()
    
    categorized: Dict[str, List[str]] = {
        "feat": [],
        "fix": [],
        "perf": [],
        "refactor": [],
        "docs": [],
        "chore": [],
        "other": []
    }
    
    # Conventional commit 正则: type(scope): subject 或 type: subject
    pattern = re.compile(r"^(\w+)(?:\(([^)]+)\))?:\s*(.+)$")
    
    for line in logs:
        if not line: continue
        parts = line.split("|")
        if len(parts) < 4: continue
        
        sha, author, date, msg = parts[0], parts[1], parts[2], parts[3]
        match = pattern.match(msg)
        
        entry = f"- {sha} {msg} ({author})"
        
        if match:
            ctype = match.group(1).lower()
            if ctype in categorized:
                # 翻译常见类型为中文显示
                scope = f"**{match.group(2)}**: " if match.group(2) else ""
                categorized[ctype].append(f"- {sha} {scope}{match.group(3)} ({author})")
            else:
                categorized["other"].append(entry)
        else:
            categorized["other"].append(entry)

    # 构建 Markdown 内容
    md_lines = [f"## {datetime.now().strftime('%Y-%m-%d')} 更新日志"]
    
    sections = [
        ("✨ 新功能 (Features)", "feat"),
        ("🐛 问题修复 (Fixed)", "fix"),
        ("⚡ 性能优化 (Performance)", "perf"),
        ("♻️ 代码重构 (Refactoring)", "refactor"),
        ("📚 文档更新 (Documentation)", "docs"),
        ("🔧 杂项 (Chores)", "chore"),
        ("📋 其他变更 (Other Changes)", "other")
    ]
    
    for title, key in sections:
        if categorized[key]:
            md_lines.append(f"\n### {title}")
            md_lines.extend(categorized[key])
            
    md_content = "\n".join(md_lines) + "\n\n"
    
    try:
        with open(output_file, "r", encoding="utf-8") as f:
            existing = f.read()
    except FileNotFoundError:
        existing = "# 项目变更日志 (Changelog)\n\n"
        
    with open(output_file, "w", encoding="utf-8") as f:
        # 将新日志插入到头部
        header_match = re.search(r"^# .+\n\n", existing)
        if header_match:
            split_pos = header_match.end()
            f.write(existing[:split_pos] + md_content + existing[split_pos:])
        else:
            f.write("# 项目变更日志 (Changelog)\n\n" + md_content + existing)
        
    print(f"✅ 变更日志已更新至 {output_file}")

def safe_merge(source_branch: str, target_branch: str = "main", push: bool = False):
    """
    安全地将 source_branch 合并入 target_branch。
    """
    current = get_current_branch()
    
    print(f"🔄 准备合并: {source_branch} -> {target_branch}...")
    
    # 1. 更新目标分支
    run_git(["checkout", target_branch])
    try:
        run_git(["pull", "origin", target_branch])
    except:
        print(f"⚠️ 警告: 无法拉取 {target_branch}，将以本地版本为准。")
        
    # 2. 合并
    print(f"🔀 正在合并 {source_branch}...")
    try:
        # 使用 --no-ff 保证合并历史清晰
        run_git(["merge", "--no-ff", source_branch, "-m", f"chore(merge): merge branch {source_branch} into {target_branch}"])
        print("✅ 合并成功。")
    except Exception:
        print("❌ 检测到合并冲突！已终止合并。请手动解决冲突。")
        run_git(["merge", "--abort"])
        sys.exit(1)
        
    # 3. 推送
    if push:
        print(f"🚀 正在推送到远端 {target_branch}...")
        run_git(["push", "origin", target_branch])
        print("✅ 推送完成。")
        
    # 4. 切回原分支
    run_git(["checkout", current])
    print(f"🔙 已切回原分支: {current}")

def rollback_commit(method: str = "soft", steps: int = 1):
    """
    回滚最近的 N 次提交。
    method: 'soft' (保留暂存区更改), 'hard' (彻底丢弃更改), 'revert' (创建反向提交)
    """
    if method == "revert":
        print(f"🔙 正在创建反向提交 (Revert) 回滚最近 {steps} 次提交...")
        #构造 commit range
        if steps == 1:
            target = "HEAD"
        else:
            target = f"HEAD~{steps}..HEAD"
        run_git(["revert", "--no-edit", target]) 
        print(f"✅ 已创建 Revert 提交。")
        
    elif method in ["soft", "mixed", "hard"]:
        target = f"HEAD~{steps}"
        print(f"🔙 正在重置 (Reset --{method}) 到 {target} ...")
        run_git(["reset", f"--{method}", target])
        print(f"✅ 回滚完成。当前 HEAD 指向: {run_git(['rev-parse', '--short', 'HEAD'])}")
    else:
        print(f"❌ 未知的回滚模式: {method}")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Git 辅助工具集")
    subparsers = parser.add_subparsers(dest="command")
    
    # Changelog
    cl_parser = subparsers.add_parser("changelog", help="生成变更日志")
    cl_parser.add_argument("--since", help="起始 Tag 或 Commit Hash", default=None)
    cl_parser.add_argument("--file", help="输出文件名 (默认: CHANGELOG.md)", default="CHANGELOG.md")
    
    # Merge
    mg_parser = subparsers.add_parser("merge", help="分支合并")
    mg_parser.add_argument("source", help="来源分支名称")
    mg_parser.add_argument("--target", help="目标分支 (默认: main)", default="main")
    mg_parser.add_argument("--push", help="合并后是否自动推送", action="store_true")
    
    # Rollback
    rb_parser = subparsers.add_parser("rollback", help="回滚提交")
    rb_parser.add_argument("--method", choices=["soft", "hard", "revert"], default="soft", help="回滚模式 (soft/hard/revert)")
    rb_parser.add_argument("--steps", type=int, default=1, help="回滚的提交数量")

    args = parser.parse_args()
    
    if args.command == "changelog":
        generate_changelog(args.since, args.file)
    elif args.command == "merge":
        safe_merge(args.source, args.target, args.push)
    elif args.command == "rollback":
        rollback_commit(args.method, args.steps)
    else:
        parser.print_help()
