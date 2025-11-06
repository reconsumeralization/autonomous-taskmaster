"""
Accessible Web Dashboard Server

Provides a FastAPI web dashboard for real-time status, alerts, and remote control.
Screen-reader friendly and accessible.
"""
import os
from fastapi import FastAPI, Request, Form, Cookie, WebSocket, Body
from fastapi.responses import HTMLResponse, RedirectResponse, JSONResponse
from fastapi.templating import Jinja2Templates
import uvicorn
import requests
import yaml
import secrets
import asyncio
import json
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.cron import CronTrigger
import datetime
from contextlib import asynccontextmanager

app = FastAPI()
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

API_BASE = "http://localhost:8080"
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "../config.yaml")
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)
REMOTE_USERS = {u['token']: u for u in config.get('REMOTE_CONTROL_USERS', [])}

COMMANDS = [
    ("audit", "Run accessibility/code quality audit"),
    ("email-intake", "Poll email inbox for new tasks"),
    ("review-tasks", "List/review/accept/reject tasks"),
    ("watchdog", "Start self-healing watchdog"),
    ("watchdog-report", "Show recovery events and uptime"),
]

SESSION_COOKIE = "dashboard_session"
SESSION_SECRET = secrets.token_hex(16)

scheduler = BackgroundScheduler()
scheduled_jobs = []

JOB_AUDIT_LOG = os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "job_audit_log.txt")
os.makedirs(os.path.dirname(JOB_AUDIT_LOG), exist_ok=True)

def log_job_execution(job_id, cmd, trigger, value, status):
    entry = {
        "timestamp": datetime.datetime.now().isoformat(),
        "job_id": job_id,
        "cmd": cmd,
        "trigger": trigger,
        "value": value,
        "status": status
    }
    with open(JOB_AUDIT_LOG, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry) + "\n")

@asynccontextmanager
def lifespan(app: FastAPI):
    if not scheduler.running:
        scheduler.start()
    yield
    # Optionally, add shutdown logic here

app.router.lifespan_context = lifespan

def get_user_from_cookie(session: str | None):
    if not session:
        return None
    try:
        token, role = session.split(":", 1)
        if token in REMOTE_USERS and REMOTE_USERS[token]["role"] == role:
            return {"token": token, "role": role}
    except Exception:
        pass
    return None

@app.get("/login", response_class=HTMLResponse)
def login_page(request: Request, error: str = ""):
    return templates.TemplateResponse("login.html", {"request": request, "error": error})

@app.post("/login", response_class=HTMLResponse)
def login(request: Request, token: str = Form(...)):
    user = REMOTE_USERS.get(token)
    if not user:
        return templates.TemplateResponse("login.html", {"request": request, "error": "Invalid token."})
    session = f"{token}:{user['role']}"
    response = RedirectResponse("/", status_code=302)
    response.set_cookie(SESSION_COOKIE, session, httponly=True, max_age=86400)
    return response

@app.get("/logout")
def logout():
    response = RedirectResponse("/login", status_code=302)
    response.delete_cookie(SESSION_COOKIE)
    return response

@app.get("/", response_class=HTMLResponse)
def home(request: Request, result: str = "", dashboard_session: str = Cookie(None)):
    user = get_user_from_cookie(dashboard_session)
    try:
        status = requests.get(f"{API_BASE}/health").json()
        alerts = requests.get(f"{API_BASE}/alerts").json().get("alerts", [])
        queue_status = requests.get(f"{API_BASE}/status").json()
    except Exception:
        status = {"status": "error"}
        alerts = []
        queue_status = {"queue_size": "?", "last_command": {}}
    return templates.TemplateResponse("home.html", {
        "request": request,
        "status": status,
        "alerts": alerts,
        "commands": COMMANDS,
        "result": result,
        "queue_status": queue_status,
        "user": user,
        "scheduled_jobs": scheduled_jobs,
    })

@app.post("/send-command", response_class=HTMLResponse)
def send_command(request: Request, cmd: str = Form(...), args: str = Form(""), dashboard_session: str = Cookie(None)):
    user = get_user_from_cookie(dashboard_session)
    if not user:
        return RedirectResponse("/login", status_code=302)
    try:
        headers = {"Authorization": f"Bearer {user['token']}"}
        data = {"cmd": cmd, "args": args.split() if args else []}
        resp = requests.post(f"{API_BASE}/command", json=data, headers=headers)
        result = resp.json().get("message", str(resp.json()))
    except Exception as e:
        result = f"Error: {e}"
    return home(request, result=result, dashboard_session=dashboard_session)

