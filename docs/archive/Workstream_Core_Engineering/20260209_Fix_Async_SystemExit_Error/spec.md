# Specification: Fix Async SystemExit Error

## 1. Problem Description
When the user triggers an update via the Telegram bot, the system calls `update_service.trigger_update()`, which eventually executes `sys.exit(EXIT_CODE_UPDATE)`. 
In an asynchronous environment (specifically with `uvloop` and `Telethon`), calling `sys.exit()` inside a callback causes the event loop to stop abruptly. 
This leads to:
1. `Fatal error on transport TCPTransport`
2. `RuntimeError: Event loop is closed`
The traceback indicates that while the exception is being handled, other async tasks (like TCP reconnects or internal uvloop callbacks) are still trying to run, but find the loop closed.

## 2. Root Cause Analysis
- `sys.exit()` raises a `SystemExit` exception.
- If caught by the `asyncio` runner, it stops the loop.
- However, if there are pending callbacks or active transports (like Telethon's connection), they might attempt to interact with the loop during the shutdown phase or immediately after.
- `uvloop` is particularly strict about "Event loop is closed".

## 3. Proposed Solution
Instead of calling `sys.exit()` immediately within the async callback:
1. Signal the main loop to stop gracefully.
2. Use a dedicated shutdown mechanism that ensures all transports are closed before the process exits.
3. Or, wrap the `sys.exit` in a way that allows the runner to catch it cleanly, but only after `await client.disconnect()` or similar cleanup.

## 4. Technical Details
- **Target Files**:
    - `app/services/update_service.py`
    - `app/handlers/commands/system_commands.py`
- **Expected Outcome**: System exits with the correct exit code without raising `RuntimeError: Event loop is closed` or transport errors in the logs.

## 5. Verification Plan
- Manual check: Trigger update via bot/CLI and observe logs for "Event loop is closed" errors.
- Code Audit: Ensure no `sys.exit` is called directly without loop cleanup.
