import os
import json
import logging
import yaml
import shutil
import time
import re
import subprocess
import ast
from typing import List, Dict, Any, Optional, Tuple

# Attempt optional imports for UI automation and TTS
try:
    import pyautogui
    import pyperclip
    PYAUTOGUI_AVAILABLE = True
except ImportError:
    logging.warning("PyAutoGUI or Pyperclip not found. UI automation features will be disabled.")
    PYAUTOGUI_AVAILABLE = False

try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    logging.warning("pyttsx3 not found. TTS features will be disabled.")
    TTS_AVAILABLE = False

# Global TTS engine instance (initialized when needed)
tts_engine = None

# ================== Task File Management ==================

def load_tasks(config: dict) -> List[Dict]:
    """Load tasks from the JSON file specified in the config."""
    todo_path = config.get('TODO_PATH', 'taskmaster_todos.json')
    tasks = []
    try:
        if os.path.exists(todo_path):
            with open(todo_path, 'r', encoding='utf-8') as f:
                loaded_json_tasks = json.load(f)
                # Handle both "task" and "description" keys
                for task_data in loaded_json_tasks:
                    desc = task_data.get("description", task_data.get("task"))
                    if desc:
                        # Standardize to use "description" key internally
                        task_data["description"] = desc
                        # Remove old "task" key if it exists and differs
                        if "task" in task_data and task_data["task"] != desc:
                            del task_data["task"]
                        tasks.append(task_data)
                    else:
                        logging.error(f"Task missing required field 'description' or 'task' in {todo_path}: {task_data}")
        else:
            logging.warning(f"Task file not found: {todo_path}. Starting with empty list.")
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from {todo_path}. Starting with empty list.")
    except Exception as e:
        logging.error(f"Error loading tasks from {todo_path}: {e}", exc_info=True)
    return tasks

def save_tasks(tasks: List[Dict], config: dict):
    """Persist task list to JSON file specified in config."""
    dry_run = config.get("DRY_RUN", False)
    todo_path = config.get("TODO_PATH", "taskmaster_todos.json")
    full_path = os.path.abspath(todo_path)

    if dry_run:
        logging.info(f"[DRY RUN] Would save {len(tasks)} tasks to {full_path}")
        return

    try:
        # Ensure the directory exists
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        
        with open(full_path, 'w', encoding='utf-8') as f:
            # Save in a structure that load_tasks can read, e.g., simple list
            json.dump(tasks, f, indent=2, ensure_ascii=False)
        logging.info(f"Saved {len(tasks)} tasks successfully to {full_path}")
    except Exception as e:
        logging.error(f"Failed to save tasks to {full_path}: {e}", exc_info=True)

# ================== Code Task (.md) Management ==================

def parse_task_header(task_content: str) -> Tuple[Dict, str]:
    """Parse YAML header from task description between --- lines."""
    parts = task_content.split("---", 2)
    header = {}
    description = task_content # Default to full content if no header
    
    if len(parts) >= 3 and parts[0].strip() == '':
        header_text = parts[1].strip()
        description = parts[2].strip()
        try:
            parsed_yaml = yaml.safe_load(header_text)
            if isinstance(parsed_yaml, dict):
                header = parsed_yaml
                logging.debug(f"Parsed YAML header: {header}")
            else:
                logging.warning("Parsed YAML header is not a dictionary. Ignoring header.")
        except yaml.YAMLError as e:
            logging.error(f"Error parsing task YAML header: {e}. Treating as plain description.")
            # Revert description if YAML parsing fails but markers were present
            description = task_content 
    else:
        logging.debug("No YAML header found (must start and end with ---).")
        
    return header, description

def mark_task_done(task_path: str, config: dict):
    """Move completed task file to the done directory specified in config."""
    dry_run = config.get("DRY_RUN", False)
    done_dir = config.get("DONE_DIR", "tasks_done")
    full_done_dir = os.path.abspath(done_dir)
    task_filename = os.path.basename(task_path)
    destination_path = os.path.join(full_done_dir, task_filename)

    if dry_run:
        logging.info(f"[DRY RUN] Would move {task_path} to {destination_path}")
        return True # Simulate success

    try:
        os.makedirs(full_done_dir, exist_ok=True)
        shutil.move(task_path, destination_path)
        logging.info(f"Moved task {task_filename} to {full_done_dir}")
        return True
    except Exception as e:
        logging.error(f"Failed to move task {task_path} to {destination_path}: {e}", exc_info=True)
        return False

