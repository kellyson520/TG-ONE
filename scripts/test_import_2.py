import sys
import os
sys.path.append(os.getcwd())
try:
    print("scheduler.chat_updater imported successfully")
except Exception as e:
    import traceback
    traceback.print_exc()