@app.get("/alerts", response_class=HTMLResponse)
def alerts_page(request: Request):
    try:
        alerts = requests.get(f"{API_BASE}/alerts").json().get("alerts", [])
    except Exception:
        alerts = []
    return templates.TemplateResponse("alerts.html", {"request": request, "alerts": alerts})

@app.get("/history", response_class=HTMLResponse)
def history_page(request: Request, dashboard_session: str = Cookie(None)):
    user = get_user_from_cookie(dashboard_session)
    if not user:
        return RedirectResponse("/login", status_code=302)
    # Load last command
    last_command = {}
    try:
        with open(os.path.join(os.path.dirname(__file__), "last_command.json"), "r", encoding="utf-8") as f:
            last_command = json.load(f)
    except Exception:
        pass
    # Load audit log (last 20 lines)
    audit_log = []
    try:
        with open(os.path.join(os.path.dirname(os.path.dirname(__file__)), "logs", "audit_log.txt"), "r", encoding="utf-8") as f:
            lines = f.readlines()
            audit_log = lines[-20:]
    except Exception:
        pass
    return templates.TemplateResponse("history.html", {
        "request": request,
        "user": user,
        "last_command": last_command,
        "audit_log": audit_log,
    })

@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    try:
        while True:
            try:
                status = requests.get(f"{API_BASE}/health").json()
                alerts = requests.get(f"{API_BASE}/alerts").json().get("alerts", [])
                queue_status = requests.get(f"{API_BASE}/status").json()
            except Exception:
                status = {"status": "error"}
                alerts = []
                queue_status = {"queue_size": "?", "last_command": {}}
            await ws.send_json({
                "status": status,
                "alerts": alerts,
                "queue_status": queue_status
            })
            await asyncio.sleep(5)
    except Exception:
        pass

@app.get("/users", response_class=HTMLResponse)
def users_page(request: Request, dashboard_session: str = Cookie(None)):
    user = get_user_from_cookie(dashboard_session)
    if not user or user["role"] != "admin":
        return RedirectResponse("/login", status_code=302)
    users = list(REMOTE_USERS.values())
    return templates.TemplateResponse("users.html", {"request": request, "user": user, "users": users, "error": ""})

@app.post("/add-user", response_class=HTMLResponse)
def add_user(request: Request, token: str = Form(...), role: str = Form(...), dashboard_session: str = Cookie(None)):
    user = get_user_from_cookie(dashboard_session)
    if not user or user["role"] != "admin":
        return RedirectResponse("/login", status_code=302)
    # Update config.yaml
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        users = config.get("REMOTE_CONTROL_USERS", [])
        users.append({"token": token, "role": role, "allowed_commands": [c[0] for c in COMMANDS]})
        config["REMOTE_CONTROL_USERS"] = users
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f)
        REMOTE_USERS[token] = {"token": token, "role": role, "allowed_commands": [c[0] for c in COMMANDS]}
    except Exception as e:
        return templates.TemplateResponse("users.html", {"request": request, "user": user, "users": list(REMOTE_USERS.values()), "error": str(e)})
    return RedirectResponse("/users", status_code=302)

@app.post("/remove-user", response_class=HTMLResponse)
def remove_user(request: Request, token: str = Form(...), dashboard_session: str = Cookie(None)):
    user = get_user_from_cookie(dashboard_session)
    if not user or user["role"] != "admin":
        return RedirectResponse("/login", status_code=302)
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f)
        users = [u for u in config.get("REMOTE_CONTROL_USERS", []) if u["token"] != token]
        config["REMOTE_CONTROL_USERS"] = users
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            yaml.safe_dump(config, f)
        REMOTE_USERS.pop(token, None)
    except Exception as e:
        return templates.TemplateResponse("users.html", {"request": request, "user": user, "users": list(REMOTE_USERS.values()), "error": str(e)})
    return RedirectResponse("/users", status_code=302)

# Template directory and minimal accessible templates
TEMPLATE_DIR = os.path.join(os.path.dirname(__file__), "templates")
os.makedirs(TEMPLATE_DIR, exist_ok=True)

