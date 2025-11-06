import logging
import time
import pyautogui
import pyperclip

# region GetAIResponse Description
# INPUT: coords (tuple[int, int]): The (x, y) coordinates to interact with the UI.
# OUTPUT: None. Performs UI automation actions, logs errors, and clears clipboard on failure.

def perform_ui_focus_and_clipboard_clear(coords):
    """
    Attempts to focus a UI element at the given coordinates and clear the clipboard.
    Handles errors robustly and logs them.
    """
    try:
        # Move mouse slightly to wake up/focus window, then to target
        pyautogui.moveTo(coords[0] + 1, coords[1] + 1, duration=0.1)
        pyautogui.moveTo(coords[0], coords[1], duration=0.1)
    except Exception as e:
        logging.error(f"UI Automation: Move to coordinates failed: {e}", exc_info=True)
        try:
            pyperclip.copy("")
        except Exception as clip_exc:
            logging.warning(f"Failed to clear clipboard after UI automation error: {clip_exc}")
        return None

def get_ai_response_via_ui(coords):
    """
    Enhanced UI automation to get AI response:
    1. Clears clipboard to ensure fresh content.
    2. Focuses the response area by moving the mouse.
    3. Handles and logs errors, always attempts to clear clipboard on failure.
    """
    try:
        # Clear clipboard first to ensure we get fresh content
        pyperclip.copy("")
        time.sleep(0.1)
        # Focus the response area
        pyautogui.moveTo(coords[0] + 1, coords[1] + 1, duration=0.1)
        pyautogui.moveTo(coords[0], coords[1], duration=0.1)
        # Simulate Ctrl+A, Ctrl+C
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(0.1) # Short delay
        pyautogui.hotkey('ctrl', 'c')
        time.sleep(0.1) # Wait for clipboard
        response_text = pyperclip.paste()
        logging.info("Successfully retrieved text via clipboard.")
        return response_text

    except Exception as e:
        logging.error(f"UI Automation: Get AI response via UI failed: {e}", exc_info=True)
        # Attempt to clear clipboard in case of partial copy?
        try:
            pyperclip.copy("")
        except Exception as clip_e:
            logging.warning(f"Failed to clear clipboard after get_ai_response error: {clip_e}")
        return None

# endregion GetAIResponse Description