def get_next_task(config: dict) -> Optional[str]:
    """Retrieve the full path to the next .md task by sorting alphabetically."""
    tasks_dir = config.get("TASKS_DIR", "tasks")
    full_tasks_dir = os.path.abspath(tasks_dir)

    if not os.path.exists(full_tasks_dir) or not os.path.isdir(full_tasks_dir):
        logging.warning(f"Tasks directory '{full_tasks_dir}' does not exist or is not a directory.")
        return None
        
    try:
        tasks = sorted([f for f in os.listdir(full_tasks_dir) if f.endswith('.md') and os.path.isfile(os.path.join(full_tasks_dir, f))])
        if not tasks:
            logging.info(f"No .md tasks found in {full_tasks_dir}")
            return None
            
        next_task_path = os.path.join(full_tasks_dir, tasks[0])
        logging.info(f"Next .md task found: {next_task_path}")
        return next_task_path
    except Exception as e:
        logging.error(f"Error accessing tasks directory {full_tasks_dir}: {e}", exc_info=True)
        return None 

# ================== Accessibility & Output ==================

def init_tts():
    """Initialize Text-to-Speech engine if available and not already initialized."""
    global tts_engine
    if TTS_AVAILABLE and tts_engine is None:
        try:
            tts_engine = pyttsx3.init()
            # You might want to configure voice, rate, volume here if needed
            # Example: 
            # voices = tts_engine.getProperty('voices')
            # tts_engine.setProperty('voice', voices[0].id) # Set voice
            # tts_engine.setProperty('rate', 150) # Set speed
            logging.info("TTS engine initialized successfully.")
            return True
        except Exception as e:
            logging.error(f"TTS engine initialization failed: {e}")
            return False
    elif tts_engine is not None:
        return True # Already initialized
    return False # Not available or failed previously

def speak_and_print(message: str, config: dict, line_num: Optional[int] = None):
    """Output message via console log and optionally TTS based on config."""
    prefix = f"{line_num}. ---> " if line_num is not None else "---> "
    log_message = prefix + message
    logging.info(log_message) # Log to console/file via logging setup
    
    # Also print directly for immediate user feedback if needed outside logs
    # print(log_message)
    
    if config.get("ENABLE_TTS", False):
        if init_tts() and tts_engine:
            try:
                # Ensure the engine is not busy from a previous call
                tts_engine.stop() 
                tts_engine.say(message)
                tts_engine.runAndWait()
            except RuntimeError as e:
                # Handle specific case where runAndWait might be called reentrantly
                if "run loop already started" in str(e).lower():
                     logging.warning("TTS run loop already started, skipping utterance.")
                else:
                    logging.warning(f"TTS runtime error: {e}")
            except Exception as e:
                logging.warning(f"TTS failed during say/runAndWait: {e}")
        else:
             logging.debug("TTS is disabled or failed to initialize.")

# ================== AI Code Generation ==================

def extract_code(response_text: str) -> str:
    """Extract Python code block from response text, handling potential markdown."""
    # Regex to find code blocks, trying language specifier first
    # Pattern: ```python\n(.*?)``` or ```\n(.*?)``` (dotall, multiline)
    pattern = r"```(?:python)?\s*\n(.*?)\n```"
    match = re.search(pattern, response_text, re.DOTALL | re.IGNORECASE)
    if match:
        return match.group(1).strip()
    
    # Fallback: If no standard markdown, check if the whole response might be code
    # Simple check: Does it contain typical Python keywords/structure?
    if 'def ' in response_text or 'class ' in response_text or 'import ' in response_text:
         # Avoid returning instructions or explanations if possible
         lines = response_text.strip().split('\n')
         # Basic heuristic: Filter out lines that seem like instructions
         code_lines = [line for line in lines if not line.strip().startswith(('# Instruction', '# Task', '//', 'Here is the code'))]
         if len(code_lines) > 0:
             return "\n".join(code_lines).strip()

    # If still nothing, return the stripped original text as a last resort
    logging.warning("Could not reliably extract code block, returning stripped response.")
    return response_text.strip()

