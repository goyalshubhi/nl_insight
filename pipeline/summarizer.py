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
    Generate structured insight bullets instead of a paragraph.
    
    Args:
        question:     The user's original question
        data_summary: Compact string of facts from eda.format_insights_for_llm()

    Returns:
        Structured bullet points with specific insights.

    Raises:
        RuntimeError: If the LLM call fails
    """
    log("INSIGHT", f"Generating bullet insights for: {question[:100]}")

    # Build the prompt for bullet-point insights
    prompt = f"""You are a data analyst. Write 3-5 bullet points about these findings.

QUESTION: {question}

DATA: {data_summary}

RULES:
1. Use ONLY the numbers from DATA above
2. Format numbers with commas: 4,240,553.19 not 4240553.19
3. Keep each bullet to 1-2 sentences
4. Make sure words are separated by spaces
5. Start each line with • followed by a space

Write exactly 3-5 bullet points now:"""

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
