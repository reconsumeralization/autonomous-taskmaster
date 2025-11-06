import os
import logging
from typing import List, Dict, Optional, Tuple
from .utils import (
    load_json_file, save_json_file, move_file, load_yaml_from_string, run_pytest, speak_and_print
)

# ================== Task File Management ==================

def load_tasks(config: dict) -> List[Dict]:
    """Load and validate task list using utils.load_json_file."""
    todo_path = config.get("TODO_PATH", "taskmaster_todos.json")
    logging.info(f"Loading tasks via utils from {todo_path}")

    default_task_list = [{"task": "Default task: Review setup", "status": "pending"}]
    # Use the utility function, provide default value
    data = load_json_file(todo_path, default_value=[]) # Return empty list on error/not found

    tasks = []
    if isinstance(data, list):
        task_list_source = data
    # Handle legacy format where tasks might be under a 'todos' key
    elif isinstance(data, dict) and "todos" in data and isinstance(data["todos"], list):
        logging.warning("Loading tasks from legacy 'todos' key in JSON.")
        task_list_source = data["todos"]
    else:
        task_list_source = None
        logging.error(f"Loaded data from {todo_path} is not a list or expected dict format.")

    if task_list_source is not None:
        for item in task_list_source:
            if isinstance(item, str):
                tasks.append({"task": item, "status": "pending"})
            elif isinstance(item, dict) and "task" in item:
                tasks.append({
                    "task": str(item["task"]),
                    "status": item.get("status", "pending")
                })
            # Ignore malformed items

    # If loading failed or file contained no valid tasks, return default
    if not tasks:
        logging.warning(f"No valid tasks loaded from {todo_path}, returning default task list.")
        return default_task_list

    logging.info(f"Loaded {len(tasks)} tasks successfully from {todo_path}.")
    return tasks

def save_tasks(tasks: List[Dict], config: dict):
    """Persist task list using utils.save_json_file."""
    dry_run = config.get("DRY_RUN", False)
    todo_path = config.get("TODO_PATH", "taskmaster_todos.json")
    # No need for os.path.abspath here, save_json_file handles it

    if dry_run:
        logging.info(f"[DRY RUN] Would save {len(tasks)} tasks to {todo_path}")
        return # Assuming save_tasks doesn't need to return status

    logging.info(f"Saving {len(tasks)} tasks via utils to {todo_path}")
    success = save_json_file(tasks, todo_path) 

    if success:
        logging.info(f"Saved tasks successfully to {todo_path}.")
    else:
        # Error is already logged by save_json_file
        logging.error(f"Failed to save tasks to {todo_path} (see previous errors).")
        # Potentially raise an exception or handle failure more explicitly if needed

# ================== Code Task (.md) Management ==================

def parse_task_header(task_content: str) -> Tuple[Dict, str]:
    """Parse YAML header from task description using utils.load_yaml_from_string."""
    logging.info("[parse_task_header] Attempting to parse header...")
    parts = task_content.split("---", 2)
    logging.info(f"[parse_task_header] Split parts count: {len(parts)}")
    header = {}
    description = task_content

    if len(parts) >= 3 and parts[0].strip() == '':
        header_text = parts[1].strip()
        logging.info(f"[parse_task_header] Extracted header text (len {len(header_text)}). Preview:\n---\n{header_text[:100]}...\n---")
        description = parts[2].strip()
        
        # Use the utility function to parse YAML
        parsed_yaml = load_yaml_from_string(header_text, default_value=None)
        
        if isinstance(parsed_yaml, dict):
            header = parsed_yaml
            logging.info(f"[parse_task_header] Successfully parsed YAML keys: {list(header.keys())}")
        elif parsed_yaml is not None: # Loading succeeded but wasn't a dict
            logging.warning("[parse_task_header] Parsed YAML header is not a dictionary. Ignoring header.")
        # If parsed_yaml is None, load_yaml_from_string already logged the error

    else:
        logging.warning("[parse_task_header] No valid YAML header structure found.")

    logging.info(f"[parse_task_header] Returning header (keys: {list(header.keys())}) and description (len: {len(description)}).")
    return header, description