def ai_generate_code(task_description: str, test_path: Optional[str], config: dict) -> str:
    """Generate code using the Grok API based on task and optional test file."""
    # Ensure requests is imported only when needed
    try:
        import requests
    except ImportError:
        logging.error("'requests' library is required for AI code generation but not installed.")
        return "# ERROR: 'requests' library not installed."

    api_key_env = config.get("GROK_API_KEY_ENV", "XAI_API_KEY")
    api_url_env = config.get("GROK_API_URL_ENV", "XAI_API_URL")
    api_key = os.environ.get(api_key_env)
    api_url = os.environ.get(api_url_env)

    if not api_key:
        logging.error(f"API Key environment variable '{api_key_env}' not set.")
        return f"# ERROR: API Key environment variable '{api_key_env}' not set."
    if not api_url:
        logging.error(f"API URL environment variable '{api_url_env}' not set.")
        return f"# ERROR: API URL environment variable '{api_url_env}' not set."

    prompt = f"Task Description (do not include this header in the response):\n{task_description}\n"
    
    test_code = ""
    if test_path and os.path.exists(test_path):
        try:
            with open(test_path, "r", encoding='utf-8') as tf:
                test_code = tf.read()
            if test_code:
                 prompt += f"\nExisting Test File ({os.path.basename(test_path)}):\n```python\n{test_code}\n```\n"
            else:
                logging.warning(f"Test file {test_path} is empty.")
        except Exception as e:
            logging.error(f"Error reading test file {test_path}: {e}")
            # Proceed without test code if reading fails

    prompt += "\nInstructions (do not include this header in the response): Write the complete Python code for the implementation file required to make the tests pass. Only output the raw Python code, nothing else (no explanations, no markdown formatting like ```python)."

    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    # Parameters can be customized via config if needed later
    data = {
        "model": "grok-1", 
        "prompt": prompt,
        "max_tokens": config.get("AI_MAX_TOKENS", 2048),
        "temperature": config.get("AI_TEMPERATURE", 0.1),
    }
    
    logging.info(f"Sending request to AI API ({api_url}) for code generation.")
    
    try:
        response = requests.post(api_url, headers=headers, json=data, timeout=config.get("AI_TIMEOUT", 120))
        response.raise_for_status() # Raise HTTPError for bad responses (4xx or 5xx)
        
        result = response.json()
        raw_response_text = result.get("choices", [{}])[0].get("text", "")
        
        if not raw_response_text:
            logging.error("API returned empty response text.")
            return "# ERROR: API returned empty response text."
            
        logging.debug(f"Raw AI response text:\n{raw_response_text[:500]}...")
        code = extract_code(raw_response_text)
        
        if not code:
            logging.error("Failed to extract code from API response.")
            return "# ERROR: Failed to extract code from API response."
        
        logging.info("Successfully received and extracted code from AI.")
        return code

    except requests.exceptions.Timeout:
         logging.error(f"AI API request timed out after {data.get('timeout')} seconds.")
         return f"# ERROR: AI API request timed out."
    except requests.exceptions.RequestException as e:
        logging.error(f"AI API request failed: {e}")
        return f"# ERROR: AI API request failed: {e}"
    except json.JSONDecodeError as e:
        logging.error(f"Failed to decode JSON response from AI API: {e}. Response text: {response.text[:500]}...")
        return f"# ERROR: Could not decode API JSON response: {e}"
    except Exception as e:
        logging.error(f"Unexpected error processing AI API response: {e}", exc_info=True)
        return f"# ERROR: Unexpected error processing API response: {e}"

# ================== Test Execution ==================

def run_pytest(config: dict, pytest_args: Optional[List[str]] = None) -> Tuple[bool, str, str]:
    """Run pytest and return status (bool), stdout (str), stderr (str). Accepts optional arguments."""
    # Ensure pytest is run using the python from the active venv if possible
    # This helps find installed packages correctly.
    python_executable = sys.executable # Path to python in current venv
    base_command = [python_executable, "-m", "pytest"]
    
    args_to_run = base_command
    if pytest_args:
        args_to_run.extend(pytest_args)
        
    logging.info(f"Running pytest command: {' '.join(args_to_run)}")
    
    try:
        # Run pytest as a module of the current python interpreter
        result = subprocess.run(
            args_to_run, 
            capture_output=True, 
            text=True, 
            encoding='utf-8', # Specify encoding
            check=False # Don't raise exception on non-zero exit code
        )
        
        stdout = result.stdout
        stderr = result.stderr
        passed = result.returncode == 0

        # Log output (potentially large, consider truncating or summarizing)
        log_limit = 1000 # Limit logged output length
        logging.debug(f"Pytest stdout:\n{stdout[:log_limit]}{'...' if len(stdout) > log_limit else ''}")
        if stderr:
             logging.debug(f"Pytest stderr:\n{stderr[:log_limit]}{'...' if len(stderr) > log_limit else ''}")
        
        logging.info(f"Pytest completed with return code {result.returncode}. Passed: {passed}")
        return passed, stdout, stderr

    except FileNotFoundError:
        error_msg = f"Error: '{python_executable}' or 'pytest' command not found. Ensure Python environment is correct and pytest is installed."
        logging.error(error_msg)
        return False, "", error_msg
    except Exception as e:
        error_msg = f"An unexpected error occurred while running pytest: {e}"
        logging.error(error_msg, exc_info=True)
        return False, "", error_msg

