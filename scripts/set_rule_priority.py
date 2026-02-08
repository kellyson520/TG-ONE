import sys
import os
import asyncio
import argparse

# Ensure project root is in path
sys.path.append(os.getcwd())

from core.container import container
from services.rule.facade import rule_management_service

async def set_priority(rule_id: int, priority: int):
    print(f"Setting priority for Rule {rule_id} to {priority}...")
    
    # 1. Update Rule
    result = await rule_management_service.update_rule(rule_id, priority=priority)
    
    if result.get('success'):
        print(f"✅ Success! Rule {rule_id} priority updated.")
    else:
        print(f"❌ Failed: {result.get('error')}")
        return

    # 2. Verify Repository Cache Update
    # Force wait a moment for cache invalidation (though it should be instant in CRUD)
    # Check the priority map
    pmap = await container.rule_repo.get_priority_map()
    
    # Needs to find the chat_id associated with this rule to verify map
    # The map is {chat_id: priority}
    
    chat_id = result.get('source_chat_id')
    if chat_id:
        mapped_priority = pmap.get(int(chat_id))
        print(f"🔍 Verification: Chat {chat_id} Priority in Map = {mapped_priority}")
        if mapped_priority == priority:
            print("🎉 Priority Map is synced!")
        else:
            print(f"⚠️ Warning: specific rule priority is {priority} but map shows {mapped_priority}. (This is normal if another rule for the same chat has higher priority)")
    else:
        print("ℹ️ Source chat ID not returned, skipping map verification.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Set Forward Rule Priority")
    parser.add_argument("rule_id", type=int, help="ID of the rule to update")
    parser.add_argument("priority", type=int, help="Priority value (e.g. 50, 100)")
    
    args = parser.parse_args()
    
    try:
        asyncio.run(set_priority(args.rule_id, args.priority))
    except Exception as e:
        print(f"Runtime Error: {e}")
