import sqlite3
from contextlib import closing
from pathlib import Path


DB_PATH = Path(__file__).parent / "data" / "northstar.db"

SCHEMA_AND_DATA = """
CREATE TABLE investors (
    investor_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    investor_type TEXT NOT NULL
);

CREATE TABLE positions (
    investor_id TEXT NOT NULL,
    fund TEXT NOT NULL,
    commitment REAL NOT NULL,
    contributed REAL NOT NULL,
    unfunded REAL NOT NULL
);

CREATE TABLE capital_calls (
    call_id TEXT PRIMARY KEY,
    investor_id TEXT NOT NULL,
    fund TEXT NOT NULL,
    amount REAL NOT NULL,
    due_date TEXT NOT NULL,
    status TEXT NOT NULL
);

INSERT INTO investors VALUES
    ('INV-001', 'Redwood Family Office', 'Family Office'),
    ('INV-002', 'Beacon University Endowment', 'Endowment'),
    ('INV-003', 'Atlas Pension Fund', 'Pension Fund');

INSERT INTO positions VALUES
    ('INV-001', 'Northstar Growth Fund II', 5000000, 3750000, 1250000),
    ('INV-002', 'Northstar Growth Fund II', 8000000, 6500000, 1500000);

INSERT INTO capital_calls VALUES
    ('CC-019', 'INV-001', 'Northstar Growth Fund II', 250000, '2026-09-30', 'Outstanding'),
    ('CC-020', 'INV-002', 'Northstar Growth Fund II', 400000, '2026-09-25', 'Paid');
"""


def main():
    if DB_PATH.exists():
        DB_PATH.unlink()

    DB_PATH.parent.mkdir(exist_ok=True)

    with closing(sqlite3.connect(DB_PATH)) as connection:
        connection.executescript(SCHEMA_AND_DATA)

    print(f"Created database: {DB_PATH}")


if __name__ == "__main__":
    main()
