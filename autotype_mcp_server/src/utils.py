import os
import logging
import sys
import json
from typing import Any, Optional, List, Tuple
import shutil
import yaml
import time
from pathlib import Path
import subprocess

# Optional imports for TTS
try:
    import pyttsx3
    TTS_AVAILABLE = True
except ImportError:
    logging.warning("pyttsx3 not found. TTS features will be disabled.")
    TTS_AVAILABLE = False

tts_engine = None

# ================== Logging Setup ==================
def setup_logging(config: dict):
    # region SetupLogging Description
    # INPUT: config (dict): Configuration dictionary with keys like LOG_FILE, LOG_LEVEL.
    # OUTPUT: None. Configures the root logger.
    """Initialize logging to file, stderr (for MCP), and console with rotation."""
    # Create handlers
    handlers = []
    log_path = config.get('LOG_FILE', 'mcp_server.log') 
    log_level_str = config.get('LOG_LEVEL', 'INFO').upper()
    log_level = getattr(logging, log_level_str, logging.INFO)

    # Always add stderr handler at DEBUG level
    try:
        stderr_handler = logging.StreamHandler(sys.stderr)
        stderr_handler.setLevel(logging.DEBUG) # Capture all levels to stderr
        stderr_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        stderr_handler.setFormatter(stderr_formatter)
        handlers.append(stderr_handler)
        logging.debug("[DEBUG] STDERR handler created and added.")
    except Exception as e:
        print(f"[ERROR] Failed to create stderr handler: {e}", file=sys.stderr)

    # Attempt to add file handler
    try:
        log_dir = os.path.dirname(log_path)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir)
            logging.debug(f"[DEBUG] Created log directory: {log_dir}")
        
        # Use a rotating file handler
        from logging.handlers import RotatingFileHandler
        file_handler = RotatingFileHandler(log_path, maxBytes=1*1024*1024, backupCount=3, encoding='utf-8') # 1MB per file, 3 backups
        file_handler.setLevel(log_level) # File handler uses level from config
        file_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(name)s - %(message)s')
        file_handler.setFormatter(file_formatter)
        handlers.append(file_handler)
        logging.debug(f"[DEBUG] File handler created for {log_path} at level {log_level_str}.")

    except Exception as e:
        print(f"[ERROR] Failed to create file handler for {log_path}: {e}", file=sys.stderr)
        logging.error(f"Failed to create file handler for {log_path}: {e}", exc_info=True) # Log error via basic config or stderr

    # Configure root logger
    # Remove existing handlers to avoid duplicates if setup_logging is called again
    root_logger = logging.getLogger()
    if root_logger.hasHandlers():
        for h in root_logger.handlers[:]:
            root_logger.removeHandler(h)
            h.close()
        logging.debug("[DEBUG] Existing handlers cleared.")
        
    root_logger.setLevel(logging.DEBUG)  # Set root logger to lowest level (DEBUG) to capture everything
    for handler in handlers:
        root_logger.addHandler(handler)
    
    logging.info(f"Logging initialized. Level: {log_level_str}. Log file: {log_path}. Outputting DEBUG+ to STDERR.")
    logging.debug("[DEBUG] Root logger handlers configured.")
    # endregion SetupLogging Description

def send_desktop_notification(title, message):
    # region SendDesktopNotification Description
    # INPUT: title (str): The title of the notification.
    # INPUT: message (str): The body/message of the notification.
    # OUTPUT: None. Sends a notification if win10toast is available.
    """Send a desktop notification (Windows toast)."""
    try:
        from win10toast import ToastNotifier
        toaster = ToastNotifier()
        toaster.show_toast(title, message, duration=10, threaded=True)
    except ImportError:
        print(f"[NOTIFY] {title}: {message} (win10toast not installed)")
    except Exception as e:
        print(f"[NOTIFY ERROR] {e}")
    # endregion SendDesktopNotification Description

# ================== File Operations ==================

def _resolve_path(file_path: str, project_root: Optional[str] = None) -> Path:
    """Resolves a file path, making it absolute based on project_root if relative."""
    path_obj = Path(file_path)
    if path_obj.is_absolute():
        return path_obj.resolve()
    elif project_root:
        return (Path(project_root) / file_path).resolve()
    else:
        # Default: resolve relative to current working directory if no project root
        return path_obj.resolve() 

