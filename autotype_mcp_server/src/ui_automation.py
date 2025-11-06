import logging
import time
from typing import Tuple, Optional, Dict, Any

# Optional imports for UI automation
try:
    import pyautogui
    import pyperclip
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    logging.warning("PyAutoGUI or Pyperclip not found. UI automation features will be disabled.")
    PYAUTOGUI_AVAILABLE = False


def capture_coordinates(prompt: str, timeout: int) -> Optional[Tuple[int, int]]:
    # region CaptureCoordinates Description
    # INPUT: prompt (str): Message to display to the user before capture.
    # INPUT: timeout (int): Countdown duration in seconds.
    # OUTPUT: (Optional[Tuple[int, int]]): Captured (x, y) coordinates, or None on error/unavailable.
    """Capture mouse coordinates after a countdown with visual feedback."""
    if not PYAUTOGUI_AVAILABLE:
        logging.error("Cannot capture coordinates: PyAutoGUI not available.")
        return None

    try:
        print(f"\n--- Coordinate Capture --- ({timeout} seconds) ---")
        print(prompt)
        for i in range(timeout, 0, -1):
            print(f"Capturing in {i}...", end='\r')
            time.sleep(1)
        print("Capturing now!           ")
        x, y = pyautogui.position()
        print(f"Captured: ({x}, {y})")
        logging.info(f"Coordinates captured via UI: ({x}, {y})")
        # Optionally provide feedback like a small click sound or visual cue if possible
        # pyautogui.click() # Example: click to confirm capture?
        return x, y
    except Exception as e:
        logging.error(f"Error capturing coordinates: {e}", exc_info=True)
        print(f"Error during coordinate capture: {e}")
        return None
    # endregion CaptureCoordinates Description

def send_chat_message(coords: Tuple[int, int], message: str, config: Dict[str, Any]) -> bool:
    # region SendChatMessage Description
    # INPUT: coords (Tuple[int, int]): The (x, y) coordinates to click before typing.
    # INPUT: message (str): The message string to type/paste.
    # INPUT: config (Dict[str, Any]): Configuration dictionary (DRY_RUN, TYPE_INTERVAL, TYPING_DELAY_SECONDS).
    # OUTPUT: (bool): True if the message was sent successfully (or in dry run), False otherwise.
    """Sends a message via simulated keyboard/mouse using config coordinates."""
    if not PYAUTOGUI_AVAILABLE:
        logging.error("UI Automation: Cannot send chat message, PyAutoGUI/Pyperclip not available.")
        return False
    
    # Extract necessary config values with defaults
    dry_run = config.get("DRY_RUN", False)
    type_interval = config.get("TYPE_INTERVAL", 0.03)
    typing_delay = config.get("TYPING_DELAY_SECONDS", 0.3)

    logging.info(f"UI Automation: Sending message to coords {coords} (Interval: {type_interval}s, Delay: {typing_delay}s)")
    logging.debug(f"UI Automation: Message content (first 100 chars): {message[:100]}...")

    if dry_run:
        logging.info(f"[DRY RUN] Would click at {coords}")
        logging.info(f"[DRY RUN] Would type {len(message)} characters: {message[:70]}...")
        logging.info("[DRY RUN] Would press Enter")
        return True

    try:
        # Store current position and add a small move before click to potentially wake up the screen/focus window
        current_pos = pyautogui.position()
        pyautogui.moveTo(coords[0] + 1, coords[1] + 1, duration=0.1)
        pyautogui.moveTo(coords[0], coords[1], duration=0.1)
        time.sleep(0.1) # Short pause after moving

        pyautogui.click()
        time.sleep(typing_delay) # Wait after click before typing

        # Type with configured interval
        # Pyperclip paste is much faster for long messages, but typewrite is more robust sometimes
        if len(message) > 200: # Heuristic for using paste
            logging.debug("UI Automation: Message long, using clipboard paste.")
            try:
                pyperclip.copy(message)
                time.sleep(0.2) # Ensure clipboard is updated
                pyautogui.hotkey('ctrl', 'v') # Use 'command', 'v' on macOS
                time.sleep(0.1)
            except Exception as paste_err:
                 logging.warning(f"UI Automation: Clipboard paste failed ({paste_err}), falling back to typewrite.")
                 pyautogui.typewrite(message, interval=type_interval) # Fallback
        else:
            pyautogui.typewrite(message, interval=type_interval)

        time.sleep(0.2) # Short pause after typing/pasting
        pyautogui.press('enter')

        logging.info(f"UI Automation: Successfully sent UI message to coords {coords}.")
        # Optional: Restore mouse position?
        # pyautogui.moveTo(current_pos)
        return True
    except pyautogui.FailSafeException:
         logging.error("UI Automation: PyAutoGUI Fail-Safe triggered during message sending (mouse moved to a corner?).")
         return False # Indicate failure
    except Exception as e:
        logging.error(f"UI Automation: Send chat message failed: {e}", exc_info=True)
        return False
    # endregion SendChatMessage Description

