"""
pipeline/followup_suggestions.py — Smart follow-up question generation.

After showing query results, suggest 3 natural next questions the user
might want to ask based on what they just saw.

This guides non-technical users through iterative analysis.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
from llm.gemini_client import call_llm
from logger import log


def generate_followup_questions(original_question: str, df: pd.DataFrame, insight: str) -> list[str]:
    """
    Generate 3 contextual follow-up questions.
    
    Args:
        original_question: The question the user just asked
        df: The results DataFrame
        insight: The generated insight text
        
    Returns:
        List of 3 follow-up question strings
    """
    if df.empty:
        return []
    
    # Build a compact summary of the results for the LLM
    result_summary = _summarize_results(df)
    
    prompt = f"""You are helping a user explore data. They just asked a question and got results. Suggest 3 natural follow-up questions.

ORIGINAL QUESTION:
{original_question}

RESULTS SUMMARY:
{result_summary}

KEY INSIGHT:
{insight[:200]}

Generate exactly 3 follow-up questions that:
1. Build on what the user just learned
2. Explore different dimensions (time, category, comparison)
3. Are specific and actionable (not vague like "tell me more")
4. Use the actual column/value names from the results
5. Are phrased naturally, as the user would ask them

Format as a simple numbered list:
1. First follow-up question
2. Second follow-up question  
3. Third follow-up question

FOLLOW-UP QUESTIONS:"""

    try:
        response = call_llm(prompt)
        questions = _parse_questions(response)
        log("FOLLOWUP", f"Generated {len(questions)} follow-up questions")
        return questions[:3]  # Ensure exactly 3
        
    except Exception as e:
        log("FOLLOWUP_ERROR", str(e))
        return []


def _summarize_results(df: pd.DataFrame) -> str:
    """Create a compact summary of DataFrame for the prompt."""
    lines = []
    lines.append(f"Rows returned: {len(df)}")
    lines.append(f"Columns: {', '.join(df.columns[:5])}")  # First 5 columns
    
    # Show first row as example
    if len(df) > 0:
        first_row = df.iloc[0]
        samples = []
        for col in df.columns[:3]:  # First 3 columns
            val = first_row[col]
            if pd.notna(val):
                samples.append(f"{col}={val}")
        if samples:
            lines.append(f"Example: {', '.join(samples)}")
    
    # Identify column types for context
    numeric_cols = df.select_dtypes(include=['number']).columns.tolist()
    if numeric_cols:
        lines.append(f"Numeric columns: {', '.join(numeric_cols[:3])}")
    
    categorical_cols = df.select_dtypes(include=['object']).columns.tolist()
    if categorical_cols:
        lines.append(f"Categorical columns: {', '.join(categorical_cols[:3])}")
    
    return "\n".join(lines)


def _parse_questions(response: str) -> list[str]:
    """Parse LLM response into list of questions."""
    questions = []
    
    for line in response.strip().split('\n'):
        line = line.strip()
        
        # Remove numbering (1., 2., 3. or 1) 2) 3))
        if line and (line[0].isdigit() or line.startswith('-') or line.startswith('•')):
            # Remove leading number/bullet and punctuation
            cleaned = line.lstrip('0123456789.-•) ').strip()
            if cleaned:
                questions.append(cleaned)
    
    return questions
