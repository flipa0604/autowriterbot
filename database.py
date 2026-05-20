import sqlite3
from contextlib import contextmanager
from datetime import datetime
from typing import Optional

from config import DB_PATH, DEFAULT_MESSAGE, DEFAULT_TIME, DEFAULT_WORKDAYS


@contextmanager
def get_conn():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def init_db():
    with get_conn() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS employees (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                identifier TEXT NOT NULL UNIQUE,  -- @username yoki +998...
                ism TEXT NOT NULL,                -- {ism} uchun
                active INTEGER NOT NULL DEFAULT 1,
                added_at TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            );

            CREATE TABLE IF NOT EXISTS send_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id INTEGER,
                identifier TEXT NOT NULL,
                sent_at TEXT NOT NULL,
                status TEXT NOT NULL,   -- ok | error
                error TEXT
            );

            CREATE TABLE IF NOT EXISTS pause_ranges (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                start_date TEXT NOT NULL,   -- YYYY-MM-DD
                end_date TEXT NOT NULL,     -- YYYY-MM-DD
                created_at TEXT NOT NULL
            );
        """)

        defaults = {
            "message": DEFAULT_MESSAGE,
            "send_time": DEFAULT_TIME,
            "workdays": DEFAULT_WORKDAYS,
            "paused": "0",
        }
        for k, v in defaults.items():
            conn.execute(
                "INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)",
                (k, v),
            )


# ---------- settings ----------

def get_setting(key: str) -> Optional[str]:
    with get_conn() as conn:
        row = conn.execute(
            "SELECT value FROM settings WHERE key = ?", (key,)
        ).fetchone()
        return row["value"] if row else None


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) "
            "ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, value),
        )


# ---------- employees ----------

def add_employee(identifier: str, ism: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO employees (identifier, ism, active, added_at) "
            "VALUES (?, ?, 1, ?)",
            (identifier, ism, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def remove_employee(identifier_or_id: str) -> int:
    with get_conn() as conn:
        if identifier_or_id.isdigit():
            cur = conn.execute(
                "DELETE FROM employees WHERE id = ?", (int(identifier_or_id),)
            )
        else:
            cur = conn.execute(
                "DELETE FROM employees WHERE identifier = ?", (identifier_or_id,)
            )
        return cur.rowcount


def list_employees(only_active: bool = False) -> list[sqlite3.Row]:
    with get_conn() as conn:
        sql = "SELECT * FROM employees"
        if only_active:
            sql += " WHERE active = 1"
        sql += " ORDER BY id"
        return conn.execute(sql).fetchall()


def find_employee(identifier: str) -> Optional[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM employees WHERE identifier = ?", (identifier,)
        ).fetchone()


def set_employee_active(identifier: str, active: bool) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE employees SET active = ? WHERE identifier = ?",
            (1 if active else 0, identifier),
        )
        return cur.rowcount


# ---------- send log ----------

def log_send(employee_id: Optional[int], identifier: str, status: str, error: Optional[str] = None):
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO send_log (employee_id, identifier, sent_at, status, error) "
            "VALUES (?, ?, ?, ?, ?)",
            (employee_id, identifier, datetime.utcnow().isoformat(), status, error),
        )


def recent_logs(limit: int = 20) -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM send_log ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()


# ---------- pause ranges ----------

def add_pause_range(start_date: str, end_date: str) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO pause_ranges (start_date, end_date, created_at) "
            "VALUES (?, ?, ?)",
            (start_date, end_date, datetime.utcnow().isoformat()),
        )
        return cur.lastrowid


def list_pause_ranges() -> list[sqlite3.Row]:
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM pause_ranges ORDER BY start_date"
        ).fetchall()


def remove_pause_range(range_id: int) -> int:
    with get_conn() as conn:
        cur = conn.execute(
            "DELETE FROM pause_ranges WHERE id = ?", (range_id,)
        )
        return cur.rowcount


def find_pause_for_date(date_str: str) -> Optional[sqlite3.Row]:
    """Returns the matching range if date falls within any pause range."""
    with get_conn() as conn:
        return conn.execute(
            "SELECT * FROM pause_ranges "
            "WHERE start_date <= ? AND end_date >= ? "
            "ORDER BY start_date LIMIT 1",
            (date_str, date_str),
        ).fetchone()
