"""Shared pytest fixtures for sqlite-checkpoint tests."""

import sqlite3

import pytest


@pytest.fixture()
def wal_db(tmp_path):
    """Create a WAL-mode SQLite database with sample data."""
    db_path = tmp_path / "test.db"
    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("CREATE TABLE items (id INTEGER PRIMARY KEY, name TEXT)")
    conn.execute("INSERT INTO items (name) VALUES ('alpha')")
    conn.execute("INSERT INTO items (name) VALUES ('bravo')")
    conn.commit()
    conn.close()
    return db_path
