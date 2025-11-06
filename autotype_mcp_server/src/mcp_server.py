# === Imports ===
import logging
import yaml
import os
import sys
import argparse
import datetime
import json
import asyncio
import re
import textwrap
from pathlib import Path
from typing import Optional
from slugify import slugify

# Ensure src directory is in path for relative imports BEFORE importing local modules
script_dir = Path(__file__).resolve().parent
project_root = script_dir.parent
sys.path.insert(0, str(project_root))

try:
    from mcp.server.fastmcp.server import FastMCP
    from src.utils import (
        setup_logging,
        load_yaml_from_string,
        load_json_file,
        save_json_file,
        move_file,
        run_pytest,
        speak_and_print,
        get_next_task,
        send_desktop_notification,
        scan_project_and_generate_map,
    )
    from src.core_logic import (
        load_tasks,
        save_tasks,
        process_code_task,
        parse_task_header,
        ProcessingResult,
    )
    from src.ui_automation import (
        capture_coordinates,
        send_chat_message,
        get_ai_response,
    )
    from src.ai_providers import ai_generate_code
except ImportError as e:
    print(f"ERROR: Failed to import necessary modules: {e}", file=sys.stderr)
    print(
        "Ensure modelcontextprotocol SDK is installed and src directory is accessible.",
        file=sys.stderr,
    )
    sys.exit(1)

# ================== Configuration & Setup ==================
CONFIG_PATH = "config.yaml"
config = {}


