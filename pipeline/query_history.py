"""
pipeline/query_history.py — Query history management.

Stores recent queries in Streamlit session state so users can:
  - See what they've asked before
  - Re-run queries with one click
  - Track their analysis journey

Why this matters:
  Data exploration is iterative. Users refine questions based on results.
  History saves time and shows the analytical process.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
import streamlit as st
from logger import log


def init_history():
    """Initialize query history in session state if not exists."""
    if 'query_history' not in st.session_state:
        st.session_state['query_history'] = []
        log("HISTORY", "Initialized query history")


def add_to_history(question: str, row_count: int, success: bool = True):
    """
    Add a query to the history.
    
    Args:
        question: The natural language question
        row_count: Number of rows returned
        success: Whether the query succeeded
    """
    init_history()
    
    entry = {
        'question': question,
        'timestamp': datetime.now(),
        'row_count': row_count,
        'success': success
    }
    
    # Add to front of list (most recent first)
    st.session_state['query_history'].insert(0, entry)
    
    # Keep only last 10 queries
    if len(st.session_state['query_history']) > 10:
        st.session_state['query_history'] = st.session_state['query_history'][:10]
    
    log("HISTORY", f"Added to history: {question[:50]}... ({row_count} rows)")


def get_history() -> list:
    """
    Get the query history.
    
    Returns:
        List of history entries (most recent first)
    """
    init_history()
    return st.session_state['query_history']


def clear_history():
    """Clear all query history."""
    st.session_state['query_history'] = []
    log("HISTORY", "Cleared query history")


def format_timestamp(dt: datetime) -> str:
    """Format timestamp for display."""
    now = datetime.now()
    diff = now - dt
    
    if diff.seconds < 60:
        return "just now"
    elif diff.seconds < 3600:
        mins = diff.seconds // 60
        return f"{mins}m ago"
    elif diff.seconds < 86400:
        hours = diff.seconds // 3600
        return f"{hours}h ago"
    else:
        return dt.strftime("%b %d, %H:%M")
