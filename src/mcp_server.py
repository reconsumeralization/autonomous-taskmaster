import logging
import yaml
import os
import sys
from typing import List, Dict, Optional, Tuple, Any
import argparse
import datetime
import json
import subprocess
import asyncio
import uvicorn
# from slugify import slugify  # Removed due to missing module
import re
import textwrap  # For formatting md content
from pathlib import Path

# Moved debug prints
print("[DEBUG] Imported logging")
print("[DEBUG] Imported yaml")
print("[DEBUG] Imported os")
print("[DEBUG] Imported sys")
print("[DEBUG] Imported typing")
print("[DEBUG] Imported argparse")
print("[DEBUG] Imported datetime")
print("[DEBUG] Imported json")
print("[DEBUG] Imported subprocess")
print("[DEBUG] Imported asyncio")
print("[DEBUG] Imported uvicorn")
# print("[DEBUG] Imported slugify")  # Removed due to missing module
print("[DEBUG] Imported re")
print("[DEBUG] Imported textwrap")
print("[DEBUG] Imported Path")

# Ensure src directory is in path for relative imports
# This might be needed if running the script directly, though MCP execution context might handle it.
script_dir = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(script_dir))
print(f"[DEBUG] Updated sys.path: {sys.path[0]}")

try:
    from mcp.server.fastmcp.server import FastMCP
    # from mcp.server.models.command_message import CommandMessage, CommandType  # Not used in this file, removed to avoid missing import error
    from src.utils import setup_logging, load_yaml_from_string, load_json_file, save_json_file, move_file, run_pytest, speak_and_print, get_next_task
    # Import specific functions needed for tools, or use core_logic.*
    from src.core_logic import (
        load_tasks, save_tasks, get_next_task, process_code_task, 
        capture_coordinates, send_chat_message, get_ai_response,
        speak_and_print # Assuming speak_and_print might be used directly by some tools
    )
    print("[DEBUG] Imported MCP/FastMCP modules and local utils/ai_providers")
except ImportError as e:
    print(f"[ERROR] Failed to import necessary modules: {e}. Ensure MCP SDK and dependencies are installed.")
    sys.exit(1)
except Exception as e:
    print(f"[ERROR] An unexpected error occurred during imports: {e}")
    sys.exit(1)

# ================== Configuration & Setup ==================
CONFIG_PATH = 'config.yaml'
config: Dict[str, Any] = {}

def load_config():
    """Load configuration from YAML file."""
    global config
    try:
        # Assume config.yaml is in the parent directory relative to src/
        config_file_path = os.path.join(os.path.dirname(script_dir), CONFIG_PATH)
        with open(config_file_path, 'r', encoding='utf-8') as f:
            config = yaml.safe_load(f)
        if not config:
            config = {}
            logging.warning(f"Config file {config_file_path} is empty.")
        logging.info(f"Configuration loaded successfully from {config_file_path}.")
    except FileNotFoundError:
        logging.error(f"Configuration file not found at {config_file_path}. Using default settings.")
        config = {} # Ensure config is an empty dict if file not found
    except yaml.YAMLError as e:
        logging.error(f"Error parsing configuration file {config_file_path}: {e}. Using default settings.")
        config = {}
    except Exception as e:
        logging.error(f"Unexpected error loading configuration: {e}", exc_info=True)
        config = {}

# Load configuration immediately
load_config()

# Initialize Logging (using setup_logging from utils)
# Pass the loaded config dictionary
try:
    setup_logging(config)
except Exception as e:
    # Fallback basic logging if setup fails
    logging.basicConfig(level=logging.WARNING, format='%(asctime)s - %(levelname)s - %(message)s')
    logging.error(f"Failed to initialize logging using setup_logging: {e}")

# Initialize TTS engine if enabled in config (optional, can be done in speak_and_print)
# if config.get("ENABLE_TTS", False):
#     from src.core_logic import init_tts
#     init_tts() 


