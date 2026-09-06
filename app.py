from datetime import datetime, timezone
from pathlib import Path
import json
import os
from html import escape
from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

from database import fetch_checks, get_db_connection, initialize_database, record_check


PROJECT_ROOT = Path(__file__).resolve().parent
SERVICE_NAME = os.getenv("OPS_TEST_SERVICE_NAME", "ops-test-lab")
STATUS_PATH = PROJECT_ROOT / "logs" / "monitor_status.json"

app = FastAPI(title=SERVICE_NAME)


initialize_database()


@app.get("/health")
def health_check():
    checked_at = datetime.now(timezone.utc).isoformat()
    record_check("ok", checked_at)

    return {
        "status": "ok",
        "service": SERVICE_NAME,
        "time": checked_at,
    }


@app.get("/ready")
def readiness_check():
    try:
        checked_at = datetime.now(timezone.utc).isoformat()

        with get_db_connection() as connection:
            connection.execute(text("SELECT 1"))

        record_check("ready", checked_at)

        return {
            "status": "ready",
            "database": "ok",
        }

    except SQLAlchemyError:
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

    try:
        with get_db_connection() as connection:
            connection.execute(text("SELECT 1"))
        database_label = "正常"
        database_color = "#15803d"
        database_description = "MySQL/SQLite 连接正常"
    except SQLAlchemyError:
        database_label = "异常"
        database_color = "#b91c1c"
        database_description = "数据库连接失败"

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
    monitor_descriptions = {
        "healthy": "最近一次巡检中，所有目标都返回 HTTP 200。",
        "unhealthy": "最近一次巡检至少有一个目标失败，请查看告警。",
        "unknown": "还没有运行 PowerShell 巡检脚本。",
    }
    monitor_description = monitor_descriptions.get(monitor_status, "暂无状态说明。")

    failed_targets = monitor.get("failed_targets", [])
    if not isinstance(failed_targets, list):
        failed_targets = []

    if latest:
        latest_status = {
            "ok": "应用正常",
            "ready": "数据库正常",
        }.get(str(latest["status"]), str(latest["status"]))
        latest_status = escape(latest_status)
        latest_time = escape(str(latest["checked_at"]))
        status_color = "#15803d" if latest["status"] in {"ok", "ready"} else "#b91c1c"
    else:
        latest_status = "暂无记录"
        latest_time = "请先调用 /health 或 /ready"
        status_color = "#6b7280"

    rows = "".join(
        f"<tr><td>{escape(str(item['id']))}</td>"
        f"<td>{escape({'ok': '应用正常', 'ready': '数据库正常'}.get(str(item['status']), str(item['status'])))}</td>"
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
            .metrics {{ display: grid; grid-template-columns: repeat(4, 1fr); gap: 16px; margin-bottom: 20px; }}
            .metric {{ background: white; border-radius: 12px; padding: 18px; box-shadow: 0 2px 8px rgba(0,0,0,.08); }}
            .metric-label {{ color: #6b7280; font-size: 14px; margin-bottom: 8px; }}
            .metric-value {{ font-size: 25px; font-weight: bold; }}
            .metric-description {{ color: #6b7280; font-size: 13px; margin-top: 8px; }}
            .status {{ color: {status_color}; font-size: 30px; font-weight: bold; }}
            .explanation {{ color: #4b5563; line-height: 1.7; }}
            .guide {{ background: #eff6ff; border-left: 4px solid #2563eb; padding: 12px 16px; line-height: 1.7; }}
            table {{ width: 100%; border-collapse: collapse; }}
            th, td {{ padding: 12px; border-bottom: 1px solid #e5e7eb; text-align: left; }}
            th {{ background: #f9fafb; }}
            a {{ margin-right: 16px; color: #2563eb; }}
            .alerts {{ color: #991b1b; background: #fef2f2; padding: 16px 32px; border-radius: 8px; }}
            .alerts li {{ margin: 8px 0; }}
            @media (max-width: 760px) {{ .metrics {{ grid-template-columns: repeat(2, 1fr); }} }}
        </style>
    </head>
    <body>
        <div class="card">
            <h1>Ops Test Lab 监控面板</h1>
            <p class="explanation">这是一个运维巡检结果展示页：PowerShell 脚本负责检查，FastAPI 负责提供接口，数据库负责保存历史记录。</p>
            <p>页面每 30 秒自动刷新。</p>
            <div class="guide">
                <strong>先理解这三个概念：</strong><br>
                当前状态 = 最近一次巡检的总结果；数据库状态 = 应用能否访问数据库；检查记录 = 每次接口检查留下的历史数据。
            </div>
        </div>
        <div class="metrics">
            <div class="metric">
                <div class="metric-label">当前巡检状态</div>
                <div class="metric-value" style="color: {monitor_color}">{monitor_label}</div>
                <div class="metric-description">{escape(monitor_description)}</div>
            </div>
            <div class="metric">
                <div class="metric-label">数据库状态</div>
                <div class="metric-value" style="color: {database_color}">{database_label}</div>
                <div class="metric-description">{escape(database_description)}</div>
            </div>
            <div class="metric">
                <div class="metric-label">最近检查记录</div>
                <div class="metric-value">{len(items)} 条</div>
                <div class="metric-description">最多展示最近 20 条</div>
            </div>
            <div class="metric">
                <div class="metric-label">最近告警数量</div>
                <div class="metric-value" style="color: {'#b91c1c' if alerts else '#15803d'}">{len(alerts)} 条</div>
                <div class="metric-description">来自 logs/alerts.log</div>
            </div>
        </div>
        <div class="card">
            <h2>当前巡检详情</h2>
            <p>当前巡检状态：</p>
            <div class="status" style="color: {monitor_color}">{monitor_label}</div>
            <p>最近巡检时间：{monitor_time}</p>
            <p>最近接口记录：{latest_status}（{latest_time}）</p>
            <h3>失败目标</h3>
            <ul><li>{"</li><li>".join(escape(str(target)) for target in failed_targets) if failed_targets else "暂无失败目标"}</li></ul>
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
            <h2>最近 20 条检查记录（来自数据库）</h2>
            <p class="explanation">每次访问 /health 或 /ready，项目都会把结果写入 service_checks 表。</p>
            <table>
                <thead><tr><th>ID</th><th>状态</th><th>检查时间</th></tr></thead>
                <tbody>{rows}</tbody>
            </table>
        </div>
    </body>
    </html>
    """
