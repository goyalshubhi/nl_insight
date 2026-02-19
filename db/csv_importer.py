"""
db/csv_importer.py — Convert uploaded files to a queryable database.

Supports CSV and Excel files. Creates a temporary in-memory SQLite database
that exists only for the current session.

Why this matters for demos:
  Non-technical users can upload their own data and start asking questions
  immediately — no PostgreSQL installation, no connection strings, no setup.

Privacy note:
  The database exists only in memory and is destroyed when the session ends.
  No data is persisted to disk.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from sqlalchemy import create_engine, inspect
import streamlit as st

from logger import log


def create_engine_from_file(uploaded_file) -> tuple:
    """
    Convert an uploaded CSV or Excel file into a temporary SQLite database.

    Args:
        uploaded_file: Streamlit UploadedFile object (from st.file_uploader)

    Returns:
        (engine, table_name, row_count)
        - engine: SQLAlchemy engine connected to in-memory SQLite DB
        - table_name: name of the created table
        - row_count: number of rows loaded

    Raises:
        ValueError: if file format is unsupported or parsing fails
    """
    filename = uploaded_file.name.lower()

    # Step 1 — Read the file into a DataFrame
    try:
        if filename.endswith('.csv'):
            df = pd.read_csv(uploaded_file)
            log("CSV_UPLOAD", f"Read {len(df)} rows from {uploaded_file.name}")
        
        elif filename.endswith(('.xlsx', '.xls')):
            # For Excel, read the first sheet by default
            df = pd.read_excel(uploaded_file, sheet_name=0)
            log("EXCEL_UPLOAD", f"Read {len(df)} rows from {uploaded_file.name}")
        
        else:
            raise ValueError(
                f"Unsupported file type: {filename}. "
                "Please upload a .csv, .xlsx, or .xls file."
            )

    except Exception as e:
        log("FILE_READ_ERROR", str(e))
        raise ValueError(f"Failed to read file: {e}") from e

    # Step 2 — Basic validation
    if df.empty:
        raise ValueError("The uploaded file is empty. Please upload a file with data.")

    if len(df.columns) == 0:
        raise ValueError("The file has no columns. Please check the file format.")

    # Clean column names — remove spaces, special chars, convert to lowercase
    # This prevents SQL injection via column names and makes queries easier
    df.columns = [
        _clean_column_name(col) for col in df.columns
    ]

    # Check for duplicate column names after cleaning
    if len(df.columns) != len(set(df.columns)):
        raise ValueError(
            "The file has duplicate column names after cleaning. "
            "Please ensure all column headers are unique."
        )

    # Step 3 — Create in-memory SQLite database
    # :memory: means the DB exists only in RAM, never touches disk
    engine = create_engine("sqlite:///:memory:")

    # Derive table name from filename (cleaned)
    table_name = _clean_column_name(
        uploaded_file.name.rsplit('.', 1)[0]  # remove extension
    )

    # Step 4 — Load DataFrame into the database
    df.to_sql(
        table_name,
        engine,
        index=False,          # don't create an index column
        if_exists='replace',  # replace if called multiple times in same session
    )

    log("SQLITE_CREATED", f"Created table '{table_name}' with {len(df)} rows, {len(df.columns)} columns")

    return engine, table_name, len(df)


def _clean_column_name(name: str) -> str:
    """
    Clean a column name to make it safe for SQL.

    Transformations:
      - Convert to lowercase
      - Replace spaces and hyphens with underscores
      - Remove all non-alphanumeric chars except underscores
      - Ensure it starts with a letter (prepend 'col_' if needed)

    Examples:
      "Customer Name"     → "customer_name"
      "Sales ($)"         → "sales"
      "2024 Revenue"      → "col_2024_revenue"
      "First-Name"        → "first_name"
    """
    import re

    # Lowercase and replace spaces/hyphens
    cleaned = name.lower().replace(' ', '_').replace('-', '_')

    # Remove all non-alphanumeric except underscores
    cleaned = re.sub(r'[^a-z0-9_]', '', cleaned)

    # Remove consecutive underscores
    cleaned = re.sub(r'_+', '_', cleaned)

    # Strip leading/trailing underscores
    cleaned = cleaned.strip('_')

    # If empty or starts with a number, prepend 'col_'
    if not cleaned or cleaned[0].isdigit():
        cleaned = f"col_{cleaned}"

    return cleaned


def validate_uploaded_file(uploaded_file) -> tuple[bool, str]:
    """
    Quick validation of uploaded file before processing.

    Returns:
        (True, "")                if file is valid
        (False, "error message")  if file should be rejected

    Checks:
      - File size (reject if >50 MB — too large for in-memory SQLite)
      - File extension
    """
    MAX_SIZE_MB = 50
    ALLOWED_EXTENSIONS = {'.csv', '.xlsx', '.xls'}

    # Check size
    file_size_mb = uploaded_file.size / (1024 * 1024)
    if file_size_mb > MAX_SIZE_MB:
        return False, (
            f"File is too large ({file_size_mb:.1f} MB). "
            f"Please upload a file smaller than {MAX_SIZE_MB} MB."
        )

    # Check extension
    ext = os.path.splitext(uploaded_file.name)[1].lower()
    if ext not in ALLOWED_EXTENSIONS:
        return False, (
            f"Unsupported file type '{ext}'. "
            f"Please upload one of: {', '.join(ALLOWED_EXTENSIONS)}"
        )

    return True, ""