# ================== MCP Server Definition ==================

logging.info("Initializing MCPServer...")
server = FastMCP(
    name="autotyper-taskmaster-mcp",
    description="Manages tasks, runs code generation/tests, and automates chat via Auto Typer logic.",
    version="0.2.0",
    # auth_middleware=auth_middleware # Temporarily disabled
)
print("[DEBUG] FastMCP server object created.")

# ================== Tool Definitions ==================

@server.tool(
    name="list_tasks", 
    description="Lists all tasks from the JSON task file, optionally filtering by status.",
    params=[
        {"name": "status_filter", "description": "Optional: Filter tasks by status (e.g., 'pending', 'completed', 'needs_breakdown').", "required": False, "type": "string"}
    ]
)
def list_tasks_tool(status_filter: Optional[str] = None) -> Dict[str, Any]:
    """MCP Tool to list tasks, optionally filtering by status."""
    logging.info(f"Tool 'list_tasks' called. Filter: {status_filter}")
    try:
        tasks = load_tasks(config) # config should be globally accessible here
        if status_filter:
            filtered_tasks = [t for t in tasks if t.get('status') == status_filter]
            logging.info(f"Found {len(filtered_tasks)} tasks matching filter '{status_filter}'.")
            return {"status": "success", "tasks": filtered_tasks}
        else:
            logging.info(f"Found {len(tasks)} total tasks.")
            return {"status": "success", "tasks": tasks}
    except Exception as e:
        logging.error(f"Error in list_tasks_tool: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to list tasks: {e}"}

@server.tool(
    name="add_task", 
    description="Adds a new task to the JSON task file with 'pending' status.",
    params=[
        {"name": "task_description", "description": "The description of the task to add.", "required": True, "type": "string"}
    ]
)
def add_task_tool(task_description: str) -> Dict[str, Any]:
    """MCP Tool to add a new task."""
    logging.info(f"Tool 'add_task' called. Task: {task_description}")
    if not task_description:
        logging.warning("Add task tool called with empty description.")
        return {"status": "error", "message": "Task description cannot be empty."}
    try:
        tasks = load_tasks(config)
        new_task = {"task": task_description, "status": "pending"}
        tasks.append(new_task)
        save_tasks(tasks, config) # save_tasks handles dry_run internally
        msg = f"Task '{task_description}' added successfully."
        logging.info(msg)
        # Use speak_and_print for user feedback if TTS enabled
        speak_and_print(f"Task added: {task_description}", config)
        return {"status": "success", "message": msg, "added_task": new_task}
    except Exception as e:
        logging.error(f"Error in add_task_tool: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to add task: {e}"}

@server.tool(
    name="get_next_code_task_path", 
    description="Gets the absolute file path of the next pending .md code task based on alphabetical order in the configured tasks directory."
    # No parameters needed for this one
)
def get_next_code_task_path_tool() -> Dict[str, Any]:
    """MCP Tool to get the path of the next .md code task."""
    logging.info("Tool 'get_next_code_task_path' called.")
    try:
        next_task_path = get_next_task(config)
        if next_task_path:
            logging.info(f"Next code task found: {next_task_path}")
            return {"status": "success", "task_path": next_task_path}
        else:
            logging.info("No pending code tasks found.")
            return {"status": "success", "task_path": None, "message": "No pending .md code tasks found."}
    except Exception as e:
        logging.error(f"Error in get_next_code_task_path_tool: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to get next code task path: {e}"}

