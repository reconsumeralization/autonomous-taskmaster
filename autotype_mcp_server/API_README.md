# Accessible API & CLI Documentation

## HTTP Endpoints (FastAPI)

### 1. POST /command

- **Description:** Enqueue a remote command for execution.
- **Auth:** Bearer token in `Authorization` header.
- **Body:** `{ "cmd": "audit", "args": [] }`
- **Response:** `{ "status": "ok", "message": "Command audit enqueued." }`

### 2. GET /status

- **Description:** Get current queue size and last command status.
- **Response:**

  ```json
  {
    "queue_size": 0,
    "last_command": {"cmd": "audit", "args": [], "status": 0, "timestamp": 1710000000}
  }
  ```

### 3. GET /health

- **Description:** Get system health (CPU, memory, disk, queue).
- **Response:**

  ```json
  {
    "status": "ok" | "alert",
    "cpu": 12.3,
    "memory": 45.6,
    "disk": 70.1,
    "queue_length": 0,
    "alerts": []
  }
  ```

### 4. WebSocket /ws

- **Description:** Real-time command and status updates.
- **Auth:** First message must be `{ "token": "<your_token>" }`
- **Send:** `{ "cmd": "audit", "args": [] }`
- **Receive:** Status updates and errors as JSON.

### 5. GET /alerts

- **Description:** Get recent critical alerts (last 20, in-memory).
- **Response:**

  ```json
  {
    "alerts": [
      {"msg": "Health Alert: High CPU", "ts": 1710000000},
      ...
    ]
  }
  ```

## CLI Commands

All commands are run as:

```bash
python autotype_mcp_server/src/mcp_server.py <command> [options]
```

### audit

- Run accessibility/code quality audit.
- Example: `python ... mcp_server.py audit --notify --log=audit_log.txt`

### email-intake

- Poll email inbox for new tasks.
- Example: `python ... mcp_server.py email-intake`

### review-tasks

- List, accept, or reject tasks.
- List: `python ... mcp_server.py review-tasks --action list`
- Accept: `python ... mcp_server.py review-tasks --action accept --file <filename>`
- Reject: `python ... mcp_server.py review-tasks --action reject --file <filename>`

### watchdog

- Start self-healing watchdog.
- Example: `python ... mcp_server.py watchdog`

### watchdog-report

- Show recovery events and uptime.
- Example: `python ... mcp_server.py watchdog-report`

### backup-restore

- Backup or restore tasks, config, and logs.
- Backup: `python ... backup_restore.py --backup`
- Restore: `python ... backup_restore.py --restore <backup_zip>`
- List backups: `python ... backup_restore.py --list`

## Security & Roles

- Use tokens from `config.yaml` (`REMOTE_CONTROL_USERS`) for HTTP/WebSocket auth.
- Each token is mapped to a role and allowed commands.

## Health Alerts

- Alerts are sent via TTS, log, email, and webhook if configured in `config.yaml`.

## OpenAPI/Swagger

- Interactive docs: [http://localhost:8080/docs](http://localhost:8080/docs)
- OpenAPI JSON: [http://localhost:8080/openapi.json](http://localhost:8080/openapi.json)

## Desktop Notifications

- Critical alerts (audit/health) trigger Windows desktop notifications (requires win10toast).

## Voice Scheduling (Dashboard & API)

### Dashboard Voice Schedule Button

1. On the dashboard, click the **Voice Schedule** button (🎤) near the "Schedule Recurring Command" section.
2. Speak a command in the format: `schedule <command> every <interval> minutes` (e.g., "schedule audit every 10 minutes").
3. The system will parse your command and schedule it automatically. Feedback is provided via ARIA live region for screen readers.

### API Endpoint: POST /voice-schedule-job

- **Description:** Schedule a recurring job via JSON POST (for remote/voice integration).
- **Body:** `{ "cmd": "audit", "interval": 10 }`
- **Response:** `{ "message": "Scheduled audit every 10 minutes.", "job_id": "..." }`
- **Error:** `{ "error": "..." }`

*This feature is fully accessible and optimized for screen readers and voice navigation.*

## Advanced Recurrence / Cron Scheduling

### Dashboard

- In the "Schedule Recurring Command" section, use the **Advanced (cron)** field to specify a cron expression for flexible scheduling (e.g., `0 9 * * 1` for every Monday at 9am).
- Leave the interval blank to use cron. See [crontab.guru](https://crontab.guru/) for help with cron expressions.

### API

- Both `/schedule-job` and `/voice-schedule-job` accept an optional `cron` field in addition to `interval`.
- If `cron` is provided, it takes precedence over `interval`.
- Example body:

  ```json
  { "cmd": "audit", "cron": "0 9 * * 1" }
  ```

- Response:

  ```json
  { "message": "Scheduled audit with cron '0 9 * * 1'.", "job_id": "..." }
  ```

- Error:

  ```json
  { "error": "Invalid cron expression: ..." }
  ```

*This feature is fully accessible and supports both interval and advanced cron-based scheduling.*

## Job Execution History

### Dashboards

- The "Job History" section displays the last 20 job executions in an accessible table.
- Each entry includes timestamp, command, trigger type, value, and status.
- Fully accessible with ARIA labeling and keyboard navigation.

### API Endpoint: GET /job-history

- **Description:** Returns the last N job executions (default 20).
- **Query parameter:** `n` (optional, default 20)
- **Response:**

  ```json
  {
    "history": [
      {"timestamp": "2024-06-15T12:34:56", "job_id": "...", "cmd": "audit", "trigger": "interval", "value": 10, "status": "success"},
      ...
    ]
  }
  ```

- **Error:** `{ "error": "...", "history": [] }`

*This feature is fully accessible and optimized for screen readers and voice navigation.*

---
*This documentation is optimized for screen readers and accessible navigation. All endpoints and commands are numbered and described concisely.*

### Dashboard Table
