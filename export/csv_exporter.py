"""
export/csv_exporter.py — Export query results to CSV.

Simple wrapper around pandas.to_csv() with sensible defaults.

Why CSV and not Excel directly?
  - CSV is universal — works in Power BI, Excel, Google Sheets, R, Python
  - Smaller file size
  - No external dependencies (openpyxl) needed just for export
  - Power BI specifically recommends CSV for data imports

The user can open the CSV in Excel if they want Excel format.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from io import StringIO

from logger import log


def export_to_csv(df: pd.DataFrame, filename: str = "query_results.csv") -> bytes:
    """
    Convert a DataFrame to CSV bytes for download.

    Args:
        df: Query results DataFrame
        filename: Suggested filename (not used in the actual export, just for logging)

    Returns:
        CSV data as bytes, ready for st.download_button()

    Design choices:
      - index=False: Don't export the pandas row index (usually meaningless)
      - UTF-8 encoding: Universal, handles any language
      - No compression: Power BI and Excel handle raw CSV better
    """
    log("CSV_EXPORT", f"Exporting {len(df)} rows to {filename}")

    csv_buffer = StringIO()
    df.to_csv(csv_buffer, index=False, encoding='utf-8')
    csv_bytes = csv_buffer.getvalue().encode('utf-8')

    log("CSV_EXPORT", f"Generated {len(csv_bytes)} bytes")
    return csv_bytes


def generate_data_dictionary(df: pd.DataFrame) -> str:
    """
    Generate a simple data dictionary describing the columns.

    Returns a plain text string like:

        Column Name       | Data Type | Sample Values
        ------------------|-----------|------------------
        customer_name     | object    | John Smith, Jane Doe
        total_spending    | float64   | 12345.67, 9876.54
        order_count       | int64     | 5, 12

    Useful for documentation when sharing the CSV with others.
    """
    lines = []
    lines.append("DATA DICTIONARY")
    lines.append("=" * 70)
    lines.append(f"{'Column Name':<25} | {'Data Type':<15} | Sample Values")
    lines.append("-" * 70)

    for col in df.columns:
        dtype = str(df[col].dtype)
        
        # Get up to 3 non-null sample values
        samples = df[col].dropna().head(3).tolist()
        sample_str = ", ".join([str(s) for s in samples])
        if len(sample_str) > 30:
            sample_str = sample_str[:27] + "..."

        lines.append(f"{col:<25} | {dtype:<15} | {sample_str}")

    lines.append("=" * 70)
    lines.append(f"Total rows: {len(df):,}")
    lines.append(f"Total columns: {len(df.columns)}")

    log("DATA_DICT", f"Generated dictionary for {len(df.columns)} columns")
    return "\n".join(lines)
