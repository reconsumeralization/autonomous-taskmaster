import sys
import os

# Add the project root directory to the Python path
# This allows imports like `from autotype_mcp_server.src import ...`
project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
sys.path.insert(0, project_root)

print(f"[conftest.py] Added {project_root} to sys.path") 