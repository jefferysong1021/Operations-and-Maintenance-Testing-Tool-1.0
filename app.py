from datetime import datetime, timezone
from pathlib import Path
import json
import sqlite3
from html import escape
from contextlib import contextmanager
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse


app = FastAPI(title="Ops Test Lab")

PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "ops_test.db"
STATUS_PATH = PROJECT_ROOT / "logs" / "monitor_status.json"


@contextmanager
def get_db_connection():
    connection = sqlite3.connect(DB_PATH)

    try:
        yield connection
    finally:
        connection.close()

def initialize_database():
    with get_db_connection() as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS service_checks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                status TEXT NOT NULL,
                checked_at TEXT NOT NULL
            )
            """
        )
        connection.commit()


initialize_database()


def record_check(status: str, checked_at: str) -> bool:
    try:
        with get_db_connection() as connection:
            connection.execute(
                "INSERT INTO service_checks (status, checked_at) VALUES (?, ?)",
                (status, checked_at),
            )
            connection.commit()
        return True
    except sqlite3.Error:
        return False


@app.get("/health")
def health_check():
    checked_at = datetime.now(timezone.utc).isoformat()
    record_check("ok", checked_at)

    return {
        "status": "ok",
        "service": "ops-test-lab",
        "time": checked_at,
    }


@app.get("/ready")
def readiness_check():
    try:
        checked_at = datetime.now(timezone.utc).isoformat()

        with get_db_connection() as connection:
            connection.execute("SELECT 1")

        record_check("ready", checked_at)

        return {
            "status": "ready",
            "database": "ok",
        }

    except sqlite3.Error:
        return JSONResponse(
            status_code=503,
            content={
                "status": "not_ready",
                "database": "error",
            },
        )


@app.get("/checks")
def list_checks(limit: int = Query(default=20, ge=1, le=100)):
    items = fetch_checks(limit)

    return {
        "count": len(items),
        "items": items,
    }


def fetch_checks(limit: int) -> list[dict[str, object]]:
    with get_db_connection() as connection:
        rows = connection.execute(
            """
            SELECT id, status, checked_at
            FROM service_checks
            ORDER BY id DESC
            LIMIT ?
            """,
            (limit,),
        ).fetchall()

    return [
        {
            "id": row[0],
            "status": row[1],
            "checked_at": row[2],
        }
        for row in rows
    ]


def read_log_lines(path: Path, limit: int) -> list[str]:
    if not path.exists():
        return []

    content = None
    for encoding in ("utf-8", "utf-16"):
        try:
            content = path.read_text(encoding=encoding)
            break
        except UnicodeError:
            continue

    if content is None:
        return []

    lines = [line.strip() for line in content.splitlines() if line.strip()]
    return list(reversed(lines[-limit:]))


def fetch_alerts(limit: int) -> list[str]:
    alert_path = PROJECT_ROOT / "logs" / "alerts.log"
    return read_log_lines(alert_path, limit)


def read_monitor_status() -> dict[str, object]:
    default_status = {
        "status": "unknown",
        "checked_at": None,
        "failed_targets": [],
    }

    if not STATUS_PATH.exists():
        return default_status

    for encoding in ("utf-8-sig", "utf-16"):
        try:
            data = json.loads(STATUS_PATH.read_text(encoding=encoding))
            if isinstance(data, dict):
                return {
                    "status": data.get("status", "unknown"),
                    "checked_at": data.get("checked_at"),
                    "failed_targets": data.get("failed_targets", []),
                }
        except (UnicodeError, json.JSONDecodeError):
            continue

    return default_status


@app.get("/alerts")
def list_alerts(limit: int = Query(default=20, ge=1, le=100)):
    items = fetch_alerts(limit)

    return {
        "count": len(items),
        "items": items,
    }


@app.get("/summary")
def summary():
    monitor = read_monitor_status()

    return {
        "current_status": monitor["status"],
        "checked_at": monitor["checked_at"],
        "failed_targets": monitor["failed_targets"],
        "recent_alert_count": len(fetch_alerts(20)),
    }


@app.get("/dashboard", response_class=HTMLResponse)
def dashboard():
    items = fetch_checks(20)
    alerts = fetch_alerts(10)
    monitor = read_monitor_status()
    latest = items[0] if items else None

    monitor_labels = {
        "healthy": "正常",
        "unhealthy": "异常",
        "unknown": "未知",
    }
    monitor_status = str(monitor["status"])
    monitor_label = monitor_labels.get(monitor_status, "未知")
    monitor_time = escape(str(monitor["checked_at"] or "暂无巡检记录"))
    monitor_color = {
        "healthy": "#15803d",
        "unhealthy": "#b91c1c",
    }.get(monitor_status, "#6b7280")

    if latest:
        latest_status = escape(str(latest["status"]))
        latest_time = escape(str(latest["checked_at"]))
        status_color = "#15803d" if latest["status"] in {"ok", "ready"} else "#b91c1c"
    else:
        latest_status = "暂无记录"
        latest_time = "请先调用 /health 或 /ready"
        status_color = "#6b7280"

    rows = "".join(
        f"<tr><td>{escape(str(item['id']))}</td>"
        f"<td>{escape(str(item['status']))}</td>"
        f"<td>{escape(str(item['checked_at']))}</td></tr>"
        for item in items
    )

    if not rows:
        rows = '<tr><td colspan="3">暂无检查记录</td></tr>'

    alert_rows = "".join(
        f"<li>{escape(alert)}</li>"
        for alert in alerts
    )

    if not alert_rows:
        alert_rows = "<li>暂无告警</li>"

    return f"""
    <!doctype html>
    <html lang="zh-CN">
    <head>
        <meta charset="utf-8">
        <meta name="viewport" content="width=device-width, initial-scale=1">
        <meta http-equiv="refresh" content="30">
        <title>Ops Test Lab Dashboard</title>
        <style>
            body {{
                max-width: 960px;
                margin: 40px auto;
                padding: 0 20px;
                font-family: Arial, sans-serif;
                color: #1f2937;
                background: #f3f4f6;
            }}
            .card {{
                background: white;
                border-radius: 12px;
                padding: 24px;
                margin-bottom: 20px;
                box-shadow: 0 2px 8px rgba(0,0,0,.08);
            }}
            .status {{ color: {status_color}; font-size: 30px; font-weight: bold; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: left; }}
            th {{ background: #f9fafb; }}
            a {{ margin-right: 16px; color: #2563eb; }}
            .alerts {{ color: #991b1b; background: #fef2f2; padding: 16px 32px; border-radius: 8px; }}
            .alerts li {{ margin: 8px 0; }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Ops Test Lab 监控面板</h1>
            <p>页面每 30 秒自动刷新。</p>
            <p>当前巡检状态：</p>
            <div class="status" style="color: {monitor_color}">{monitor_label}</div>
            <p>最近巡检时间：{monitor_time}</p>
            <p>最近接口记录：{latest_status}（{latest_time}）</p>
            <a href="/health">执行健康检查</a>
            <a href="/ready">执行数据库检查</a>
            <a href="/checks">查看 JSON</a>
            <a href="/alerts">查看告警 JSON</a>
            <a href="/summary">查看状态摘要</a>
            <a href="/docs">接口文档</a>
        </div>
        <div class="card alerts">
            <h2>最近告警</h2>
            <ul>{alert_rows}</ul>
        </div>
        <div class="card">
            <h2>最近 20 条检查记录</h2>
            <table>
                <thead><tr><th>ID</th><th>状态</th><th>检查时间</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </body>
    </html>
    """