# ================== UI Automation Helpers ==================

def capture_coordinates(prompt: str, timeout: int) -> Optional[Tuple[int, int]]:
    """Capture mouse coordinates after user positioning. Requires PyAutoGUI."""
    if not PYAUTOGUI_AVAILABLE:
        logging.error("Cannot capture coordinates, PyAutoGUI not available.")
        return None
    try:
        logging.info(prompt)
        for i in range(timeout, 0, -1):
            msg = f"Position mouse in {i} seconds..."
            logging.info(msg)
            print(msg) # Direct print for user
            time.sleep(1)
        coords = pyautogui.position()
        logging.info(f"Coordinates captured: {coords}")
        print(f"Coordinates captured: {coords}")
        return coords
    except Exception as e:
        logging.error(f"Failed to capture coordinates: {e}", exc_info=True)
        return None

def send_chat_message(coords: Tuple[int, int], message: str, config: dict) -> bool:
    """Send message via simulated keyboard/mouse. Requires PyAutoGUI."""
    if not PYAUTOGUI_AVAILABLE:
        logging.error("Cannot send chat message, PyAutoGUI not available.")
        return False
        
    dry_run = config.get("DRY_RUN", False)
    if dry_run:
        logging.info(f"[DRY RUN] Would click at {coords} and type: {message}")
        return True
        
    try:
        pyautogui.click(coords) # Click at the specified coordinates
        time.sleep(0.3) # Small pause
        pyautogui.typewrite(message, interval=config.get("TYPE_INTERVAL", 0.05))
        time.sleep(0.1)
        pyautogui.press('enter')
        logging.info(f"Sent message to coords {coords}: {message[:50]}{'...' if len(message)>50 else ''}")
        return True
    except Exception as e:
        logging.error(f"Send chat message failed: {e}", exc_info=True)
        return False

def get_ai_response(coords: Tuple[int, int], config: dict) -> Optional[str]:
    """Capture text from chat history via clipboard. Requires PyAutoGUI/Pyperclip."""
    if not PYAUTOGUI_AVAILABLE:
        logging.error("Cannot get AI response, PyAutoGUI/Pyperclip not available.")
        return None
        
    dry_run = config.get("DRY_RUN", False)
    if dry_run:
        logging.info(f"[DRY RUN] Would click at {coords} and read clipboard.")
        return "[DRY RUN RESPONSE]"
        
    try:
        pyautogui.click(coords) # Click on the chat history area
        time.sleep(0.3)
        pyautogui.hotkey('ctrl', 'a') # Select all
        time.sleep(0.2)
        pyautogui.hotkey('ctrl', 'c') # Copy
        time.sleep(0.5) # Allow time for clipboard operation
        response = pyperclip.paste()
        logging.info(f"Retrieved text from clipboard (length: {len(response)}). Start: {response[:100]}...")
        return response
    except Exception as e:
        logging.error(f"Get AI response via clipboard failed: {e}", exc_info=True)
        return None

# ================== Core Task Processing Logic ==================

