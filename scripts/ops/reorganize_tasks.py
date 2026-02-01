import shutil
from pathlib import Path

docs_root = Path(r"c:\Users\lihuo\Desktop\重构\TG ONE\docs")
archive_root = docs_root / "archive"
finish_root = docs_root / "finish"
ws_core = docs_root / "Workstream_Core_Engineering"

def move_task(src, dest):
    dest.parent.mkdir(parents=True, exist_ok=True)
    if dest.exists():
        print(f"Warning: {dest} already exists. Skipping.")
        return
    shutil.move(str(src), str(dest))
    print(f"Moved: {src.relative_to(docs_root)} -> {dest.relative_to(docs_root)}")

# 1. Move active task back
src_active = archive_root / "Workstream_Core_Engineering" / "20260115_Display_Chat_Name_Instead_Of_ID"
if src_active.exists():
    move_task(src_active, ws_core / src_active.name)

# 2. Move 20260115 tasks from archive to finish
for ws_dir in archive_root.iterdir():
    if ws_dir.is_dir() and ws_dir.name.startswith("Workstream_"):
        for task_dir in ws_dir.iterdir():
            if task_dir.is_dir() and task_dir.name.startswith("20260115_"):
                # Special case: already handled Display_Chat_Name
                if task_dir.name == "20260115_Display_Chat_Name_Instead_Of_ID":
                    continue
                move_task(task_dir, finish_root / ws_dir.name / task_dir.name)

print("Folders reorganized.")
