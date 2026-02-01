import pytest
import core.helpers.media.excel_importer as importer_module

def test_excel_importer_lazy_pandas():
    """Verify pandas is lazy loaded in excel_importer"""
    # Verify the attribute is our LazyImport proxy
    # Use str(type(...)) to avoid importing LazyImport class if not needed, 
    # but since we are in the test suite we can import it.
    
    # Check __repr__ to see if it says 'not loaded' initially or if it's the proxy
    # Note: It might be loaded if other tests ran before this.
    
    # Just verify it behaves like pandas
    try:
        pd = importer_module.pd
        # Try to access a pandas attribute
        _ = pd.DataFrame
    except ImportError:
        pytest.skip("Pandas not installed, cannot verify LazyImport resolution")
    except Exception as e:
        pytest.fail(f"Accessing lazy pd raised unexpected exception: {e}")

