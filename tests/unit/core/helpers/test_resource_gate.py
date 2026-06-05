import pytest
from unittest.mock import MagicMock, patch
from core.helpers.resource_gate import ResourceGate

class TestResourceGate:
    
    @patch('core.helpers.resource_gate.psutil')
    def test_check_memory_safe_below_limit(self, mock_psutil):
        # Mock process memory to 1MB
        mock_process = MagicMock()
        mock_process.memory_info.return_value.rss = 1 * 1024 * 1024
        mock_psutil.Process.return_value = mock_process
        
        # Should be safe (limit is 2GB)
        assert ResourceGate.check_memory_safe() is True
        
    @patch('core.helpers.resource_gate.psutil')
    def test_check_memory_safe_exceeds_limit(self, mock_psutil):
        # Mock process memory to 3GB
        mock_process = MagicMock()
        mock_process.memory_info.return_value.rss = 3 * 1024 * 1024 * 1024
        mock_psutil.Process.return_value = mock_process
        
        # Should be unsafe
        assert ResourceGate.check_memory_safe() is False
        
    @patch('core.helpers.resource_gate.psutil')
    def test_enforce_memory_limit_raises(self, mock_psutil):
        # Mock process memory to 3GB
        mock_process = MagicMock()
        mock_process.memory_info.return_value.rss = 3 * 1024 * 1024 * 1024
        mock_psutil.Process.return_value = mock_process
        
        with pytest.raises(MemoryError) as excinfo:
            ResourceGate.enforce_memory_limit()
        
        assert "exceeded allowed memory limit" in str(excinfo.value)

    def test_psutil_missing(self):
        # When psutil is None
        with patch('core.helpers.resource_gate.psutil', None):
            assert ResourceGate.check_memory_safe() is True
