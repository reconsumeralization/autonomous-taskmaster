import sys
import os
import json
import logging
import subprocess
from pathlib import Path
import markdown
from PySide6.QtWidgets import (
    QApplication,
    QMainWindow,
    QTabWidget,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QListWidget,
    QLabel,
    QMessageBox,
    QListWidgetItem,
    QTextBrowser,
    QSplitter,
    QPushButton,
    QPlainTextEdit,
    QGroupBox,
    QTextEdit,
    QSpacerItem,
    QSizePolicy,
)
from PySide6.QtCore import Qt, QSize
from PySide6.QtGui import QIcon, QPalette, QColor, QFont
import yaml

# Determine the base directory (autotype/)
BASE_DIR = Path(__file__).resolve().parent.parent.parent
TASK_FILE = BASE_DIR / "autotype_mcp_server" / "taskmaster_todos.json"
DOCS_DIR = BASE_DIR / "docs"
SERVER_DIR = BASE_DIR / "autotype_mcp_server"
SERVER_TESTS_DIR = SERVER_DIR / "tests"
SERVER_VENV_PYTHON = SERVER_DIR / ".venv" / "Scripts" / "python.exe"
CONFIG_FILE = BASE_DIR / "config.yaml"


class AutotypeDashboard(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("SaiGent Autotype Dashboard")
        self.setGeometry(100, 100, 1000, 800)
        self.config = self._load_app_config()
        self._setup_styles()

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.project_context_label = QLabel("Project Context: Loading...")
        self.project_context_label.setStyleSheet(
            "padding: 5px; font-style: italic; color: #a9a9a9;"
        )
        layout.addWidget(self.project_context_label, 0, Qt.AlignRight)
        self._update_project_context_display()

        self.tabs = QTabWidget()
        layout.addWidget(self.tabs)

        self._create_goals_tab()
        self._create_tests_tab()
        self._create_docs_tab()
        self._create_efforts_tab()

        self.load_goals()
        self._load_doc_files()
        self._load_efforts()

    def _setup_styles(self):
        self.setStyleSheet(
            """
            QWidget {
                background-color: #2b2b2b;
                color: #f0f0f0;
                font-size: 11pt;
            }
            QMainWindow {
                background-color: #3c3f41;
            }
            QTabWidget::pane {
                border-top: 2px solid #5c5f61;
            }
            QTabBar::tab {
                background: #4b4f51;
                border: 1px solid #5c5f61;
                padding: 8px 15px;
                margin-right: 2px;
                border-top-left-radius: 4px;
                border-top-right-radius: 4px;
            }
            QTabBar::tab:selected {
                background: #5c5f61;
                border-bottom-color: #5c5f61;
            }
            QTabBar::tab:!selected {
                margin-top: 2px;
            }
            QListWidget, QPlainTextEdit, QTextEdit {
                background-color: #3c3f41;
                border: 1px solid #5c5f61;
                font-family: Consolas, Courier New, monospace;
            }
            QListWidget::item {
                padding: 5px;
            }
            QListWidget::item:selected {
                background-color: #5c5f61;
                color: #ffffff;
            }
            QLabel {
                padding: 5px;
            }
            QTextBrowser {
                background-color: #3c3f41;
                border: 1px solid #5c5f61;
                color: #f0f0f0;
            }
            QSplitter::handle {
                background-color: #5c5f61;
            }
            QSplitter::handle:horizontal {
                width: 1px;
            }
            QSplitter::handle:vertical {
                height: 1px;
            }
            QPushButton {
                background-color: #5c5f61;
                color: #f0f0f0;
                border: 1px solid #6c6f71;
                padding: 5px 10px;
                border-radius: 4px;
                min-width: 60px;
            }
            QPushButton:hover {
                background-color: #6c6f71;
            }
            QPushButton:pressed {
                background-color: #4b4f51;
            }
            QPlainTextEdit, QTextEdit {
                 color: #f0f0f0;
            }
            QGroupBox {
                border: 1px solid #5c5f61;
                border-radius: 4px;
                margin-top: 10px;
                padding: 10px;
                padding-top: 20px;
            }
            QGroupBox::title {
                subcontrol-origin: margin;
                subcontrol-position: top left;
                padding: 0 5px;
                left: 10px;
                color: #f0f0f0;
                margin-top: -5px;
            }
        """
        )

    def _create_goals_tab(self):
        self.goals_tab = QWidget()
        layout = QVBoxLayout(self.goals_tab)

        top_layout = QHBoxLayout()
        top_layout.addWidget(QLabel("Current Goals (from taskmaster_todos.json):"))
        top_layout.addStretch(1)
        self.refresh_goals_button = QPushButton("🔄 Refresh")
        self.refresh_goals_button.setToolTip("Reload tasks from taskmaster_todos.json")
        self.refresh_goals_button.clicked.connect(self.load_goals)
        top_layout.addWidget(self.refresh_goals_button)
        layout.addLayout(top_layout)

        self.goals_list_widget = QListWidget()
        layout.addWidget(self.goals_list_widget)
        self.tabs.addTab(self.goals_tab, "🎯 Goals")

    def _create_tests_tab(self):
        self.tests_tab = QWidget()
        layout = QVBoxLayout(self.tests_tab)

        self.run_tests_button = QPushButton("Run Server Tests")
        self.run_tests_button.clicked.connect(self._run_server_tests)
        layout.addWidget(self.run_tests_button, 0, Qt.AlignLeft)

        layout.addWidget(QLabel("Test Output:"))
        self.test_results_area = QPlainTextEdit()
        self.test_results_area.setReadOnly(True)
        font = QFont("Consolas", 10)
        self.test_results_area.setFont(font)
        layout.addWidget(self.test_results_area)

        self.tabs.addTab(self.tests_tab, "🧪 Tests")

    def _create_docs_tab(self):
        self.docs_tab = QWidget()
        layout = QHBoxLayout(self.docs_tab)

        splitter = QSplitter(Qt.Horizontal)
        layout.addWidget(splitter)

        left_widget = QWidget()
        left_layout = QVBoxLayout(left_widget)
        docs_header_layout = QHBoxLayout()
        docs_header_layout.addWidget(QLabel("Documentation Files:"))
        docs_header_layout.addStretch(1)
        self.refresh_docs_button = QPushButton("🔄 Refresh")
        self.refresh_docs_button.setToolTip(
            "Rescan the docs directory for Markdown files"
        )
        self.refresh_docs_button.clicked.connect(self._load_doc_files)
        docs_header_layout.addWidget(self.refresh_docs_button)
        left_layout.addLayout(docs_header_layout)

        self.docs_list_widget = QListWidget()
        self.docs_list_widget.itemSelectionChanged.connect(self._display_selected_doc)
        left_layout.addWidget(self.docs_list_widget)
        splitter.addWidget(left_widget)

        right_widget = QWidget()
        right_layout = QVBoxLayout(right_widget)
        right_layout.addWidget(QLabel("Content:"))
        self.docs_text_browser = QTextBrowser()
        self.docs_text_browser.setOpenExternalLinks(True)
        right_layout.addWidget(self.docs_text_browser)
        splitter.addWidget(right_widget)

        splitter.setSizes([250, 750])

        self.tabs.addTab(self.docs_tab, "📚 Docs")

    def _create_efforts_tab(self):
        self.efforts_tab = QWidget()
        layout = QVBoxLayout(self.efforts_tab)

        top_layout = QHBoxLayout()
        top_layout.addStretch(1)
        self.refresh_efforts_button = QPushButton("🔄 Refresh")
        self.refresh_efforts_button.setToolTip("Reload current and recent tasks")
        self.refresh_efforts_button.clicked.connect(self._load_efforts)
        top_layout.addWidget(self.refresh_efforts_button)
        layout.addLayout(top_layout)

        current_group = QGroupBox("Currently In Progress")
        current_layout = QVBoxLayout()
        self.current_efforts_text = QTextEdit()
        self.current_efforts_text.setReadOnly(True)
        current_layout.addWidget(self.current_efforts_text)
        current_group.setLayout(current_layout)
        layout.addWidget(current_group)

        recent_group = QGroupBox("Recent Activity (Last 5 Completed)")
        recent_layout = QVBoxLayout()
        self.recent_efforts_text = QTextEdit()
        self.recent_efforts_text.setReadOnly(True)
        recent_layout.addWidget(self.recent_efforts_text)
        recent_group.setLayout(recent_layout)
        layout.addWidget(recent_group)

        self.tabs.addTab(self.efforts_tab, "🚀 Efforts")

    def load_goals(self):
        self.goals_list_widget.clear()
        try:
            if not TASK_FILE.exists():
                self.goals_list_widget.addItem("Task file not found: " + str(TASK_FILE))
                return

            with open(TASK_FILE, "r", encoding="utf-8") as f:
                tasks = json.load(f)

            if not tasks:
                self.goals_list_widget.addItem("No tasks found in the file.")
                return

            for task in tasks:
                task_id = task.get("id", "N/A")
                task_desc = task.get("task", task.get("description", "No description"))
                task_status = task.get("status", "Pending")
                item_text = f"[{task_status}] ID: {task_id} - {task_desc}"
                list_item = QListWidgetItem(item_text)

                if task_status.lower() == "completed":
                    list_item.setForeground(QColor("#8fbc8f"))
                elif task_status.lower() == "in progress":
                    list_item.setForeground(QColor("#add8e6"))
                elif task_status.lower() == "failed" or task_status.lower() == "error":
                    list_item.setForeground(QColor("#f08080"))

                self.goals_list_widget.addItem(list_item)

        except json.JSONDecodeError:
            self.goals_list_widget.addItem(
                f"Error: Could not decode JSON from {TASK_FILE}"
            )
            logging.error(f"JSON decode error in {TASK_FILE}", exc_info=True)
        except Exception as e:
            self.goals_list_widget.addItem(f"Error loading tasks: {e}")
            logging.error(f"Error loading task file {TASK_FILE}: {e}", exc_info=True)

    def _load_doc_files(self):
        self.docs_list_widget.clear()
        if not DOCS_DIR.is_dir():
            self.docs_list_widget.addItem(
                f"Documentation directory not found: {DOCS_DIR}"
            )
            logging.warning(f"Docs directory not found: {DOCS_DIR}")
            return

        try:
            found_files = False
            for item in DOCS_DIR.glob("**/*.md"):
                if item.is_file():
                    relative_path = item.relative_to(DOCS_DIR)
                    list_item = QListWidgetItem(str(relative_path))
                    list_item.setData(Qt.UserRole, str(item))
                    self.docs_list_widget.addItem(list_item)
                    found_files = True

            if not found_files:
                self.docs_list_widget.addItem("No .md files found in docs directory.")

        except Exception as e:
            self.docs_list_widget.addItem(f"Error scanning docs directory: {e}")
            logging.error(f"Error scanning {DOCS_DIR}: {e}", exc_info=True)

    def _display_selected_doc(self):
        selected_items = self.docs_list_widget.selectedItems()
        if not selected_items:
            self.docs_text_browser.clear()
            return

        list_item = selected_items[0]
        file_path_str = list_item.data(Qt.UserRole)

        if not file_path_str:
            self.docs_text_browser.setPlainText(
                "Error: Could not retrieve file path for selected item."
            )
            return

        file_path = Path(file_path_str)

        try:
            if file_path.is_file():
                markdown_content = file_path.read_text(encoding="utf-8")
                html_content = markdown.markdown(
                    markdown_content, extensions=["fenced_code", "tables"]
                )
                html_with_style = f"""
                <style>
                    body {{ color: #f0f0f0; background-color: #3c3f41; font-size: 10pt; }}
                    pre {{ background-color: #2b2b2b; padding: 10px; border-radius: 4px; overflow: auto; }}
                    code {{ font-family: Consolas, monospace; }}
                    table {{ border-collapse: collapse; margin: 1em 0; }}
                    th, td {{ border: 1px solid #5c5f61; padding: 8px; }}
                    th {{ background-color: #4b4f51; }}
                    a {{ color: #6897bb; }}
                </style>
                {html_content}
                """
                self.docs_text_browser.setHtml(html_with_style)
            else:
                self.docs_text_browser.setPlainText(
                    f"Error: File not found: {file_path}"
                )
        except Exception as e:
            error_msg = f"Error reading or rendering file {file_path}:\n{e}"
            self.docs_text_browser.setPlainText(error_msg)
            logging.error(error_msg, exc_info=True)

    def _run_server_tests(self):
        self.test_results_area.setPlainText("Running tests...")
        QApplication.processEvents()

        if not SERVER_VENV_PYTHON.exists():
            self.test_results_area.setPlainText(
                f"Error: Server venv python not found at {SERVER_VENV_PYTHON}"
            )
            return

        command = [
            str(SERVER_VENV_PYTHON),
            "-m",
            "pytest",
            str(SERVER_TESTS_DIR),
            "-v",
        ]

        try:
            logging.info(f"Running test command: {' '.join(command)} in {SERVER_DIR}")
            result = subprocess.run(
                command,
                capture_output=True,
                text=True,
                cwd=SERVER_DIR,
                encoding="utf-8",
                errors="replace",
            )

            output = f"Exit Code: {result.returncode}\n\n"
            output += "--- STDOUT ---\n"
            output += result.stdout if result.stdout else "(No stdout)"
            output += "\n\n--- STDERR ---\n"
            output += result.stderr if result.stderr else "(No stderr)"

            self.test_results_area.setPlainText(output)
            logging.info(f"Test run completed with exit code {result.returncode}")

        except FileNotFoundError:
            error_msg = f"Error: Could not run pytest. Is '{SERVER_VENV_PYTHON}' correct and pytest installed in the server venv?"
            self.test_results_area.setPlainText(error_msg)
            logging.error(error_msg)
        except Exception as e:
            error_msg = f"An unexpected error occurred while running tests: {e}"
            self.test_results_area.setPlainText(error_msg)
            logging.error(error_msg, exc_info=True)

    def _load_efforts(self):
        current_text = ""
        recent_text = ""
        try:
            if not TASK_FILE.exists():
                current_text = f"Task file not found: {TASK_FILE}"
            else:
                with open(TASK_FILE, "r", encoding="utf-8") as f:
                    tasks = json.load(f)

                if not tasks:
                    current_text = "No tasks found."
                else:
                    in_progress_tasks = [
                        t for t in tasks if t.get("status", "").lower() == "in progress"
                    ]
                    completed_tasks = sorted(
                        [
                            t
                            for t in tasks
                            if t.get("status", "").lower() == "completed"
                        ],
                        key=lambda x: x.get("id", ""),
                        reverse=True,
                    )

                    if in_progress_tasks:
                        for task in in_progress_tasks:
                            current_text += f"- ID: {task.get('id', 'N/A')} - {task.get('task', 'No description')}\n"
                    else:
                        current_text = "No tasks currently in progress."

                    if completed_tasks:
                        for i, task in enumerate(completed_tasks[:5]):
                            recent_text += f"- ID: {task.get('id', 'N/A')} - {task.get('task', 'No description')}\n"
                    else:
                        recent_text = "No tasks recently completed."

        except Exception as e:
            error_msg = f"Error loading efforts data: {e}"
            current_text = error_msg
            recent_text = error_msg
            logging.error(error_msg, exc_info=True)

        self.current_efforts_text.setPlainText(current_text.strip())
        self.recent_efforts_text.setPlainText(recent_text.strip())

    def _load_app_config(self) -> dict:
        if not CONFIG_FILE.is_file():
            logging.error(f"Main configuration file not found: {CONFIG_FILE}")
            QMessageBox.warning(
                self,
                "Config Error",
                f"Main configuration file not found:\n{CONFIG_FILE}",
            )
            return {}
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                loaded_config = yaml.safe_load(f)
            if not isinstance(loaded_config, dict):
                logging.error(f"Config file is not a valid dictionary: {CONFIG_FILE}")
                return {}
            logging.info(f"Loaded main configuration from {CONFIG_FILE}")
            return loaded_config
        except yaml.YAMLError as e:
            logging.error(f"Error parsing YAML configuration file {CONFIG_FILE}: {e}")
            QMessageBox.critical(
                self,
                "Config Error",
                f"Error parsing configuration file:\n{CONFIG_FILE}\n\n{e}",
            )
            return {}
        except Exception as e:
            logging.error(
                f"Unexpected error loading configuration {CONFIG_FILE}: {e}",
                exc_info=True,
            )
            QMessageBox.critical(
                self,
                "Config Error",
                f"Unexpected error loading configuration:\n{CONFIG_FILE}\n\n{e}",
            )
            return {}

    def _update_project_context_display(self):
        project_name = self.config.get("CURRENT_PROJECT_NAME")
        if project_name:
            proj_path = BASE_DIR / "projects" / project_name
            if proj_path.is_dir():
                display_text = f"Project Context: {project_name}"
            else:
                display_text = f"Project Context: '{project_name}' (Not Found)"
                logging.warning(f"Project directory for '{project_name}' not found.")
        else:
            display_text = "Project Context: [Workspace Root]"
        self.project_context_label.setText(display_text)


if __name__ == "__main__":
    log_dir = BASE_DIR / "logs"
    log_dir.mkdir(exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(message)s",
        handlers=[
            logging.FileHandler(log_dir / "autotype_dashboard.log"),
            logging.StreamHandler(),
        ],
    )

    app = QApplication(sys.argv)
    # app.setWindowIcon(QIcon('path/to/icon.png'))

    window = AutotypeDashboard()
    window.show()

    logging.info("Autotype Dashboard started.")
    sys.exit(app.exec())
