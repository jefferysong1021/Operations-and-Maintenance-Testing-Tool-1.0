from datetime import datetime, timezone
from pathlib import Path
import sqlite3

from fastapi import FastAPI
from fastapi.responses import JSONResponse


app = FastAPI(title="Ops Test Lab")

PROJECT_ROOT = Path(__file__).resolve().parent
DB_PATH = PROJECT_ROOT / "ops_test.db"


def get_db_connection():
    return sqlite3.connect(DB_PATH)


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


@app.get("/health")
def health_check():
    return {
        "status": "ok",
        "service": "ops-test-lab",
        "time": datetime.now(timezone.utc).isoformat(),
    }


@app.get("/ready")
def readiness_check():
    try:
        with get_db_connection() as connection:
            connection.execute("SELECT 1")

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