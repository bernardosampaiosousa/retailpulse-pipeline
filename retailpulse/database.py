"""SQLite storage with idempotent upserts and explicit schema management."""

from contextlib import contextmanager
from dataclasses import astuple
from pathlib import Path
import sqlite3
from typing import Iterator

from .models import Transaction


SCHEMA = """
CREATE TABLE IF NOT EXISTS transactions (
    transaction_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL,
    customer_id TEXT NOT NULL,
    ordered_at TEXT NOT NULL,
    country TEXT NOT NULL,
    category TEXT NOT NULL,
    quantity INTEGER NOT NULL CHECK (quantity BETWEEN 1 AND 1000),
    unit_price_cents INTEGER NOT NULL CHECK (unit_price_cents BETWEEN 1 AND 10000000),
    status TEXT NOT NULL CHECK (status IN ('PAID', 'REFUNDED', 'CANCELLED'))
);
CREATE INDEX IF NOT EXISTS idx_transactions_month_country
    ON transactions(ordered_at, country);
"""

FIELDS = (
    "transaction_id", "order_id", "customer_id", "ordered_at", "country",
    "category", "quantity", "unit_price_cents", "status",
)


@contextmanager
def database(path: Path) -> Iterator[sqlite3.Connection]:
    """Opens SQLite with the expected tables and closes it after use."""
    path.parent.mkdir(parents=True, exist_ok=True)
    connection = sqlite3.connect(path)
    try:
        connection.execute("PRAGMA foreign_keys = ON")
        connection.executescript(SCHEMA)
        yield connection
    finally:
        connection.close()


def save_transaction(connection: sqlite3.Connection, item: Transaction) -> str:
    """Uses transaction IDs to update corrected sales without inserting duplicates."""
    existing = connection.execute(
        "SELECT " + ", ".join(FIELDS) + " FROM transactions WHERE transaction_id = ?",
        (item.transaction_id,),
    ).fetchone()
    values = astuple(item)
    if existing == values:
        return "unchanged"
    if existing is None:
        connection.execute(
            "INSERT INTO transactions (" + ", ".join(FIELDS) + ") VALUES (" + ", ".join("?" for _ in FIELDS) + ")",
            values,
        )
        return "inserted"
    connection.execute(
        "UPDATE transactions SET " + ", ".join(f"{key} = ?" for key in FIELDS[1:]) + " WHERE transaction_id = ?",
        (*values[1:], item.transaction_id),
    )
    return "updated"
