# Auto Typer Taskmaster MCP Server

**A hands-free, accessible task automation and code execution platform designed for developers with motor impairments.**

---

## Table of Contents

*   [Project Purpose](#project-purpose)
*   [Core Features](#core-features)
*   [Architecture Overview](#architecture-overview)
*   [Setup](#setup)
    *   [Prerequisites](#prerequisites)
    *   [Installation](#installation)
    *   [Configuration](#configuration)
*   [Usage](#usage)
    *   [Running the MCP Server](#running-the-mcp-server)
    *   [Running the Watchdog](#running-the-watchdog)
    *   [Task Management](#task-management)
    *   [Interacting via MCP Client](#interacting-via-mcp-client)
*   [Accessibility](#accessibility)
*   [Testing](#testing)
*   [Contributing](#contributing)

---

## Project Purpose

This project aims to provide a robust and accessible platform for software development and task automation, controllable primarily via voice commands and eye blinks (specifically, double-blink or 'DD'). It empowers users who may face challenges with traditional keyboard/mouse input to remain productive and competitive.

The core is an MCP (Model Context Protocol) server that exposes various tools for task management, code generation, testing, UI automation, and more, designed to be driven by an AI assistant like Cursor's Agent.

## Core Features

*   **Task Management:** Load, save, add, prioritize, and process tasks defined in JSON or Markdown files.
*   **AI Integration:** Generate code via AI APIs (currently configured for Groq/X-AI).
*   **Test Automation:** Run `pytest` for specified task files.
*   **UI Automation (via PyAutoGUI):** Capture screen coordinates, send chat messages, get responses (requires user setup).
*   **MCP Server:** Exposes project functionality as tools consumable by MCP-compatible clients (like Cursor).
*   **Accessibility:** Designed with screen reader compatibility and TTS/DD interaction in mind.
*   **Watchdog:** Ensures the MCP server process stays running.

## Architecture Overview

The system consists of several key components within the `autotype_mcp_server` directory:

*   `src/mcp_server.py`: The main FastAPI/MCP server application. Defines MCP tools and handles client communication.
*   `src/core_logic.py`: Contains core functions for processing tasks, interacting with AI, running tests, and performing UI automation.
*   `src/utils.py`: Holds utility functions for logging, file I/O (JSON, YAML), notifications, etc.
*   `src/ai_providers.py`: Handles interaction with external AI APIs.
*   `src/ui_automation.py`: Contains functions using `pyautogui` and `pyperclip` for screen interaction.
*   `taskmaster.py`: (Potentially legacy or alternative interface) Script for managing tasks and potentially running the main loop (review needed).
*   `screen_idle_dd.py`: Monitors screen activity and detects double-blinks (DD) for user input/confirmation.
*   `src/watchdog.py`: A simple process monitor that restarts `mcp_server.py` if it crashes.
*   `config.yaml`: Main configuration file for API keys, paths, timeouts, feature flags.
*   `taskmaster_todos.json`: The primary list of tasks managed by the system.
*   `tasks/`: Directory typically containing detailed task descriptions in `.md` format.

**Interaction Flow (Simplified):**
1.  An MCP Client (e.g., Cursor Agent) connects to the running `mcp_server.py`.
2.  The client requests actions using the defined MCP tools (e.g., `list_tasks`, `run_tdd_cycle`).
3.  `mcp_server.py` calls functions in `core_logic.py`, `utils.py`, etc., to perform the requested actions.
4.  `core_logic.py` might interact with `ai_providers.py` for code generation or `ui_automation.py` for screen interaction.
5.  Results are returned to the client via MCP.
6.  `screen_idle_dd.py` runs (often managed by `taskmaster.py`) to listen for DD input, signaling confirmation or actions.

## Setup

### Prerequisites

*   Python (Version 3.10+ recommended, check `.python-version` files if present)
*   Access to a terminal or command prompt.
*   Git (for cloning, if necessary)

### Installation

1.  **Clone the Repository (if needed):**
    ```bash
    git clone <repository_url>
    cd autotype
    ```
2.  **Navigate to Server Directory:**
    ```bash
    cd autotype_mcp_server
    ```
3.  **Create a Virtual Environment:**
    ```bash
    python -m venv .venv
    ```
4.  **Activate the Virtual Environment:**
    *   Windows (PowerShell): `.\.venv\Scripts\Activate.ps1`
    *   Windows (cmd.exe): `.\.venv\Scripts\activate.bat`
    *   macOS/Linux: `source .venv/bin/activate`
5.  **Install Dependencies:**
    ```bash
    python -m pip install -r requirements.txt
    ```
6.  **Install Local MCP SDK:** (Requires the `mcp_sdk_source` directory to be present)
    ```bash
    python -m pip install -e ../mcp_sdk_source
    ```

### Configuration

1.  **Copy Example Config:** If `config.yaml` doesn't exist, copy `config.example.yaml` (if available) to `config.yaml`.
2.  **API Keys:** Obtain API keys for the desired AI provider (e.g., Groq). Set them as environment variables. The server primarily looks for:
    *   `XAI_API_KEY`
    *   `XAI_API_URL`
    (These environment variable names can be changed in `config.yaml` using `GROK_API_KEY_ENV` and `GROK_API_URL_ENV`).
3.  **Edit `config.yaml`:** Review and adjust settings:
    *   `TASKS_DIR`: Path to the directory containing `.md` task files.
    *   `TODO_PATH`: Path to the JSON task list (`taskmaster_todos.json`).
    *   `LOG_LEVEL`, `LOG_FILE`: Logging configuration.
    *   `ENABLE_TTS`: Enable/disable Text-to-Speech feedback.
    *   `AI_MODEL`, `AI_MAX_TOKENS`, etc.: AI model parameters.
    *   `INPUT_COORDS`, `HISTORY_COORDS`: Screen coordinates for UI automation (use `capture_coordinates` tool or capture manually).
    *   `IDLE_TIMEOUT_SECONDS`, `POST_DD_WAIT_SECONDS`: Parameters for `screen_idle_dd.py`.

## Usage

**(Ensure the virtual environment is activated for all commands)**

### Running the MCP Server

This makes the MCP tools available to clients like Cursor.

```bash
python src/mcp_server.py
```

The server will start, typically on `http://127.0.0.1:8000`. You can configure the host and port if needed (check `uvicorn` arguments or FastMCP documentation).

### Running the Watchdog

To ensure the MCP server restarts automatically if it crashes:

```bash
python src/watchdog.py
```
*(Note: The watchdog currently runs the server in the foreground within its loop. For background operation, modifications would be needed.)*

### Task Management

Tasks are primarily managed via:

*   **`taskmaster_todos.json`:** A JSON list of task objects (e.g., `{"id": "task_xyz", "description": "Do something", "status": "pending"}`).
*   **`tasks/` directory:** Contains `.md` files with detailed task descriptions, implementation/test file paths, and status in a YAML front matter block.
*   **MCP Tools:** Use tools like `list_tasks`, `add_task`, `get_next_code_task_path`, `run_tdd_cycle` via an MCP client.

### Interacting via MCP Client

1.  Ensure the `mcp_server.py` process is running.
2.  Configure your MCP client (e.g., Cursor via `.cursor/mcp.json`) to connect to the server's SSE endpoint (e.g., `http://127.0.0.1:8000/sse`).
3.  Use the client (e.g., Cursor chat) to invoke the available MCP tools:
    *   `@autotyper-taskmaster-mcp list_tasks`
    *   `@autotyper-taskmaster-mcp add_task task_description="Implement feature X"`
    *   `@autotyper-taskmaster-mcp run_tdd_cycle task_path="C:\...\tasks\task_abc.md"`
    *   *(Agent may use tools automatically based on context)*

## Accessibility

*   **Screen Reader Friendly:** Output (logs, status) aims for compatibility.
*   **TTS:** Text-to-Speech feedback can be enabled in `config.yaml`.
*   **DD Input:** `screen_idle_dd.py` provides double-blink detection for confirmation/triggering actions (integration primarily via `taskmaster.py`).

## Testing

Tests are located in the `tests/` directory and use `pytest`.

1.  **Run All Tests:**
    ```bash
    pytest
    ```
2.  **Run Specific File:**
    ```bash
    pytest tests/test_utils.py
    ```
3.  **Run Specific Test (by name substring):**
    ```bash
    pytest -k ai_generate_code
    ```
4.  **Generate Coverage Report:**
    ```bash
    pytest --cov=src --cov-report=html
    ```
    (View report at `htmlcov/index.html`)

*Current test coverage is tracked but may require updates. The UI automation tests (`test_ui_automation.py`) are currently blocked due to import issues.* 

## Contributing

(Placeholder for contribution guidelines if the project becomes open source or involves collaborators).

---
*This README is optimized for screen readers and accessible navigation.*
