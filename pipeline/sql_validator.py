"""
pipeline/sql_validator.py — SQL safety checks.

This runs BEFORE any query touches the database.
If validation fails, execution is blocked entirely.

Why is this important?
  Even though we prompt the LLM to only write SELECT queries,
  we cannot trust the LLM's output blindly. A badly-worded question
  or a prompt injection attempt could produce dangerous SQL.
  This module is the hard safety net.

Design: simple keyword matching — easy to explain, hard to bypass.
"""

import re
import config
from logger import log


def validate_sql(sql: str) -> tuple[bool, str]:
    """
    Check whether a SQL string is safe to execute.

    Checks performed (in order):
      1. Not empty
      2. Not the CANNOT_ANSWER signal from the LLM
      3. Must start with SELECT
      4. Must not contain any blocked keywords
      5. Must not contain multiple statements (no semicolons mid-query)
      6. Must not contain SQL comments (-- or /* */) — common injection vectors

    Args:
        sql: The raw SQL string returned by the LLM

    Returns:
        (True,  cleaned_sql)      if safe to execute
        (False, "reason string")  if blocked

    Usage:
        ok, result = validate_sql(raw_sql)
        if ok:
            run_query(result)   # result is the cleaned SQL
        else:
            show_error(result)  # result is the reason it was blocked
    """
    if not sql or not sql.strip():
        log("VALIDATION", "BLOCKED — empty SQL returned by LLM")
        return False, "The model returned an empty response. Please rephrase your question."

    sql_clean = sql.strip()

    # ── Check for CANNOT_ANSWER signal ────────────────────────────────────────
    if sql_clean.upper().startswith("CANNOT_ANSWER"):
        log("VALIDATION", "BLOCKED — LLM signalled CANNOT_ANSWER")
        return False, (
            "This question cannot be answered from the available data. "
            "Try asking about customers, products, orders, or order items."
        )

    # ── Must start with SELECT ─────────────────────────────────────────────────
    # Strip leading whitespace and check first word
    first_word = sql_clean.split()[0].upper()
    if first_word != "SELECT":
        log("VALIDATION", f"BLOCKED — query starts with '{first_word}', not SELECT")
        return False, (
            f"Safety check failed: query must start with SELECT, "
            f"but got '{first_word}'. Only read-only queries are allowed."
        )

    # ── Check for blocked keywords ─────────────────────────────────────────────
    # Use word-boundary regex so "DELETED_AT" column doesn't trigger "DELETE"
    sql_upper = sql_clean.upper()
    for keyword in config.BLOCKED_SQL_KEYWORDS:
        pattern = r'\b' + re.escape(keyword) + r'\b'
        if re.search(pattern, sql_upper):
            log("VALIDATION", f"BLOCKED — dangerous keyword found: {keyword}")
            return False, (
                f"Safety check failed: query contains forbidden keyword '{keyword}'. "
                f"Only SELECT queries are permitted."
            )

    # ── Block multiple statements ──────────────────────────────────────────────
    # A semicolon followed by any non-whitespace = second statement
    # We allow a trailing semicolon (harmless) but not "SELECT ...; DROP ..."
    statements = [s.strip() for s in sql_clean.split(";") if s.strip()]
    if len(statements) > 1:
        log("VALIDATION", "BLOCKED — multiple SQL statements detected")
        return False, (
            "Safety check failed: query contains multiple statements. "
            "Only a single SELECT query is allowed."
        )

    # ── Block SQL comments ─────────────────────────────────────────────────────
    if "--" in sql_clean or "/*" in sql_clean:
        log("VALIDATION", "BLOCKED — SQL comments detected")
        return False, (
            "Safety check failed: query contains SQL comments. "
            "Please ask your question in plain English."
        )

    # ── All checks passed ──────────────────────────────────────────────────────
    # Remove trailing semicolon if present — SQLAlchemy doesn't need it
    final_sql = sql_clean.rstrip(";").strip()
    log("VALIDATION", f"PASSED — {final_sql[:100]}")
    return True, final_sql