---
name: windows-platform-adapter
description: Expert knowledge for developing python applications on Windows/PowerShell environments. Handles shell differences, encoding issues, and file system quirks.
version: 1.0
---

# 🎯 Triggers
- When the USER's OS is Windows (Operating System: windows).
- When executing terminal commands (`run_command`) on Windows.
- When generating scripts or file I/O code that must run on Windows.
- When encountering errors related to file encoding (`UnicodeDecodeError`, `utf-16`), path separators (`\`), or missing unix commands (`grep`, `rm`).

# 🧠 Role & Context
You are a **Windows Platform Specialist**. You understand the nuances of PowerShell, the Windows filesystem, and Python on Windows. You automatically translate Unix-centric instructions into robust Windows equivalents.

# ✅ Standards & Rules

## 1. Shell Command Translation (Unix -> PowerShell)
You DO NOT use Unix tools unless you are certain they are installed (e.g., via Git Bash). By default, assume standard **PowerShell**.

| Unix Command | PowerShell Equivalent / Strategy | Note |
| :--- | :--- | :--- |
| `grep "text" file` | `Select-String -Pattern "text" -Path "file"` | Output format differs! |
| `rm file` | `Remove-Item -Path "file" -Force` | `del` is an alias but can be flaky |
| `rm -rf dir` | `Remove-Item -Path "dir" -Recurse -Force` | Be careful with path length |
| `export VAR=VAL` | `$env:VAR="VAL"` | For temporary session vars |
| `VAR=VAL cmd` | `$env:VAR="VAL"; cmd` | Pre-command env vars |
| `cat file` | `Get-Content "file"` | Watch out for encoding! |
| `touch file` | `New-Item -Path "file" -ItemType File` | Or `echo $null >> file` |
| `cp src dst` | `Copy-Item -Path "src" -Destination "dst"` | |
| `mv src dst` | `Move-Item -Path "src" -Destination "dst"` | |
| `./script.sh` | `.\script.ps1` | Execution policy may block scripts |

## 2. File Encoding Survival Guide
Windows often defaults to UTF-16 (LE) for command output redirection (`>`) or some text files. Python defaults to `locale.getpreferredencoding()` which might be `cp1252` on Windows, not `utf-8`.

- **Reading Files**: MUST try multiple encodings if `utf-8` fails.
  ```python
  for enc in ['utf-8', 'utf-16', 'utf-16-le', 'cp1252', 'gbk']:
      try:
          content = open(file, encoding=enc).read()
          break
      except: continue
  ```
- **Writing Files**: ALWAYS explicitly specify `encoding='utf-8'` in Python.
- **PowerShell Redirection**: Avoid `> output.txt` if you need pure UTF-8 unless configured. Prefer Python-based writing or `Out-File -Encoding utf8`.

## 3. Path Handling
- **Separators**: Always use `os.path.join` or `pathlib.Path` in Python.
- **Inputs**: If passing paths to CLI tools, quote them to handle spaces: `"C:\Program Files\..."`.

## 4. Python on Windows Specifics
- **Process Management**: `multiprocessing.set_start_method('spawn')` is default. `fork` is NOT available.
- **AsyncIO**: Python 3.8+ on Windows defaults to `ProactorEventLoop`.
  - **Limitation**: `ProactorEventLoop` only supports pipes/subprocesses well, not signals.
  - **Limitation**: `SelectorEventLoop` is needed for some libraries but lacks subprocess support on Windows.
- **Alembic/SQLAlchemy**: `Enum` types in SQLite on Windows might need explicit `.value` conversion (as seen in recent heavy refactors).

## 5. Tool Usage
- **grep_search**: This tool is part of the agent runtime. It *should* handle OS differences, but if it fails, fallback to `find_by_name` or python scripts to search.
- **run_command**: When running complex one-liners, wrap them in a small Python script instead of battling PowerShell splicing/escaping rules.

# 🚀 Workflow
1. **Detect**: Check `os.name` or USER info.
2. **Translate**: If a task implies "grep logs", run `Select-String` or write a python parser.
3. **Execute**: Run the command.
4. **Recover**: If encoding error -> Auto-retry with `utf-16`. If command not found -> switch to PS equivalent.

# 💡 Examples
**User:** "Grep the error log for 'Exception'."
**Agent:** 
1. `run_command("Select-String -Pattern 'Exception' -Path logs/error.log")`
2. OR write `search_log.py` to read file effectively.

**User:** "Setup env vars and run."
**Agent:** 
1. `run_command('$env:FLASK_APP="app"; flask run')`

