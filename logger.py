"""
logger.py — Centralised logging for the pipeline.

Every stage (intent, SQL, execution, analysis, viz, summary) calls
log() with its stage name so we get a clear audit trail in pipeline.log.

Format:
    2024-12-01 14:23:01 | SQL_GENERATION | SELECT * FROM orders LIMIT 100
    2024-12-01 14:23:02 | EXECUTION      | Returned 42 rows

Why a custom logger instead of Python's logging module?
  Simpler to read, simpler to explain in an interview, and we only
  need one thing: append a timestamped line to a file.
"""

import os
from datetime import datetime

import config


def log(stage: str, message: str) -> None:
    """
    Append one line to the pipeline log file.

    Args:
        stage:   Short label like "SQL_GENERATION", "EXECUTION", "EDA"
        message: The content to log (truncated to 300 chars to keep file tidy)
    """
    os.makedirs(os.path.dirname(config.LOG_FILE), exist_ok=True)

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    short_msg = str(message).replace("\n", " ")[:300]  # keep log lines single-line
    line = f"{timestamp} | {stage:<20} | {short_msg}\n"

    with open(config.LOG_FILE, "a", encoding="utf-8") as f:
        f.write(line)