@server.tool(
    name="process_code_task_by_path", 
    description="Processes a specific .md code task file: reads it, generates code via AI if tests fail, runs tests, and marks done if successful.",
    params=[
        {"name": "task_path", "description": "The absolute path to the .md task file to process.", "required": True, "type": "string"}
    ]
)
def process_code_task_by_path_tool(task_path: str) -> Dict[str, Any]:
    """MCP Tool to process a specific .md code task."""
    logging.info(f"Tool 'process_code_task_by_path' called for path: {task_path}")
    if not task_path or not os.path.isabs(task_path) or not os.path.exists(task_path):
        msg = f"Invalid or non-existent task path provided: {task_path}"
        logging.error(msg)
        return {"status": "error", "message": msg}
        
    # Check if API keys are available before starting potentially long process
    api_key_env = config.get("GROK_API_KEY_ENV", "XAI_API_KEY")
    api_url_env = config.get("GROK_API_URL_ENV", "XAI_API_URL")
    if not os.environ.get(api_key_env) or not os.environ.get(api_url_env):
        msg = f"Cannot process code task: API Key/URL environment variables ('{api_key_env}', '{api_url_env}') not set."
        logging.error(msg)
        # Also provide feedback to user via speak_and_print
        speak_and_print(f"Error: {msg}", config)
        return {"status": "error", "message": msg}

    try:
        # process_code_task returns True if task completed successfully and was marked done
        success = process_code_task(task_path, config)
        if success:
            msg = f"Successfully processed code task: {os.path.basename(task_path)}"
            logging.info(msg)
            return {"status": "success", "message": msg}
        else:
            msg = f"Processing failed or tests did not pass for code task: {os.path.basename(task_path)}. Manual review may be required."
            logging.warning(msg)
            # Return success=True from tool perspective (it ran) but indicate failure in message
            return {"status": "success", "task_completed": False, "message": msg} 
            
    except Exception as e:
        logging.error(f"Error in process_code_task_by_path_tool for {task_path}: {e}", exc_info=True)
        # Provide feedback via speak_and_print as well
        speak_and_print(f"Critical error processing task {os.path.basename(task_path)}: {e}", config)
        return {"status": "error", "message": f"Failed to process code task {os.path.basename(task_path)}: {e}"}

@server.tool(
    name="capture_coordinates",
    description="Guides the user to position the mouse and captures coordinates after a countdown. Updates config and config.yaml.",
    params=[
        {"name": "prompt", "description": "Prompt to display to the user.", "required": True, "type": "string"},
        {"name": "timeout", "description": "Countdown in seconds before capturing coordinates.", "required": False, "type": "integer"}
    ]
)
def capture_coordinates_tool(prompt: str, timeout: Optional[int] = None) -> Dict[str, Any]:
    """MCP Tool to capture mouse coordinates and update config/config.yaml."""
    import yaml
    logging.info(f"Tool 'capture_coordinates' called. Prompt: {prompt}, Timeout: {timeout}")
    try:
        if timeout is None:
            timeout = config.get("INITIAL_DELAY", 5)
        coords = capture_coordinates(prompt, timeout)
        if coords:
            # Save to config in memory and to config.yaml
            config["LAST_CAPTURED_COORDS"] = list(coords)
            # Optionally, update INPUT_COORDS or HISTORY_COORDS as needed
            # Save config to file
            config_path = os.path.join(os.path.dirname(script_dir), CONFIG_PATH)
            with open(config_path, 'w', encoding='utf-8') as f:
                yaml.dump(config, f)
            logging.info(f"Coordinates {coords} captured and saved to config.")
            return {"status": "success", "coords": list(coords)}
        else:
            return {"status": "error", "message": "Failed to capture coordinates."}
    except Exception as e:
        logging.error(f"Error in capture_coordinates_tool: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to capture coordinates: {e}"}

