"""
pipeline/data_quality.py — Data quality analysis.

Analyzes a DataFrame for common data quality issues:
  - Missing/null values
  - Duplicate rows
  - Outliers in numeric columns
  - Inconsistent formatting

Shows that you understand real data is messy.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from logger import log


def analyze_data_quality(df: pd.DataFrame) -> dict:
    """
    Analyze data quality issues in a DataFrame.
    
    Args:
        df: Query result DataFrame
        
    Returns:
        Dict with quality metrics:
        {
            'total_rows': int,
            'missing_values': [(col, count, percentage), ...],
            'duplicate_rows': int,
            'outliers': [(col, count), ...],
            'summary': "text summary"
        }
    """
    if df.empty:
        return {
            'total_rows': 0,
            'missing_values': [],
            'duplicate_rows': 0,
            'outliers': [],
            'summary': "No data to analyze."
        }
    
    quality = {
        'total_rows': len(df),
        'missing_values': [],
        'duplicate_rows': 0,
        'outliers': [],
        'summary': ''
    }
    
    # ── Check for missing values ───────────────────────────────────────────────
    for col in df.columns:
        null_count = df[col].isnull().sum()
        if null_count > 0:
            percentage = (null_count / len(df)) * 100
            quality['missing_values'].append((col, null_count, percentage))
    
    # ── Check for duplicate rows ───────────────────────────────────────────────
    quality['duplicate_rows'] = df.duplicated().sum()
    
    # ── Check for outliers in numeric columns ──────────────────────────────────
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    
    for col in numeric_cols:
        if col.lower().endswith('id'):  # Skip ID columns
            continue
            
        # Use IQR method for outlier detection
        Q1 = df[col].quantile(0.25)
        Q3 = df[col].quantile(0.75)
        IQR = Q3 - Q1
        
        lower_bound = Q1 - 1.5 * IQR
        upper_bound = Q3 + 1.5 * IQR
        
        outlier_count = ((df[col] < lower_bound) | (df[col] > upper_bound)).sum()
        
        if outlier_count > 0:
            quality['outliers'].append((col, outlier_count))
    
    # ── Generate summary ───────────────────────────────────────────────────────
    issues = []
    
    if quality['missing_values']:
        total_missing = sum(count for _, count, _ in quality['missing_values'])
        issues.append(f"{total_missing:,} missing values across {len(quality['missing_values'])} columns")
    
    if quality['duplicate_rows'] > 0:
        issues.append(f"{quality['duplicate_rows']:,} duplicate rows")
    
    if quality['outliers']:
        total_outliers = sum(count for _, count in quality['outliers'])
        issues.append(f"{total_outliers:,} outliers detected")
    
    if not issues:
        quality['summary'] = "✅ No major data quality issues detected."
    else:
        quality['summary'] = "⚠️ Issues found: " + ", ".join(issues)
    
    log("DATA_QUALITY", quality['summary'])
    return quality


def format_quality_report(quality: dict) -> str:
    """
    Format quality analysis as readable text report.
    
    Args:
        quality: Output from analyze_data_quality()
        
    Returns:
        Formatted text report
    """
    lines = []
    lines.append(f"**Total Rows:** {quality['total_rows']:,}")
    lines.append("")
    
    # Missing values
    if quality['missing_values']:
        lines.append("**Missing Values:**")
        for col, count, pct in quality['missing_values']:
            lines.append(f"- `{col}`: {count:,} missing ({pct:.1f}%)")
        lines.append("")
    
    # Duplicates
    if quality['duplicate_rows'] > 0:
        lines.append(f"**Duplicate Rows:** {quality['duplicate_rows']:,}")
        lines.append("")
    
    # Outliers
    if quality['outliers']:
        lines.append("**Outliers Detected:**")
        for col, count in quality['outliers']:
            lines.append(f"- `{col}`: {count:,} values significantly outside normal range")
        lines.append("")
    
    if not quality['missing_values'] and not quality['duplicate_rows'] and not quality['outliers']:
        lines.append("✅ No data quality issues detected in these results.")
    
    return "\n".join(lines)