def load_json_file(file_path: str, default_value: Any = None, project_root: Optional[str] = None) -> Any:
    # region LoadJsonFile Description
    # INPUT: file_path (str): The absolute or relative path to the JSON file.
    # INPUT: default_value (Any): The value to return if the file is not found or invalid.
    # INPUT: project_root (Optional[str]): The root directory for resolving relative paths.
    # OUTPUT: (Any): The loaded data from JSON, or the default_value on error.
    """Loads data from a JSON file, resolving path relative to project_root if provided."""
    absolute_path = _resolve_path(file_path, project_root)
    logging.debug(f"Attempting to load JSON from: {absolute_path}")
    if not absolute_path.is_file():
        logging.warning(f"JSON file not found: {absolute_path}")
        return default_value
    try:
        with open(absolute_path, 'r', encoding='utf-8') as f:
            # Handle empty file case
            content = f.read()
            if not content:
                logging.warning(f"JSON file is empty: {absolute_path}")
                return default_value
            # Reset pointer and load JSON
            # f.seek(0) # Not needed as we read content first
            data = json.loads(content)
            # logging.info(f"Successfully loaded JSON from: {absolute_path}")
            return data
    except json.JSONDecodeError as e:
        logging.error(f"Error decoding JSON from {absolute_path}: {e}", exc_info=True)
        return default_value
    except Exception as e:
        logging.error(f"Error reading file {absolute_path}: {e}", exc_info=True)
        return default_value
    # endregion LoadJsonFile Description

def save_json_file(data: Any, file_path: str, indent: int = 2, project_root: Optional[str] = None) -> bool:
    # region SaveJsonFile Description
    # INPUT: data (Any): The Python object to serialize and save.
    # INPUT: file_path (str): The absolute or relative path to save the JSON file.
    # INPUT: indent (int): Indentation level for pretty-printing (default: 2).
    # INPUT: project_root (Optional[str]): The root directory for resolving relative paths.
    # OUTPUT: (bool): True if saving was successful, False otherwise.
    """Saves data to a JSON file, resolving path relative to project_root if provided."""
    absolute_path = _resolve_path(file_path, project_root)
    logging.debug(f"Attempting to save JSON to: {absolute_path}")
    try:
        # Ensure the directory exists
        absolute_path.parent.mkdir(parents=True, exist_ok=True)
        with open(absolute_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=indent, ensure_ascii=False)
        # logging.info(f"Successfully saved JSON to: {absolute_path}")
        return True
    except TypeError as e:
        # More specific error for non-serializable data
        logging.error(f"TypeError saving JSON to {absolute_path}. Data type might not be serializable: {e}", exc_info=True)
        # Attempt to clean up the partially written or empty file
        try:
            absolute_path.unlink(missing_ok=True) # missing_ok=True handles race conditions if file wasn't created yet
            logging.debug(f"Removed potentially incomplete file due to serialization error: {absolute_path}")
        except OSError as unlink_error:
            logging.error(f"Error trying to remove incomplete file {absolute_path}: {unlink_error}")
        return False
    except Exception as e:
        logging.error(f"Error writing JSON file {absolute_path}: {e}", exc_info=True)
        return False
    # endregion SaveJsonFile Description

def move_file(source_path: str, destination_path: str, project_root: Optional[str] = None) -> bool:
    # region MoveFile Description
    # INPUT: source_path (str): The absolute or relative path of the file to move.
    # INPUT: destination_path (str): The absolute or relative path of the destination file/directory.
    # INPUT: project_root (Optional[str]): The root directory for resolving relative paths.
    # OUTPUT: (bool): True if moving was successful, False otherwise.
    """Moves a file, resolving paths relative to project_root if provided."""
    abs_source_path = _resolve_path(source_path, project_root)
    abs_dest_path = _resolve_path(destination_path, project_root)
    logging.debug(f"Attempting to move file from {abs_source_path} to {abs_dest_path}")

    if not abs_source_path.is_file():
        logging.error(f"Source file for move not found: {abs_source_path}")
        return False
    
    try:
        # Ensure destination directory exists if moving to a specific file path
        # If abs_dest_path refers to a directory, shutil.move handles it.
        # If it refers to a file, we need to ensure its parent dir exists.
        dest_parent_dir = abs_dest_path.parent
        # Check if the intended destination *might* be a file path within a non-existent dir
        # This is a bit heuristic - if the dest doesn't exist but has a suffix, assume it's a file path
        if not abs_dest_path.exists() and abs_dest_path.suffix:
             dest_parent_dir.mkdir(parents=True, exist_ok=True)
             logging.debug(f"Ensured destination directory exists: {dest_parent_dir}")
        elif not dest_parent_dir.exists():
             # This case might occur if dest_path is just a directory name that doesn't exist yet
             # We might want to create it, but shutil.move might handle this depending on usage
             # For now, let mkdir handle the direct parent if dest looks like a file path
             pass 
             
        # Use shutil.move for robustness (handles cross-filesystem moves, overwrites)
        shutil.move(str(abs_source_path), str(abs_dest_path))
        logging.info(f"Successfully moved {abs_source_path} to {abs_dest_path}")
        return True
    except Exception as e:
        logging.error(f"Error moving file {abs_source_path} to {abs_dest_path}: {e}", exc_info=True)
        return False
    # endregion MoveFile Description

