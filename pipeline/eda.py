"""
pipeline/eda.py — Simple exploratory data analysis.

Given a DataFrame from a query result, extract basic insights:
  - Row and column counts
  - Top/bottom values for numeric columns
  - Value counts for categorical columns
  - Growth rates if there's a date column

All calculations are simple and explainable — no ML, no black boxes.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from logger import log


def analyze_dataframe(df: pd.DataFrame) -> dict:
    """
    Perform basic EDA on a DataFrame and return structured insights.

    Args:
        df: Query results

    Returns:
        A dictionary with:
        {
            'row_count': int,
            'column_count': int,
            'numeric_summary': dict,    # {col_name: {min, max, mean, ...}}
            'categorical_summary': dict, # {col_name: {top_value, count, ...}}
            'date_range': dict or None,  # {col_name, earliest, latest} if date col exists
            'growth': dict or None,      # first_value, last_value, pct_change if applicable
        }
    """
    if df.empty:
        log("EDA", "Empty DataFrame — no analysis performed")
        return {
            'row_count': 0,
            'column_count': len(df.columns),
            'numeric_summary': {},
            'categorical_summary': {},
            'date_range': None,
            'growth': None,
        }

    insights = {
        'row_count': len(df),
        'column_count': len(df.columns),
        'numeric_summary': {},
        'categorical_summary': {},
        'date_range': None,
        'growth': None,
    }

    # ── Numeric columns ────────────────────────────────────────────────────────
    numeric_cols = df.select_dtypes(include=['number']).columns

    for col in numeric_cols:
        insights['numeric_summary'][col] = {
            'min': df[col].min(),
            'max': df[col].max(),
            'mean': df[col].mean(),
            'median': df[col].median(),
            'sum': df[col].sum(),
        }

    # ── Categorical columns ────────────────────────────────────────────────────
    categorical_cols = df.select_dtypes(include=['object', 'category']).columns

    for col in categorical_cols:
        # Skip if too many unique values (likely an ID column)
        if df[col].nunique() > 50:
            continue

        value_counts = df[col].value_counts()
        insights['categorical_summary'][col] = {
            'unique_count': df[col].nunique(),
            'top_value': value_counts.index[0] if len(value_counts) > 0 else None,
            'top_count': int(value_counts.iloc[0]) if len(value_counts) > 0 else 0,
        }

    # ── Date columns ───────────────────────────────────────────────────────────
    date_cols = df.select_dtypes(include=['datetime64']).columns

    if len(date_cols) > 0:
        date_col = date_cols[0]  # use first date column
        insights['date_range'] = {
            'column': date_col,
            'earliest': df[date_col].min(),
            'latest': df[date_col].max(),
            'span_days': (df[date_col].max() - df[date_col].min()).days,
        }

    # ── Growth calculation ─────────────────────────────────────────────────────
    # If there's a date column and a numeric column, calculate first-to-last growth
    if date_cols.size > 0 and numeric_cols.size > 0:
        date_col = date_cols[0]
        num_col = numeric_cols[0]

        df_sorted = df.sort_values(date_col)
        first_value = df_sorted[num_col].iloc[0]
        last_value = df_sorted[num_col].iloc[-1]

        if first_value != 0:
            pct_change = ((last_value - first_value) / first_value) * 100
        else:
            pct_change = None

        insights['growth'] = {
            'metric': num_col,
            'first_value': first_value,
            'last_value': last_value,
            'absolute_change': last_value - first_value,
            'percent_change': pct_change,
        }

    log("EDA", f"Analysis complete: {insights['row_count']} rows, {insights['column_count']} cols")
    return insights


def format_insights_for_llm(insights: dict) -> str:
    """
    Convert the insights dict into a compact string for the LLM prompt.

    This string will be injected into the insight_summary_prompt so the
    LLM can write a plain-English paragraph grounded in real numbers.

    Design: compact, no fluff, just the facts.
    """
    lines = []

    lines.append(f"Row count: {insights['row_count']:,}")
    lines.append(f"Column count: {insights['column_count']}")

    # Numeric summaries
    if insights['numeric_summary']:
        lines.append("\nNumeric columns:")
        for col, stats in insights['numeric_summary'].items():
            lines.append(
                f"  - {col}: min={stats['min']:,.2f}, max={stats['max']:,.2f}, "
                f"mean={stats['mean']:,.2f}, sum={stats['sum']:,.2f}"
            )

    # Categorical summaries
    if insights['categorical_summary']:
        lines.append("\nCategorical columns:")
        for col, stats in insights['categorical_summary'].items():
            lines.append(
                f"  - {col}: {stats['unique_count']} unique values, "
                f"top value is '{stats['top_value']}' ({stats['top_count']} occurrences)"
            )

    # Date range
    if insights['date_range']:
        dr = insights['date_range']
        lines.append(
            f"\nDate range ({dr['column']}): {dr['earliest']} to {dr['latest']} "
            f"({dr['span_days']} days)"
        )

    # Growth
    if insights['growth']:
        g = insights['growth']
        lines.append(
            f"\nGrowth ({g['metric']}): from {g['first_value']:,.2f} to {g['last_value']:,.2f}"
        )
        if g['percent_change'] is not None:
            lines.append(f"  Change: {g['absolute_change']:+,.2f} ({g['percent_change']:+.1f}%)")

    return "\n".join(lines)