@server.tool(
    name="send_chat_message",
    description="Sends a message via simulated mouse/keyboard at specified coordinates.",
    params=[
        {"name": "coords", "description": "Tuple [x, y] for the chat input area. If omitted, uses INPUT_COORDS from config.", "required": False, "type": "array"},
        {"name": "message", "description": "The message to type and send.", "required": True, "type": "string"}
    ]
)
def send_chat_message_tool(message: str, coords: Optional[list] = None) -> Dict[str, Any]:
    """MCP Tool to send a chat message using pyautogui."""
    logging.info(f"Tool 'send_chat_message' called. Message: {message}, Coords: {coords}")
    try:
        if coords is None:
            coords = config.get("INPUT_COORDS") or config.get("LAST_CAPTURED_COORDS")
        if not coords or not isinstance(coords, (list, tuple)) or len(coords) != 2:
            return {"status": "error", "message": "Valid coordinates must be provided or set in config."}
        coords_tuple = tuple(coords)
        success = send_chat_message(coords_tuple, message, config)
        if success:
            return {"status": "success", "message": f"Message sent at {coords_tuple}."}
        else:
            return {"status": "error", "message": "Failed to send message."}
    except Exception as e:
        logging.error(f"Error in send_chat_message_tool: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to send chat message: {e}"}

@server.tool(
    name="get_chat_response",
    description="Captures text from the chat history area using clipboard automation.",
    params=[
        {"name": "coords", "description": "Tuple [x, y] for the chat history area. If omitted, uses HISTORY_COORDS from config.", "required": False, "type": "array"}
    ]
)
def get_chat_response_tool(coords: Optional[list] = None) -> Dict[str, Any]:
    """MCP Tool to get chat response using pyautogui/pyperclip."""
    logging.info(f"Tool 'get_chat_response' called. Coords: {coords}")
    try:
        if coords is None:
            coords = config.get("HISTORY_COORDS") or config.get("LAST_CAPTURED_COORDS")
        if not coords or not isinstance(coords, (list, tuple)) or len(coords) != 2:
            return {"status": "error", "message": "Valid coordinates must be provided or set in config."}
        coords_tuple = tuple(coords)
        response = get_ai_response(coords_tuple, config)
        if response is not None:
            return {"status": "success", "response": response}
        else:
            return {"status": "error", "message": "Failed to get chat response."}
    except Exception as e:
        logging.error(f"Error in get_chat_response_tool: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to get chat response: {e}"}

@server.tool(
    name="run_web_search",
    description="Performs a web search using the assistant's web search tool and returns the results.",
    params=[
        {"name": "query", "description": "The search query to look up.", "required": True, "type": "string"}
    ]
)
def run_web_search_tool(query: str) -> Dict[str, Any]:
    """MCP Tool to perform a web search using the assistant's web search tool."""
    logging.info(f"Tool 'run_web_search' called. Query: {query}")
    try:
        # Use the assistant's web search tool
        # from functions import web_search  # Removed due to missing module
        logging.warning("web_search function is not available (missing 'functions' module). Returning error.")
        return {"status": "error", "message": "web_search function is not available (missing 'functions' module)."}
        # results = web_search(query, explanation="MCP server web search step for research/discovery.")
        # return {"status": "success", "results": results}
    except Exception as e:
        logging.error(f"Error in run_web_search_tool: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to perform web search: {e}"}

@server.tool(
    name="reload_config",
    description="Reloads the configuration from config.yaml at runtime.",
    params=[]
)
def reload_config_tool() -> Dict[str, Any]:
    """MCP Tool to reload configuration from config.yaml."""
    logging.info("Tool 'reload_config' called.")
    try:
        load_config()
        logging.info("Configuration reloaded successfully.")
        return {"status": "success", "message": "Configuration reloaded successfully."}
    except Exception as e:
        logging.error(f"Error in reload_config_tool: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to reload configuration: {e}"}

@server.tool(
    name="server_status",
    description="Returns a brief health/status report for the MCP server.",
    params=[]
)
def server_status_tool() -> Dict[str, Any]:
    """MCP Tool to report server health/status."""
    import platform
    import datetime
    logging.info("Tool 'server_status' called.")
    try:
        status = {
            "server": "autotyper-taskmaster-mcp",
            "status": "running",
            "python_version": platform.python_version(),
            "platform": platform.platform(),
            "cwd": os.getcwd(),
            "time": datetime.datetime.now().isoformat(),
            "config_keys": list(config.keys()),
        }
        return {"status": "success", "server_status": status}
    except Exception as e:
        logging.error(f"Error in server_status_tool: {e}", exc_info=True)
        return {"status": "error", "message": f"Failed to get server status: {e}"}

