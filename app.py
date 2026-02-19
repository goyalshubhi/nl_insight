"""
app.py — Streamlit entry point for NL Insight.

Supports two data source modes:
  1. PostgreSQL — connect to an existing database (development/production)
  2. CSV Upload — upload a file and query it instantly (demos/non-technical users)

Phase 2 complete: Full NL → SQL → DataFrame pipeline working.
Phase 3 coming: Charts and EDA analysis.
"""

# ── Path fix (MUST be first) ──────────────────────────────────────────────────
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# ──────────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd

import config
from db.connector import get_engine, test_connection
from db.schema_reader import get_schema, format_schema_for_prompt
from db.csv_importer import create_engine_from_file, validate_uploaded_file
from pipeline.sql_generator import generate_sql
from pipeline.query_runner import run_query
from pipeline.visualizer import create_chart
from pipeline.eda import analyze_dataframe, format_insights_for_llm
from pipeline.summarizer import generate_insight
from pipeline.templates import get_templates_by_category, get_template_by_id
from pipeline.comparative_analyzer import is_comparison_query, enhance_comparison_result, generate_comparison_insight
from export.csv_exporter import export_to_csv, generate_data_dictionary
from logger import log

# ── Page Config ───────────────────────────────────────────────────────────────

st.set_page_config(
    page_title=config.APP_TITLE,
    page_icon=config.APP_ICON,
    layout="wide",
)

st.title(f"{config.APP_ICON} {config.APP_TITLE}")
st.caption("Ask business questions in plain English — no SQL required.")

st.divider()

# ── Data Source Selection ─────────────────────────────────────────────────────

with st.sidebar:
    st.header("📂 Data Source")
    
    data_mode = st.radio(
        "Choose your data source:",
        options=["PostgreSQL Database", "Upload CSV/Excel"],
        help="PostgreSQL: Connect to your existing database\nCSV Upload: Upload a file for instant analysis"
    )

# ── Mode 1: PostgreSQL ────────────────────────────────────────────────────────

if data_mode == "PostgreSQL Database":
    
    @st.cache_resource
    def load_engine():
        return get_engine()

    engine = load_engine()
    ok, msg = test_connection(engine)

    if ok:
        st.success(f"✅ Database connected — `{config.DATABASE_URL.split('@')[-1]}`")
        log("STARTUP", f"PostgreSQL connected: {msg}")
    else:
        st.error(f"❌ {msg}")
        st.info(
            "**PostgreSQL not running?** Switch to **Upload CSV/Excel** mode in the sidebar "
            "to try the system without a database."
        )
        log("STARTUP", f"PostgreSQL connection failed: {msg}")
        st.stop()

# ── Mode 2: CSV Upload ────────────────────────────────────────────────────────

elif data_mode == "Upload CSV/Excel":
    
    with st.sidebar:
        st.caption("📤 Upload your data file")
        uploaded_file = st.file_uploader(
            "Choose a CSV or Excel file",
            type=['csv', 'xlsx', 'xls'],
            help="Max 50 MB. The file stays in memory only — not saved to disk."
        )

    if not uploaded_file:
        st.info(
            "👈 **Upload a CSV or Excel file** in the sidebar to get started.\n\n"
            "The system will create a temporary database from your file and let you "
            "ask questions about it in plain English."
        )
        st.stop()

    # Validate file
    valid, error_msg = validate_uploaded_file(uploaded_file)
    if not valid:
        st.error(error_msg)
        st.stop()

    # Convert to SQLite database
    with st.spinner("📊 Processing your file..."):
        try:
            engine, table_name, row_count = create_engine_from_file(uploaded_file)
            st.success(
                f"✅ File processed — **{row_count:,} rows** loaded into table `{table_name}`"
            )
            log("CSV_MODE", f"SQLite engine created from {uploaded_file.name}")
        except ValueError as e:
            st.error(str(e))
            st.stop()

# ── Templates Sidebar (Now that engine exists) ────────────────────────────────

