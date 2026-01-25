
import os
import secrets
from pathlib import Path

def fix_env_secret_key():
    env_path = Path(".env")
    if not env_path.exists():
        print("No .env file found.")
        return

    try:
        content = env_path.read_text(encoding='utf-8')
    except UnicodeDecodeError:
        try:
            content = env_path.read_text(encoding='gbk')
        except UnicodeDecodeError:
            print("Could not read .env file with utf-8 or gbk encoding.")
            return

    if "SECRET_KEY=" in content:
        print("SECRET_KEY already exists in .env.")
        # Optional: force update if it looks weak? No, safer to leave it.
        return

    new_key = secrets.token_hex(32)
    print(f"Generated new SECRET_KEY: {new_key[:8]}...")
    
    # Append with newline
    if not content.endswith('\n'):
        content += '\n'
    
    new_content = content + f"\n# Security\nSECRET_KEY={new_key}\n"
    
    # Write back as utf-8
    env_path.write_text(new_content, encoding='utf-8')
    print("Successfully added SECRET_KEY to .env")

if __name__ == "__main__":
    fix_env_secret_key()