def mark_task_done(task_path: str, config: dict):
    """Move completed task file using utils.move_file."""
    dry_run = config.get("DRY_RUN", False)
    done_dir = config.get("DONE_DIR", "tasks_done")
    # No need for abspath, move_file handles it
    task_filename = os.path.basename(task_path)
    # Construct destination path (could be dir or specific file)
    # For consistency, let's assume destination is the directory
    destination_dir_path = done_dir 
    # Let move_file handle joining directory and filename if dest is a dir
    # OR specify the full destination file path explicitly:
    # destination_file_path = os.path.join(done_dir, task_filename)

    if dry_run:
        # Construct the destination path for logging even in dry run
        full_dest_path_for_log = os.path.abspath(os.path.join(destination_dir_path, task_filename))
        logging.info(f"[DRY RUN] Would move {task_path} to {full_dest_path_for_log}")
        return True

    logging.info(f"Moving task {task_filename} via utils to directory {destination_dir_path}")
    # Call move_file - it handles directory creation and logging
    success = move_file(task_path, destination_dir_path) 

    if success:
        logging.info(f"Moved task {task_filename} successfully.")
    else:
        # Error is logged by move_file
        logging.error(f"Failed to move task {task_filename} (see previous errors).")
        
    return success # Return the success status from the utility function

# ================== Accessibility & Output ==================
# Functions init_tts, speak_and_print moved to utils.py

# ================== AI Code Generation ==================
# Functions moved to ai_providers.py

# ================== Test Execution ==================
# Function run_pytest moved to utils.py

# ================== UI Automation ==================
# Functions moved to ui_automation.py

# ================== Core Task Processing Logic ==================

class ProcessingResult:
    """Represents the outcome of process_code_task."""
    def __init__(self, status: str, message: str, context: Optional[Dict] = None):
        self.status = status
        self.message = message
        self.context = context