def load_config():
    """Load configuration from YAML file."""
    global config
    try:
        config_file_path = os.path.join(os.path.dirname(script_dir), CONFIG_PATH)
        with open(config_file_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        if not config:
            config = {}
            logging.warning(f"Config file {config_file_path} is empty.")
        fallback_list = config.get("AI_MODEL_FALLBACK_LIST")
        if not isinstance(fallback_list, list) or not fallback_list:
            config["AI_MODEL_FALLBACK_LIST"] = [
                "phi3:mini-4k-instruct-q4_K_M",
                "phi:latest",
            ]
            logging.info(
                "Set AI_MODEL_FALLBACK_LIST to Ollama defaults: phi3:mini-4k-instruct-q4_K_M, phi:latest"
            )
        logging.info(f"Configuration loaded successfully from {config_file_path}.")
    except FileNotFoundError:
        logging.error(
            f"Configuration file not found at {config_file_path}. Using default settings."
        )
        config = {}
    except yaml.YAMLError as e:
        logging.error(
            f"Error parsing configuration file {config_file_path}: {e}. Using default settings."
        )
        config = {}
    except Exception as e:
        logging.error(f"Unexpected error loading configuration: {e}", exc_info=True)
        config = {}


load_config()

try:
    setup_logging(config)
except Exception as e:
    logging.basicConfig(
        level=logging.WARNING, format="%(asctime)s - %(levelname)s - %(message)s"
    )
    logging.error(f"Failed to initialize logging using setup_logging: {e}")

# ================== Helper Functions ==================


def create_md_task_file(
    task_description: str, parent_goal: Optional[str], config: dict
) -> Optional[str]:
    """Creates a basic .md task file from a task description."""
    tasks_dir = os.path.abspath(config.get("TASKS_DIR", "tasks"))
    os.makedirs(tasks_dir, exist_ok=True)
    try:
        impl_file = "src/placeholder.py"
        test_file = "tests/test_placeholder.py"
        note = "\n**NOTE:** Implementation and Test files are placeholders. Please update them based on the task description."
        path_match = re.search(r"[`'](.*?\.\w+)[`']", task_description)
        if path_match:
            extracted_path = path_match.group(1).replace("\\", "/")
            filename = os.path.basename(extracted_path)
            if extracted_path.startswith("src/"):
                impl_file = extracted_path
                test_file = f"tests/test_{filename}"
            elif extracted_path.startswith("tests/"):
                impl_file = f"src/{filename.replace('test_', '')}"
                test_file = extracted_path
            else:
                impl_file = f"src/{filename}"
                test_file = f"tests/test_{filename}"
            note = "\n(Implementation and Test files were inferred from the task description. Please verify.)"
        safe_desc = re.sub(r"[^\w\s-]", "", task_description).strip()
        slug = slugify(safe_desc, max_length=50, word_boundary=True)
        timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S%f")
        filename = f"task_{slug}_{timestamp}.md"
        file_path = os.path.join(tasks_dir, filename)
        header = {
            "Description": task_description,
            "Implementation File": impl_file,
            "Test File": test_file,
            "Status": "pending",
        }
        if parent_goal:
            header["Parent Goal"] = parent_goal
        md_content = f"---\n{yaml.dump(header, default_flow_style=False, allow_unicode=True).strip()}\n---\n\n# Task: {task_description}\n"
        if parent_goal:
            md_content += (
                f"\nParent Goal Context:\n{textwrap.indent(parent_goal, '> ')}\n"
            )
        md_content += note
        with open(file_path, "w", encoding="utf-8") as f:
            f.write(md_content)
        logging.info(f"Created .md task file: {filename}")
        return filename
    except Exception as md_e:
        logging.error(
            f"Failed to create .md file for task '{task_description[:30]}...': {md_e}",
            exc_info=True,
        )
        return None


# === MCP Server Setup ===


def actual_dummy_auth_middleware(mcp_request_context):
    """Dummy middleware assuming FastMCP provides context. Allows all."""
    logging.info("Dummy Auth Middleware: Allowing request.")
    return


server = FastMCP(
    name="autotyper-taskmaster-mcp",
    description="Manages tasks, runs code generation/tests, and automates chat via Auto Typer logic.",
)

# ================== Main Application Setup & CLI ==================


def run_accessibility_audit_cli():
    """Command-line entry point for running accessibility audit."""
    parser = argparse.ArgumentParser(
        description="Run accessibility audit from the command line."
    )
    parser.add_argument(
        "--target",
        type=str,
        default="all",
        choices=["python", "html", "docs", "all"],
        help="Type of file to audit.",
    )
    parser.add_argument(
        "path",
        type=str,
        nargs="?",
        default=".",
        help="Specific file or directory to audit.",
    )
    args = parser.parse_args()
    result = accessibility_audit_tool(target_type=args.target, path=args.path)
    print(json.dumps(result, indent=2))


def review_tasks_cli():
    """
    Command-line utility to review, pretty-print, and potentially clean up the
    taskmaster_todos.json file.
    """
    parser = argparse.ArgumentParser(
        description="Review and manage the Taskmaster TODO JSON file."
    )
    parser.add_argument(
        "--clean",
        action="store_true",
        help="Remove tasks marked 'done' or 'error' from the list.",
    )
    parser.add_argument(
        "--status",
        type=str,
        choices=["pending", "done", "error", "all"],
        default="all",
        help="Filter tasks by status.",
    )
    args = parser.parse_args()
    try:
        tasks = load_tasks(config)
        print(f"Found {len(tasks)} total tasks in '{config.get('TODO_PATH')}'.\n")
        if args.clean:
            original_count = len(tasks)
            tasks_to_keep = [
                t for t in tasks if t.get("status", "pending") not in ["done", "error"]
            ]
            if len(tasks_to_keep) < original_count:
                print(
                    f"Cleaning tasks... Removing {original_count - len(tasks_to_keep)} 'done' or 'error' tasks."
                )
                save_tasks(tasks_to_keep, config)
                tasks = tasks_to_keep
                print("File cleaned and saved.")
            else:
                print("No 'done' or 'error' tasks to clean.")
            print("-" * 20)
        filtered_tasks = (
            tasks
            if args.status == "all"
            else [t for t in tasks if t.get("status", "pending") == args.status]
        )
        if not filtered_tasks:
            print(f"No tasks with status '{args.status}' found.")
        else:
            print(
                f"Displaying {len(filtered_tasks)} tasks with status '{args.status}':"
            )
            for i, task in enumerate(filtered_tasks):
                print(f"  {i+1}. [Status: {task.get('status', 'pending')}]")
                print(f"     Task: {task.get('task', 'No description')}")
                if "md_file" in task:
                    print(f"     MD File: {task['md_file']}")
            print("-" * 20)
    except Exception as e:
        print(f"An error occurred: {e}")
        logging.error(f"Error in review_tasks_cli: {e}", exc_info=True)


if __name__ == "__main__":
    try:
        from fastapi import FastAPI, Request
        from fastapi.responses import JSONResponse
        from sse_starlette.sse import EventSourceResponse
        import uvicorn

        app = FastAPI()

        @app.post("/tools/{tool_name}")
        async def call_tool(tool_name: str, request: Request):
            tool = server.get_tool(tool_name)
            if not tool:
                return JSONResponse(
                    status_code=404, content={"error": "Tool not found"}
                )
            try:
                payload = await request.json()
                result = await server.call_tool(tool_name, **payload)
                return JSONResponse(content=result)
            except Exception as e:
                return JSONResponse(status_code=500, content={"error": str(e)})

        @app.get("/tools")
        async def list_tools_endpoint():
            return JSONResponse(
                content={"tools": [t.name for t in server.list_tools()]}
            )

        @app.get("/sse")
        async def sse_endpoint():
            async def event_generator():
                yield {
                    "event": "message",
                    "id": "initial",
                    "data": json.dumps(
                        {"message": "SSE connection established. Waiting for logs..."}
                    ),
                }

            return EventSourceResponse(event_generator())

    except ImportError:
        print(
            "FastAPI or sse-starlette not found. Web server endpoints will be disabled."
        )
        app = None

    parser = argparse.ArgumentParser(
        description="Autotyper MCP Server: Task Management and Automation"
    )
    parser.add_argument(
        "--run-loop",
        action="store_true",
        help="Run one iteration of the autonomous development loop.",
    )
    parser.add_argument(
        "--serve",
        action="store_true",
        help="Run the full MCP server to listen for tool calls.",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="127.0.0.1",
        help="Host for the server to bind to.",
    )
    parser.add_argument(
        "--port", type=int, default=8000, help="Port for the server to listen on."
    )
    parser.add_argument(
        "--review-tasks",
        action="store_true",
        help="Enter interactive task review mode.",
    )
    parser.add_argument(
        "--run-audit",
        action="store_true",
        help="Run the accessibility audit CLI.",
    )
    args, unknown = parser.parse_known_args()

    if args.run_loop:
        logging.info("Running one autonomous dev loop iteration as requested...")
        result = asyncio.run(autonomous_dev_loop_tool())
        logging.info(f"Autonomous loop iteration finished. Result: {result}")
        print(json.dumps(result, indent=2))
    elif args.serve:
        if not app:
            logging.error(
                "Cannot run server because FastAPI is not installed. Please run 'pip install fastapi uvicorn'."
            )
            sys.exit(1)
        logging.info(f"Starting MCP server at http://{args.host}:{args.port}")
        uvicorn.run(app, host=args.host, port=args.port)
    elif args.review_tasks:
        print("Entering task review mode...")
        review_tasks_cli()
    elif args.run_audit:
        print("Running accessibility audit...")
        run_accessibility_audit_cli()
    else:
        print("No action specified. Use --help to see available options.")
