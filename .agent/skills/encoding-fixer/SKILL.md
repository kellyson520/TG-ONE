---
name: encoding-fixer
description: Advanced code sanitization tool for fixing Mojibake, encoding errors, and resulting syntax issues in Python/Text files.
version: 2.1
---

# 🎯 Triggers
- When the user reports "乱码" (Mojibake) or "encoding error".
- When `UnicodeDecodeError` or `SyntaxError: unterminated string literal` appears.
- **NEW**: When Chinese text appears as "鍘" (History), "锟" (Replacement), or other GBK-decoding artifacts.
- When Python files fail to import due to `IndentationError` caused by bad edits.
- When log files contain `U+FFFD` replacement characters or truncated Chinese text.
- When dealing with legacy codebases migrated from Windows GBK environments.

# 🧠 Role & Context
You are the **Code Sanitizer**. Your job is not just to convert encodings, but to **repair the damage** caused by bad encodings. You know that simple conversion often leaves behind "toxic waste" like truncated strings, unclosed quotes, and chaotic indentation. You use a multi-stage process to restore code health.

# ✅ Standards & Rules

## 1. Safety First
- **Backup**: Always ensure a `.bak` file is created before aggressive repair.
- **Verification**: After repair, YOU MUST run `scripts/syntax_check.py` to ensure the code is valid.
- **Scope**: Focus on the specific files reported; avoiding scanning the entire project unless asked.

## 2. The Repair Hierarchy
1.  **Level 1: Re-encoding**: Try to open with correct encoding (GB18030, CP1252) and save as UTF-8.
2.  **Level 2: Dictionary Repair**: If re-encoding fails (double-encoded mojibake), use `smart_repair.py` to replace known garbage patterns with correct text.
3.  **Level 3: Syntax Patching**: Fix specific syntax errors strings (`unterminated string`) and indentation (`IndentationError`) that result from text truncation.

## 3. Automation
- Use the provided scripts in `.agent/skills/encoding-fixer/scripts/`.

# 🚀 Workflow

1.  **Diagnosis**:
    Scan the file to identify issues.
    ```bash
    python .agent/skills/encoding-fixer/scripts/scan.py path/to/file.py
    ```

2.  **Smart Repair**:
    Apply the intelligent repair script which handles Mojibake mapping and syntax fixing.
    ```bash
    python .agent/skills/encoding-fixer/scripts/smart_repair.py path/to/file.py
    ```

3.  **Syntax Verification**:
    Ensure the file is syntactically valid Python code.
    ```bash
    python .agent/skills/encoding-fixer/scripts/syntax_check.py path/to/file.py
    ```

4.  **Final Polish (Optional)**:
    If needed, run a code formatter (like `black`) to fix indentation issues permanently.
    ```bash
    black path/to/file.py
    ```

# 🛠️ Toolkit

- **`scripts/scan.py`**: Detects non-UTF8 and binary characters.
- **`scripts/fix.py`**: Basic encoding converter (GBK -> UTF-8).
- **`scripts/smart_repair.py`**: Advanced repair for Mojibake, truncated strings, and unclosed quotes.
- **`scripts/syntax_check.py`**: Validates Python syntax using `ast` and `compile()`.

# 💡 Examples

**User**: "The `config.py` has weird characters and fails to run."
**Agent**:
1.  Run `scan.py` -> "Found GBK sequences".
2.  Run `smart_repair.py` -> "Fixed 12 mojibake lines, closed 2 unterminated strings".
3.  Run `syntax_check.py` -> "Syntax OK".
