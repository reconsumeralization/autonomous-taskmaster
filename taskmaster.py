import os
import sys
import json
import logging
import subprocess
import threading
from pathlib import Path
from typing import List, Dict, Optional, Tuple, Any
from logging.handlers import RotatingFileHandler
import argparse
import shlex


def safe_import(module_name, alias=None):
    """Safely import a module, optionally assigning it an alias in globals."""
    try:
        module = __import__(module_name)
        if alias:
            globals()[alias] = module
        else:
            globals()[module_name] = module
        return True
    except ImportError:
        return False


TTS_AVAILABLE = safe_import("pyttsx3")
PYAUTOGUI_AVAILABLE = safe_import("pyautogui") and safe_import("pyperclip")
REQUESTS_AVAILABLE = safe_import("requests")

VERSION = "0.8.0-Robust"
CONFIG: Dict[str, Any] = {}
TTS_ENGINE = None
TERMINATE_EVENT = threading.Event()
IDLE_DD_DETECTED = threading.Event()
MODEL_COOLDOWNS = {}
ApiCallResult = Tuple[Optional[str], bool]


def _handle_idle_dd_signal(turn_count: int):
    logging.info(f"Idle DD signal received (Turn: {turn_count}). Setting event.")
    IDLE_DD_DETECTED.set()


class Task:
    def __init__(
        self,
        id: str,
        description: str,
        test_file: Optional[str] = None,
        implementation_file: Optional[str] = None,
        project_root: Optional[str] = None,
        source_file: Optional[str] = None,
        **kwargs,
    ):
        self.id = id
        self.description = description
        self.test_file = test_file
        self.implementation_file = implementation_file
        self.project_root = project_root
        self.source_file = source_file
        for k, v in kwargs.items():
            setattr(self, k, v)

    def __str__(self) -> str:
        return f"Task(id={self.id}, test={self.test_file}, impl={self.implementation_file})"

    def resolve_paths(self, default_project_root: Optional[str]) -> None:
        effective_root = self.project_root or default_project_root
        if effective_root:
            root_path = Path(effective_root)
            if self.test_file and not Path(self.test_file).is_absolute():
                self.test_file = str(root_path / self.test_file)
            if (
                self.implementation_file
                and not Path(self.implementation_file).is_absolute()
            ):
                self.implementation_file = str(root_path / self.implementation_file)
        self.test_file = str(self.test_file) if self.test_file else None
        self.implementation_file = (
            str(self.implementation_file) if self.implementation_file else None
        )
        logging.debug(
            f"Resolved paths for task {self.id}: Test='{self.test_file}', Impl='{self.implementation_file}', Root='{effective_root}'"
        )


class TaskResult:
    def __init__(
        self, task_id: str, status: str, message: str, context: Optional[Dict] = None
    ):
        self.task_id = task_id
        self.status = status
        self.message = message
        self.context = context if context else {}

    def __str__(self) -> str:
        return f"Result(id={self.task_id}, status={self.status}, msg='{self.message[:60]}...')"


