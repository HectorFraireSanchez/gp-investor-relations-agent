import sqlite3
from contextlib import closing


from backend.paths import DB_PATH


def get_connection():
    connection = sqlite3.connect(DB_PATH)
    connection.row_factory = sqlite3.Row
    return connection


def list_investors() -> list[dict]:
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT investor_id, name, investor_type
            FROM investors
            ORDER BY name, investor_id
            """
        ).fetchall()
    return [dict(row) for row in rows]


def find_investor(name: str) -> dict | None:
    with closing(get_connection()) as connection:
        row = connection.execute(
            """
            SELECT investor_id, name, investor_type
            FROM investors
            WHERE lower(name) LIKE ?
            LIMIT 1
            """,
            (f"%{name.lower()}%",),
        ).fetchone()

    return dict(row) if row else None


def get_positions(investor_id: str) -> list[dict]:
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT investor_id, fund, commitment, contributed, unfunded
            FROM positions
            WHERE investor_id = ?
            """,
            (investor_id,),
        ).fetchall()

    return [dict(row) for row in rows]


def get_capital_calls(investor_id: str) -> list[dict]:
    with closing(get_connection()) as connection:
        rows = connection.execute(
            """
            SELECT call_id, investor_id, fund, amount, due_date, status
            FROM capital_calls
            WHERE investor_id = ?
            """,
            (investor_id,),
        ).fetchall()

    return [dict(row) for row in rows]
