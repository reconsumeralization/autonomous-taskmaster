import pyautogui
import time
import sys
import logging
from logging.handlers import RotatingFileHandler
from pathlib import Path
from collections import deque
from typing import Deque, Optional, Dict, Any, Callable
import yaml
import argparse
import requests
import json

try:
    import numpy as np
    from PIL import Image, ImageGrab
    _IMAGE_LIBS_AVAILABLE = True
except ImportError:
    print("ERROR: Required libraries 'numpy' and 'Pillow' not found.")
    print("Please install them: pip install numpy Pillow")
    _IMAGE_LIBS_AVAILABLE = False

try:
    import pytesseract
    pytesseract.pytesseract.tesseract_cmd = r'C:\Program Files\Tesseract-OCR\tesseract.exe'
    _OCR_AVAILABLE = True
except ImportError:
    print("Warning: pytesseract not installed. 'Generating' detection disabled.")
    _OCR_AVAILABLE = False

# === Default Configuration ===
DEFAULT_CONFIG = {
    "screenshot_interval_seconds": 20,  # Increased by 10 seconds
    "comparison_interval_count": 3,
    "base_idle_threshold_seconds": 55,  # Increased by 10 seconds
    "backoff_increment_seconds": 25,    # Increased by 10 seconds
    "change_threshold": 5.0,
    "target_x": 1685,
    "target_y": 970,
    "typing_delay_seconds": 0.2,
    "typewrite_interval": 0.05,
    "enter_presses": 2,
    "log_directory": "logs",
    "log_filename": "idle_monitor_v3.log",
    "log_level_file": "DEBUG",
    "log_level_console": "INFO",
    "startup_delay_seconds": 3,
    "post_dd_wait_seconds": 40,         # Increased by 10 seconds
    "ocr_check_enabled": True,
    "ocr_region_offset_left": 200,
    "ocr_region_offset_top": 50,
    "ocr_region_offset_right": 200,
    "ocr_region_offset_bottom": 50,
    "ocr_lang": "eng",
    "ocr_retry_delay_seconds": 20,      # Increased by 10 seconds
    "generating_slowdown_seconds": 40,  # Increased by 10 seconds
    "generating_max_wait_seconds": 100, # Increased by 10 seconds
    "key_facts": [
        "Don't forget you can use MCP tools and make them too!",
        "Use and create agents when you need help.",
        "Make sure you work on MCP tools.",
        "You can use curl commands to interact with APIs or download files.",
        "Use cursor commands to navigate and select text efficiently.",
        "As admin, you can take screenshots or run privileged commands as needed.",
        "You can combine dd with ll for more context.",
        "For screenshots: try using the screenshot tool or snipping tool as admin.",
        "Cursor navigation: use arrow keys, Ctrl+Arrow for word jumps, Shift+Arrow to select.",
        "If you need to break up your work, use multiple dd messages for clarity.",
    ],
    "reminder_index_file": "dd_reminder_index.txt",  # For persistent cycling if desired
    "mcp_reminder_interval": 16,  # Increased by 10 seconds (if this is a time interval)
    "mcp_dev_reminder_interval": 20,  # Increased by 10 seconds (if this is a time interval)
    "generating_dot_extra_cooldown": 20,  # Increased by 10 seconds
    # --- Ollama Planner Configuration ---
    "ollama_host": "http://localhost:11434",
    "ollama_model": "llama3",  # Default model name for Ollama
    "ollama_extra_options": {}, # Dict of extra options for Ollama API if needed
}

def load_config(config_path: str = 'config.yaml') -> Dict[str, Any]:
    config = DEFAULT_CONFIG.copy()
    try:
        config_file_path = Path(config_path).resolve()
        logging.debug(f"Attempting to load config from resolved path: {config_file_path}")
        if config_file_path.is_file():
            with open(config_file_path, 'r', encoding='utf-8') as f:
                user_config = yaml.safe_load(f)
                if isinstance(user_config, dict):
                    config.update(user_config)
                    logging.info(f"Loaded configuration from {config_file_path}")
                else:
                    logging.warning(f"Config file {config_file_path} is not a valid dictionary. Using defaults.")
        else:
            logging.warning(f"Config file {config_file_path} not found. Using defaults.")
    except Exception as e:
        logging.error(f"Error loading config file {config_path}: {e}. Using defaults.", exc_info=True)
    return config

