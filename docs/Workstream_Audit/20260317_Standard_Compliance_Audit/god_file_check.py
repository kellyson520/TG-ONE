import os

def find_god_files(root_dir, limit=1000):
    god_files = []
    exclude_dirs = {'.venv', 'venv', '.git', '__pycache__', 'tests', 'docs'}
    
    for root, dirs, files in os.walk(root_dir):
        # 排除目录
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            if file.endswith('.py'):
                file_path = os.path.join(root, file)
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        line_count = sum(1 for _ in f)
                        if line_count > limit:
                            god_files.append((file_path, line_count))
                except Exception as e:
                    # 尝试其他编码
                    try:
                        with open(file_path, 'r', encoding='gbk') as f:
                            line_count = sum(1 for _ in f)
                            if line_count > limit:
                                god_files.append((file_path, line_count))
                    except:
                        pass
                        
    return god_files

if __name__ == '__main__':
    root = r'e:\重构\TG ONE'
    results = find_god_files(root)
    results.sort(key=lambda x: x[1], reverse=True)
    
    output_path = r'e:\重构\TG ONE\docs\Workstream_Audit\20260317_Standard_Compliance_Audit\god_files.txt'
    with open(output_path, 'w', encoding='utf-8') as out:
        out.write(f"{'File':<80} | {'Lines':<10}\n")
        out.write("-" * 95 + "\n")
        for path, count in results:
            rel_path = os.path.relpath(path, root)
            out.write(f"{rel_path:<80} | {count:<10}\n")
    print(f"Results written to {output_path}")
