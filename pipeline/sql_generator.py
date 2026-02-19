"""
pipeline/sql_generator.py — Natural language → SQL.

This module ties together:
  1. Schema reading    (db/schema_reader.py)
  2. Prompt building   (llm/prompts.py)
  3. LLM call          (llm/gemini_client.py)
  4. Safety validation (pipeline/sql_validator.py)

It returns either a validated SQL string ready to execute,
or raises a clear error explaining why it couldn't.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.schema_reader import format_schema_for_prompt
from llm.prompts import sql_generation_prompt
from llm.gemini_client import call_llm
from pipeline.sql_validator import validate_sql
from logger import log


def generate_sql(question: str, engine) -> str:
    """
    Convert a natural language question into a validated SQL query.

    Args:
        question : The user's plain-English question
        engine   : SQLAlchemy engine (used to read the live schema)

    Returns:
        A validated SQL SELECT string, ready to execute.

    Raises:
        ValueError  : If the LLM cannot answer the question from the schema
        RuntimeError: If the LLM API call fails
    """
    log("NL_QUESTION", question)

    # Step 1 — Read the live database schema
    schema_str = format_schema_for_prompt(engine)
    log("SCHEMA_READ", f"Schema loaded ({len(schema_str)} chars)")

    # Step 2 — Build the prompt
    prompt = sql_generation_prompt(schema_str, question)
    log("PROMPT_BUILT", f"Prompt length: {len(prompt)} chars")

    # Step 3 — Call the LLM
    raw_response = call_llm(prompt)
    log("SQL_RAW", raw_response)

    # Step 4 — Clean up common LLM formatting habits
    # Some models wrap SQL in markdown code blocks even when told not to
    sql = _strip_markdown(raw_response)

    # Step 5 — Validate for safety
    ok, result = validate_sql(sql)
    if not ok:
        raise ValueError(result)

    log("SQL_VALIDATED", result)
    return result


def _strip_markdown(text: str) -> str:
    """
    Remove markdown code block formatting if the LLM added it anyway.

    Handles:
      ```sql          →  remove
      ```postgresql   →  remove
      ```             →  remove

    This is a common LLM habit even when the prompt says not to.
    """
    text = text.strip()

    # Remove opening code fence (with optional language tag)
    if text.startswith("```"):
        lines = text.split("\n")
        # Remove first line (```sql or ```)
        lines = lines[1:]
        # Remove last line if it's a closing ```
        if lines and lines[-1].strip() == "```":
            lines = lines[:-1]
        text = "\n".join(lines).strip()

    return text