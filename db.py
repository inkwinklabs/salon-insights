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
