import os
import re
from pathlib import Path

docs_root = Path(r"c:\Users\lihuo\Desktop\重构\TG ONE\docs")
process_md = docs_root / "process.md"

# 1. Map all tasks to their current location
task_map = {} # task_name -> relative_path_from_docs

def scan_for_tasks(root_dir):
    for dirpath, dirnames, filenames in os.walk(root_dir):
        dp = Path(dirpath)
        # Only look at directories that start with YYYYMMDD_
        # And we want the first level within Workstream_ folder in archive/finish/Workstream_*
        for d in dirnames:
            if re.match(r"^\d{8}_", d):
                rel = (dp / d).relative_to(docs_root)
                # We want the most specific path. If it's already in map, first come first serve?
                # Usually they shouldn't be duplicated in different locations.
                if d not in task_map:
                    task_map[d] = rel.as_posix()

# Scan expected locations
scan_for_tasks(docs_root / "archive")
scan_for_tasks(docs_root / "finish")
for ws in docs_root.glob("Workstream_*"):
    if ws.is_dir():
        scan_for_tasks(ws)

print(f"Found {len(task_map)} tasks in filesystem.")

# 2. Update process.md
if not process_md.exists():
    print("process.md not found.")
    exit(1)

content = ""
try:
    with open(process_md, "r", encoding="utf-8") as f:
        content = f.read()
except:
    with open(process_md, "r", encoding="utf-16") as f:
        content = f.read()

# Update links
# Match [label](old_path)
# We look for links containing a task name from our map.
# Pattern: (\[.*\]\()((?:\./|docs/|archive/|finish/|Workstream_[^/]+/)?([^/ \)]+))(/?.*)(\))
# Group 1: [label](
# Group 2: Full path (variable)
# Group 3: Task name (e.g. 20260115_ABC)
# Group 4: Suffix (e.g. /report.md)
# Group 5: )

def replacer(match):
    label_part = match.group(1)
    full_path = match.group(2)
    task_name = match.group(3)
    suffix = match.group(4)
    close_paren = match.group(5)
    
    if task_name in task_map:
        new_base = f"./{task_map[task_name]}"
        # Ensure it starts with ./
        return f"{label_part}{new_base}{suffix}{close_paren}"
    return match.group(0)

# Regex to find links in markdown
link_pattern = r'(\[.*\]\()([^ \)]+)(\))'

def thorough_replace(content):
    def link_repl(m):
        full_link = m.group(2)
        # Try to find a task name in the link
        for task_name, rel_path in task_map.items():
            if task_name in full_link:
                # Replace the part before the task name and the task name itself
                # Links can be ./Workstream_X/TaskName/... or archive/Workstream_X/TaskName/...
                # We want to replace it with ./actual_path/TaskName/...
                # Let's find index of task_name
                idx = full_link.find(task_name)
                suffix = full_link[idx + len(task_name):]
                return f"[{m.group(1)[1:-2]}](./{rel_path}{suffix})"
        return m.group(0)
    
    return re.sub(link_pattern, link_repl, content)

new_content = thorough_replace(content)

with open(process_md, "w", encoding="utf-8") as f:
    f.write(new_content)

print("process.md links updated.")
