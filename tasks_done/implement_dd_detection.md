---
Description: Implement core logic for detecting a double blink (DD) using suitable input methods (e.g., webcam eye tracking, dedicated hardware signal). The function should return True if a double blink is detected within a specified timeframe, False otherwise. Consider configurability for sensitivity and timing.
Implementation File: src/accessibility_input.py
Test File: tests/test_accessibility_input.py
Status: pending
---

# Task: Implement Double Blink (DD) Detection

Implement a Python function `detect_double_blink(config: dict) -> bool` within the `src/accessibility_input.py` file.

**Requirements:**

1.  Access input source (placeholder/mock for now, actual integration later).
2.  Define logic to identify two distinct blink signals within a configurable time window (e.g., `DD_MAX_INTERVAL_MS` in config).
3.  Return `True` upon successful detection of a double blink.
4.  Return `False` if the time window expires or only a single blink is detected.
5.  Make timing parameters configurable via the passed `config` dictionary. 