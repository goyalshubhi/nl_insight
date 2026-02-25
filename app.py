"""
app.py — Streamlit entry point for NL Insight.

Complete system with all features:
- PostgreSQL + CSV upload modes
- Query history with re-run
- Smart follow-up suggestions
- Data quality reports
- Anomaly detection
- Bullet-point insights
"""

# ── Path fix ───────────────────────────────────────────────────────────────────
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
# ──────────────────────────────────────────────────────────────────────────────

import streamlit as st
import pandas as pd

import config
from db.connector import get_engine, test_connection
from db.schema_reader import get_schema
from db.csv_importer import create_engine_from_file, validate_uploaded_file
from pipeline.sql_generator import generate_sql
from pipeline.query_runner import run_query
from pipeline.visualizer import create_chart
from pipeline.eda import analyze_dataframe, format_insights_for_llm
from pipeline.summarizer import generate_insight
from pipeline.comparative_analyzer import is_comparison_query, enhance_comparison_result, generate_comparison_insight
from pipeline.query_history import init_history, add_to_history, get_history, format_timestamp
from pipeline.data_quality import analyze_data_quality, format_quality_report
from pipeline.followup_suggestions import generate_followup_questions
from pipeline.anomaly_detector import detect_anomalies
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

# Initialize history
init_history()


# ── Session state keys ─────────────────────────────────────────────────────────
# We manage the question input via session_state so "click-to-run" (history/followups)
# can reliably populate the text box and auto-execute on rerun.
st.session_state.setdefault("question_input", "")
st.session_state.setdefault("pending_question", None)   # question to inject into textbox on next rerun
st.session_state.setdefault("auto_run", False)          # whether to auto-execute Analyse on rerun
# ── Sidebar: Data Source + History ────────────────────────────────────────────

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

    valid, error_msg = validate_uploaded_file(uploaded_file)
    if not valid:
        st.error(error_msg)
        st.stop()

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

# ── Query History Sidebar ──────────────────────────────────────────────────────

with st.sidebar:
    st.divider()
    st.header("📜 Query History")
    
    history = get_history()
    
    if history:
        st.caption(f"{len(history)} recent queries")
        
        for idx, entry in enumerate(history[:5]):  # Show last 5
            with st.expander(
                f"🕐 {format_timestamp(entry['timestamp'])} • {entry['row_count']} rows",
                expanded=False
            ):
                st.caption(entry['question'])
                if st.button("🔄 Re-run", key=f"rerun_{idx}"):
                    st.session_state['pending_question'] = entry['question']
                    st.session_state['auto_run'] = True
                    st.rerun()
    else:
        st.caption("No queries yet")

# ── Schema Sidebar ────────────────────────────────────────────────────────────

with st.sidebar:
    st.divider()
    st.header("📋 Database Schema")
    st.caption("Tables and columns available")

    schema = get_schema(engine)

    if not schema:
        st.warning("No tables found in the database.")
    else:
        for table_name, columns in schema.items():
            with st.expander(f"🗂 {table_name}", expanded=False):
                for col in columns:
                    st.markdown(f"- `{col['name']}` — *{col['type']}*")

    st.divider()
    st.caption(f"🤖 Provider: `{config.LLM_PROVIDER}`")
    if config.LLM_PROVIDER == "groq":
        st.caption(f"Model: `{config.GROQ_MODEL}`")
    st.caption(f"Row limit: `{config.QUERY_ROW_LIMIT}`")

# ── Question Input ────────────────────────────────────────────────────────────

st.subheader("💬 Ask a question about your data")

EXAMPLE_QUESTIONS = [
    "Which city had the highest total revenue?",
    "Show the top 5 customers by total spending.",
    "What is the count of orders by status?",
    "Which products were ordered in the last 30 days?",
    "Compare Electronics and Clothing category revenue.",
]

if data_mode == "Upload CSV/Excel":
    EXAMPLE_QUESTIONS = [
        "Show me the first 10 rows.",
        "What is the total in the first numeric column?",
        "Count rows grouped by the first categorical column.",
    ]

with st.expander("💡 Example questions"):
    for q in EXAMPLE_QUESTIONS:
        st.markdown(f"- *{q}*")

# Check for re-run from history or follow-up
# If something set a pending question, inject it into the textbox state.
if st.session_state.get("pending_question"):
    st.session_state["question_input"] = st.session_state["pending_question"]
    st.session_state["pending_question"] = None

# DEBUG PANEL
with st.expander("🔧 DEBUG: Session State", expanded=False):
    st.write("Full session state:", dict(st.session_state))

question = st.text_area(
    label="Your question",
    key="question_input",
    placeholder="e.g. Which product has the lowest sales last month?",
    height=80,
    label_visibility="collapsed",
)

st.caption("💡 Click the **Analyse** button below to run your query")

run_button = st.button("🔍 Analyse", type="primary", disabled=not question.strip())

# Auto-run if a follow-up/history click requested it
if st.session_state.get("auto_run") and question.strip():
    run_button = True
# ── Pipeline ──────────────────────────────────────────────────────────────────

