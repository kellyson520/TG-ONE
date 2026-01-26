
import os

files_to_fix = [
    r"docs\Workstream_Core_Engineering\test_summary.txt",
    r"logs\debug_output.txt",
    r"logs\dedup_log.txt",
    r"tests\temp\test_fail.txt",
    r"test_service_fail.txt"
]

def convert_file(path):
    full_path = os.path.abspath(path)
    if not os.path.exists(full_path):
        print(f"Skipping {path} (not found)")
        return

    print(f"Processing {path}...")
    content = None
    
    # Try reading as UTF-16 (BOM) or LE/BE
    encodings = ['utf-16', 'utf-16-le', 'gbk']
    
    for enc in encodings:
        try:
            with open(full_path, 'r', encoding=enc) as f:
                content = f.read()
                print(f"  - Read successfully using {enc}")
                break
        except UnicodeError:
            continue
        except Exception as e:
            print(f"  - Error reading as {enc}: {e}")
            
    if content is not None:
        try:
            with open(full_path, 'w', encoding='utf-8') as f:
                f.write(content)
            print("  - Saved as UTF-8")
        except Exception as e:
            print(f"  - Error writing: {e}")
    else:
        print("  - Failed to decode file")

if __name__ == "__main__":
    for f in files_to_fix:
        convert_file(f)