def load_yaml_from_string(yaml_string: str, default_value: Any = None) -> Any:
    # region LoadYamlFromString Description
    # INPUT: yaml_string (str): The string containing YAML data.
    # INPUT: default_value (Any): The value to return if parsing fails.
    # OUTPUT: (Any): The loaded data (usually a dict), or the default_value on error.
    """Safely load YAML data from a string."""
    if not yaml_string:
        return default_value
    try:
        data = yaml.safe_load(yaml_string)
        return data
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML string: {e}", exc_info=True)
        return default_value
    except Exception as e:
        logging.error(f"Unexpected error loading YAML string: {e}", exc_info=True)
        return default_value
    # endregion LoadYamlFromString Description

def get_next_task(config: dict, project_root: Optional[str] = None) -> Optional[str]:
    # region GetNextTask Description
    # INPUT: config (dict): Configuration dictionary containing TASKS_DIR.
    # INPUT: project_root (Optional[str]): Project root for resolving TASKS_DIR if relative.
    # OUTPUT: (Optional[str]): The absolute path to the next .md task file, or None if none found or error.
    """Retrieve the full path to the next .md task by sorting alphabetically."""
    tasks_dir_relative = config.get("TASKS_DIR", "tasks")
    # Resolve tasks_dir relative to project_root if provided, else relative to CWD
    full_tasks_dir = _resolve_path(tasks_dir_relative, project_root)
    logging.debug(f"Looking for tasks in: {full_tasks_dir}")

    if not full_tasks_dir.is_dir():
        logging.warning(f"Tasks directory '{full_tasks_dir}' does not exist or is not a directory.")
        return None

    try:
        # Find all .md files directly in the tasks directory
        tasks = sorted([
            f for f in full_tasks_dir.iterdir() 
            if f.is_file() and f.suffix.lower() == '.md'
        ])
        if not tasks:
            logging.info(f"No .md tasks found in {full_tasks_dir}")
            return None

        next_task_path = str(tasks[0]) # Get the first one alphabetically
        logging.info(f"Next .md task found: {next_task_path}")
        return next_task_path
    except Exception as e:
        logging.error(f"Error accessing tasks directory {full_tasks_dir}: {e}", exc_info=True)
        return None
    # endregion GetNextTask Description

def run_pytest(config: dict, pytest_args: Optional[List[str]] = None, project_root: Optional[str] = None) -> Tuple[bool, str, str]:
    # region RunPytest Description
    # INPUT: config (dict): Configuration dictionary (may contain python path).
    # INPUT: pytest_args (Optional[List[str]]): List of arguments to pass to pytest (e.g., file paths).
    # INPUT: project_root (Optional[str]): The directory from which to run pytest (sets CWD).
    # OUTPUT: (Tuple[bool, str, str]): A tuple containing (success_boolean, stdout_string, stderr_string).
    """Run pytest with specified arguments and capture output, optionally setting the working directory."""
    success = False # Initialize success variable
    stdout = ""
    stderr = ""
    try:
        # Determine Python executable (from config, venv, or system default)
        # This logic might need refinement depending on how venvs are managed per project
        python_exe = config.get("PYTHON_EXECUTABLE", sys.executable)
        # If running in a project context, prefer the project's venv if detectable?
        if project_root:
            proj_venv_python = Path(project_root) / ".venv" / "Scripts" / "python.exe" # Common pattern
            if proj_venv_python.exists():
                python_exe = str(proj_venv_python)
                logging.info(f"Using project venv python: {python_exe}")
            else:
                 logging.warning(f"Project venv python not found at {proj_venv_python}, using default: {python_exe}")
        
        base_command = [python_exe, '-m', 'pytest']
        command_args = pytest_args if pytest_args else []

        # Resolve relative paths in command_args based on project_root if needed?
        # Pytest itself often handles relative paths from its CWD correctly.
        resolved_args = []
        for arg in command_args:
            # Simple check: if it looks like a relative path, resolve it
            # This might incorrectly resolve flags like '-k' if they match file names
            # A more robust solution would check if the arg actually IS a path
            arg_path = Path(arg)
            if not arg_path.is_absolute() and (arg_path.exists() or '/' in arg or '\\' in arg):
                 resolved_args.append(str(_resolve_path(arg, project_root)))
            else:
                 resolved_args.append(arg)
        
        command = base_command + resolved_args
        cwd = project_root if project_root else os.getcwd() # Run from project root if specified

        logging.info(f"Running pytest command: {' '.join(command)} in CWD: {cwd}")
        result = subprocess.run(
            command,
            capture_output=True,
            text=True, 
            encoding='utf-8',
            errors='replace',
            cwd=cwd, # Set working directory
            check=False 
        )

        stdout = result.stdout.strip() if result.stdout else ""
        stderr = result.stderr.strip() if result.stderr else ""
        # Pytest exit code 5 means no tests were collected - treat as non-failure for summary? No, treat as failure.
        success = result.returncode == 0 

        if success:
            logging.info(f"Pytest PASSED (Exit Code: {result.returncode}) in {cwd}")
            logging.debug(f"Pytest STDOUT:\n{stdout}")
            if stderr: logging.debug(f"Pytest STDERR:\n{stderr}")
        else:
            logging.warning(f"Pytest FAILED (Exit Code: {result.returncode}) in {cwd}")
            logging.warning(f"Pytest STDOUT:\n{stdout}")
            logging.warning(f"Pytest STDERR:\n{stderr}")

        return success, stdout, stderr

    except FileNotFoundError:
        error_msg = f"Error running pytest: '{python_exe} -m pytest' command not found. Is pytest installed in the correct environment?"
        logging.error(error_msg)
        return False, "", error_msg
    except Exception as e:
        logging.error(f"run_pytest failed: {e}", exc_info=True)
        return False, "", f"Exception during pytest execution: {e}"
    # endregion RunPytest Description