@server.tool(
    name="accessibility_audit",
    description="Performs an accessibility/code quality audit on Python, HTML, and documentation files.",
    params=[
        {"name": "target_type", "description": "Type of files to audit: python, html, docs, or all.", "required": False, "type": "string"},
        {"name": "path", "description": "Path to audit (default: project root).", "required": False, "type": "string"},
    ]
)
def accessibility_audit_tool(target_type: str = "all", path: str = ".") -> dict:
    """MCP Tool to perform accessibility/code quality audit."""
    import subprocess
    import glob
    import os
    import re
    import sys
    import pathlib
    logging.info(f"Tool 'accessibility_audit' called. Target: {target_type}, Path: {path}")
    results = {}
    root = os.path.abspath(path)
    if not os.path.exists(root):
        return {"status": "error", "message": f"Path does not exist: {root}"}
    
    # 1. Python code audit (ruff, docstrings)
    if target_type in ("all", "python"):
        try:
            ruff_result = subprocess.run([sys.executable, "-m", "ruff", root], capture_output=True, text=True)
            results["ruff"] = ruff_result.stdout.strip() or "No issues found."
        except Exception as e:
            results["ruff"] = f"Error running ruff: {e}"
        # Docstring check: look for .py files missing docstrings
        missing_docstrings = []
        for pyfile in glob.glob(os.path.join(root, "**", "*.py"), recursive=True):
            with open(pyfile, encoding="utf-8") as f:
                content = f.read()
                if not re.search(r'"""|\'\'\'', content):
                    missing_docstrings.append(pyfile)
        if missing_docstrings:
            results["python_docstrings"] = f"Files missing docstrings: {missing_docstrings}"
        else:
            results["python_docstrings"] = "All Python files have docstrings."
    # 2. HTML audit (wcag-zoo)
    if target_type in ("all", "html"):
        html_files = glob.glob(os.path.join(root, "**", "*.html"), recursive=True)
        wcag_results = {}
        for html_file in html_files:
            try:
                wcag_proc = subprocess.run([sys.executable, "-m", "wcag_zoo.parade", html_file, "--level=AA"], capture_output=True, text=True)
                wcag_results[html_file] = wcag_proc.stdout.strip() or "No issues found."
            except Exception as e:
                wcag_results[html_file] = f"Error running wcag-zoo: {e}"
        results["wcag_zoo"] = wcag_results if wcag_results else "No HTML files found."
    # 3. Documentation audit (README, Sphinx/mkdocs)
    if target_type in ("all", "docs"):
        readme_found = any(os.path.isfile(os.path.join(root, f)) for f in ["README.md", "README.rst", "README.txt"]) \
            or any(f.lower().startswith("readme") for f in os.listdir(root))
        results["readme"] = "README found." if readme_found else "README not found!"
        sphinx_conf = os.path.isfile(os.path.join(root, "docs", "conf.py"))
        mkdocs_conf = os.path.isfile(os.path.join(root, "mkdocs.yml"))
        results["sphinx"] = "Sphinx config found." if sphinx_conf else "Sphinx config not found."
        results["mkdocs"] = "MkDocs config found." if mkdocs_conf else "MkDocs config not found."
    return {"status": "success", "audit_results": results}

# --- Add more tools below ---


# ================== Server Execution ==================

if __name__ == "__main__":
    logging.info("Starting Auto Typer Taskmaster MCP Server...")
    try:
        server.run()
    except Exception as e:
        logging.error(f"MCP Server failed to run: {e}", exc_info=True)
        sys.exit(1)
    logging.info("MCP Server stopped.") 