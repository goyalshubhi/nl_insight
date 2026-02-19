"""
db/connector.py — Database connection management.

Creates a SQLAlchemy engine from the URL in config.py.
All other modules get the engine from here — nobody else touches the URL.

Why SQLAlchemy instead of raw psycopg2?
  - Database-agnostic: swap PostgreSQL → SQLite by changing one string in config.py
  - Safe parameter binding built in
  - Connection pooling handled automatically
"""

from sqlalchemy import create_engine, text
from sqlalchemy.exc import OperationalError

import config


def get_engine():
    """
    Create and return a SQLAlchemy engine.

    The engine is lightweight — it doesn't open a connection until you use it.
    Call this once and pass the engine around rather than recreating it.
    """
    engine = create_engine(
        config.DATABASE_URL,
        # Keep a small pool — this is a single-user student app
        pool_size=2,
        max_overflow=2,
    )
    return engine


def test_connection(engine) -> tuple[bool, str]:
    """
    Try a trivial query to confirm the database is reachable.

    Returns:
        (True, "Connected successfully")  on success
        (False, "Error message...")       on failure

    Used at app startup so the user sees a clear error instead of a
    confusing traceback if their PostgreSQL credentials are wrong.
    """
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        return True, "Connected successfully"
    except OperationalError as e:
        # Strip the internal SQLAlchemy boilerplate for a cleaner message
        raw = str(e.orig) if e.orig else str(e)
        return False, f"Database connection failed: {raw}"
    except Exception as e:
        return False, f"Unexpected error: {e}"