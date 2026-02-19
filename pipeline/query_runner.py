"""
pipeline/query_runner.py — Execute validated SQL → Pandas DataFrame.

This module only runs SQL that has already passed sql_validator.py.
It enforces one final safety measure: statement_timeout on PostgreSQL
so a slow query cannot hang the app indefinitely.

Why Pandas?
  Once data is in a DataFrame, all the EDA and visualisation modules
  can work on it without knowing anything about the database.
  The database connection is only needed for this one step.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError

import config
from logger import log


def run_query(sql: str, engine) -> pd.DataFrame:
    """
    Execute a validated SQL query and return results as a DataFrame.

    Args:
        sql    : A validated SELECT query (from sql_generator.py)
        engine : SQLAlchemy engine

    Returns:
        pandas DataFrame with query results.
        Empty DataFrame if query returns no rows (not an error).

    Raises:
        RuntimeError: If the query fails at the database level
                      (e.g. column doesn't exist, syntax error slipped through)
    """
    log("EXECUTION_START", sql)

    try:
        with engine.connect() as conn:
            # Set a 30-second timeout on PostgreSQL so slow queries don't hang the UI
            # This only works on PostgreSQL — silently skipped on SQLite
            try:
                conn.execute(text("SET statement_timeout = '30s'"))
            except Exception:
                pass   # SQLite doesn't support this — that's fine

            df = pd.read_sql(text(sql), conn)

        row_count = len(df)
        col_count = len(df.columns)
        log("EXECUTION_DONE", f"Returned {row_count} rows × {col_count} columns")

        if row_count == 0:
            log("EXECUTION_DONE", "Query returned 0 rows")

        # Warn if we hit the row limit — the user may want to know results are truncated
        if row_count >= config.QUERY_ROW_LIMIT:
            log("EXECUTION_WARN", f"Hit row limit ({config.QUERY_ROW_LIMIT}). Results may be truncated.")

        return df

    except SQLAlchemyError as e:
        # Clean up the SQLAlchemy error message for display
        msg = str(e.orig) if hasattr(e, "orig") and e.orig else str(e)
        log("EXECUTION_ERROR", msg)
        raise RuntimeError(
            f"Query execution failed: {msg}\n\n"
            f"This sometimes happens when the generated SQL references a column "
            f"that doesn't exist. Try rephrasing your question."
        ) from e

    except Exception as e:
        log("EXECUTION_ERROR", str(e))
        raise RuntimeError(f"Unexpected error during query execution: {e}") from e