# ================== Accessibility & Output ==================

def init_tts():
    # region InitTTS Description
    # INPUT: None
    # OUTPUT: (bool): True if TTS engine is initialized or already was, False on error.
    """Initialize Text-to-Speech engine if available and not already initialized."""
    global tts_engine
    if TTS_AVAILABLE and tts_engine is None:
        try:
            tts_engine = pyttsx3.init()
            logging.info("TTS engine initialized successfully.")
            return True
        except Exception as e:
            logging.error(f"TTS engine initialization failed: {e}")
            return False
    elif tts_engine is not None:
        return True
    return False
    # endregion InitTTS Description

def speak_and_print(message: str, config: dict, line_num: Optional[int] = None):
    # region SpeakAndPrint Description
    # INPUT: message (str): The message to log and potentially speak.
    # INPUT: config (dict): Configuration dictionary to check ENABLE_TTS flag.
    # INPUT: line_num (Optional[int]): Optional line number prefix for logging.
    # OUTPUT: None.
    """Output message via console log and optionally TTS based on config."""
    prefix = f"{line_num}. ---> " if line_num is not None else "---> "
    log_message = prefix + message
    logging.info(log_message)

    # TTS execution logic
    if config.get("ENABLE_TTS", False):
        if init_tts() and tts_engine:
            try:
                # Ensure any previous speech is stopped
                tts_engine.stop()
                tts_engine.say(message)
                tts_engine.runAndWait()
            except RuntimeError as e:
                # Handle specific error if the engine is busy
                if "run loop already started" in str(e).lower():
                    logging.warning("TTS run loop already busy, skipping utterance.")
                else:
                    logging.warning(f"TTS runtime error: {e}")
            except Exception as e:
                logging.warning(f"TTS failed during say/runAndWait: {e}")
        else:
            logging.debug("TTS is disabled or failed to initialize.")
    # endregion SpeakAndPrint Description

# --- Project Map Generation ---

# Directories/files to ignore during scanning
IGNORE_PATTERNS = [
    ".venv", ".git", ".vscode", ".cursor", "__pycache__", 
    "logs", "htmlcov", "backups", "tasks_done", "rejected_tasks",
    ".pytest_cache", ".ruff_cache", ".coverage", ".last_audit.json",
    "*.log", "*.pyc", "*.pyo", "*.swp", "*.bak", "*.tmp",
    "node_modules", "*.msi"
]

def should_ignore(path: Path, root: Path, ignore_patterns: list) -> bool:
    # region ShouldIgnore Description
    # INPUT: path (Path): The Path object of the file/directory to check.
    # INPUT: root (Path): The root Path object of the scan.
    # INPUT: ignore_patterns (list): List of patterns (strings) to ignore.
    # OUTPUT: (bool): True if the path should be ignored, False otherwise.
    """Check if a path should be ignored based on patterns."""
    relative_path_parts = path.relative_to(root).parts
    for pattern in ignore_patterns:
        # Check direct name match
        if path.name == pattern:
            return True
        # Check if any part of the relative path matches
        if pattern in relative_path_parts:
             return True
        # Check glob patterns (simple ones for now)
        if pattern.startswith('*.') and path.name.endswith(pattern[1:]):
            return True
    return False
    # endregion ShouldIgnore Description

