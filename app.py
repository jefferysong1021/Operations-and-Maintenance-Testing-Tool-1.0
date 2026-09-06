from datetime import datetime, timezone
from pathlib import Path
import sqlite3
from contextlib import contextmanager
from fastapi import FastAPI, Query
from fastapi.responses import JSONResponse


app = FastAPI(title="Ops Test Lab")

PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "ops_test.db"


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

    items = [
        {
            "id": row[0],
            "status": row[1],
            "checked_at": row[2],
        }
        for row in rows
    ]

    return {
        "count": len(items),
        "items": items,
    }