with st.sidebar:
    st.divider()
    st.header("📊 Analytics Templates")
    st.caption("One-click reports based on your data")
    
    # Only show templates if we have a valid engine
    try:
        templates_by_category = get_templates_by_category(engine)
        
        if templates_by_category:
            selected_template = None
            for category, templates in templates_by_category.items():
                with st.expander(f"{category}", expanded=False):
                    for template in templates:
                        if st.button(
                            template["title"],
                            key=f"template_{template['id']}",
                            help=template["description"],
                            use_container_width=True
                        ):
                            selected_template = template
            
            # Store selected template in session state
            if selected_template:
                st.session_state['selected_template'] = selected_template
                st.rerun()
        else:
            st.caption("No templates available for this schema")
    except Exception as e:
        st.caption(f"Templates unavailable: {str(e)[:50]}")

# ── Schema Sidebar ────────────────────────────────────────────────────────────

with st.sidebar:
    st.divider()
    st.header("📋 Database Schema")
    st.caption("Tables and columns available for queries")

    schema = get_schema(engine)

    if not schema:
        st.warning("No tables found in the database.")
    else:
        for table_name, columns in schema.items():
            with st.expander(f"🗂 {table_name}", expanded=True):
                for col in columns:
                    st.markdown(f"- `{col['name']}` — *{col['type']}*")

    st.divider()
    st.caption(f"🤖 Provider: `{config.LLM_PROVIDER}`")
    if config.LLM_PROVIDER == "groq":
        st.caption(f"Model: `{config.GROQ_MODEL}`")
    elif config.LLM_PROVIDER == "gemini":
        st.caption(f"Model: `{config.GEMINI_MODEL}`")
    else:
        st.caption(f"Model: `{config.OLLAMA_MODEL}`")
    st.caption(f"Row limit: `{config.QUERY_ROW_LIMIT}`")

# ── Question Input ────────────────────────────────────────────────────────────

st.subheader("💬 Ask a question about your data")

# Check if a template was selected
default_question = ""
auto_run = False

if 'selected_template' in st.session_state:
    template = st.session_state['selected_template']
    default_question = template['question']
    auto_run = True
    st.info(f"📋 **Template selected:** {template['title']}\n\n{template['description']}")
    # Clear the template after displaying
    del st.session_state['selected_template']

EXAMPLE_QUESTIONS = [
    # Simple aggregations
    "Which city had the highest total revenue?",
    "Show the top 5 customers by total spending.",
    "What is the count of orders by status?",
    
    # Intermediate - date filters
    "Which products were ordered in the last 30 days?",
    "Show monthly revenue for 2024.",
    
    # Advanced - window functions and ranking
    "Show the top 3 products by revenue in each category.",
    "Which customers made repeat purchases within 7 days?",
    
    # Anti-joins
    "Which customers have never placed an order?",
    "Show products that have never been ordered.",
]

# In CSV mode, show simpler examples
if data_mode == "Upload CSV/Excel":
    EXAMPLE_QUESTIONS = [
        "Show me the first 10 rows.",
        "What are the column names?",
        "Count the total number of rows.",
        "What is the average value in each numeric column?",
        "Show me rows where [column_name] is greater than [value].",
    ]

with st.expander("💡 Example questions — click to see ideas"):
    for q in EXAMPLE_QUESTIONS:
        st.markdown(f"- *{q}*")

question = st.text_area(
    label="Your question",
    value=default_question,  # Pre-fill with template question if selected
    placeholder="e.g. Which product has the lowest sales last month?",
    height=80,
    label_visibility="collapsed",
)

run_button = st.button("🔍 Analyse", type="primary", disabled=not question.strip())

# Auto-run if template was selected
if auto_run and question.strip():
    run_button = True

# ── Pipeline ──────────────────────────────────────────────────────────────────

