import time
import logging
from typing import List, Dict, Optional

# Placeholder for fetching blink events/timestamps
# In a real scenario, this would interact with hardware/camera API
def _get_blink_timestamps() -> List[float]:
    """Returns a list of recent blink timestamps. Mocked for now."""
    # This function will be mocked by the tests
    # Return an empty list by default for the real function for now
    logging.debug("[_get_blink_timestamps] Called (returning empty list)")
    return [] 

# region detect_double_blink
# INPUT: config (dict): Configuration dictionary, expects 'DD_MAX_INTERVAL_MS'.
# OUTPUT: (bool): True if a double blink is detected, False otherwise.
def detect_double_blink(config: dict) -> bool:
    """Detects a double blink based on timestamps within a configured interval."""
    logging.debug("[detect_double_blink] Starting detection...")
    
    max_interval_ms = config.get('DD_MAX_INTERVAL_MS', 500)
    max_interval_sec = max_interval_ms / 1000.0
    
    # Get recent blink timestamps (mocked in tests)
    timestamps = _get_blink_timestamps()
    logging.debug(f"[detect_double_blink] Timestamps received: {timestamps}")
    
    # Basic logic: Check if last two timestamps are within the interval
    if len(timestamps) >= 2:
        last_blink_time = timestamps[-1]
        second_last_blink_time = timestamps[-2]
        interval = last_blink_time - second_last_blink_time
        
        logging.debug(f"[detect_double_blink] Checking interval: {interval:.3f}s against max: {max_interval_sec:.3f}s")
        
        if 0 < interval <= max_interval_sec:
            logging.info("[detect_double_blink] Valid double blink detected.")
            return True
            
    logging.debug("[detect_double_blink] No valid double blink detected.")
    return False
# endregion detect_double_blink

# Example usage (for direct execution if needed)
if __name__ == '__main__':
    # This part is not typically used when run via MCP/TDD loop
    # but can be useful for standalone testing
    logging.basicConfig(level=logging.DEBUG)
    test_config = {'DD_MAX_INTERVAL_MS': 500}
    
    # Modify this mock function directly for simple testing
    def _mock_get_timestamps_for_run() -> List[float]:
        t = time.time()
        # return [t - 0.6, t - 0.2] # Should detect
        # return [t - 1.0, t - 0.2] # Should NOT detect
        return [] # Default: no blinks
        
    # Replace the actual function with the mock for this run
    _get_blink_timestamps_orig = _get_blink_timestamps
    _get_blink_timestamps = _mock_get_timestamps_for_run
    
    print(f"Running detection with config: {test_config}")
    detected = detect_double_blink(test_config)
    print(f"Double blink detected: {detected}")
    
    # Restore original function if needed elsewhere
    _get_blink_timestamps = _get_blink_timestamps_orig
