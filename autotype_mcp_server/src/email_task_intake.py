"""
Email Task Intake Module

Automates polling an email inbox for new tasks and adds them to the task queue.
Accessible and screen-reader friendly.
"""

import os
import imaplib
import email
from email.header import decode_header
import yaml
import logging
import datetime
from typing import Optional

CONFIG_PATH: str = os.path.join(os.path.dirname(__file__), "../config.yaml")


def load_config(config_path: str) -> dict:
    """Load YAML configuration from the given path."""
    with open(config_path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


config = load_config(CONFIG_PATH)

IMAP_SERVER: str = config.get("IMAP_SERVER", "imap.example.com")
IMAP_USER: str = config.get("IMAP_USER", "user@example.com")
IMAP_PASSWORD: str = config.get("IMAP_PASSWORD", "password")
TASKS_DIR: str = os.path.abspath(config.get("TASKS_DIR", "tasks"))
LOG_FILE: str = config.get("LOG_FILE", "logs/email_intake.log")

logging.basicConfig(
    filename=LOG_FILE,
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
)


def save_task(content: str, ext: str = "md") -> None:
    """Save the given content as a task file in the tasks directory.

    Args:
        content: The content to save.
        ext: The file extension (default: 'md').
    """
    os.makedirs(TASKS_DIR, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    fname = f"email_task_{timestamp}.{ext}"
    fpath = os.path.join(TASKS_DIR, fname)
    with open(fpath, "w", encoding="utf-8") as f:
        f.write(content)
    logging.info(f"Saved new task: {fpath}")


def _decode_header_value(header_val) -> str:
    """Decode an email header value, handling bytes and encoding."""
    val, encoding = decode_header(header_val)[0]
    if isinstance(val, bytes):
        return val.decode(encoding or "utf-8", errors="ignore")
    return val


def _extract_attachment(part) -> Optional[tuple[str, str]]:
    """Extract filename and extension from an email part if present and valid.

    Args:
        part: The email part.

    Returns:
        Tuple of (filename, extension) if valid, else None.
    """
    filename = part.get_filename()
    if filename:
        fname, enc = decode_header(filename)[0]
        if isinstance(fname, bytes):
            fname = fname.decode(enc or "utf-8", errors="ignore")
        ext = fname.split(".")[-1].lower()
        return fname, ext
    return None


def fetch_email_tasks() -> None:
    """Poll the IMAP inbox for new tasks and save them to the task queue."""
    try:
        mail = imaplib.IMAP4_SSL(IMAP_SERVER)
        mail.login(IMAP_USER, IMAP_PASSWORD)
        mail.select("inbox")
        status, messages = mail.search(None, "(UNSEEN)")
        if status != "OK":
            logging.info("No new emails found.")
            return

        for num in messages[0].split():
            status, data = mail.fetch(num, "(RFC822)")
            if status != "OK":
                continue
            msg = email.message_from_bytes(data[0][1])
            subject = _decode_header_value(msg["Subject"])
            logging.info(f"Processing email: {subject}")

            # Track if a task was saved from an attachment
            task_saved = False

            # Check for attachments
            for part in msg.walk():
                if part.get_content_maintype() == "multipart":
                    continue
                attachment_info = _extract_attachment(part)
                if attachment_info:
                    fname, ext = attachment_info
                    if ext in ("md", "json"):
                        content = part.get_payload(decode=True).decode(
                            "utf-8", errors="ignore"
                        )
                        save_task(content, ext=ext)
                        task_saved = True

            # If no attachment, check body for task
            if not task_saved:
                if msg.is_multipart():
                    for part in msg.walk():
                        if part.get_content_type() == "text/plain":
                            body = part.get_payload(decode=True).decode(
                                "utf-8", errors="ignore"
                            )
                            if "task:" in body.lower():
                                save_task(body, ext="md")
                                break
                else:
                    body = msg.get_payload(decode=True).decode("utf-8", errors="ignore")
                    if "task:" in body.lower():
                        save_task(body, ext="md")

            # Mark as seen
            mail.store(num, "+FLAGS", "\\Seen")
        mail.logout()
    except Exception as e:
        logging.error(f"Error in fetch_email_tasks: {e}")


if __name__ == "__main__":
    fetch_email_tasks()