with open(os.path.join(TEMPLATE_DIR, "login.html"), "w", encoding="utf-8") as f:
    f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Login - Accessible Dashboard</title>
</head>
<body>
  <h1>Login</h1>
  <form action="/login" method="post">
    <label for="token">Access Token:</label>
    <input type="password" name="token" id="token" required aria-label="Access Token">
    <button type="submit">Login</button>
  </form>
  {% if error %}<div role="alert">{{ error }}</div>{% endif %}
</body>
</html>
''')

with open(os.path.join(TEMPLATE_DIR, "home.html"), "w", encoding="utf-8") as f:
    f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Status - Accessible Dashboard</title>
  <script>
    let ws;
    function connectWS() {
      ws = new WebSocket("ws://" + window.location.host + "/ws");
      ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        document.getElementById("status-text").textContent = data.status.status;
        document.getElementById("cpu-text").textContent = data.status.cpu + "%";
        document.getElementById("mem-text").textContent = data.status.memory + "%";
        document.getElementById("disk-text").textContent = data.status.disk + "%";
        document.getElementById("queue-text").textContent = data.status.queue_length;
        document.getElementById("queue-size").textContent = data.queue_status.queue_size;
        document.getElementById("last-command").textContent = JSON.stringify(data.queue_status.last_command);
        let alerts = data.alerts.map(a => `<li>${a.msg} (${a.ts})</li>`).join("");
        if (!alerts) alerts = "<li>No alerts.</li>";
        document.getElementById("alerts-list").innerHTML = alerts;
      };
    }
    window.onload = connectWS;
  </script>
</head>
<body>
  <h1 id="main-title">System Status</h1>
  <div role="status" aria-live="polite">
    <p>Status: <span id="status-text">{{ status["status"] }}</span></p>
    <p>CPU: <span id="cpu-text">{{ status["cpu"] }}%</span></p>
    <p>Memory: <span id="mem-text">{{ status["memory"] }}%</span></p>
    <p>Disk: <span id="disk-text">{{ status["disk"] }}%</span></p>
    <p>Queue: <span id="queue-text">{{ status["queue_length"] }}</span></p>
  </div>
  <h2>Recent Alerts</h2>
  <ul id="alerts-list">
    {% for alert in alerts %}
      <li>{{ alert.msg }} ({{ alert.ts }})</li>
    {% else %}
      <li>No alerts.</li>
    {% endfor %}
  </ul>
  {% if user %}
  <h2>Remote Command</h2>
  <form action="/send-command" method="post">
    <label for="cmd">Command:</label>
    <select name="cmd" id="cmd">
      {% for value, label in commands %}
        <option value="{{ value }}">{{ label }}</option>
      {% endfor %}
    </select>
    <label for="args">Args:</label>
    <input type="text" name="args" id="args" aria-label="Arguments (space separated)">
    <button type="submit">Send</button>
  </form>
  {% if result %}<div role="alert">{{ result }}</div>{% endif %}
  <h2>Queue Status</h2>
  <p>Queue Size: <span id="queue-size">{{ queue_status["queue_size"] }}</span></p>
  <p>Last Command: <span id="last-command">{{ queue_status["last_command"] }}</span></p>
  <nav>
    <a href="/alerts">View All Alerts</a> |
    <a href="/logout">Logout</a>
  </nav>
  {% if user and user.role == "admin" %}
  <nav>
    <a href="/users">User Management</a>
  </nav>
  {% endif %}
  <a href="/accessibility-report" target="_blank">Accessibility Report</a> |
  {% else %}
  <nav>
    <a href="/alerts">View All Alerts</a> |
    <a href="/login">Login</a>
  </nav>
  {% endif %}
  <h2>Schedule Recurring Command</h2>
  <form action="/schedule-job" method="post">
    <label for="cmd">Command:</label>
    <select name="cmd" id="cmd">
      {% for value, label in commands %}
        <option value="{{ value }}">{{ label }}</option>
      {% endfor %}
    </select>
    <label for="interval">Interval (minutes):</label>
    <input type="number" name="interval" id="interval" min="1" required>
    <button type="submit">Schedule</button>
  </form>
  <h2>Scheduled Jobs</h2>
  <table border="1" aria-label="Scheduled Jobs">
    <tr><th>Command</th><th>Interval (min)</th><th>Actions</th></tr>
    {% for job in scheduled_jobs %}
      <tr>
        <td>{{ job.cmd }}</td>
        <td>{{ job.interval }}</td>
        <td>
          <form action="/remove-job" method="post" style="display:inline">
            <input type="hidden" name="job_id" value="{{ job.id }}">
            <button type="submit">Remove</button>
          </form>
        </td>
      </tr>
    {% else %}
      <tr><td colspan="3">No scheduled jobs.</td></tr>
    {% endfor %}
  </table>
</body>
</html>
''')

