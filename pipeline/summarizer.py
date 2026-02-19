"""
pipeline/summarizer.py — Generate insight summaries.

Takes the user's question + the EDA analysis + calls the LLM to write
a short, plain-English paragraph that explains what the data shows.

Critical: The insight is grounded in actual numbers from the DataFrame.
  We don't let the LLM see the raw data — only the aggregated stats
  from eda.py. This prevents hallucination.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from llm.prompts import insight_summary_prompt
from llm.gemini_client import call_llm
from logger import log


def generate_insight(question: str, data_summary: str) -> str:
    """
    Generate a plain-English insight paragraph.

    Args:
        question:     The user's original question
        data_summary: Compact string of facts from eda.format_insights_for_llm()

    Returns:
        A 3-5 sentence paragraph explaining the findings.

    Raises:
        RuntimeError: If the LLM call fails
    """
    log("INSIGHT", f"Generating summary for: {question[:100]}")

    # Build the prompt
    prompt = insight_summary_prompt(question, data_summary)

    # Call the LLM
    try:
        insight = call_llm(prompt)
        log("INSIGHT", f"Generated: {insight[:200]}")
        return insight.strip()
    except Exception as e:
        log("INSIGHT_ERROR", str(e))
        # Fallback: return the raw data summary if LLM fails
        return (
            f"Data summary:\n{data_summary}\n\n"
            "(Note: AI insight generation failed — showing raw statistics instead)"
        )