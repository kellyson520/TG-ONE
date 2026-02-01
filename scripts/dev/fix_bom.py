import os

def fix_bom(directory):
    for root, dirs, files in os.walk(directory):
        for file in files:
            if file.endswith('.py'):
                path = os.path.join(root, file)
                try:
                    with open(path, 'rb') as f:
                        content = f.read()
                    if content.startswith(b'\xef\xbb\xbf'):
                        with open(path, 'wb') as f:
                            f.write(content[3:])
                        print(f"✅ Fixed BOM in {path}")
                except Exception as e:
                    print(f"❌ Error processing {path}: {e}")

if __name__ == "__main__":
    fix_bom('.')
