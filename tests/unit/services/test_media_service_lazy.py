import pytest
import services.media_service as ms

def test_media_service_lazy_pil():
    """Verify PIL.Image is lazy loaded in media_service"""
    try:
        # Accessing the lazy object
        # If imports are working, this should give us the Image module or class
        img_module = ms.Image
        
        # Check if we can access 'open' method (standard PIL.Image method)
        _ = img_module.open
    except ImportError:
        pytest.skip("PIL/Pillow not installed")
    except Exception as e:
        pytest.fail(f"Accessing lazy PIL.Image raised unexpected exception: {e}")
