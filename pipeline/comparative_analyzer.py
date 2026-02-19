"""
pipeline/comparative_analyzer.py — Comparative analysis enhancement.

Detects when the user is asking a comparison question and ensures
the results are structured for side-by-side comparison.

Patterns detected:
  - "compare X and Y"
  - "X vs Y"
  - "difference between X and Y"
  - "how does X compare to Y"

Enhancement:
  When comparison is detected, we add a calculated "difference" column
  to the results and ensure the visualization shows both entities clearly.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import re
from logger import log


def is_comparison_query(question: str) -> bool:
    """
    Detect if the user is asking a comparison question.
    
    Args:
        question: User's natural language query
        
    Returns:
        True if comparison patterns are detected
    """
    comparison_patterns = [
        r'\bcompare\b',
        r'\bvs\.?\b',
        r'\bversus\b',
        r'\bdifference between\b',
        r'\bcompared to\b',
        r'\bhow does .+ compare\b',
        r'\b(higher|lower|more|less) than\b',
    ]
    
    question_lower = question.lower()
    for pattern in comparison_patterns:
        if re.search(pattern, question_lower):
            log("COMPARISON", f"Detected comparison pattern: {pattern}")
            return True
    
    return False


def enhance_comparison_result(df: pd.DataFrame, question: str) -> pd.DataFrame:
    """
    Add comparison metrics to a DataFrame if appropriate.
    
    For numeric columns, calculate:
      - Absolute difference between values
      - Percentage difference
      - Rank/position
    
    Args:
        df: Query results
        question: Original question for context
        
    Returns:
        Enhanced DataFrame with comparison columns added
    """
    if df.empty or len(df) < 2:
        return df  # Need at least 2 rows to compare
    
    # Find numeric columns
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    
    if not numeric_cols:
        return df  # No numeric data to compare
    
    # For each numeric column, add comparison metrics
    df_enhanced = df.copy()
    
    for col in numeric_cols:
        # Skip if column is likely an ID
        if 'id' in col.lower():
            continue
            
        # Add rank
        df_enhanced[f'{col}_rank'] = df_enhanced[col].rank(ascending=False, method='dense').astype(int)
        
        # If exactly 2 rows, add direct comparison
        if len(df) == 2:
            val1 = df[col].iloc[0]
            val2 = df[col].iloc[1]
            
            abs_diff = val1 - val2
            
            if val2 != 0:
                pct_diff = ((val1 - val2) / val2) * 100
                df_enhanced[f'{col}_diff'] = [abs_diff, -abs_diff]
                df_enhanced[f'{col}_diff_pct'] = [pct_diff, -pct_diff]
    
    log("COMPARISON", f"Enhanced DataFrame with {len(df_enhanced.columns) - len(df.columns)} comparison columns")
    return df_enhanced


def generate_comparison_insight(df: pd.DataFrame, question: str) -> str:
    """
    Generate a text insight specifically for comparison queries.
    
    Args:
        df: Query results (potentially enhanced with comparison columns)
        question: Original question
        
    Returns:
        Plain-English comparison summary
    """
    if df.empty:
        return "No data to compare."
    
    # Find the main numeric column (first non-ID numeric)
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    numeric_cols = [c for c in numeric_cols if 'id' not in c.lower() and 'rank' not in c.lower()]
    
    if not numeric_cols:
        return "No numeric metrics found for comparison."
    
    metric_col = numeric_cols[0]
    
    # Get top 2 rows
    if len(df) >= 2:
        top1 = df.iloc[0]
        top2 = df.iloc[1]
        
        # Try to find a label column (first non-numeric, non-ID column)
        label_cols = df.select_dtypes(include=['object']).columns.tolist()
        label_cols = [c for c in label_cols if 'id' not in c.lower()]
        
        if label_cols:
            label_col = label_cols[0]
            name1 = top1[label_col]
            name2 = top2[label_col]
            val1 = top1[metric_col]
            val2 = top2[metric_col]
            
            diff = val1 - val2
            if val2 != 0:
                pct_diff = ((val1 - val2) / val2) * 100
                return (
                    f"{name1} leads with {val1:,.2f} compared to {name2}'s {val2:,.2f}. "
                    f"That's a difference of {diff:,.2f} ({pct_diff:+.1f}%)."
                )
            else:
                return f"{name1} has {val1:,.2f} while {name2} has {val2:,.2f}."
    
    return f"Comparison shows {len(df)} entries ranked by {metric_col}."
