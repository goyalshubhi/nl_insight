"""
pipeline/visualizer.py — Automatic chart generation.

Given a DataFrame, decide which chart type makes sense and render it.

Chart selection logic (simple, explainable):
  - Has a date/datetime column + numeric column → line chart
  - Has categorical column + numeric column → bar chart
  - Single numeric column → histogram
  - Otherwise → just show the table (no chart)

Why Plotly?
  Interactive charts (zoom, hover, pan) with minimal code.
  Works natively in Streamlit.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go

from logger import log


def create_chart(df: pd.DataFrame):
    """
    Analyze a DataFrame and return appropriate Plotly chart(s).

    Args:
        df: Query results as a pandas DataFrame

    Returns:
        Single plotly.graph_objects.Figure if one chart is appropriate
        List of Figures if multiple charts should be shown
        None if no suitable chart can be created

    Decision tree:
      1. Empty DataFrame → None
      2. Check if multi-chart makes sense (multiple dimensions)
      3. Otherwise fall back to single chart logic
    """
    if df.empty:
        log("CHART", "No chart — DataFrame is empty")
        return None

    # Identify column types
    date_cols = _get_date_columns(df)
    numeric_cols = _get_numeric_columns(df)
    categorical_cols = _get_categorical_columns(df)

    log("CHART", f"Detected: {len(date_cols)} date, {len(numeric_cols)} numeric, {len(categorical_cols)} categorical")

    # ── Multi-chart dashboard logic ────────────────────────────────────────────
    # If we have multiple categorical columns and at least one numeric,
    # create a chart for each categorical dimension
    if len(categorical_cols) >= 2 and len(numeric_cols) >= 1:
        charts = _create_multi_chart_dashboard(df, categorical_cols, numeric_cols)
        if charts:
            return charts

    # ── Single column ──────────────────────────────────────────────────────────
    if len(df.columns) == 1:
        col = df.columns[0]

        if col in numeric_cols:
            # Histogram for single numeric column
            fig = px.histogram(
                df,
                x=col,
                title=f"Distribution of {col}",
                labels={col: col.replace('_', ' ').title()},
            )
            log("CHART", f"Created histogram for {col}")
            return fig

        elif col in categorical_cols:
            # Bar chart of value counts
            counts = df[col].value_counts().reset_index()
            counts.columns = [col, 'count']
            fig = px.bar(
                counts,
                x=col,
                y='count',
                title=f"Count by {col}",
                labels={col: col.replace('_', ' ').title()},
            )
            log("CHART", f"Created bar chart for categorical {col}")
            return fig

    # ── Two+ columns ───────────────────────────────────────────────────────────

    # Priority 1: Date + numeric → line chart
    if date_cols and numeric_cols:
        date_col = date_cols[0]
        numeric_col = numeric_cols[0]

        # Sort by date for proper line chart
        df_sorted = df.sort_values(date_col)

        fig = px.line(
            df_sorted,
            x=date_col,
            y=numeric_col,
            title=f"{numeric_col.replace('_', ' ').title()} over time",
            labels={
                date_col: date_col.replace('_', ' ').title(),
                numeric_col: numeric_col.replace('_', ' ').title(),
            },
            markers=True,
        )
        log("CHART", f"Created line chart: {date_col} vs {numeric_col}")
        return fig

    # Priority 2: Categorical + numeric → bar chart
    if categorical_cols and numeric_cols:
        cat_col = categorical_cols[0]
        num_col = numeric_cols[0]

        # Limit to top 20 categories to avoid cluttered charts
        if df[cat_col].nunique() > 20:
            top_values = df.nlargest(20, num_col)
            fig = px.bar(
                top_values,
                x=cat_col,
                y=num_col,
                title=f"Top 20: {num_col.replace('_', ' ').title()} by {cat_col.replace('_', ' ').title()}",
                labels={
                    cat_col: cat_col.replace('_', ' ').title(),
                    num_col: num_col.replace('_', ' ').title(),
                },
            )
        else:
            # Sort by the numeric column for better readability
            df_sorted = df.sort_values(num_col, ascending=False)
            fig = px.bar(
                df_sorted,
                x=cat_col,
                y=num_col,
                title=f"{num_col.replace('_', ' ').title()} by {cat_col.replace('_', ' ').title()}",
                labels={
                    cat_col: cat_col.replace('_', ' ').title(),
                    num_col: num_col.replace('_', ' ').title(),
                },
            )
        log("CHART", f"Created bar chart: {cat_col} vs {num_col}")
        return fig

    # Priority 3: Two numerics → scatter plot
    if len(numeric_cols) >= 2:
        x_col = numeric_cols[0]
        y_col = numeric_cols[1]

        fig = px.scatter(
            df,
            x=x_col,
            y=y_col,
            title=f"{y_col.replace('_', ' ').title()} vs {x_col.replace('_', ' ').title()}",
            labels={
                x_col: x_col.replace('_', ' ').title(),
                y_col: y_col.replace('_', ' ').title(),
            },
        )
        log("CHART", f"Created scatter plot: {x_col} vs {y_col}")
        return fig

    # ── No suitable chart ──────────────────────────────────────────────────────
    log("CHART", "No chart created — no suitable column combination found")
    return None


def _create_multi_chart_dashboard(df: pd.DataFrame, categorical_cols: list, numeric_cols: list) -> list:
    """
    Create multiple charts when the query asks for multiple metrics.
    
    Works when you have:
    - 2 numeric columns (e.g., revenue AND order_count)
    - OR 2 categorical columns with 1 numeric
    """
    log("MULTI_CHART", f"Check: {len(df)} rows, {len(numeric_cols)} numeric cols, {len(categorical_cols)} categorical cols")
    
    # Need at least 2 dimensions to chart
    if len(numeric_cols) < 2 and len(categorical_cols) < 2:
        log("MULTI_CHART", "Skip: Need 2+ numeric OR 2+ categorical columns")
        return None
    
    # Too many rows gets messy
    if len(df) > 25:
        log("MULTI_CHART", f"Skip: Too many rows ({len(df)})")
        return None
    
    charts = []
    
    # Case 1: Multiple numeric columns (revenue + order_count + etc)
    if len(numeric_cols) >= 2 and len(categorical_cols) >= 1:
        cat_col = categorical_cols[0]
        log("MULTI_CHART", f"Creating chart for each of {len(numeric_cols)} numeric columns")
        
        # Create one chart per numeric column
        for num_col in numeric_cols[:3]:  # Max 3 charts
            df_sorted = df.sort_values(num_col, ascending=False).head(15)  # Top 15 only
            fig = px.bar(
                df_sorted,
                x=cat_col,
                y=num_col,
                title=f"{num_col.replace('_', ' ').title()}",
                labels={
                    cat_col: cat_col.replace('_', ' ').title(),
                    num_col: num_col.replace('_', ' ').title(),
                },
            )
            charts.append(fig)
            log("MULTI_CHART", f"  ✓ Chart added: {num_col}")
    
    # Case 2: Multiple categorical columns (category + region + etc)
    elif len(categorical_cols) >= 2 and len(numeric_cols) >= 1:
        num_col = numeric_cols[0]
        log("MULTI_CHART", f"Creating chart for each of {len(categorical_cols)} categorical columns")
        
        # Create one chart per categorical dimension
        for cat_col in categorical_cols[:3]:  # Max 3 charts
            unique_vals = df[cat_col].nunique()
            if unique_vals > 20:
                log("MULTI_CHART", f"  ✗ Skip {cat_col}: too many values ({unique_vals})")
                continue
                
            df_sorted = df.sort_values(num_col, ascending=False).head(15)
            fig = px.bar(
                df_sorted,
                x=cat_col,
                y=num_col,
                title=f"{num_col.replace('_', ' ').title()} by {cat_col.replace('_', ' ').title()}",
                labels={
                    cat_col: cat_col.replace('_', ' ').title(),
                    num_col: num_col.replace('_', ' ').title(),
                },
            )
            charts.append(fig)
            log("MULTI_CHART", f"  ✓ Chart added: {cat_col}")
    
    # Return if we got 2+ charts
    if len(charts) >= 2:
        log("MULTI_CHART", f"✓ SUCCESS: Created {len(charts)} charts")
        return charts
    else:
        log("MULTI_CHART", f"✗ FAIL: Only got {len(charts)} chart(s), need 2+")
        return None
    
    return None  # Fall back to single chart if multi-chart doesn't make sense


# ── Helper functions ──────────────────────────────────────────────────────────

def _get_date_columns(df: pd.DataFrame) -> list:
    """Return list of column names that are dates or datetimes."""
    date_cols = []
    for col in df.columns:
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            date_cols.append(col)
        # Also check if column can be parsed as date (string dates)
        elif df[col].dtype == 'object':
            try:
                pd.to_datetime(df[col].dropna().head(10), errors='raise')
                date_cols.append(col)
            except (ValueError, TypeError):
                pass
    return date_cols


def _get_numeric_columns(df: pd.DataFrame) -> list:
    """Return list of column names that are numeric."""
    return df.select_dtypes(include=['number']).columns.tolist()


def _get_categorical_columns(df: pd.DataFrame) -> list:
    """
    Return list of column names that are categorical.

    Categorical = strings/objects with a reasonable number of unique values.
    We exclude columns with >50 unique values to avoid treating IDs as categories.
    """
    categorical = []
    for col in df.columns:
        if df[col].dtype == 'object' or pd.api.types.is_categorical_dtype(df[col]):
            if df[col].nunique() <= 50:  # reasonable cutoff for categories
                categorical.append(col)
    return categorical
