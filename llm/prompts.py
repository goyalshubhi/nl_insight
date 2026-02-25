"""
llm/prompts.py — All prompt templates live here.

Why centralise prompts?
  - Easy to tune without touching business logic
  - Easy to compare prompt versions
  - Keeps other files clean and readable

Design principle: prompts are kept compact to minimise token usage.
  We inject only what the model needs — schema + question + strict rules.
  No examples, no lengthy explanations in the prompt itself.
"""


def sql_generation_prompt(schema_str: str, question: str) -> str:
    """
    Build the prompt sent to the LLM for SQL generation.

    Args:
        schema_str : compact schema string from schema_reader.format_schema_for_prompt()
        question   : the user's natural language question

    Returns:
        A single string ready to send to the LLM.

    Token budget: ~500-700 tokens per call — within free tier limits.
    """
    return f"""You are an expert PostgreSQL analyst. Write a single SELECT query to answer the question.

SCHEMA:
{schema_str}

QUESTION:
{question}

STRICT RULES:
1. Return ONLY the raw SQL query. No explanation, no markdown, no code blocks, no backticks.
2. Only use SELECT statements. Never INSERT, UPDATE, DELETE, DROP, ALTER, TRUNCATE, CREATE.
3. Only reference tables and columns that exist in the SCHEMA above.
4. ALWAYS use case-insensitive text comparisons: WHERE UPPER(column) = UPPER('value') or column ILIKE 'value'

LIMIT RULES:
- If question asks for "the" (singular) or "which one" → LIMIT 1
- If question asks for "top N" or "bottom N" → LIMIT N
- Otherwise use LIMIT 100 as a safety cap

ADVANCED PATTERNS — use when needed:
- CTEs (WITH): For multi-step logic, use WITH clauses to break down complex queries
- Window functions: Use ROW_NUMBER(), RANK(), DENSE_RANK(), LAG(), LEAD() for rankings and comparisons
- Anti-joins: For "customers who bought X but NOT Y", use LEFT JOIN ... WHERE right_table.id IS NULL
- Self-joins: For comparing rows within the same table (e.g., repeat purchases)
- CASE WHEN: For conditional logic and categorization
- Date arithmetic: Use CURRENT_DATE, DATE_TRUNC(), and interval '30 days' for time-based filters
- Aggregations: COUNT(DISTINCT ...), SUM(CASE WHEN ...), etc.
- Case-insensitive comparisons: Use ILIKE or UPPER() when comparing text values (e.g., WHERE UPPER(category) = UPPER('electronics'))

SUPERLATIVES ("highest", "most", "best", "top"):
- Always ORDER BY the relevant column
- Use DESC for highest/most/best, ASC for lowest/least/worst
- Combine with LIMIT for top-N queries

DATE FILTERS:
- "last month": WHERE order_date >= DATE_TRUNC('month', CURRENT_DATE - interval '1 month') AND order_date < DATE_TRUNC('month', CURRENT_DATE)
- "this year": WHERE order_date >= DATE_TRUNC('year', CURRENT_DATE)
- "last 30 days": WHERE order_date >= CURRENT_DATE - interval '30 days'

JOINS:
- Use explicit JOIN syntax (JOIN, LEFT JOIN, etc.) — never implicit joins
- Always use table aliases for readability (e.g., o for orders, c for customers)
- Join on foreign key relationships shown in the schema

If the question cannot be answered from the available schema, return exactly: CANNOT_ANSWER

SQL:"""


def insight_summary_prompt(question: str, data_summary: str) -> str:
    """
    Build the prompt for generating a plain-English insight paragraph.

    Args:
        question     : the original user question
        data_summary : a compact string of actual data values from the DataFrame
                       (built by summarizer.py — never raw data, always aggregated)

    Returns:
        A single string ready to send to the LLM.

    Important: data_summary contains real numbers so the LLM cannot hallucinate.
    """
    return f"""You are a business analyst writing a short insight for a non-technical audience.

QUESTION ASKED:
{question}

DATA FINDINGS:
{data_summary}

Write a clear, concise insight paragraph (3-5 sentences) that:
1. Directly answers the question using the numbers in DATA FINDINGS above.
2. Highlights the most important trend or finding.
3. Uses plain English — no jargon, no SQL, no technical terms.
4. Only uses numbers that appear in DATA FINDINGS — do not invent or estimate.
5. Format all numbers with commas for readability (e.g., 126,345.07 not 126345.07).
6. Use proper spacing between words and numbers (e.g., "spend of 631,725.34" not "spendof631725.34").
7. Keep the paragraph natural and easy to read — like you're explaining it to a colleague.

INSIGHT:"""