if run_button and question.strip():
    # Prevent auto-run from triggering repeatedly on subsequent reruns
    st.session_state['auto_run'] = False

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
            add_to_history(question.strip(), 0, success=False)
            st.stop()

    with st.expander("🔎 Generated SQL"):
        st.code(sql, language="sql")

    # ── Step 2: Execute Query ──────────────────────────────────────────────────
    with st.status("⚙️ Running query...", expanded=True) as status:
        try:
            df = run_query(sql, engine)
            status.update(
                label=f"✅ Query complete — {len(df):,} rows returned",
                state="complete"
            )
            add_to_history(question.strip(), len(df), success=True)
        except RuntimeError as e:
            status.update(label="❌ Query execution failed", state="error")
            st.error(str(e))
            add_to_history(question.strip(), 0, success=False)
            st.stop()

    # ── Step 3: Results + Download ─────────────────────────────────────────────
    st.subheader("📊 Results")

    if df.empty:
        st.info("The query returned no results. Try adjusting your question.")
    else:
        col1, col2 = st.columns([3, 1])
        with col1:
            st.caption(f"{len(df):,} rows × {len(df.columns)} columns")
        with col2:
            csv_data = export_to_csv(df)
            st.download_button(
                label="📥 Download CSV",
                data=csv_data,
                file_name="query_results.csv",
                mime="text/csv",
                help="Download for Power BI or Excel"
            )
        
        st.dataframe(df, use_container_width=True)

        if len(df) >= config.QUERY_ROW_LIMIT:
            st.warning(
                f"⚠️ Results capped at {config.QUERY_ROW_LIMIT:,} rows. "
                "Add filters for more specific results."
            )

    # ── Step 4: Data Quality Check ─────────────────────────────────────────────
    if not df.empty:
        with st.status("🔍 Checking data quality...", expanded=False) as status:
            quality = analyze_data_quality(df)
            status.update(label=quality['summary'], state="complete")
        
        if quality['missing_values'] or quality['duplicate_rows'] or quality['outliers']:
            with st.expander("⚠️ Data Quality Issues Detected"):
                st.markdown(format_quality_report(quality))

    # ── Step 5: Anomaly Detection ──────────────────────────────────────────────
    if not df.empty and len(df) >= 3:
        anomalies = detect_anomalies(df, question.strip())
        
        if anomalies:
            st.subheader("🚨 Anomalies Detected")
            for anomaly in anomalies:
                if anomaly['severity'] == 'high':
                    st.error(f"{anomaly['icon']} {anomaly['message']}")
                elif anomaly['severity'] == 'medium':
                    st.warning(f"{anomaly['icon']} {anomaly['message']}")
                else:
                    st.info(f"{anomaly['icon']} {anomaly['message']}")

    # ── Step 6: Comparison Enhancement ─────────────────────────────────────────
    is_comparison = is_comparison_query(question.strip())
    
    if is_comparison and not df.empty:
        with st.status("🔄 Enhancing comparison...", expanded=False) as status:
            df = enhance_comparison_result(df, question.strip())
            status.update(label="✅ Comparison metrics added", state="complete")
    
    # ── Step 7: Visualize ──────────────────────────────────────────────────────
    if not df.empty:
        with st.status("📈 Creating visualization...", expanded=False) as status:
            chart_result = create_chart(df)
            
            if isinstance(chart_result, list):
                status.update(label=f"✅ Created {len(chart_result)} charts", state="complete")
            elif chart_result:
                status.update(label="✅ Chart created", state="complete")
            else:
                status.update(label="ℹ️ No suitable chart", state="complete")

        if isinstance(chart_result, list):
            st.subheader("📊 Multi-Dimensional Analysis")
            cols = st.columns(min(len(chart_result), 2))
            for idx, chart in enumerate(chart_result):
                with cols[idx % 2]:
                    st.plotly_chart(chart, use_container_width=True)
        elif chart_result:
            st.plotly_chart(chart_result, use_container_width=True)

    # ── Step 8: Insights (Bullet Points) ───────────────────────────────────────
    if not df.empty:
        with st.status("🔍 Analyzing data...", expanded=False) as status:
            insights = analyze_dataframe(df)
            status.update(label="✅ Analysis complete", state="complete")

        with st.status("✨ Generating insights...", expanded=False) as status:
            data_summary = format_insights_for_llm(insights)
            
            try:
                if is_comparison:
                    comparison_insight = generate_comparison_insight(df, question.strip())
                    insight_text = f"**Comparison Finding:**\n{comparison_insight}\n\n**Detailed Insights:**\n" + generate_insight(question.strip(), data_summary)
                else:
                    insight_text = generate_insight(question.strip(), data_summary)
                    
                status.update(label="✅ Insights generated", state="complete")
            except Exception as e:
                status.update(label="⚠️ Insight generation failed", state="error")
                insight_text = f"Could not generate insights: {e}"

        st.subheader("💡 Key Insights")
        st.info(insight_text)

        with st.expander("📊 Detailed statistics"):
            st.text(data_summary)
            st.divider()
            st.caption("📖 Data Dictionary")
            st.text(generate_data_dictionary(df))

    # ── Step 9: Follow-Up Suggestions ──────────────────────────────────────────
    if not df.empty and len(df) > 0:
        with st.status("💭 Generating follow-up suggestions...", expanded=False) as status:
            try:
                followups = generate_followup_questions(question.strip(), df, insight_text)
                if followups:
                    status.update(label="✅ Suggestions ready", state="complete")
                else:
                    status.update(label="ℹ️ No suggestions", state="complete")
            except Exception as e:
                status.update(label="⚠️ Suggestion generation failed", state="error")
                followups = []
        
        if followups:
            st.subheader("🔮 What to explore next?")
            st.caption("Click any question to run it")
            
            cols = st.columns(3)
            for idx, followup_q in enumerate(followups):
                with cols[idx % 3]:
                    if st.button(
                        followup_q,
                        key=f"followup_{idx}",
                        use_container_width=True,
                        type="secondary"
                    ):
                        st.session_state['pending_question'] = followup_q
                        st.session_state['auto_run'] = True
                        st.rerun()
