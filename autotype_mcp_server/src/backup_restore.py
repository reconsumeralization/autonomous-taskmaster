"""
Backup and Restore Utility

Backs up tasks/, config.yaml, and logs/ into a timestamped zip file.
Accessible, screen-reader friendly, and logs all actions.
"""
import os
import zipfile
import datetime
import logging
import argparse

BACKUP_DIR = 'backups'
TASKS_DIR = 'tasks'
LOGS_DIR = 'logs'
CONFIG_FILE = 'config.yaml'

os.makedirs(BACKUP_DIR, exist_ok=True)

logging.basicConfig(filename=os.path.join(LOGS_DIR, 'backup_restore.log'),
                    level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

def backup():
    """Create a timestamped zip backup of tasks/, config.yaml, and logs/."""
    now = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
    backup_name = f"backup_{now}.zip"
    backup_path = os.path.join(BACKUP_DIR, backup_name)
    with zipfile.ZipFile(backup_path, 'w', zipfile.ZIP_DEFLATED) as z:
        if os.path.exists(TASKS_DIR):
            for root, _, files in os.walk(TASKS_DIR):
                for f in files:
                    fp = os.path.join(root, f)
                    z.write(fp, os.path.relpath(fp))
        if os.path.exists(LOGS_DIR):
            for root, _, files in os.walk(LOGS_DIR):
                for f in files:
                    fp = os.path.join(root, f)
                    z.write(fp, os.path.relpath(fp))
        if os.path.exists(CONFIG_FILE):
            z.write(CONFIG_FILE)
    logging.info(f"Backup created: {backup_path}")
    print(f"Backup created: {backup_path}")

def restore(backup_file):
    """Restore tasks/, config.yaml, and logs/ from a backup zip file."""
    if not os.path.exists(backup_file):
        print(f"Backup file not found: {backup_file}")
        return
    with zipfile.ZipFile(backup_file, 'r') as z:
        z.extractall('.')
    logging.info(f"Restored from backup: {backup_file}")
    print(f"Restored from backup: {backup_file}")

def list_backups():
    """List all available backup zip files."""
    backups = [f for f in os.listdir(BACKUP_DIR) if f.endswith('.zip')]
    if not backups:
        print("No backups found.")
        return
    print("Available backups:")
    for b in sorted(backups):
        print(f"- {b}")

def main():
    parser = argparse.ArgumentParser(description="Backup and restore utility for tasks, config, and logs.")
    parser.add_argument('--backup', action='store_true', help='Create a new backup zip file.')
    parser.add_argument('--restore', type=str, help='Restore from the specified backup zip file.')
    parser.add_argument('--list', action='store_true', help='List available backups.')
    args = parser.parse_args()
    if args.backup:
        backup()
    elif args.restore:
        restore(args.restore)
    elif args.list:
        list_backups()
    else:
        parser.print_help()

if __name__ == '__main__':
    main() 