with open(os.path.join(TEMPLATE_DIR, "alerts.html"), "w", encoding="utf-8") as f:
    f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Alerts - Accessible Dashboard</title>
  <script>
    let ws;
    function connectWS() {
      ws = new WebSocket("ws://" + window.location.host + "/ws");
      ws.onmessage = function(event) {
        const data = JSON.parse(event.data);
        let alerts = data.alerts.map(a => `<li>${a.msg} (${a.ts})</li>`).join("");
        if (!alerts) alerts = "<li>No alerts.</li>";
        document.getElementById("alerts-list").innerHTML = alerts;
      };
    }
    window.onload = connectWS;
  </script>
</head>
<body>
  <h1 id="alerts-title">Recent Alerts</h1>
  <ul id="alerts-list">
    {% for alert in alerts %}
      <li>{{ alert.msg }} ({{ alert.ts }})</li>
    {% else %}
      <li>No alerts.</li>
    {% endfor %}
  </ul>
  <nav>
    <a href="/">Back to Status</a>
  </nav>
</body>
</html>
''')

with open(os.path.join(TEMPLATE_DIR, "history.html"), "w", encoding="utf-8") as f:
    f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Command History & Audit Log - Accessible Dashboard</title>
</head>
<body>
  <h1>Command History & Audit Log</h1>
  <h2>Last Command</h2>
  <table border="1" aria-label="Last Command">
    <tr><th>Field</th><th>Value</th></tr>
    {% for k, v in last_command.items() %}
      <tr><td>{{ k }}</td><td>{{ v }}</td></tr>
    {% else %}
      <tr><td colspan="2">No command history found.</td></tr>
    {% endfor %}
  </table>
  <h2>Audit Log (Last 20 Entries)</h2>
  <pre aria-label="Audit Log">{% for line in audit_log %}{{ line }}{% endfor %}</pre>
  <nav>
    <a href="/">Back to Status</a> |
    <a href="/logout">Logout</a>
  </nav>
</body>
</html>
''')

with open(os.path.join(TEMPLATE_DIR, "users.html"), "w", encoding="utf-8") as f:
    f.write('''
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>User Management - Accessible Dashboard</title>
</head>
<body>
  <h1>User Management</h1>
  <h2>Current Users</h2>
  <table border="1" aria-label="User List">
    <tr><th>Token</th><th>Role</th><th>Actions</th></tr>
    {% for u in users %}
      <tr><td>{{ u.token }}</td><td>{{ u.role }}</td>
        <td>
          <form action="/remove-user" method="post" style="display:inline">
            <input type="hidden" name="token" value="{{ u.token }}">
            <button type="submit">Remove</button>
          </form>
        </td>
      </tr>
    {% else %}
      <tr><td colspan="3">No users found.</td></tr>
    {% endfor %}
  </table>
  <h2>Add User</h2>
  <form action="/add-user" method="post">
    <label for="token">Token:</label>
    <input type="text" name="token" id="token" required>
    <label for="role">Role:</label>
    <select name="role" id="role">
      <option value="admin">admin</option>
      <option value="readonly">readonly</option>
    </select>
    <button type="submit">Add User</button>
  </form>
  {% if error %}<div role="alert">{{ error }}</div>{% endif %}
  <nav>
    <a href="/">Back to Status</a> |
    <a href="/logout">Logout</a>
  </nav>
</body>
</html>
''')

