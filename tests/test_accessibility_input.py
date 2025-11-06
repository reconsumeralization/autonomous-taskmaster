import pytest
import time
from unittest import mock
import os
import sys

# Ensure src directory is in path for imports
# This assumes the tests are run from the project root (e.g., using pytest)
# Or that the necessary adjustments are made in conftest.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

# Attempt to import the function to be tested
try:
    from src.accessibility_input import detect_double_blink
    IMPORT_SUCCESSFUL = True
except ImportError:
    IMPORT_SUCCESSFUL = False
    # Define a dummy function if import fails, so tests can be collected (but skipped)
    def detect_double_blink(config: dict) -> bool:
        raise NotImplementedError("Function not implemented yet")

# Pytest marker to skip tests if the main function couldn't be imported
pytestmark = pytest.mark.skipif(not IMPORT_SUCCESSFUL, reason="src.accessibility_input or detect_double_blink not found")

# Default configuration for tests
@pytest.fixture
def default_config():
    return {
        'DD_MAX_INTERVAL_MS': 500, # Default max interval: 0.5 seconds
        # Add other relevant config defaults if needed
    }

# Test Cases
# region TestDetectDoubleBlink

@mock.patch('src.accessibility_input._get_blink_timestamps')
def test_detect_valid_double_blink(mock_get_timestamps, default_config):
    # INPUT: mock_get_timestamps (Mock): Mocked timestamp provider
    # INPUT: default_config (dict): Test configuration
    # OUTPUT: (None) Asserts True for valid double blink
    """Test detection of a valid double blink within the time interval."""
    start_time = time.time()
    mock_get_timestamps.return_value = [start_time, start_time + 0.2] # Blinks 200ms apart
    assert detect_double_blink(default_config) is True

@mock.patch('src.accessibility_input._get_blink_timestamps')
def test_detect_single_blink(mock_get_timestamps, default_config):
    # INPUT: mock_get_timestamps (Mock): Mocked timestamp provider
    # INPUT: default_config (dict): Test configuration
    # OUTPUT: (None) Asserts False for single blink
    """Test that a single blink is not detected as a double blink."""
    start_time = time.time()
    mock_get_timestamps.return_value = [start_time] # Only one blink
    assert detect_double_blink(default_config) is False

@mock.patch('src.accessibility_input._get_blink_timestamps')
def test_detect_blinks_too_far_apart(mock_get_timestamps, default_config):
    # INPUT: mock_get_timestamps (Mock): Mocked timestamp provider
    # INPUT: default_config (dict): Test configuration
    # OUTPUT: (None) Asserts False for blinks too far apart
    """Test that blinks separated by more than the interval are not detected."""
    start_time = time.time()
    interval_seconds = default_config['DD_MAX_INTERVAL_MS'] / 1000.0
    mock_get_timestamps.return_value = [start_time, start_time + interval_seconds + 0.1] # Blinks just over interval
    assert detect_double_blink(default_config) is False

@mock.patch('src.accessibility_input._get_blink_timestamps')
def test_detect_no_blinks(mock_get_timestamps, default_config):
    # INPUT: mock_get_timestamps (Mock): Mocked timestamp provider
    # INPUT: default_config (dict): Test configuration
    # OUTPUT: (None) Asserts False when no blinks occur
    """Test that no blinks result in False."""
    mock_get_timestamps.return_value = [] # No blinks
    assert detect_double_blink(default_config) is False
    
@mock.patch('src.accessibility_input._get_blink_timestamps')
def test_configurability_of_interval(mock_get_timestamps, default_config):
    # INPUT: mock_get_timestamps (Mock): Mocked timestamp provider
    # INPUT: default_config (dict): Test configuration (base)
    # OUTPUT: (None) Asserts detection changes based on config interval
    """Test that the DD_MAX_INTERVAL_MS configuration is respected."""
    start_time = time.time()
    # Simulate blinks 300ms apart
    mock_get_timestamps.return_value = [start_time, start_time + 0.3]

    # Test with a short interval (200ms) - should fail
    config_short = default_config.copy()
    config_short['DD_MAX_INTERVAL_MS'] = 200
    assert detect_double_blink(config_short) is False, "Should fail with short interval"

    # Test with a long interval (400ms) - should succeed
    config_long = default_config.copy()
    config_long['DD_MAX_INTERVAL_MS'] = 400
    assert detect_double_blink(config_long) is True, "Should succeed with long interval"

# endregion TestDetectDoubleBlink

# Note: These tests assume detect_double_blink internally calls a (mocked)
# function like _get_blink_timestamps() that returns a list of recent blink timestamps.
# The actual implementation of detect_double_blink will need to match this assumption
# or the tests will need modification. 