if run_button and question.strip():
    log("QUESTION", question.strip())

    st.divider()

    # ── Step 1: Generate SQL ───────────────────────────────────────────────────
    with st.status("⚙️ Generating SQL...", expanded=True) as status:
        try:
            sql = generate_sql(question.strip(), engine)
            status.update(label="✅ SQL generated", state="complete")
        except (ValueError, RuntimeError) as e:
            status.update(label="❌ SQL generation failed", state="error")
            st.error(str(e))
            st.stop()

    # Show the generated SQL
    with st.expander("🔎 Generated SQL (click to see the query)"):
        st.code(sql, language="sql")

    # ── Step 2: Execute Query ──────────────────────────────────────────────────
    with st.status("⚙️ Running query...", expanded=True) as status:
        try:
            df = run_query(sql, engine)
            status.update(
                label=f"✅ Query complete — {len(df):,} rows returned",
                state="complete"
            )
        except RuntimeError as e:
            status.update(label="❌ Query execution failed", state="error")
            st.error(str(e))
            st.stop()

    # ── Step 3: Show Results ───────────────────────────────────────────────────
    st.subheader("📊 Results")

    if df.empty:
        st.info("The query returned no results. Try adjusting your question.")
    else:
        # Action buttons at the top
        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption(f"{len(df):,} rows × {len(df.columns)} columns")
        with col2:
            # CSV download button
            csv_data = export_to_csv(df)
            st.download_button(
                label="📥 Download CSV",
                data=csv_data,
                file_name="query_results.csv",
                mime="text/csv",
                help="Download results for Power BI, Excel, or further analysis"
            )
        
        # Show the raw data table
        st.dataframe(df, use_container_width=True)

        # Row limit warning
        if len(df) >= config.QUERY_ROW_LIMIT:
            st.warning(
                f"⚠️ Results are capped at {config.QUERY_ROW_LIMIT:,} rows. "
                "Add filters to your question for more specific results."
            )

    # ── Step 4: Comparative Analysis Enhancement ──────────────────────────────
    is_comparison = is_comparison_query(question.strip())
    
    if is_comparison and not df.empty:
        with st.status("🔄 Enhancing comparison analysis...", expanded=False) as status:
            df = enhance_comparison_result(df, question.strip())
            status.update(label="✅ Comparison metrics added", state="complete")
    
    # ── Step 5: Visualize ──────────────────────────────────────────────────────
    if not df.empty:
        with st.status("📈 Creating visualization...", expanded=False) as status:
            chart_result = create_chart(df)
            
            if isinstance(chart_result, list):
                # Multi-chart dashboard
                status.update(label=f"✅ Created {len(chart_result)} charts", state="complete")
            elif chart_result:
                # Single chart
                status.update(label="✅ Chart created", state="complete")
            else:
                status.update(label="ℹ️ No suitable chart for this data", state="complete")

        # Display charts
        if isinstance(chart_result, list):
            # Multi-chart dashboard - show side by side
            st.subheader("📊 Multi-Dimensional Analysis")
            cols = st.columns(min(len(chart_result), 2))  # Max 2 charts per row
            for idx, chart in enumerate(chart_result):
                with cols[idx % 2]:
                    st.plotly_chart(chart, use_container_width=True)
        elif chart_result:
            # Single chart
            st.plotly_chart(chart_result, use_container_width=True)

    # ── Step 6: EDA + Insight Summary ──────────────────────────────────────────
    if not df.empty:
        with st.status("🔍 Analyzing data...", expanded=False) as status:
            insights = analyze_dataframe(df)
            status.update(label="✅ Analysis complete", state="complete")

        # Generate AI insight summary
        with st.status("✨ Generating insight summary...", expanded=False) as status:
            data_summary = format_insights_for_llm(insights)
            
            try:
                if is_comparison:
                    # For comparison queries, add comparison-specific insight
                    comparison_insight = generate_comparison_insight(df, question.strip())
                    insight_text = f"{comparison_insight}\n\n" + generate_insight(question.strip(), data_summary)
                else:
                    insight_text = generate_insight(question.strip(), data_summary)
                    
                status.update(label="✅ Insight generated", state="complete")
            except Exception as e:
                status.update(label="⚠️ Insight generation failed", state="error")
                insight_text = f"Could not generate insight: {e}"

        # Display the insight
        st.subheader("💡 Key Insights")
        st.info(insight_text)

        # Show raw stats in an expander for transparency
        with st.expander("📊 Detailed statistics"):
            st.text(data_summary)
            
            st.divider()
            st.caption("📖 Data Dictionary (for documentation)")
            data_dict = generate_data_dictionary(df)
            st.text(data_dict)