@app.get("/accessibility-report")
def accessibility_report():
    try:
        report_path = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../accessibility_report.json'))
        with open(report_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(content=data)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.post("/schedule-job")
def schedule_job(cmd: str = Form(...), interval: int = Form(None), cron: str = Form(None)):
    try:
        if cron:
            try:
                trigger = CronTrigger.from_crontab(cron)
            except Exception as e:
                return {"error": f"Invalid cron expression: {e}"}
            def job_func(job_id=None):
                try:
                    print(f"Scheduled job (cron) executed: {cmd}")
                    log_job_execution(job.id if job_id is None else job_id, cmd, "cron", cron, "success")
                except Exception as e:
                    log_job_execution(job.id if job_id is None else job_id, cmd, "cron", cron, f"error: {e}")
            job = scheduler.add_job(lambda: job_func(), trigger)
            scheduled_jobs.append({"id": job.id, "cmd": cmd, "trigger": "cron", "value": cron})
            return {"message": f"Scheduled {cmd} with cron '{cron}'.", "job_id": job.id}
        elif interval:
            def job_func(job_id=None):
                try:
                    print(f"Scheduled job (interval) executed: {cmd}")
                    log_job_execution(job.id if job_id is None else job_id, cmd, "interval", interval, "success")
                except Exception as e:
                    log_job_execution(job.id if job_id is None else job_id, cmd, "interval", interval, f"error: {e}")
            job = scheduler.add_job(lambda: job_func(), IntervalTrigger(minutes=interval))
            scheduled_jobs.append({"id": job.id, "cmd": cmd, "trigger": "interval", "value": interval})
            return {"message": f"Scheduled {cmd} every {interval} minutes.", "job_id": job.id}
        else:
            return {"error": "Must provide either interval or cron."}
    except Exception as e:
        return {"error": str(e)}

@app.get("/scheduled-jobs")
def get_scheduled_jobs():
    return {"jobs": scheduled_jobs}

@app.post("/remove-job")
def remove_job(job_id: str = Form(...)):
    try:
        scheduler.remove_job(job_id)
        global scheduled_jobs
        scheduled_jobs = [j for j in scheduled_jobs if j["id"] != job_id]
        return {"message": f"Removed job {job_id}"}
    except Exception as e:
        return {"error": str(e)}

@app.post("/voice-schedule-job")
def voice_schedule_job(payload: dict = Body(...)):
    cmd = payload.get("cmd")
    interval = payload.get("interval")
    cron = payload.get("cron")
    if not cmd or (not interval and not cron):
        return JSONResponse(content={"error": "Missing 'cmd' and either 'interval' or 'cron' in request."}, status_code=400)
    try:
        if cron:
            try:
                trigger = CronTrigger.from_crontab(cron)
            except Exception as e:
                return JSONResponse(content={"error": f"Invalid cron expression: {e}"}, status_code=400)
            def job_func(job_id=None):
                try:
                    print(f"Voice scheduled job (cron) executed: {cmd}")
                    log_job_execution(job.id if job_id is None else job_id, cmd, "cron", cron, "success")
                except Exception as e:
                    log_job_execution(job.id if job_id is None else job_id, cmd, "cron", cron, f"error: {e}")
            job = scheduler.add_job(lambda: job_func(), trigger)
            scheduled_jobs.append({"id": job.id, "cmd": cmd, "trigger": "cron", "value": cron})
            return {"message": f"Scheduled {cmd} with cron '{cron}'.", "job_id": job.id}
        elif interval:
            def job_func(job_id=None):
                try:
                    print(f"Voice scheduled job (interval) executed: {cmd}")
                    log_job_execution(job.id if job_id is None else job_id, cmd, "interval", interval, "success")
                except Exception as e:
                    log_job_execution(job.id if job_id is None else job_id, cmd, "interval", interval, f"error: {e}")
            job = scheduler.add_job(lambda: job_func(), IntervalTrigger(minutes=interval))
            scheduled_jobs.append({"id": job.id, "cmd": cmd, "trigger": "interval", "value": interval})
            return {"message": f"Scheduled {cmd} every {interval} minutes.", "job_id": job.id}
        else:
            return JSONResponse(content={"error": "Must provide either interval or cron."}, status_code=400)
    except Exception as e:
        return JSONResponse(content={"error": str(e)}, status_code=500)

@app.get("/job-history")
def job_history(n: int = 20):
    try:
        with open(JOB_AUDIT_LOG, "r", encoding="utf-8") as f:
            lines = f.readlines()[-n:]
        entries = [json.loads(line) for line in lines]
        return {"history": entries}
    except Exception as e:
        return {"error": str(e), "history": []}

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8090) 