def setup_logging(config: Dict[str, Any]):
    log_dir = Path(config["log_directory"])
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file_path = log_dir / config["log_filename"]

    log_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')

    try:
        file_log_level = getattr(logging, config["log_level_file"].upper(), logging.DEBUG)
    except AttributeError:
        file_log_level = logging.DEBUG
        print(f"Warning: Invalid file log level '{config['log_level_file']}'. Defaulting to DEBUG.")

    file_handler = RotatingFileHandler(
        log_file_path, maxBytes=2*1024*1024, backupCount=3, encoding='utf-8'
    )
    file_handler.setFormatter(log_formatter)
    file_handler.setLevel(file_log_level)

    # Stream Handler (Console)
    try:
        console_log_level = getattr(logging, config["log_level_console"].upper(), logging.INFO)
    except AttributeError:
        console_log_level = logging.INFO
        print(f"Warning: Invalid console log level '{config['log_level_console']}'. Defaulting to INFO.")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(log_formatter)
    stream_handler.setLevel(console_log_level)

    # Configure Root Logger (clear existing handlers first)
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        for h in root_logger.handlers[:]:
            root_logger.removeHandler(h)
            h.close()

    logging.basicConfig(level=logging.DEBUG, handlers=[file_handler, stream_handler])
    logging.getLogger("PIL").setLevel(logging.WARNING)
    logging.info("Logging configured.")

def clear_line(length=70):
    """Clears the current console line."""
    print(" " * length, end='\r')

# === Ollama Planner Integration ===

def get_plan_from_ollama(task_details: Dict[str, Any], config: Dict[str, Any]) -> Optional[str]:
    """Generates a plan for the task using the configured Ollama instance."""
    ollama_host = config.get("ollama_host", "http://localhost:11434")
    ollama_model = config.get("ollama_model", "llama3")
    ollama_extra_options = config.get("ollama_extra_options", {})

    # Construct the prompt
    prompt = f"""You are an expert AI assistant. Analyze the following software development task and generate a concise, step-by-step plan to accomplish it.
Task Description: {task_details.get('description', 'No description provided.')}
Relevant Files:
- Implementation: {task_details.get('implementation_file', 'N/A')}
- Test: {task_details.get('test_file', 'N/A')}
- Source (if applicable): {task_details.get('source_file', 'N/A')}
Project Root: {task_details.get('project_root', 'N/A')}

Provide the plan as a numbered list. Focus on clarity and actionable steps.
Plan:
"""

    payload = {
        "model": ollama_model,
        "prompt": prompt,
        "stream": False,
    }
    if ollama_extra_options:
        payload.update(ollama_extra_options)

    url = f"{ollama_host.rstrip('/')}/api/generate"
    logging.info(f"Invoking Ollama for planning task {task_details.get('id', 'N/A')}:")
    logging.info(f"Ollama URL: {url}")
    logging.debug(f"Ollama payload: {json.dumps(payload)[:500]}...")  # Truncate for log

    print(f"Generating plan for task {task_details.get('id', 'N/A')} using Ollama...")

    try:
        response = requests.post(url, json=payload, timeout=120)
        if response.status_code == 200:
            data = response.json()
            plan = data.get("response", "").strip()
            logging.info(f"--- Ollama Generated Plan (Task {task_details.get('id', 'N/A')}) ---")
            logging.info(plan)
            logging.info(f"--- End Ollama Plan ---")
            print(f"Plan generated successfully (see {config.get('log_filename', 'idle_monitor_v3.log')} for details).")
            return plan
        else:
            logging.error(f"Ollama API call failed for task {task_details.get('id', 'N/A')}. Status: {response.status_code}")
            logging.error(f"Ollama response: {response.text}")
            print(f"Error: Ollama API call failed (Status: {response.status_code}). Check logs.")
            return None
    except requests.exceptions.RequestException as e:
        logging.error(f"Error connecting to Ollama: {e}", exc_info=True)
        print(f"Error: Could not connect to Ollama at {ollama_host}. Is it running?")
        return None
    except Exception as e:
        logging.error(f"Error running Ollama: {e}", exc_info=True)
        print(f"Error: An unexpected error occurred while running Ollama. Check logs.")
        return None

