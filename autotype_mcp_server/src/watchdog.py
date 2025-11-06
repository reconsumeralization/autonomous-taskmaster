"""
Watchdog Module

Monitors the MCP server and system health, providing self-healing and recovery features.
Accessible and screen-reader friendly.
"""
import subprocess
import time
import os
import yaml
import logging
import datetime

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '../config.yaml')

with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

LOG_FILE = config.get('LOG_FILE', 'logs/watchdog.log')
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

RECOVERY_LOG = 'watchdog_recovery.log'

MCP_SERVER_PATH = os.path.join(os.path.dirname(__file__), 'mcp_server.py')


def log_recovery(event):
    with open(RECOVERY_LOG, 'a', encoding='utf-8') as f:
        f.write(f"[{datetime.datetime.now().isoformat()}] {event}\n")
    logging.info(event)
    print(event)

def run_watchdog():
    start_time = time.time()
    while True:
        proc = subprocess.Popen(['python', MCP_SERVER_PATH])
        log_recovery('MCP server started.')
        proc.wait()
        log_recovery('MCP server stopped or crashed. Restarting...')
        time.sleep(2)  # brief pause before restart

def report_recovery():
    if not os.path.exists(RECOVERY_LOG):
        print('No recovery events logged.')
        return
    with open(RECOVERY_LOG, 'r', encoding='utf-8') as f:
        print(f.read())
    uptime = None
    if os.path.exists('watchdog_uptime.txt'):
        with open('watchdog_uptime.txt', 'r', encoding='utf-8') as f:
            uptime = f.read().strip()
    if uptime:
        print(f'Last recorded uptime: {uptime}')

if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Watchdog for MCP server.')
    parser.add_argument('--report', action='store_true', help='Report recovery events and uptime.')
    args = parser.parse_args()
    if args.report:
        report_recovery()
    else:
        run_watchdog() 