def get_ai_response(coords: Tuple[int, int], config: Dict[str, Any]) -> Optional[str]:
    # region GetAIResponse Description
    # INPUT: coords (Tuple[int, int]): The (x, y) coordinates to click to focus the response area.
    # INPUT: config (Dict[str, Any]): Configuration dictionary (DRY_RUN, TYPING_DELAY_SECONDS).
    # OUTPUT: (Optional[str]): The text retrieved from the clipboard, or None on error/unavailable.
    """Captures text from chat history via clipboard using configured coordinates and actions."""
    if not PYAUTOGUI_AVAILABLE:
        logging.error("UI Automation: Cannot get AI response via UI, PyAutoGUI/Pyperclip not available.")
        return None
    
    dry_run = config.get("DRY_RUN", False)
    action_delay = config.get("TYPING_DELAY_SECONDS", 0.3) # Use this for delays between actions

    logging.info(f"UI Automation: Attempting to retrieve response via clipboard using coords {coords}...")
    if dry_run:
        logging.info(f"[DRY RUN] Would click at {coords}")
        logging.info("[DRY RUN] Would press Ctrl+A (Select All)")
        logging.info("[DRY RUN] Would press Ctrl+C (Copy)")
        logging.info("[DRY RUN] Would read clipboard")
        return "[DRY RUN UI RESPONSE - Placeholder text]"

    try:
        # Clear clipboard first to ensure we get fresh content
        original_clipboard = pyperclip.paste() # Store original clipboard content? Maybe not needed.
        pyperclip.copy("")
        time.sleep(0.1)

        # Click in the response area to focus it
        current_pos = pyautogui.position()
        pyautogui.moveTo(coords[0] + 1, coords[1] + 1, duration=0.1)
        pyautogui.moveTo(coords[0], coords[1], duration=0.1)
        time.sleep(0.1)
        pyautogui.click()
        time.sleep(action_delay) # Wait after click

        # Select all (adjust hotkey if needed for macOS/Linux)
        logging.debug("UI Automation: Sending Select All (Ctrl+A)...")
        pyautogui.hotkey('ctrl', 'a') # Use 'command', 'a' on macOS
        time.sleep(0.3) # Wait for select all to register reliably

        # Copy
        logging.debug("UI Automation: Sending Copy (Ctrl+C)...")
        pyautogui.hotkey('ctrl', 'c') # Use 'command', 'c' on macOS
        time.sleep(0.5) # Wait for clipboard to update (can take a moment for large content)

        response = pyperclip.paste()
        # Optional: Restore original clipboard?
        # pyperclip.copy(original_clipboard)

        if not response:
             logging.warning("UI Automation: Retrieved empty response from clipboard via UI.")
             return None # Return None for empty

        logging.info(f"UI Automation: Retrieved text from clipboard via UI (Length: {len(response)}).")
        logging.debug(f"UI Automation: Clipboard content preview: {response[:200]}...")
        # Optional: Restore mouse position?
        # pyautogui.moveTo(current_pos)
        return response

    except pyautogui.FailSafeException:
        logging.error("UI Automation: PyAutoGUI Fail-Safe triggered during response retrieval.")
        return None
    except Exception as e:
        logging.error(f"UI Automation: Get AI response via UI failed: {e}", exc_info=True)
        # Attempt to clear clipboard in case of partial copy? Risky.
        try: pyperclip.copy("")
        except: pass
        return None 
    # endregion GetAIResponse Description 