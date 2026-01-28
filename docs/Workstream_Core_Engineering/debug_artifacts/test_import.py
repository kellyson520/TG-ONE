#!/usr/bin/env python
"""测试 prompt_handlers 导入"""
import sys
import os
import traceback

# 添加项目根目录到 sys.path
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../..'))
sys.path.insert(0, project_root)

print("=" * 60)
print("Testing prompt_handlers import...")
print("=" * 60)

try:
    print("✅ SUCCESS: handlers.prompt_handlers imported successfully")
except Exception as e:
    print(f"❌ FAILED: {type(e).__name__}: {e}")
    print("\nFull Traceback:")
    traceback.print_exc()
    sys.exit(1)
