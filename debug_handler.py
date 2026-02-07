import asyncio
from core.helpers.error_handler import handle_errors

@handle_errors(default_return="error_occurred")
async def test_func():
    raise ValueError("Test error")

async def main():
    try:
        result = await test_func()
        print(f"Result: {result}")
    except Exception as e:
        print(f"Caught exception: {type(e).__name__}: {e}")

if __name__ == "__main__":
    asyncio.run(main())
