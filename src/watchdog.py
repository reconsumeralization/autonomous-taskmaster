import os
import sys
import time
import datetime
import subprocess

MCP_SERVER_PATH = os.path.join(os.path.dirname(__file__), "mcp_server.py")


def run_watchdog() -> None:
    """Continuously runs and restarts the MCP server process, logging output and errors."""
    while True:
        now = datetime.datetime.now()
        print(f"[{now}] Starting MCP server process: {MCP_SERVER_PATH}")
        try:
            proc = subprocess.Popen(
                [sys.executable, MCP_SERVER_PATH],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
            )
            stdout, stderr = proc.communicate()
            print(
                f"[{datetime.datetime.now()}] MCP server process finished with code {proc.returncode}"
            )
            if stdout:
                print("--- MCP Server STDOUT ---")
                print(stdout.decode(errors="ignore"))
                print("------------------------")
            if stderr:
                print("--- MCP Server STDERR ---")
                print(stderr.decode(errors="ignore"))
                print("------------------------")
        except Exception as e:
            print(f"[{datetime.datetime.now()}] Exception occurred: {e}")

        print(f"[{datetime.datetime.now()}] Restarting server in 5 seconds...")
        time.sleep(5)