def delegate_task_to_planner(task, config):
    logger = logging.getLogger("Taskmaster")
    python_exe = sys.executable
    try:
        script_dir = Path(__file__).parent
    except Exception as e:
        logger.error(f"Could not determine script directory: {e}")
        return TaskResult(
            getattr(task, "id", "unknown"),
            "error",
            f"Could not determine script directory: {e}",
            {"source_file": getattr(task, "source_file", None)},
        )
    screen_idle_dd_path = script_dir / "screen_idle_dd.py"
    if not screen_idle_dd_path.is_file():
        logger.error(f"screen_idle_dd.py not found at {screen_idle_dd_path}")
        return TaskResult(
            getattr(task, "id", "unknown"),
            "error",
            f"screen_idle_dd.py not found at {screen_idle_dd_path}",
            {"source_file": getattr(task, "source_file", None)},
        )

    task_details = {
        "id": getattr(task, "id", None),
        "description": getattr(task, "description", None),
        "test_file": getattr(task, "test_file", None),
        "implementation_file": getattr(task, "implementation_file", None),
        "project_root": getattr(task, "project_root", None),
        "source_file": getattr(task, "source_file", None),
    }
    for k in dir(task):
        if (
            not k.startswith("_")
            and k not in task_details
            and not callable(getattr(task, k, None))
        ):
            try:
                val = getattr(task, k)
                json.dumps(val)
                task_details[k] = val
            except Exception:
                continue

    try:
        task_json = json.dumps(task_details)
    except Exception as e:
        logger.error(f"Failed to serialize task details: {e}")
        return TaskResult(
            getattr(task, "id", "unknown"),
            "error",
            f"Failed to serialize task details: {e}",
            {"source_file": getattr(task, "source_file", None)},
        )

    cmd = [python_exe, str(screen_idle_dd_path), "--delegate-task", task_json]
    logger.info(
        f"Delegating task {getattr(task, 'id', 'unknown')} to LLM planner via screen_idle_dd.py"
    )
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=300,
        )
        logger.info(f"Delegation subprocess exited with code {result.returncode}")
        if result.stdout:
            logger.info(f"Delegation STDOUT: {result.stdout[:500]}")
        if result.stderr:
            logger.warning(f"Delegation STDERR: {result.stderr[:500]}")
        if result.returncode == 0:
            return TaskResult(
                getattr(task, "id", "unknown"),
                "delegated",
                f"Task delegated to LLM planner (screen_idle_dd.py).",
                {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "source_file": getattr(task, "source_file", None),
                },
            )
        else:
            return TaskResult(
                getattr(task, "id", "unknown"),
                "error",
                f"Delegation to LLM planner failed (exit code {result.returncode}).",
                {
                    "stdout": result.stdout,
                    "stderr": result.stderr,
                    "source_file": getattr(task, "source_file", None),
                },
            )
    except Exception as e:
        logger.error(
            f"Exception while delegating task to LLM planner: {e}", exc_info=True
        )
        return TaskResult(
            getattr(task, "id", "unknown"),
            "error",
            f"Exception during delegation to LLM planner: {e}",
            {"source_file": getattr(task, "source_file", None)},
        )


