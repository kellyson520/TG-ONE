
import asyncio
import logging
import sys
import os
import shutil
from unittest.mock import MagicMock
from pathlib import Path

# Add project root to path
sys.path.append(os.getcwd())

# Ensure clean state
temp_log_dir = Path("tests/temp_logs")
if temp_log_dir.exists():
    shutil.rmtree(temp_log_dir)

# Setup Log Environment
os.environ["LOG_FORMAT"] = "text"
os.environ["LOG_LEVEL"] = "INFO"
os.environ["LOG_COLOR"] = "false"
os.environ["LOG_DIR"] = str(temp_log_dir) # Enable file logging
os.environ["LOG_LANGUAGE"] = "zh"

from core.context import setup_logging
from core.pipeline import Pipeline, Middleware, MessageContext

# Initialize Logging
setup_logging()
logger = logging.getLogger("test.trace")

class TestMiddleware(Middleware):
    async def process(self, ctx: MessageContext, next_call):
        logger.info("Step 1: Middleware processing")
        await asyncio.sleep(0.01) # Simulate delay
        logger.info("Step 2: Database lookup simulated")
        await next_call()
        logger.info("Step 3: Post-processing finished")

async def main():
    logger.info("Simulation Start")
    
    pipeline = Pipeline()
    pipeline.add(TestMiddleware())
    
    ctx = MessageContext(
        client=MagicMock(),
        task_id=1,
        chat_id=123,
        message_id=456,
        message_obj=MagicMock()
    )
    
    await pipeline.execute(ctx)
    trace_id = ctx.metadata.get("trace_id")
    print(f"Generated Trace ID: {trace_id}")
    
    # Verify file content
    log_file = temp_log_dir / "app.log"
    if log_file.exists():
        print(f"Log file created at: {log_file}")
        with open(log_file, "r", encoding="utf-8") as f:
            content = f.read()
            print("\n--- Log File Content Preview ---")
            print(content)
            if trace_id in content:
                 print("\nSUCCESS: Trace ID found in log file.")
            else:
                 print("\nFAILURE: Trace ID NOT found in log file.")
    else:
        print("FAILURE: Log file not created.")

if __name__ == "__main__":
    asyncio.run(main())
