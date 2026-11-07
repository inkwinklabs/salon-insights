"""
All database code lives in this one file.

Why one file? If the app goes online later and moves from SQLite to a hosted
database, this is the only file that has to change.

Two separate database files keep demo data and real data apart:
    data/salon.db : the salon's REAL customers and visits
    data/demo.db  : made-up sample data for trying the app
Which one is in use (the "mode") is saved in data/mode.txt.
"""

import sqlite3
from contextlib import contextmanager
from pathlib import Path

from settings import BASE_DIR

DATA_DIR = BASE_DIR / "data"
REAL_DB = DATA_DIR / "salon.db"
DEMO_DB = DATA_DIR / "demo.db"
MODE_FILE = DATA_DIR / "mode.txt"

# The two modes and the database file each one uses.
DB_FILES = {"real": REAL_DB, "demo": DEMO_DB}

# The tables. "IF NOT EXISTS" means this is safe to run every time we connect.
SCHEMA = """
-- One row per person. The phone number identifies them,
-- because two different customers can share a name.
CREATE TABLE IF NOT EXISTS customers (
    id          INTEGER PRIMARY KEY,
    name        TEXT NOT NULL,
    phone       TEXT NOT NULL UNIQUE,      -- 10 digits, no spaces
    created_at  TEXT NOT NULL DEFAULT (date('now'))
);

-- One row per visit. We store the service NAME and the PRICE PAID on the visit
-- itself (not a link to settings.toml), so history stays correct when prices
-- or service names change later.
CREATE TABLE IF NOT EXISTS visits (
    id           INTEGER PRIMARY KEY,
    customer_id  INTEGER NOT NULL REFERENCES customers(id) ON DELETE CASCADE,
    service      TEXT    NOT NULL,
    price        INTEGER NOT NULL CHECK (price >= 0),   -- whole rupees
    visit_date   TEXT    NOT NULL,                      -- 'YYYY-MM-DD'
    staff        TEXT    NOT NULL,
    created_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- Indexes are like a book's index: they make lookups by customer or date fast.
CREATE INDEX IF NOT EXISTS idx_visits_customer ON visits(customer_id);
CREATE INDEX IF NOT EXISTS idx_visits_date     ON visits(visit_date);
"""


# ---------------------------------------------------------------- mode

def get_mode() -> str:
    """'real' or 'demo'. Defaults to 'real', so a salon never opens on fake data by surprise."""
    try:
        mode = MODE_FILE.read_text(encoding="utf-8").strip()
    except FileNotFoundError:
        return "real"
    return mode if mode in DB_FILES else "real"


def set_mode(mode: str) -> None:
    if mode not in DB_FILES:
        raise ValueError(f"Unknown mode: {mode!r} (use 'real' or 'demo')")
    DATA_DIR.mkdir(exist_ok=True)
    MODE_FILE.write_text(mode, encoding="utf-8")


# ---------------------------------------------------------------- connecting

@contextmanager
def open_db(path: Path | None = None):
    """Open a database, hand it over, then save and close it.

    Use it like this:
        with open_db() as conn:
            conn.execute("SELECT ...")

    With no path it opens the database for the current mode (real or demo).
    """
    path = path or DB_FILES[get_mode()]
    DATA_DIR.mkdir(exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row             # rows behave like dicts: row["name"]
    conn.execute("PRAGMA foreign_keys = ON")   # SQLite needs this to enforce links
    conn.executescript(SCHEMA)
    try:
        yield conn
        conn.commit()                          # save changes if nothing went wrong
    finally:
        conn.close()


# ---------------------------------------------------------------- demo data

def clear_demo() -> None:
    """Empty the DEMO database. It can never touch the real one."""
    path = DEMO_DB
    assert path != REAL_DB, "Safety stop: clear_demo must never touch the real database"
    with open_db(path) as conn:
        conn.execute("DELETE FROM visits")
        conn.execute("DELETE FROM customers")


# ---------------------------------------------------------------- customers and visits

def find_customer_by_phone(phone: str) -> dict | None:
    """The customer with this phone number (plus visit count and last visit), or None."""
    with open_db() as conn:
        row = conn.execute(
            """
            SELECT c.id, c.name,
                   COUNT(DISTINCT v.visit_date) AS visits,   -- same day = one visit
                   MAX(v.visit_date)            AS last_visit
            FROM customers c
            LEFT JOIN visits v ON v.customer_id = c.id
            WHERE c.phone = ?
            GROUP BY c.id
            """,
            (phone,),
        ).fetchone()
    return dict(row) if row else None


def add_visit(visit: dict) -> dict:
    """Save one service line. Creates the customer first if the phone is new.

    visit: phone, name, service, price, visit_date, staff (already checked).
    A returning customer keeps their saved name, so a mistyped phone number
    can't rename somebody else.
    """
    with open_db() as conn:
        found = conn.execute(
            "SELECT id, name FROM customers WHERE phone = ?", (visit["phone"],)
        ).fetchone()
        if found:
            customer_id, name, is_new = found["id"], found["name"], False
        else:
            customer_id = conn.execute(
                "INSERT INTO customers (name, phone, created_at) VALUES (?, ?, ?)",
                (visit["name"], visit["phone"], visit["visit_date"]),
            ).lastrowid
            name, is_new = visit["name"], True

        visit_id = conn.execute(
            "INSERT INTO visits (customer_id, service, price, visit_date, staff) "
            "VALUES (?, ?, ?, ?, ?)",
            (customer_id, visit["service"], visit["price"], visit["visit_date"], visit["staff"]),
        ).lastrowid
    return {"visit_id": visit_id, "customer_id": customer_id, "name": name, "new_customer": is_new}


def customer_visit_rows() -> list[dict]:
    """Every customer with every service line, in order. analysis.py turns this into stats."""
    with open_db() as conn:
        rows = conn.execute(
            """
            SELECT c.id, c.name, c.phone, v.visit_date, v.service, v.price
            FROM customers c
            LEFT JOIN visits v ON v.customer_id = c.id
            ORDER BY c.id, v.visit_date, v.id
            """
        ).fetchall()
    return [dict(r) for r in rows]


def visit_lines() -> list[dict]:
    """Every service line (no names or phones), oldest first. Used by the dashboard."""
    with open_db() as conn:
        rows = conn.execute(
            "SELECT customer_id, visit_date, service, price FROM visits ORDER BY visit_date, id"
        ).fetchall()
    return [dict(r) for r in rows]


def visits_for_customer(customer_id: int) -> list[dict]:
    """One customer's history, newest first."""
    with open_db() as conn:
        rows = conn.execute(
            "SELECT visit_date, service, price, staff FROM visits "
            "WHERE customer_id = ? ORDER BY visit_date DESC, id DESC",
            (customer_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ---------------------------------------------------------------- summaries

def summary_counts() -> dict:
    """A few headline numbers for the current mode: proof the data is there."""
    with open_db() as conn:
        row = conn.execute(
            """
            SELECT
              (SELECT COUNT(*) FROM customers)        AS customers,
              COUNT(*)                                AS visits,
              COALESCE(SUM(price), 0)                 AS revenue,
              MIN(visit_date)                         AS first_visit,
              MAX(visit_date)                         AS last_visit
            FROM visits
            """
        ).fetchone()
    return dict(row)