def handle_delegated_task(task_details_json: str, config: Dict[str, Any]):
    """Handles a task delegated via command line argument."""
    try:
        task_details = json.loads(task_details_json)
        logging.info(f"Received delegated task: {task_details.get('id', 'Unknown ID')}")
        logging.debug(f"Task Details: {task_details}")

        # Attempt to generate a plan using Ollama
        plan = get_plan_from_ollama(task_details, config)

        # Exit after attempting planning, regardless of success/failure
        if plan:
            sys.exit(0)
        else:
            sys.exit(1)

    except json.JSONDecodeError:
        logging.error(f"Failed to decode task JSON data: {task_details_json}")
        print("Error: Invalid task data received.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error handling delegated task: {e}", exc_info=True)
        print("Error: An unexpected error occurred while handling the delegated task.")
        sys.exit(1)

# === ScreenIdleMonitor Class ===

class ScreenIdleMonitor:
    def __init__(self, config: Dict[str, Any], dd_action_callback: Optional[Callable[[int], None]] = None):
        if not _IMAGE_LIBS_AVAILABLE:
            logging.critical("Required image libraries (numpy, Pillow) not found. Exiting.")
            sys.exit(1)
        self.config = config
        self.screenshot_deque: Deque[Optional['Image.Image']] = deque(maxlen=self.config["comparison_interval_count"])
        self.last_change_time = time.time()
        self.screenshot_counter = 0
        self.backoff_intervals = 0
        self.post_dd_waiting = False
        self.post_dd_start_time = None
        self.turn_count = 0
        self.running = False
        self.dd_action_callback = dd_action_callback
        self.ocr_available = _OCR_AVAILABLE and self.config.get("ocr_check_enabled", True)
        self.ocr_region = self._calculate_ocr_region()
        self._reminder_index = 0
        self._change_detected_during_post_dd = False
        logging.info("ScreenIdleMonitor initialized.")
        self._log_config()

    def _log_config(self):
        logging.info(f"--- Monitor Configuration ---")
        logging.info(f"  Target Coords: ({self.config['target_x']}, {self.config['target_y']})")
        logging.info(f"  Screenshot Interval: {self.config['screenshot_interval_seconds']}s")
        logging.info(f"  Comparison Interval: {self.config['comparison_interval_count']} screenshots")
        logging.info(f"  Base Idle Threshold: {self.config['base_idle_threshold_seconds']}s")
        logging.info(f"  Backoff Increment: {self.config['backoff_increment_seconds']}s")
        logging.info(f"  Change Threshold: {self.config['change_threshold']:.2f}")
        logging.info(f"  Post-DD Wait: {self.config['post_dd_wait_seconds']}s")
        logging.info(f"  OCR Check Enabled: {self.ocr_available}")
        if self.ocr_available:
            logging.info(f"  OCR Region: {self.ocr_region}")
            logging.info(f"  OCR Retry Delay: {self.config['ocr_retry_delay_seconds']}s")
        logging.info(f"----------------------------")

    def _calculate_ocr_region(self) -> Optional[tuple[int, int, int, int]]:
        if not self.ocr_available:
            return None
        tx, ty = self.config['target_x'], self.config['target_y']
        left = tx - self.config.get('ocr_region_offset_left', 200)
        top = ty - self.config.get('ocr_region_offset_top', 50)
        right = tx + self.config.get('ocr_region_offset_right', 200)
        bottom = ty + self.config.get('ocr_region_offset_bottom', 50)
        return (left, top, right, bottom)

    def _take_screenshot(self) -> Optional['Image.Image']:
        try:
            return ImageGrab.grab()
        except Exception as e:
            logging.error(f"Failed to take screenshot: {e}")
            return None

    def _compare_images(self, img1: Optional['Image.Image'], img2: Optional['Image.Image']) -> float:
        if img1 is None or img2 is None or img1.size != img2.size:
            logging.debug("Cannot compare images: None or mismatched size.")
            return float('inf')
        try:
            arr1 = np.array(img1.convert('L'), dtype=np.float32)
            arr2 = np.array(img2.convert('L'), dtype=np.float32)
            diff = np.mean(np.abs(arr1 - arr2))
            logging.debug(f"Image difference calculated: {diff:.2f}")
            return diff
        except Exception as e:
            logging.error(f"Error comparing images: {e}")
            return float('inf')

    def _is_generating_visible(self, screenshot: 'Image.Image') -> bool:
        if not self.ocr_available or self.ocr_region is None:
            return False
        try:
            region_img = screenshot.crop(self.ocr_region)
            text = pytesseract.image_to_string(region_img, lang=self.config.get('ocr_lang', 'eng'))
            logging.debug(f"OCR text in region {self.ocr_region}: {text.strip()}")
            if "generating" in text.lower():
                logging.info(f"Detected 'generating' in region {self.ocr_region}. Will wait and retry.")
                return True
            return False
        except Exception as e:
            logging.error(f"OCR error during 'generating' check: {e}")
            return False

    def _get_next_reminder(self) -> str:
        key_facts = self.config.get('key_facts', [])
        if not key_facts:
            return ""
        reminder = key_facts[self._reminder_index % len(key_facts)]
        self._reminder_index += 1
        return reminder

    def _default_dd_action(self, turn_count: int):
        target_coords = (self.config['target_x'], self.config['target_y'])
        logging.info(f"Performing default 'dd' action at {target_coords}")

        enter_presses = self.config.get('enter_presses', 2)
        type_interval = self.config.get('typewrite_interval', 0.05)
        typing_delay = self.config.get('typing_delay_seconds', 0.2)

        reminder = self._get_next_reminder()
        if reminder:
            dd_message = f"dd {reminder}"
        else:
            dd_message = "dd"

        try:
            pyautogui.moveTo(target_coords[0], target_coords[1])
            time.sleep(0.1)
            pyautogui.click()
            time.sleep(typing_delay)
            pyautogui.typewrite(dd_message, interval=type_interval)
            logging.debug(f"Typed message: {dd_message}")
            for i in range(enter_presses):
                time.sleep(typing_delay)
                pyautogui.press('enter')
                logging.debug(f"Pressed Enter #{i+1} for dd message")
            time.sleep(0.3)
            logging.info("Default 'dd' action completed.")
        except pyautogui.FailSafeException:
            logging.error("PyAutoGUI Fail-Safe triggered (mouse moved to corner?). Stopping monitor.")
            self.stop()
        except Exception as e:
            logging.error(f"Error performing pyautogui action: {e}", exc_info=True)
            print(f"\nERROR performing action: {e}")

    def _check_and_perform_action(self):
        current_time = time.time()
        effective_idle_threshold = max(
            self.config['post_dd_wait_seconds'],
            self.config['base_idle_threshold_seconds'] + (self.backoff_intervals * self.config['backoff_increment_seconds'])
        )
        idle_duration = current_time - self.last_change_time

        if not self.post_dd_waiting:
            if idle_duration >= effective_idle_threshold:
                clear_line()
                logging.info(f"Screen idle for {idle_duration:.1f}s (Threshold: {effective_idle_threshold}s). Triggering action.")
                print("Idle threshold reached. Performing action...")

                self.turn_count += 1
                if self.dd_action_callback:
                    logging.debug("Calling provided dd_action_callback.")
                    self.dd_action_callback(self.turn_count)
                else:
                    logging.debug("No callback provided, performing default dd action (typing).")
                    self._default_dd_action(self.turn_count)

                if self.running:
                    self.post_dd_waiting = True
                    self.post_dd_start_time = time.time()
                    self.last_change_time = time.time()
                    self.screenshot_counter = 0
                    self.screenshot_deque.clear()
                    new_baseline = self._take_screenshot()
                    if new_baseline:
                        self.screenshot_deque.append(new_baseline)
                    else:
                        logging.warning("Failed to get post-action baseline screenshot.")
                    print("Action completed. Monitoring screen...     ", end='\r')
            else:
                if self.screenshot_counter != 0 or len(self.screenshot_deque) < self.config['comparison_interval_count']:
                    remaining_time = effective_idle_threshold - idle_duration
                    backoff_display = self.backoff_intervals * self.config['backoff_increment_seconds']
                    print(f"Idle... Triggering in {remaining_time:3.0f}s (Backoff: +{backoff_display}s)       ", end='\r')
        else:
            elapsed_since_dd = current_time - self.post_dd_start_time if self.post_dd_start_time else 0
            if elapsed_since_dd >= self.config['post_dd_wait_seconds']:
                if not hasattr(self, '_change_detected_during_post_dd') or not self._change_detected_during_post_dd:
                    self.backoff_intervals += 1
                    logging.info(f"No change detected for {self.config['post_dd_wait_seconds']}s after dd. Incrementing backoff to {self.backoff_intervals}.")
                else:
                    logging.info("Change detected during post-dd wait. Not incrementing backoff.")
                self.post_dd_waiting = False
                self.post_dd_start_time = None
            else:
                wait_remaining = self.config['post_dd_wait_seconds'] - elapsed_since_dd
                print(f"Waiting {wait_remaining:3.0f}s after dd before backoff...       ", end='\r')

    def run_monitor_loop(self):
        self.running = True
        logging.info("Starting monitoring loop.")

        startup_delay = self.config.get("startup_delay_seconds", 3)
        if startup_delay > 0:
            logging.info(f"Startup delay: {startup_delay} seconds...")
            time.sleep(startup_delay)

        initial_ss = self._take_screenshot()
        if initial_ss:
            self.screenshot_deque.append(initial_ss)
            self.last_change_time = time.time()
        else:
            logging.warning("Failed to get initial screenshot. Monitoring may be unreliable.")

        while self.running:
            try:
                time.sleep(self.config["screenshot_interval_seconds"])
                current_screenshot = self._take_screenshot()
                if current_screenshot is None:
                    logging.warning("Skipping check cycle due to screenshot error.")
                    print("Screenshot error. Retrying...        ", end='\r')
                    continue

                self.screenshot_deque.append(current_screenshot)
                self.screenshot_counter += 1
                logging.debug(f"Screenshot taken (Count: {self.screenshot_counter}). Deque size: {len(self.screenshot_deque)}")

                change_detected_this_cycle = False
                if self.screenshot_counter >= self.config["comparison_interval_count"] and len(self.screenshot_deque) == self.config["comparison_interval_count"]:
                    logging.debug(f"Performing comparison (Cycle #{self.screenshot_counter}).")
                    s1 = self.screenshot_deque[0]
                    s2 = self.screenshot_deque[1]
                    s3 = self.screenshot_deque[-1]

                    ocr_retry_delay = self.config.get('ocr_retry_delay_seconds', 20)
                    ocr_detected_generating = False
                    if self.ocr_available:
                        if self._is_generating_visible(s3):
                            ocr_detected_generating = True
                            logging.info(f"'generating' detected. Resetting idle timer and waiting {ocr_retry_delay}s...")
                            print(f"'generating' detected. Resetting timer...   ", end='\r')
                            self.last_change_time = time.time()
                            time.sleep(ocr_retry_delay)

                    if not ocr_detected_generating:
                        diff1 = self._compare_images(s1, s3)
                        diff2 = self._compare_images(s2, s3)

                        if diff1 > self.config['change_threshold'] or diff2 > self.config['change_threshold']:
                            change_detected_this_cycle = True
                            logging.info(f"Change detected (Diffs: {diff1:.2f}, {diff2:.2f}). Resetting timer.")
                            print("Change detected. Countdown reset.     ", end='\r')
                            self.last_change_time = time.time()
                            self.backoff_intervals = 0
                            if self.post_dd_waiting:
                                logging.info("Change detected during post-dd wait period.")
                                self._change_detected_during_post_dd = True
                                self.post_dd_waiting = False
                                self.post_dd_start_time = None
                        else:
                            logging.info(f"No significant change detected (Diffs: {diff1:.2f}, {diff2:.2f}).")
                            if not self.post_dd_waiting and not ocr_detected_generating:
                                print("No change detected.             ", end='\r')
                            if self.post_dd_waiting:
                                self._change_detected_during_post_dd = False

                    self.screenshot_counter = 0

                self._check_and_perform_action()

            except KeyboardInterrupt:
                clear_line()
                logging.info("--- Script interrupted by user (Ctrl+C) ---")
                print("\nExiting script.")
                self.stop()
            except pyautogui.FailSafeException:
                clear_line()
                logging.error("PyAutoGUI Fail-Safe triggered (mouse moved to corner?). Stopping monitor.")
                print("\nExiting due to Fail-Safe.")
                self.stop()
            except Exception as e:
                clear_line()
                logging.critical(f"An unexpected critical error occurred in monitor loop: {e}", exc_info=True)
                print(f"\nCRITICAL ERROR: {e}")
                time.sleep(5)

    def start(self):
        if self.running:
            logging.warning("Monitor is already running.")
            return
        self.run_monitor_loop()

    def stop(self):
        logging.info("Stopping monitor loop...")
        self.running = False

    def get_status(self) -> Dict[str, Any]:
        idle_duration = time.time() - self.last_change_time if hasattr(self, 'last_change_time') else 0
        return {
            "running": self.running,
            "last_change_time": self.last_change_time if hasattr(self, 'last_change_time') else None,
            "current_idle_time": round(idle_duration, 1),
            "backoff_intervals": self.backoff_intervals,
            "post_dd_waiting": self.post_dd_waiting,
            "turn_count": self.turn_count,
            "ocr_available": self.ocr_available,
            "state": "waiting" if not self.post_dd_waiting else "post_dd_wait",
            "config": self.config
        }

