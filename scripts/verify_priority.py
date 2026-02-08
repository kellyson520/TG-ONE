import sys
import os
import asyncio

# Ensure project root is in path
sys.path.append(os.getcwd())

from core.container import container

async def test_repo():
    print("Testing RuleRepository.get_priority_map...")
    repo = container.rule_repo
    try:
        # Mock container.db if needed, but lets try running with the real one if it connects
        # If connection fails, we at least verified imports and method existence.
        pmap = await repo.get_priority_map()
        print(f"Priority map: {pmap}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    try:
        asyncio.run(test_repo())
    except Exception as e:
        print(f"Runtime Error: {e}")

import py_compile
try:
    py_compile.compile('listeners/message_listener.py', doraise=True)
    print("listeners/message_listener.py syntax is OK.")
except Exception as e:
    print(f"Syntax Error in listeners/message_listener.py: {e}")
