import sys
import os
sys.path.append(os.getcwd())
try:
    from scheduler import chat_updater
    print("scheduler.chat_updater imported successfully")
except Exception as e:
    import traceback
    traceback.print_exc()
