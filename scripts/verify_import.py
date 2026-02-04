
import sys
import os

# Add project root to path
sys.path.insert(0, os.getcwd())

print("Attempting to import core.container...")
try:
    from core.container import container
    print("✅ Successfully imported core.container")
except ImportError as e:
    print(f"❌ Failed to import core.container: {e}")
    sys.exit(1)

print("Attempting to import services.dedup.engine...")
try:
    from services.dedup.engine import smart_deduplicator
    print("✅ Successfully imported services.dedup.engine")
except ImportError as e:
    print(f"❌ Failed to import services.dedup.engine: {e}")
    sys.exit(1)

print("Attempting to import core.lifecycle...")
try:
    from core.lifecycle import get_lifecycle
    print("✅ Successfully imported core.lifecycle")
except ImportError as e:
    print(f"❌ Failed to import core.lifecycle: {e}")
    sys.exit(1)

print("✨ Circular import check passed!")
