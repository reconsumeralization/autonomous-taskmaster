"""
Security Hardening Audit Utility

Scans for secrets, open ports, and dependency vulnerabilities.
Accessible, screen-reader friendly, and logs all findings.
"""
import os
import re
import logging
import argparse
import subprocess

LOGS_DIR = 'logs'
logging.basicConfig(filename=os.path.join(LOGS_DIR, 'security_audit.log'),
                    level=logging.INFO,
                    format='%(asctime)s %(levelname)s %(message)s')

SECRET_PATTERNS = [
    re.compile(r'api[_-]?key\s*[:=]\s*[\w-]+', re.IGNORECASE),
    re.compile(r'secret[_-]?key\s*[:=]\s*[\w-]+', re.IGNORECASE),
    re.compile(r'password\s*[:=]\s*[^\s]+', re.IGNORECASE),
    re.compile(r'token\s*[:=]\s*[\w-]+', re.IGNORECASE),
]

EXCLUDE_DIRS = {'.venv', 'site-packages', '__pycache__', 'backups', 'logs', '.git'}


def scan_for_secrets():
    """Scan code and config files for potential secrets."""
    findings = []
    for root, dirs, files in os.walk('.'):
        dirs[:] = [d for d in dirs if d not in EXCLUDE_DIRS]
        for f in files:
            if f.endswith(('.py', '.yaml', '.yml', '.env', '.json', '.txt')):
                path = os.path.join(root, f)
                try:
                    with open(path, encoding='utf-8', errors='ignore') as file:
                        for i, line in enumerate(file, 1):
                            for pat in SECRET_PATTERNS:
                                if pat.search(line):
                                    findings.append(f"{path}:{i}: {line.strip()}")
                except Exception:
                    continue
    if findings:
        print("[1] Potential secrets found:")
        for f in findings:
            print(f)
        logging.warning("Potential secrets found:\n" + '\n'.join(findings))
    else:
        print("[1] No secrets found.")
        logging.info("No secrets found.")


def scan_open_ports():
    """List open TCP ports on localhost."""
    print("[2] Open TCP ports on localhost:")
    try:
        result = subprocess.run(['netstat', '-an'], capture_output=True, text=True)
        lines = result.stdout.splitlines()
        for line in lines:
            if 'LISTEN' in line or 'LISTENING' in line:
                print(line)
        logging.info("Open ports scan completed.")
    except Exception as e:
        print(f"Error scanning ports: {e}")
        logging.error(f"Error scanning ports: {e}")


def scan_dependencies():
    """Run pip-audit to check for dependency vulnerabilities."""
    print("[3] Dependency vulnerability scan (pip-audit):")
    try:
        result = subprocess.run(['pip', 'install', '--quiet', 'pip-audit'], capture_output=True, text=True)
        result = subprocess.run(['pip-audit'], capture_output=True, text=True)
        if result.returncode == 0:
            print(result.stdout)
            logging.info("pip-audit results:\n" + result.stdout)
        else:
            print(result.stderr)
            logging.warning("pip-audit errors:\n" + result.stderr)
    except Exception as e:
        print(f"Error running pip-audit: {e}")
        logging.error(f"Error running pip-audit: {e}")


def main():
    parser = argparse.ArgumentParser(description="Security hardening audit utility.")
    parser.add_argument('--secrets', action='store_true', help='Scan for secrets in code/config.')
    parser.add_argument('--ports', action='store_true', help='List open TCP ports.')
    parser.add_argument('--deps', action='store_true', help='Check for dependency vulnerabilities.')
    parser.add_argument('--all', action='store_true', help='Run all security checks.')
    args = parser.parse_args()
    if args.all or args.secrets:
        scan_for_secrets()
    if args.all or args.ports:
        scan_open_ports()
    if args.all or args.deps:
        scan_dependencies()
    if not (args.all or args.secrets or args.ports or args.deps):
        parser.print_help()

if __name__ == '__main__':
    main() 