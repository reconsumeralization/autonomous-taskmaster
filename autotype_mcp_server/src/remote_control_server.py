"""
Remote Control Server Module

Provides HTTP and WebSocket endpoints for remote and accessible control of the MCP server.
Screen-reader and TTS optimized.
"""
from fastapi import FastAPI, Request, HTTPException, WebSocket, WebSocketDisconnect
import subprocess
import logging
import os
import yaml
from threading import Thread, Lock
import uvicorn
import time
from queue import Queue
import json
from typing import List
import psutil
import smtplib
import requests
from email.mime.text import MIMEText
from src.utils import send_desktop_notification

CONFIG_PATH = os.path.join(os.path.dirname(__file__), '../config.yaml')
with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
    config = yaml.safe_load(f)

LOG_FILE = config.get('LOG_FILE', 'logs/remote_control.log')
logging.basicConfig(filename=LOG_FILE, level=logging.INFO, format='%(asctime)s %(levelname)s %(message)s')

REMOTE_CONTROL_TOKEN = config.get('REMOTE_CONTROL_TOKEN', 'changeme')
SSL_KEYFILE = config.get('REMOTE_SSL_KEYFILE')
SSL_CERTFILE = config.get('REMOTE_SSL_CERTFILE')

app = FastAPI()

COMMAND_MAP = {
    'audit': ['python', os.path.join(os.path.dirname(__file__), 'mcp_server.py'), 'audit'],
    'email-intake': ['python', os.path.join(os.path.dirname(__file__), 'mcp_server.py'), 'email-intake'],
    'review-tasks': ['python', os.path.join(os.path.dirname(__file__), 'mcp_server.py'), 'review-tasks', '--action', 'list'],
    'watchdog': ['python', os.path.join(os.path.dirname(__file__), 'mcp_server.py'), 'watchdog'],
    'watchdog-report': ['python', os.path.join(os.path.dirname(__file__), 'mcp_server.py'), 'watchdog-report'],
}

queue = Queue()
queue_lock = Lock()
last_command = {'cmd': None, 'args': None, 'status': None, 'timestamp': None}

QUEUE_FILE = os.path.join(os.path.dirname(__file__), 'queue.json')
LAST_COMMAND_FILE = os.path.join(os.path.dirname(__file__), 'last_command.json')

ws_clients: List[WebSocket] = []

USERS = {u['token']: u for u in config.get('REMOTE_CONTROL_USERS', [])}

HEALTH_THRESHOLDS = {
    'cpu': 90,      # percent
    'memory': 90,  # percent
    'disk': 90,    # percent
    'queue': 10    # items
}

HEALTH_ALERT_EMAIL = config.get('HEALTH_ALERT_EMAIL')
HEALTH_ALERT_WEBHOOK = config.get('HEALTH_ALERT_WEBHOOK')

last_alert = {'msg': None, 'ts': 0}
ALERTS = []  # Store recent alerts (max 20)

def save_queue():
    with queue_lock:
        with open(QUEUE_FILE, 'w', encoding='utf-8') as f:
            json.dump(list(queue.queue), f)
        with open(LAST_COMMAND_FILE, 'w', encoding='utf-8') as f:
            json.dump(last_command, f)

def load_queue():
    try:
        with open(QUEUE_FILE, 'r', encoding='utf-8') as f:
            items = json.load(f)
        for item in items:
            queue.put(item)
    except Exception:
        pass
    try:
        with open(LAST_COMMAND_FILE, 'r', encoding='utf-8') as f:
            last = json.load(f)
        with queue_lock:
            last_command.update(last)
    except Exception:
        pass

load_queue()

def speak_and_print(message):
    print(message)
    if config.get('ENABLE_TTS', False):
        try:
            from src.core_logic import speak_and_print as tts_speak
            tts_speak(message, config)
        except Exception as e:
            logging.error(f"TTS failed: {e}")

def command_worker():
    while True:
        item = queue.get()
        if item is None:
            break
        cmd, args = item['cmd'], item['args']
        full_cmd = COMMAND_MAP[cmd] + args
        logging.info(f"[QUEUE] Executing: {full_cmd}")
        speak_and_print(f"[QUEUE] Executing: {cmd}")
        result = subprocess.run(full_cmd)
        with queue_lock:
            last_command.update({'cmd': cmd, 'args': args, 'status': result.returncode, 'timestamp': time.time()})
        queue.task_done()
        save_queue()

worker_thread = Thread(target=command_worker, daemon=True)
worker_thread.start()

async def broadcast_status():
    data = {
        "queue_size": queue.qsize(),
        "last_command": last_command.copy()
    }
    for ws in ws_clients[:]:
        try:
            await ws.send_json(data)
        except Exception:
            try:
                ws_clients.remove(ws)
            except ValueError:
                pass

def check_permission(token, cmd):
    user = USERS.get(token)
    if not user:
        return False, None
    allowed = user.get('allowed_commands', [])
    return cmd in allowed, user.get('role')

