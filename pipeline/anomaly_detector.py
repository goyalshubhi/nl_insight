"""
pipeline/anomaly_detector.py — Anomaly detection for query results.

Flags unusual patterns that deserve attention:
  - Sudden drops or spikes
  - Values far from average
  - Missing expected data

This shows proactive analysis, not just reactive queries.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from logger import log


def detect_anomalies(df: pd.DataFrame, question: str) -> list[dict]:
    """
    Detect anomalies in query results.
    
    Args:
        df: Query results DataFrame
        question: Original question for context
        
    Returns:
        List of anomaly dicts:
        [
            {
                'type': 'spike' | 'drop' | 'outlier' | 'missing',
                'severity': 'high' | 'medium' | 'low',
                'message': "Human-readable description",
                'icon': '⚠️' | '✨' | '🔴'
            },
            ...
        ]
    """
    if df.empty or len(df) < 3:  # Need some data to detect patterns
        return []
    
    anomalies = []
    
    # Get numeric columns
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    numeric_cols = [c for c in numeric_cols if 'id' not in c.lower()]  # Skip IDs
    
    if not numeric_cols:
        return []
    
    # ── Check for extreme outliers ─────────────────────────────────────────────
    for col in numeric_cols[:2]:  # Check first 2 numeric columns only
        mean_val = df[col].mean()
        std_val = df[col].std()
        
        if std_val == 0:  # All values the same
            continue
        
        # Find values > 3 standard deviations from mean
        z_scores = np.abs((df[col] - mean_val) / std_val)
        extreme = df[z_scores > 3]
        
        if len(extreme) > 0:
            max_outlier = extreme[col].max()
            anomalies.append({
                'type': 'outlier',
                'severity': 'medium',
                'message': f"**Unusual value detected:** {col.replace('_', ' ').title()} of {max_outlier:,.2f} is significantly higher than average ({mean_val:,.2f})",
                'icon': '⚠️'
            })
    
    # ── Check for sudden drops in values (if sorted) ──────────────────────────
    if len(df) >= 5 and len(numeric_cols) > 0:
        col = numeric_cols[0]
        
        # Check if values are mostly descending (sorted by this column)
        diffs = df[col].diff().dropna()
        if (diffs < 0).sum() > len(diffs) * 0.7:  # 70% descending
            # Check for sudden large drop
            first_val = df[col].iloc[0]
            fifth_val = df[col].iloc[min(4, len(df)-1)]
            
            if first_val > 0:
                drop_pct = ((first_val - fifth_val) / first_val) * 100
                
                if drop_pct > 50:
                    anomalies.append({
                        'type': 'drop',
                        'severity': 'high',
                        'message': f"**Steep decline:** {col.replace('_', ' ').title()} drops {drop_pct:.0f}% from top to 5th position",
                        'icon': '🔴'
                    })
    
    # ── Check for concentration (top-heavy distribution) ──────────────────────
    if len(df) >= 5 and len(numeric_cols) > 0:
        col = numeric_cols[0]
        total = df[col].sum()
        
        if total > 0:
            top3_sum = df[col].head(3).sum()
            top3_pct = (top3_sum / total) * 100
            
            if top3_pct > 70:
                anomalies.append({
                    'type': 'concentration',
                    'severity': 'low',
                    'message': f"**High concentration:** Top 3 entries account for {top3_pct:.0f}% of total {col.replace('_', ' ')}",
                    'icon': '📊'
                })
    
    # ── Check for missing expected data ────────────────────────────────────────
    if len(df) < 5 and 'top' in question.lower():
        anomalies.append({
            'type': 'missing',
            'severity': 'low',
            'message': f"**Limited data:** Query asked for top results but only {len(df)} rows found. Consider broadening criteria.",
            'icon': 'ℹ️'
        })
    
    log("ANOMALY", f"Detected {len(anomalies)} anomalies")
    return anomalies[:3]  # Return max 3 to avoid overwhelming user