def find_related_task_ids(file_path: str, tasks: list) -> list:
    # region FindRelatedTaskIds Description
    # INPUT: file_path (str): The normalized file path string (using '/').
    # INPUT: tasks (list): The list of loaded task dictionaries.
    # OUTPUT: (list): A list of task IDs (or task descriptions if ID missing) related to the file path.
    """Attempt to find task IDs related to a file path."""
    related_ids = []
    normalized_path = file_path.replace('\\', '/') # Normalize path separators
    for task in tasks:
        desc = task.get("description", task.get("task", ""))
        task_id = task.get("id", task.get("task")) # Use task desc as ID if no id
        # Simple check: does the normalized path appear in the description?
        if normalized_path in desc.replace('\\', '/'):
            related_ids.append(str(task_id))
    return related_ids
    # endregion FindRelatedTaskIds Description

def scan_project_and_generate_map(root_dir: str, task_file_path: str) -> list:
    # region ScanProjectAndGenerateMap Description
    # INPUT: root_dir (str): The root directory path of the project to scan.
    # INPUT: task_file_path (str): Path to the JSON task file for linking.
    # OUTPUT: (list): A list representing the scanned project structure (nested).
    """Scans the project directory and generates a nested file map."""
    root_path = Path(root_dir).resolve()
    project_map = []
    tasks = []
    try:
        with open(task_file_path, 'r', encoding='utf-8') as f:
            tasks = json.load(f)
    except FileNotFoundError:
        logging.warning(f"Task file not found at {task_file_path}, cannot link tasks.")
    except json.JSONDecodeError:
        logging.error(f"Error decoding JSON from task file {task_file_path}.")

    for item in root_path.iterdir():
        if should_ignore(item, root_path, IGNORE_PATTERNS):
            continue

        rel_path_str = str(item.relative_to(root_path).as_posix())
        entry = {
            "path": rel_path_str,
            "type": "directory" if item.is_dir() else "file",
            "last_modified": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(item.stat().st_mtime)),
            "status": "unknown", # Initial status
            "related_task_ids": find_related_task_ids(rel_path_str, tasks)
        }

        if item.is_dir():
            entry["children"] = _scan_directory_recursive(item, root_path, tasks)
        
        project_map.append(entry)
        
    # Sort root level for consistency
    project_map.sort(key=lambda x: (x['type'], x['path']))
    return project_map
    # endregion ScanProjectAndGenerateMap Description

def _scan_directory_recursive(dir_path: Path, root_path: Path, tasks: list) -> list:
    # region ScanDirectoryRecursive Description
    # INPUT: dir_path (Path): The Path object of the directory to scan.
    # INPUT: root_path (Path): The root Path object of the overall project scan.
    # INPUT: tasks (list): The list of loaded task dictionaries for linking.
    # OUTPUT: (list): A list of entries for files/subdirectories within dir_path.
    """Recursively scans a directory."""
    children = []
    try:
        for item in dir_path.iterdir():
            if should_ignore(item, root_path, IGNORE_PATTERNS):
                continue
            
            rel_path_str = str(item.relative_to(root_path).as_posix())
            entry = {
                "path": rel_path_str,
                "type": "directory" if item.is_dir() else "file",
                "last_modified": time.strftime('%Y-%m-%dT%H:%M:%SZ', time.gmtime(item.stat().st_mtime)),
                "status": "unknown",
                "related_task_ids": find_related_task_ids(rel_path_str, tasks)
            }

            if item.is_dir():
                entry["children"] = _scan_directory_recursive(item, root_path, tasks)
            
            children.append(entry)
    except OSError as e:
        logging.error(f"Error scanning directory {dir_path}: {e}")
        
    # Sort children for consistency
    children.sort(key=lambda x: (x['type'], x['path']))
    return children
    # endregion ScanDirectoryRecursive Description

# Example Usage (can be removed later)
# if __name__ == '__main__':
#     example_config = {
#         "LOG_FILE": "test_log.log",
#         "LOG_LEVEL": "DEBUG"
#     }
#     setup_logging(example_config)
#     logging.debug("This is a debug message.")
#     logging.info("This is an info message.")
#     logging.warning("This is a warning message.")
#     logging.error("This is an error message.") 