@app.post("/command")
async def run_command(request: Request):
    auth = request.headers.get('authorization')
    if not auth or not auth.startswith('Bearer '):
        raise HTTPException(status_code=401, detail='Missing or invalid Authorization header')
    token = auth.split(' ', 1)[1]
    if token != REMOTE_CONTROL_TOKEN:
        raise HTTPException(status_code=403, detail='Invalid token')
    data = await request.json()
    cmd = data.get('cmd')
    args = data.get('args', [])
    if cmd not in COMMAND_MAP:
        msg = f"Unknown command: {cmd}"
        logging.warning(msg)
        speak_and_print(msg)
        return {"status": "error", "message": msg}
    allowed, role = check_permission(token, cmd)
    if not allowed:
        msg = f"Permission denied for token {token[:4]}... role {role} on command {cmd}"
        logging.warning(msg)
        speak_and_print(msg)
        raise HTTPException(status_code=403, detail=msg)
    logging.info(f"User role {role} executing command: {cmd}")
    queue.put({'cmd': cmd, 'args': args})
    logging.info(f"Enqueued remote command: {cmd} {args}")
    speak_and_print(f"Enqueued remote command: {cmd}")
    save_queue()
    await broadcast_status()
    return {"status": "ok", "message": f"Command {cmd} enqueued."}

@app.get("/status")
async def status():
    with queue_lock:
        qsize = queue.qsize()
        last = last_command.copy()
    return {
        "queue_size": qsize,
        "last_command": last
    }

@app.get("/health")
async def health():
    cpu = psutil.cpu_percent(interval=0.5)
    mem = psutil.virtual_memory().percent
    disk = psutil.disk_usage('/').percent
    qlen = queue.qsize()
    status = 'ok'
    alerts = []
    if cpu > HEALTH_THRESHOLDS['cpu']:
        alerts.append(f"High CPU: {cpu}%")
    if mem > HEALTH_THRESHOLDS['memory']:
        alerts.append(f"High Memory: {mem}%")
    if disk > HEALTH_THRESHOLDS['disk']:
        alerts.append(f"High Disk: {disk}%")
    if qlen > HEALTH_THRESHOLDS['queue']:
        alerts.append(f"Queue Length: {qlen}")
    if alerts:
        status = 'alert'
        msg = ' | '.join(alerts)
        logging.warning(f"HEALTH ALERT: {msg}")
        speak_and_print(f"HEALTH ALERT: {msg}")
        send_desktop_notification("Health Alert", msg)
        add_alert(msg)
    return {
        'status': status,
        'cpu': cpu,
        'memory': mem,
        'disk': disk,
        'queue_length': qlen,
        'alerts': alerts
    }

def add_alert(msg):
    ALERTS.append({'msg': msg, 'ts': time.time()})
    if len(ALERTS) > 20:
        ALERTS.pop(0)

def send_health_alert(msg):
    global last_alert
    import time
    now = time.time()
    # Avoid spamming: only alert if message or >5min since last
    if last_alert['msg'] == msg and now - last_alert['ts'] < 300:
        return
    last_alert['msg'] = msg
    last_alert['ts'] = now
    logging.warning(f"EXTERNAL HEALTH ALERT: {msg}")
    send_desktop_notification("Health Alert", msg)
    add_alert(msg)
    if HEALTH_ALERT_EMAIL:
        try:
            email_msg = MIMEText(msg)
            email_msg['Subject'] = 'MCP Health Alert'
            email_msg['From'] = HEALTH_ALERT_EMAIL
            email_msg['To'] = HEALTH_ALERT_EMAIL
            with smtplib.SMTP('localhost') as s:
                s.sendmail(HEALTH_ALERT_EMAIL, [HEALTH_ALERT_EMAIL], email_msg.as_string())
        except Exception as e:
            logging.error(f"Failed to send health alert email: {e}")
    if HEALTH_ALERT_WEBHOOK:
        try:
            requests.post(HEALTH_ALERT_WEBHOOK, json={'alert': msg})
        except Exception as e:
            logging.error(f"Failed to send health alert webhook: {e}")

def poll_health():
    import threading
    import asyncio
    async def check():
        try:
            res = await health()
            if res['status'] == 'alert' and res['alerts']:
                send_health_alert(' | '.join(res['alerts']))
        except Exception as e:
            logging.error(f"Health polling error: {e}")
    asyncio.get_event_loop().create_task(check())
    threading.Timer(60, poll_health).start()

# Start polling after app definition
poll_health()

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    ws_clients.append(ws)
    try:
        # First message must be {"token": ...}
        auth_msg = await ws.receive_json()
        token = auth_msg.get('token')
        user = USERS.get(token)
        if not user:
            await ws.send_json({"error": "Invalid token"})
            await ws.close()
            return
        role = user.get('role')
        await broadcast_status()
        while True:
            msg = await ws.receive_json()
            cmd = msg.get('cmd')
            args = msg.get('args', [])
            allowed = cmd in user.get('allowed_commands', [])
            if not allowed:
                await ws.send_json({"error": f"Permission denied for role {role} on command {cmd}"})
                continue
            queue.put({'cmd': cmd, 'args': args})
            save_queue()
            await broadcast_status()
    except WebSocketDisconnect:
        ws_clients.remove(ws)
    except Exception:
        ws_clients.remove(ws)

@app.get("/alerts")
async def get_alerts():
    """Get recent critical alerts (last 20)."""
    return {'alerts': ALERTS[-20:]}

if __name__ == "__main__":
    uvicorn_kwargs = dict(host="0.0.0.0", port=8080)
    if SSL_KEYFILE and SSL_CERTFILE:
        uvicorn_kwargs['ssl_keyfile'] = SSL_KEYFILE
        uvicorn_kwargs['ssl_certfile'] = SSL_CERTFILE
        print(f"[HTTPS] Remote control server using SSL cert: {SSL_CERTFILE}")
    else:
        print("[HTTP] Remote control server running without SSL (insecure)")
    uvicorn.run(app, **uvicorn_kwargs) 