def process_code_task(task_path: str, config: dict) -> bool:
    """Process a single code task (.md file), generating code and running tests."""
    logging.info(f"Processing code task: {task_path}")
    speak_and_print(f"Starting code task: {os.path.basename(task_path)}", config)

    try:
        with open(task_path, "r", encoding='utf-8') as f:
            task_content = f.read()
            
        header, task_description = parse_task_header(task_content)
        test_file_rel = header.get("Test File") # Path relative to project root
        impl_file_rel = header.get("Implementation File") # Path relative to project root

        logging.info(f"Task Header: {header}")
        # Log only start of description for brevity
        logging.debug(f"Task Description (start): {task_description[:200]}...") 

        if not (test_file_rel and impl_file_rel):
            logging.warning("Task does not specify 'Test File' and 'Implementation File' in YAML header. Skipping automated processing.")
            speak_and_print("Task missing required header fields (Test File, Implementation File). Manual review needed.", config)
            # Optionally mark as done or move to a 'needs_manual_review' state/dir?
            # For now, we just log and don't mark as done automatically.
            # mark_task_done(task_path, config)
            return False # Indicate automatic processing skipped

        # Convert relative paths from config to absolute paths
        test_file_abs = os.path.abspath(test_file_rel)
        impl_file_abs = os.path.abspath(impl_file_rel)
        logging.info(f"Absolute Test File Path: {test_file_abs}")
        logging.info(f"Absolute Implementation File Path: {impl_file_abs}")

        # Ensure implementation directory exists
        impl_dir = os.path.dirname(impl_file_abs)
        if impl_dir:
            os.makedirs(impl_dir, exist_ok=True)

        # Ensure test directory exists and create placeholder if test file missing
        test_dir = os.path.dirname(test_file_abs)
        if test_dir:
            os.makedirs(test_dir, exist_ok=True)
        if not os.path.exists(test_file_abs):
             try:
                 with open(test_file_abs, "w", encoding='utf-8') as tf:
                     tf.write(f"# TODO: Write pytest tests for {impl_file_rel} based on task description in {os.path.basename(task_path)}.\nimport pytest\n\n# Example test structure\n# def test_example():\n#     assert True\n")
                 logging.info(f"Created placeholder test file: {test_file_abs}")
                 speak_and_print(f"Created placeholder test file: {test_file_rel}", config)
             except Exception as e:
                 logging.error(f"Failed to create placeholder test file {test_file_abs}: {e}")
                 speak_and_print(f"Error creating placeholder test file for {test_file_rel}. Stopping task.", config)
                 return False # Cannot proceed without tests

        # --- Test-Generate-Test Loop ---
        max_retries = config.get("AI_MAX_RETRIES", 3)
        tests_passed = False
        for attempt in range(max_retries):
            speak_and_print(f"Running tests (Attempt {attempt + 1}/{max_retries})...", config)
            logging.info(f"Running pytest (Attempt {attempt + 1}/{max_retries}) for {test_file_abs}...")
            
            # Run pytest, potentially targeting the specific test file
            passed, stdout, stderr = run_pytest(config, pytest_args=[test_file_abs]) 
            
            if passed:
                logging.info("Tests passed.")
                speak_and_print("Tests passed.", config)
                tests_passed = True
                break # Exit loop if tests pass
            else:
                logging.info(f"Tests failed (Attempt {attempt + 1}). Stdout: {stdout[:300]}... Stderr: {stderr[:300]}...")
                speak_and_print(f"Tests failed (Attempt {attempt + 1}). Generating code...", config)
                
                # Generate code only if tests failed
                code = ai_generate_code(task_description, test_file_abs, config)
                
                if not code or code.startswith("# ERROR"):
                    logging.error(f"Code generation failed: {code}")
                    speak_and_print(f"Code generation failed: {code}. Stopping task.", config)
                    break # Stop retrying if generation fails

                logging.info(f"AI-generated code (attempt {attempt + 1}, length {len(code)}):
{code[:500]}{'...' if len(code) > 500 else ''}")
                
                # Validate syntax before writing
                try:
                    ast.parse(code)
                    logging.info("Generated code syntax is valid.")
                    # Write the generated code to the implementation file
                    try:
                        with open(impl_file_abs, "w", encoding='utf-8') as f:
                            f.write(code)
                        logging.info(f"Wrote generated code to {impl_file_abs}")
                        speak_and_print(f"Generated code written to {impl_file_rel}", config)
                    except Exception as e:
                         logging.error(f"Error writing generated code to {impl_file_abs}: {e}")
                         speak_and_print(f"Error writing code to {impl_file_rel}. Stopping task.", config)
                         break # Stop if we can't write the file
                         
                except SyntaxError as e:
                    logging.error(f"Generated code has syntax errors: {e}. Will not write to file.")
                    speak_and_print(f"Generated code has syntax errors (Attempt {attempt + 1}). Retrying test/generation.", config)
                    # Continue loop to potentially get better code next time
                    # Optionally add a delay here
                    time.sleep(2)

        # --- End Loop ---

        if tests_passed:
            speak_and_print(f"Task {os.path.basename(task_path)} completed successfully.", config)
            mark_task_done(task_path, config) # Mark as done only if tests passed
            return True
        else:
            logging.error(f"Failed to generate passing code for task {task_path} after {max_retries} attempts.")
            speak_and_print(f"Failed to pass tests after {max_retries} attempts for task {os.path.basename(task_path)}. Manual review required.", config)
            # Do not mark as done if tests didn't pass
            return False

    except FileNotFoundError:
        logging.error(f"Task file not found during processing: {task_path}")
        speak_and_print(f"Error: Task file not found: {os.path.basename(task_path)}", config)
        return False
    except Exception as e:
        logging.error(f"An unexpected error occurred processing task {task_path}: {e}", exc_info=True)
        speak_and_print(f"Unexpected error processing task {os.path.basename(task_path)}: {e}", config)
        return False 