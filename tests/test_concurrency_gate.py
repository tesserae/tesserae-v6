import os
import json
import time
import tempfile
import pytest
from backend.concurrency_gate import ConcurrencyConfig

def test_concurrency_config_cross_worker_sync():
    """Test that ConcurrencyConfig correctly reads from a shared JSON file."""
    # Temporarily override the config path to a temp file
    old_path = ConcurrencyConfig._CONFIG_FILE
    
    with tempfile.NamedTemporaryFile(suffix='.json', delete=False) as tf:
        temp_path = tf.name
        
    try:
        ConcurrencyConfig._CONFIG_FILE = temp_path
        
        # Reset to ensure clean state
        ConcurrencyConfig._cache_ts = 0
        ConcurrencyConfig._cache = None
        
        # Initial state should be defaults
        assert ConcurrencyConfig.get_max_searches() == ConcurrencyConfig._default_max
        
        # Simulate another worker updating the JSON file directly
        new_config = {
            'max_searches': 42,
            'memory_threshold_gb': 16.5,
            'queue_timeout': 999,
            'queue_poll_interval': 1.5,
            'stress_test_mode': True,
            'stress_test_enabled_at': time.time()
        }
        with open(temp_path, 'w') as f:
            json.dump(new_config, f)
            
        # Fast forward time to expire the TTL cache (5 seconds)
        ConcurrencyConfig._cache_ts = time.monotonic() - 10
        
        # Now the config should read the new values
        assert ConcurrencyConfig.get_max_searches() == 42
        assert ConcurrencyConfig.get_memory_threshold() == 16.5
        assert ConcurrencyConfig.get_queue_timeout() == 999
        assert ConcurrencyConfig.get_queue_poll_interval() == 1.5
        assert ConcurrencyConfig.is_stress_test_mode() is True
        
    finally:
        ConcurrencyConfig._CONFIG_FILE = old_path
        if os.path.exists(temp_path):
            os.remove(temp_path)
