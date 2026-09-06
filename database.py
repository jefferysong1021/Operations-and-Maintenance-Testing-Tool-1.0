from contextlib import contextmanager
from pathlib import Path
import os
import sqlite3


PROJECT_ROOT = Path(__file__).resolve().parent
configured_db_path = os.getenv("OPS_TEST_DB_PATH")
DB_PATH = Path(configured_db_path) if configured_db_path else PROJECT_ROOT / "ops_test.db"
if not DB_PATH.is_absolute():
    DB_PATH = PROJECT_ROOT / DB_PATH


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