# === Main Execution ===

if __name__ == "__main__":
    # --- Argument Parsing for Task Delegation ---
    parser = argparse.ArgumentParser(description="Screen Idle Monitor or Delegated Task Planner.")
    parser.add_argument(
        "--delegate-task",
        metavar='TASK_JSON',
        type=str,
        help="Receive task details as a JSON string for planning via Ollama."
    )
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to the configuration file."
    )
    args = parser.parse_args()

    # Load Config First
    script_dir = Path(__file__).parent
    config_path = args.config
    if not Path(config_path).is_absolute():
        config_path = script_dir / config_path

    config = load_config(str(config_path))
    setup_logging(config)

    # --- Check if running as Delegated Task Handler ---
    if args.delegate_task:
        logging.info("Running in Delegated Task Planner mode.")
        handle_delegated_task(args.delegate_task, config)

    # --- Else, run as Screen Idle Monitor ---
    logging.info("Running in Screen Idle Monitor mode.")
    if not _IMAGE_LIBS_AVAILABLE:
        logging.critical("Required image libraries (numpy, Pillow) not found for monitor mode. Exiting.")
        print("ERROR: Required libraries 'numpy' and 'Pillow' not found.")
        print("Please install them: pip install numpy Pillow")
        sys.exit(1)

    print(f"Screen Idle Monitor starting up... (Startup delay: {config.get('startup_delay_seconds', 3)}s)")
    time.sleep(config.get('startup_delay_seconds', 3))

    # Optional: Connect to Taskmaster if a callback is provided (example placeholder)
    taskmaster_callback = None

    monitor = ScreenIdleMonitor(config, dd_action_callback=taskmaster_callback)
    monitor.start()

    try:
        while monitor.running:
            status = monitor.get_status()
            idle_time = status['current_idle_time']
            state = status['state']
            clear_line()
            print(f"Status: {state} | Idle: {idle_time:.1f}s | Turn: {status['turn_count']} | DD Wait: {status['post_dd_waiting']}", end='\r')
            time.sleep(2)
    except KeyboardInterrupt:
        print("\nCtrl+C detected. Stopping monitor...")
    finally:
        monitor.stop()
        print("\nMonitor stopped.")
