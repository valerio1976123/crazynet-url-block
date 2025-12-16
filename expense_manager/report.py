from __future__ import annotations

import sqlite3
from dataclasses import dataclass


@dataclass(frozen=True)
class CategoryTotal:
    category: str
    total: float


def month_summary(conn: sqlite3.Connection, month: str) -> list[CategoryTotal]:
    # month: YYYY-MM
    cur = conn.execute(
        """
        SELECT COALESCE(category, 'Altro') AS category,
               ROUND(SUM(amount), 2) AS total
        FROM transactions
        WHERE substr(date, 1, 7) = ?
        GROUP BY COALESCE(category, 'Altro')
        ORDER BY total ASC
        """,
        (month,),
    )
    return [CategoryTotal(category=r["category"], total=float(r["total"] or 0.0)) for r in cur.fetchall()]


def month_budget(conn: sqlite3.Connection, month: str) -> dict[str, float]:
    cur = conn.execute("SELECT category, amount FROM budgets WHERE month = ?", (month,))
    return {str(r["category"]): float(r["amount"]) for r in cur.fetchall()}


def set_budget(conn: sqlite3.Connection, month: str, category: str, amount: float) -> None:
    conn.execute(
        "INSERT INTO budgets(month, category, amount) VALUES(?, ?, ?) "
        "ON CONFLICT(month, category) DO UPDATE SET amount=excluded.amount",
        (month, category, amount),
    )
    conn.commit()