def process_task(task, config, main_logger, effective_project_root=None):
    """
    Process a task based on its type: TDD, implementation, test, command, or general AI.
    Handles working directory changes, error handling, and result reporting.
    """
    if not hasattr(task, "id"):
        main_logger.error("Task object missing 'id' attribute.")
        return TaskResult("unknown", "error", "Task object missing 'id' attribute.")

    if getattr(task, "delegate_to_llm", False):
        main_logger.info(f"Task {task.id} is marked for delegation to LLM planner.")
        return delegate_task_to_planner(task, config)

    original_cwd = os.getcwd()
    try:
        task_cwd = (
            Path(effective_project_root)
            if effective_project_root
            else Path(original_cwd)
        )
        logging.info(f"Effective project root for task {task.id}: {task_cwd.resolve()}")
    except Exception as e:
        main_logger.error(f"Error resolving project root: {e}")
        task_cwd = Path(original_cwd)

    has_test = bool(
        getattr(task, "test_file", None) and Path(getattr(task, "test_file", "")).suffix
    )
    has_impl = bool(
        getattr(task, "implementation_file", None)
        and Path(getattr(task, "implementation_file", "")).suffix
    )

    if has_test and has_impl:
        action_type = "tdd"
    elif has_impl and not has_test:
        action_type = "implement_only"
    elif has_test and not has_impl:
        action_type = "test_only"
    elif hasattr(task, "command") and getattr(task, "command", None):
        action_type = "command"
    else:
        action_type = "unknown"

    logging.info(f"Determined action type: {action_type}")
    print(f"[DEBUG] Task '{task.id}' classified as action_type: {action_type}")

    task_result = None

    try:
        # Change to project root if specified and valid
        if effective_project_root:
            project_path = Path(effective_project_root)
            if project_path.is_dir():
                try:
                    os.chdir(project_path)
                    logging.info(
                        f"Changed working directory to project root: {project_path.resolve()}"
                    )
                except Exception as cd_err:
                    logging.error(f"Error changing CWD to {project_path}: {cd_err}")
            else:
                logging.warning(
                    f"Project root '{effective_project_root}' not found. Staying in default directory."
                )

        if action_type == "tdd":
            if not getattr(task, "test_file", None) or not getattr(
                task, "implementation_file", None
            ):
                task_result = TaskResult(
                    task.id,
                    "error",
                    f"TDD task missing required file path(s). Test: '{getattr(task, 'test_file', None)}', Impl: '{getattr(task, 'implementation_file', None)}'",
                )
            else:
                try:
                    test_success, test_stdout, test_stderr = run_pytest(
                        task.test_file, project_root=getattr(task, "project_root", None)
                    )
                except Exception as e:
                    main_logger.error(f"Exception running pytest: {e}", exc_info=True)
                    test_success, test_stdout, test_stderr = False, "", str(e)
                if test_success:
                    msg = f"Test(s) already passing for {task.test_file}. No implementation needed."
                    main_logger.info(msg)
                    task_result = TaskResult(
                        task.id, "success", msg, {"test_stdout": test_stdout}
                    )
                else:
                    main_logger.info(
                        f"Test(s) failed for {task.test_file}. Attempting to implement {task.implementation_file} using AI."
                    )
                    try:
                        prompt = (
                            f"Given the following test file:\n\n"
                            f"{read_file(task.test_file)}\n\n"
                            f"Write the implementation for the file '{task.implementation_file}' so that the tests pass."
                        )
                    except Exception as e:
                        main_logger.error(f"Error reading test file: {e}")
                        prompt = f"Write the implementation for the file '{task.implementation_file}' so that the tests pass."
                    ai_code = None
                    try:
                        ai_code = interact_with_ai(prompt, task, config)
                    except Exception as e:
                        main_logger.error(f"AI interaction failed: {e}", exc_info=True)
                    if ai_code:
                        try:
                            code = extract_code(ai_code, language="python")
                        except Exception as e:
                            main_logger.error(f"Error extracting code: {e}")
                            code = None
                        if code:
                            try:
                                write_ok = write_file(
                                    task.implementation_file, code, config
                                )
                            except Exception as e:
                                main_logger.error(
                                    f"Error writing implementation file: {e}"
                                )
                                write_ok = False
                            if write_ok:
                                try:
                                    retry_success, retry_stdout, retry_stderr = (
                                        run_pytest(
                                            task.test_file,
                                            project_root=getattr(
                                                task, "project_root", None
                                            ),
                                        )
                                    )
                                except Exception as e:
                                    main_logger.error(
                                        f"Exception running pytest after implementation: {e}",
                                        exc_info=True,
                                    )
                                    retry_success, retry_stdout, retry_stderr = (
                                        False,
                                        "",
                                        str(e),
                                    )
                                if retry_success:
                                    msg = f"Test(s) passed after implementing {task.implementation_file}."
                                    main_logger.info(msg)
                                    task_result = TaskResult(
                                        task.id,
                                        "success",
                                        msg,
                                        {
                                            "test_stdout": retry_stdout,
                                            "ai_raw_output": ai_code,
                                        },
                                    )
                                else:
                                    msg = f"Test(s) still failing after implementation. Manual intervention required."
                                    main_logger.warning(msg)
                                    task_result = TaskResult(
                                        task.id,
                                        "test_failed",
                                        msg,
                                        {
                                            "initial_test_stderr": test_stderr,
                                            "retry_test_stderr": retry_stderr,
                                            "ai_raw_output": ai_code,
                                        },
                                    )
                            else:
                                msg = f"Failed to write implementation file '{task.implementation_file}'."
                                main_logger.error(msg)
                                task_result = TaskResult(task.id, "error", msg)
                        else:
                            msg = f"AI did not return valid code for implementation."
                            main_logger.error(msg)
                            task_result = TaskResult(
                                task.id, "error", msg, {"ai_raw_output": ai_code}
                            )
                    else:
                        msg = f"AI did not return any response for implementation."
                        main_logger.error(msg)
                        task_result = TaskResult(task.id, "error", msg)
        elif action_type == "implement_only":
            main_logger.info(
                f"Implementing only: {getattr(task, 'implementation_file', None)} (no test file provided)."
            )
            prompt = (
                f"Write the implementation for the file '{getattr(task, 'implementation_file', None)}'.\n"
                f"Task description: {getattr(task, 'description', '')}"
            )
            ai_code = None
            try:
                ai_code = interact_with_ai(prompt, task, config)
            except Exception as e:
                main_logger.error(f"AI interaction failed: {e}", exc_info=True)
            if ai_code:
                try:
                    code = extract_code(ai_code, language="python")
                except Exception as e:
                    main_logger.error(f"Error extracting code: {e}")
                    code = None
                if code:
                    try:
                        write_ok = write_file(
                            getattr(task, "implementation_file", None), code, config
                        )
                    except Exception as e:
                        main_logger.error(f"Error writing implementation file: {e}")
                        write_ok = False
                    if write_ok:
                        msg = f"Implementation file '{getattr(task, 'implementation_file', None)}' written successfully."
                        main_logger.info(msg)
                        task_result = TaskResult(
                            task.id, "success", msg, {"ai_raw_output": ai_code}
                        )
                    else:
                        msg = f"Failed to write implementation file '{getattr(task, 'implementation_file', None)}'."
                        main_logger.error(msg)
                        task_result = TaskResult(task.id, "error", msg)
                else:
                    msg = f"AI did not return valid code for implementation."
                    main_logger.error(msg)
                    task_result = TaskResult(
                        task.id, "error", msg, {"ai_raw_output": ai_code}
                    )
            else:
                msg = f"AI did not return any response for implementation."
                main_logger.error(msg)
                task_result = TaskResult(task.id, "error", msg)
        elif action_type == "test_only":
            main_logger.info(
                f"Running test only: {getattr(task, 'test_file', None)} (no implementation file provided)."
            )
            try:
                test_success, test_stdout, test_stderr = run_pytest(
                    getattr(task, "test_file", None),
                    project_root=getattr(task, "project_root", None),
                )
            except Exception as e:
                main_logger.error(f"Exception running pytest: {e}", exc_info=True)
                test_success, test_stdout, test_stderr = False, "", str(e)
            if test_success:
                msg = f"Test(s) passed for {getattr(task, 'test_file', None)}."
                main_logger.info(msg)
                task_result = TaskResult(
                    task.id, "success", msg, {"test_stdout": test_stdout}
                )
            else:
                msg = f"Test(s) failed for {getattr(task, 'test_file', None)}."
                main_logger.warning(msg)
                task_result = TaskResult(
                    task.id, "test_failed", msg, {"test_stderr": test_stderr}
                )
        elif action_type == "command":
            if not hasattr(task, "command") or not getattr(task, "command", None):
                task_result = TaskResult(
                    task.id,
                    "error",
                    "Command action type specified, but 'command' field is missing or empty in task definition.",
                )
            else:
                cmd_str = getattr(task, "command", "")
                cmd_cwd = getattr(task, "working_directory", None)
                is_background = getattr(task, "is_background", False)
                resolved_cwd = original_cwd
                if cmd_cwd:
                    try:
                        if not Path(cmd_cwd).is_absolute():
                            resolved_cwd = str(Path(original_cwd) / cmd_cwd)
                            if not Path(resolved_cwd).is_dir():
                                main_logger.warning(
                                    f"Specified working directory '{cmd_cwd}' (resolved to '{resolved_cwd}') does not exist for command task {task.id}. Using default CWD."
                                )
                                resolved_cwd = original_cwd
                        else:
                            resolved_cwd = cmd_cwd
                    except Exception as e:
                        main_logger.error(
                            f"Error resolving command working directory: {e}"
                        )
                        resolved_cwd = original_cwd
                main_logger.info(
                    f"Executing command: '{cmd_str}' in CWD: '{resolved_cwd}' (Background: {is_background})"
                )
                try:
                    speak_and_print(f"Executing command: {cmd_str}", config)
                except Exception as e:
                    main_logger.warning(f"speak_and_print failed: {e}")
                if config.get("DRY_RUN", False):
                    main_logger.info(
                        f"[DRY RUN] Would execute command '{cmd_str}' in '{resolved_cwd}'"
                    )
                    task_result = TaskResult(
                        task.id, "success", "[DRY RUN] Command task simulated."
                    )
                else:
                    try:
                        if is_background:
                            proc = subprocess.Popen(
                                cmd_str,
                                cwd=resolved_cwd,
                                shell=True,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                encoding="utf-8",
                                errors="replace",
                            )
                            main_logger.info(
                                f"Started background process PID: {proc.pid}"
                            )
                            task_result = TaskResult(
                                task.id,
                                "success",
                                f"Command started in background (PID: {proc.pid}).",
                                {"stdout": "", "stderr": ""},
                            )
                        else:
                            completed_process = subprocess.run(
                                cmd_str,
                                cwd=resolved_cwd,
                                shell=True,
                                capture_output=True,
                                text=True,
                                check=False,
                                encoding="utf-8",
                                errors="replace",
                            )
                            stdout = (
                                completed_process.stdout.strip()
                                if completed_process.stdout
                                else ""
                            )
                            stderr = (
                                completed_process.stderr.strip()
                                if completed_process.stderr
                                else ""
                            )
                            exit_code = completed_process.returncode
                            if exit_code == 0:
                                main_logger.info(
                                    f"Command '{cmd_str}' completed successfully (Exit Code: 0)."
                                )
                                if stdout:
                                    main_logger.debug(f"  STDOUT: {stdout}")
                                if stderr:
                                    main_logger.debug(f"  STDERR: {stderr}")
                                task_result = TaskResult(
                                    task.id,
                                    "success",
                                    f"Command executed successfully.",
                                    {
                                        "exit_code": exit_code,
                                        "stdout": stdout,
                                        "stderr": stderr,
                                    },
                                )
                            else:
                                main_logger.error(
                                    f"Command '{cmd_str}' failed (Exit Code: {exit_code})."
                                )
                                main_logger.error(f"  STDOUT: {stdout}")
                                main_logger.error(f"  STDERR: {stderr}")
                                task_result = TaskResult(
                                    task.id,
                                    "error",
                                    f"Command failed with exit code {exit_code}.",
                                    {
                                        "exit_code": exit_code,
                                        "stdout": stdout,
                                        "stderr": stderr,
                                    },
                                )
                    except FileNotFoundError:
                        err_msg = f"Command execution failed: Command or shell not found while trying to run '{cmd_str}'. Check PATH."
                        main_logger.error(err_msg)
                        task_result = TaskResult(task.id, "error", err_msg)
                    except Exception as cmd_exec_err:
                        err_msg = f"Error executing command '{cmd_str}': {cmd_exec_err}"
                        main_logger.error(err_msg, exc_info=True)
                        task_result = TaskResult(task.id, "error", err_msg)
        else:
            main_logger.warning(
                f"Unhandled action type '{action_type}' for task {task.id}. Treating as general AI task."
            )
            ai_prompt = (
                f"Perform the following task: {getattr(task, 'description', '')}"
            )
            ai_response = None
            try:
                ai_response = interact_with_ai(ai_prompt, task, config)
            except Exception as e:
                main_logger.error(f"AI interaction failed: {e}", exc_info=True)
            if ai_response:
                task_result = TaskResult(
                    task.id,
                    "placeholder_success",
                    f"General AI task completed.",
                    {"ai_response": ai_response},
                )
            else:
                task_result = TaskResult(
                    task.id,
                    "error",
                    f"General AI task failed to get response for action type '{action_type}'.",
                )

    except Exception as outer_e:
        error_msg = f"Outer exception during task processing: {outer_e}"
        main_logger.error(error_msg, exc_info=True)
        task_result = TaskResult(getattr(task, "id", "unknown"), "error", error_msg)

    finally:
        try:
            if os.getcwd() != original_cwd:
                try:
                    os.chdir(original_cwd)
                    logging.debug(f"Restored working directory to: {original_cwd}")
                except Exception as restore_err:
                    logging.error(f"Failed to restore working directory: {restore_err}")
        except Exception as e:
            logging.error(f"Error checking or restoring working directory: {e}")

        if task_result is None:
            task_result = TaskResult(
                getattr(task, "id", "unknown"),
                "error",
                "Task processing completed without setting a result status (internal error).",
            )
            logging.error(
                f"No TaskResult was set during process_task execution for task {getattr(task, 'id', 'unknown')}."
            )
        return task_result