def process_code_task(task_path: str, config: dict) -> ProcessingResult:
    """
    Process a single code task (.md file), running tests and potentially signaling for code generation.
    Returns a ProcessingResult object indicating the outcome.
    """
    logging.info(f"[process_code_task START] Processing: {task_path}")
    speak_and_print(f"Starting code task: {os.path.basename(task_path)}", config)

    try:
        logging.info("[process_code_task] Reading task file...")
        with open(task_path, "r", encoding='utf-8') as f:
            task_content = f.read()

        logging.info("[process_code_task] Parsing task header...")
        header, task_description = parse_task_header(task_content)
        test_file_rel = header.get("Test File")
        impl_file_rel = header.get("Implementation File")

        logging.info(f"[process_code_task] Task Header: {header}")
        logging.debug(f"[process_code_task] Task Description (start): {task_description[:200]}...")

        if not (test_file_rel and impl_file_rel):
            msg = "Task does not specify 'Test File' and 'Implementation File' in YAML header. Cannot process."
            logging.warning(f"[process_code_task] {msg}")
            speak_and_print("Task missing required header fields. Manual review needed.", config)
            logging.info("[process_code_task END] Error: Missing header fields.")
            return ProcessingResult("error", msg)

        logging.info("[process_code_task] Resolving absolute file paths...")
        test_file_abs = os.path.abspath(test_file_rel)
        impl_file_abs = os.path.abspath(impl_file_rel)
        logging.info(f"[process_code_task] Absolute Test File Path: {test_file_abs}")
        logging.info(f"[process_code_task] Absolute Implementation File Path: {impl_file_abs}")

        logging.info("[process_code_task] Ensuring directories exist...")
        os.makedirs(os.path.dirname(impl_file_abs), exist_ok=True)
        os.makedirs(os.path.dirname(test_file_abs), exist_ok=True)

        logging.info("[process_code_task] Checking/creating implementation file...")
        if not os.path.exists(impl_file_abs):
            try:
                with open(impl_file_abs, "w", encoding='utf-8') as impf:
                    impf.write("# Placeholder for implementation\npass\n")
                logging.info(f"[process_code_task] Created placeholder implementation file: {impl_file_abs}")
            except Exception as e:
                logging.error(f"[process_code_task] Failed to create placeholder implementation file {impl_file_abs}: {e}")
                logging.info("[process_code_task END] Error: Cannot create placeholder implementation.")
                return ProcessingResult("error", f"Failed to create placeholder implementation file: {e}")

        logging.info("[process_code_task] Checking test file...")
        if not os.path.exists(test_file_abs):
            msg = f"Test file {test_file_abs} not found. Test generation step might have failed or was skipped."
            logging.error(f"[process_code_task] {msg}")
            speak_and_print("Test file not found, cannot proceed with TDD cycle.", config)
            logging.info("[process_code_task END] Error: Test file not found.")
            return ProcessingResult("error", msg)

        logging.info("[process_code_task] Entering test loop...")
        max_retries = config.get("TEST_MAX_RETRIES", 1)
        tests_passed = False
        last_stdout = ""
        last_stderr = ""

        for attempt in range(max_retries):
            logging.info(f"[process_code_task] Running pytest (Attempt {attempt + 1}/{max_retries})...")
            test_passed, stdout, stderr = run_pytest(config, [test_file_abs])
            last_stdout = stdout
            last_stderr = stderr

            if test_passed:
                logging.info("[process_code_task] Tests passed.")
                speak_and_print("Tests passed.", config)
                tests_passed = True
                break
            else:
                logging.info(f"[process_code_task] Tests failed (Attempt {attempt + 1}). Stdout: {stdout[:300]}... Stderr: {stderr[:300]}...")
                speak_and_print(f"Tests failed (Attempt {attempt + 1}). Implementation required.", config)
                break

        logging.info(f"[process_code_task] Exited test loop. Tests passed: {tests_passed}")

        if tests_passed:
            logging.info("[process_code_task] Marking task as done...")
            speak_and_print(f"Task {os.path.basename(task_path)} completed successfully.", config)
            move_successful = mark_task_done(task_path, config)
            if move_successful:
                logging.info("[process_code_task END] Success.")
                return ProcessingResult("success", f"Task {os.path.basename(task_path)} completed successfully.")
            else:
                # Handle failure to move the task file
                error_msg = f"Tests passed for {os.path.basename(task_path)}, but failed to move task file to done directory."
                logging.error(f"[process_code_task END] {error_msg}")
                return ProcessingResult("error", error_msg)
        else:
            logging.warning(f"[process_code_task] Tests failed for task {task_path}. Signaling for implementation generation.")
            context_for_agent = {
                "task_description": task_description,
                "implementation_file_path": impl_file_rel,
                "test_file_path": test_file_rel,
                "test_stdout": last_stdout,
                "test_stderr": last_stderr
            }
            logging.info("[process_code_task END] Action Required: Implementation needed.")
            return ProcessingResult(
                status="action_required",
                message=f"Tests failed for {os.path.basename(task_path)}. Implementation required in {impl_file_rel}.",
                context=context_for_agent
            )

    except FileNotFoundError:
        msg = f"Task file not found during processing: {task_path}"
        logging.error(f"[process_code_task] {msg}")
        speak_and_print(f"Error: Task file not found: {os.path.basename(task_path)}", config)
        logging.info("[process_code_task END] Error: Task file not found.")
        return ProcessingResult("error", msg)
    except Exception as e:
        msg = f"An unexpected error occurred processing task {task_path}: {e}"
        logging.error(f"[process_code_task] {msg}", exc_info=True)
        speak_and_print(f"Unexpected error processing task {os.path.basename(task_path)}: {e}", config)
        logging.info("[process_code_task END] Error: Unexpected exception.")
        return ProcessingResult("error", msg)