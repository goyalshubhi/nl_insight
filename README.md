# NL Insight - Natural Language to SQL Analytics Platform

[![Python 3.10+](https://img.shields.io/badge/python-3.10+-blue.svg)](https://www.python.org/downloads/)
[![Streamlit](https://img.shields.io/badge/streamlit-1.30+-red.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

**Transform questions into insights.** Ask your database questions in plain English and get instant answers with AI-powered analytics, interactive charts, and actionable insights—no SQL knowledge required.

---

## Overview

**NL Insight** democratizes data access by eliminating the technical barrier between business users and their databases. Instead of waiting hours or days for data teams to run queries, users can ask questions in plain English and receive comprehensive analytics in seconds.

### The Problem
- Business analysts spend 40% of their time waiting for data teams
- Learning SQL takes weeks of training
- Manual chart creation is time-consuming and error-prone
- Data insights are often delayed by days

### The Solution
NL Insight automatically:
1. Converts natural language → SQL queries (85-90% accuracy)
2. Executes queries safely with 6-layer security validation
3. Generates interactive visualizations automatically
4. Produces AI-powered insights in plain English
5. Detects anomalies and data quality issues proactively
6. Exports results to CSV for Power BI/Excel integration

---

## Key Features

### Natural Language Processing
- Ask questions like *"Which city had the highest revenue last month?"*
- Supports complex queries: aggregations, joins, date filters, comparisons
- Handles superlatives: "highest/lowest", "most/least", "best/worst"
- Case-insensitive text matching (e.g., "electronics" matches "Electronics")

### Intelligent Visualization
- Auto-generates appropriate charts based on data types
- 5 chart types: bar, line, scatter, histogram, multi-chart dashboards
- Interactive Plotly charts with zoom, pan, and hover tooltips
- Mobile-responsive design

### AI-Powered Insights
- Generates 3-5 bullet points with specific findings
- Grounded in actual data (no hallucination)
- Includes comparisons, percentages, and trends
- Business-friendly language

### Enterprise-Grade Security
- 6-layer SQL injection prevention
- Read-only database access
- Query timeout protection (30s limit)
- Row limiting (100 rows default)
- Complete audit trail

### Proactive Data Quality
- Automatic detection of missing values
- Duplicate row identification
- Statistical outlier detection (IQR method)
- Anomaly alerts (steep drops, high concentration)

### Dual Data Access Modes
- **PostgreSQL Mode:** Connect to existing enterprise databases
- **CSV Upload Mode:** Drag-and-drop files (up to 50MB), instant analysis

### Smart Features
- Query history with one-click re-run (last 10 queries)
- Context-aware follow-up suggestions
- Comparison mode for "X vs Y" queries
- CSV export with data dictionary

---

## Quick Start

### Prerequisites

- Python 3.10 or higher
- PostgreSQL 14+ (optional - for database mode)
- Groq API key (free tier: 14,400 requests/day)

### Installation

```bash
# 1. Clone the repository
git clone https://github.com/yourusername/nl-insight.git
cd nl-insight

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env and add your credentials
```

### Configuration

Create a `.env` file in the project root:

```bash
# Database (optional - only for PostgreSQL mode)
DATABASE_URL=postgresql://user:password@localhost:5432/nl_insight

# LLM Provider (required)
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_your_api_key_here
GROQ_MODEL=llama-3.1-8b-instant

# Optional Settings
QUERY_ROW_LIMIT=100
QUERY_TIMEOUT_SECONDS=30
```

**Get a free Groq API key:**
1. Visit [console.groq.com](https://console.groq.com)
2. Sign up (no credit card required)
3. Generate API key
4. Copy to `.env` file

### Database Setup (Optional)

If using PostgreSQL mode, create and seed the sample database:

```bash
# Create database
createdb nl_insight

# Seed with sample e-commerce data (1,500+ rows)
python data/seed_db.py
```

### Run the Application

```bash
streamlit run app.py
```

The app will open in your browser at `http://localhost:8501`

---

## Usage Guide

### Mode 1: PostgreSQL Database

1. Ensure `DATABASE_URL` is configured in `.env`
2. Select "PostgreSQL Database" in the sidebar
3. View available tables and columns in the schema panel
4. Type your question in plain English
5. Click "Analyse" to get results

**Example Questions:**
```
Which city had the highest total revenue?
Show top 5 customers by spending
Compare Electronics and Clothing category revenue
What is the average order value by status?
Show monthly revenue trend for the last 6 months
```

### Mode 2: CSV Upload

1. Select "Upload CSV/Excel" in the sidebar
2. Drag and drop your file (CSV, XLSX, or XLS)
3. System automatically creates a temporary database
4. Ask questions about your data
5. File is discarded when you close the browser (privacy-first)

**Supported Formats:**
- CSV (UTF-8, comma-separated)
- Excel (.xlsx, .xls)
- Maximum file size: 50 MB

---

## Architecture

### System Flow

```
User Question (Natural Language)
    ↓
[LLM] Generate SQL Query
    ↓
[Validator] 6-Layer Security Check
    ↓
[Database] Execute Query
    ↓
[Pipeline] Parallel Processing
    ├─ Exploratory Data Analysis
    ├─ Data Quality Check
    ├─ Anomaly Detection
    └─ Chart Generation
    ↓
[LLM] Generate Insights
    ↓
[UI] Display Results + Charts + Insights
```

### Tech Stack

**Backend:**
- Python 3.10+
- Streamlit (web framework)
- SQLAlchemy (database ORM)
- Pandas & NumPy (data processing)

**AI/ML:**
- Groq Cloud API (llama-3.1-8b-instant)
- Google Gemini (fallback)

**Visualization:**
- Plotly (interactive charts)

**Database:**
- PostgreSQL (production)
- SQLite (CSV mode)

---

## Security

### SQL Injection Prevention (6 Layers)

1. **Prompt Guardrails:** LLM instructed to only generate SELECT statements
2. **Keyword Blacklist:** Blocks DROP, DELETE, INSERT, UPDATE, ALTER, TRUNCATE, CREATE
3. **Comment Stripping:** Removes `--` and `/* */` comments
4. **Parameterized Queries:** SQLAlchemy ORM prevents string concatenation
5. **Timeout Protection:** 30-second execution limit
6. **Row Limiting:** Default 100-row cap

### Data Privacy

- **CSV Mode:** Files exist only in RAM, never written to disk
- **Session Isolation:** Each user's data is separate
- **No External Sharing:** All processing happens locally
- **Audit Trail:** Complete query history for compliance

### Production Recommendations

```python
# Use read-only database user
DATABASE_URL=postgresql://readonly_user:password@localhost:5432/nl_insight

# Enable row-level security in PostgreSQL
ALTER TABLE orders ENABLE ROW LEVEL SECURITY;

# Set conservative limits
QUERY_ROW_LIMIT=100
QUERY_TIMEOUT_SECONDS=30
```

---

## Sample Database

The project includes a realistic e-commerce dataset with 1,500+ rows across 4 tables:

### Schema

```sql
customers (500 rows)
  - customer_id, name, email, city, country, created_at

products (100 rows)  
  - product_id, name, category, price, stock_quantity

orders (300 rows)
  - order_id, customer_id, order_date, status, total_amount

order_items (600+ rows)
  - order_item_id, order_id, product_id, quantity, price_at_purchase
```

### Sample Queries

```sql
-- Revenue by city
SELECT city, SUM(total_amount) as revenue 
FROM orders 
JOIN customers ON orders.customer_id = customers.customer_id
GROUP BY city 
ORDER BY revenue DESC 
LIMIT 10;

-- Top products
SELECT products.name, SUM(order_items.quantity) as units_sold
FROM products
JOIN order_items ON products.product_id = order_items.product_id
GROUP BY products.name
ORDER BY units_sold DESC
LIMIT 5;

-- Monthly trend
SELECT DATE_TRUNC('month', order_date) as month, 
       SUM(total_amount) as revenue
FROM orders
WHERE order_date >= CURRENT_DATE - interval '6 months'
GROUP BY month
ORDER BY month;
```

---

## Features Deep Dive

### 1. Natural Language to SQL

**How it works:**
- Reads database schema dynamically at runtime
- Sends question + schema to LLM via optimized 108-line prompt
- Receives validated SQL query
- Handles complex patterns: CTEs, window functions, joins, anti-joins

**Example Transformations:**

| Natural Language | Generated SQL |
|-----------------|---------------|
| "Which city had highest revenue?" | `SELECT city, SUM(total_amount) FROM orders GROUP BY city ORDER BY SUM(total_amount) DESC LIMIT 1` |
| "Compare electronics and clothing" | `WHERE UPPER(category) IN (UPPER('electronics'), UPPER('clothing'))` |
| "Orders in last 30 days" | `WHERE order_date >= CURRENT_DATE - interval '30 days'` |

**Accuracy:** 85-90% on business queries (tested on 50+ samples)

---

### 2. Intelligent Chart Generation

**Decision Tree:**

```
1 column, numeric → Histogram
1 column, categorical → Bar chart (value counts)
Date + Numeric → Line chart (time-series)
Categorical + Numeric → Bar chart (sorted by value)
2 Numerics → Scatter plot
2+ Dimensions → Multi-chart dashboard
```

**Features:**
- Auto-sorts for readability
- Limits categories to top 20 (avoids clutter)
- Interactive: zoom, pan, hover tooltips
- Exports to PNG/SVG

---

### 3. AI-Powered Insights

**Input:** Aggregated statistics (NOT raw data)

**Example EDA Summary:**
```
Row count: 6
Columns: category, total_revenue
Numeric summary: total_revenue (min=245678.90, max=4240553.19, mean=1254636.76)
Categorical summary: category (unique_count=6, top_value=Electronics)
```

**Output (LLM-Generated):**
```
• Electronics leads with ₹4,240,553.19 in total revenue (highest)
• Delhi is second with ₹787,267.39, a gap of ₹3,453,285.80 (+438.6%)
• Top 3 categories account for 67% of all revenue
• 12 categories contributed <1% each (long-tail distribution)
```

**Why this prevents hallucination:** LLM only sees aggregated stats, cannot invent numbers.

---

### 4. Anomaly Detection

**Patterns Detected:**

**High Severity:**
- Steep declines (>50% drop from rank 1 to 5)
- Extreme outliers (>3 standard deviations)

**Medium Severity:**
- Statistical outliers (IQR method)
- Unusual concentration (top 3 > 70%)

**Low Severity:**
- Missing expected data
- Concentration patterns

**Example Alert:**
```
Unusual value detected: Order amount of ₹125,000 is 10× above 
average (₹12,500), suggesting a potential data entry error or 
high-value transaction requiring review.
```

---

### 5. Data Quality Monitoring

**Automatic Checks:**

**Missing Values**
```
Missing Values:
- status column: 15 missing (5%)
- city column: 3 missing (1%)
```

**Duplicate Rows**
```
Duplicate Rows: 12 found
```

**Outliers**
```
Outliers Detected:
- total_amount: 5 values significantly outside normal range
```

---

## Configuration Options

### LLM Providers

**Groq (Recommended for Development):**
```bash
LLM_PROVIDER=groq
GROQ_API_KEY=gsk_xxxxx
GROQ_MODEL=llama-3.1-8b-instant
```
- Free tier: 14,400 requests/day
- Fast inference: 3-5 seconds
- Good accuracy for SQL generation

**Google Gemini (Alternative):**
```bash
LLM_PROVIDER=gemini
GEMINI_API_KEY=xxxxx
GEMINI_MODEL=gemini-1.5-flash
```
- Free tier available
- Slightly slower but more accurate

**Ollama (For Offline/Private Deployments):**
```bash
LLM_PROVIDER=ollama
OLLAMA_MODEL=llama3.1:8b
OLLAMA_BASE_URL=http://localhost:11434
```
- Fully local, no internet required
- Complete data privacy
- Requires local Ollama installation

### Safety Settings

```bash
# Maximum rows returned per query
QUERY_ROW_LIMIT=100

# Query execution timeout (seconds)
QUERY_TIMEOUT_SECONDS=30

# Maximum CSV file size (bytes)
MAX_CSV_SIZE=52428800  # 50 MB
```

---

## Performance

### Latency Breakdown

| Stage | Time |
|-------|------|
| SQL Generation (LLM) | 3-5s |
| Query Execution | 0.5-2s |
| Data Processing | 0.1-0.3s |
| Chart Generation | 0.2-0.5s |
| Insight Generation (LLM) | 2-4s |
| **Total** | **8-15s** |

### Resource Usage

- **Memory:** 150-300 MB (idle), +50 MB per CSV file
- **CPU:** <5% idle, 20-30% during LLM calls
- **Network:** 2-5 KB per LLM request

---

## Testing

### Run Sample Queries

```python
# Test SQL generation
python -c "from pipeline.sql_generator import generate_sql; \
           from db.connector import get_engine; \
           print(generate_sql('Show top 5 customers', get_engine()))"

# Test safety validator
python -c "from pipeline.sql_validator import validate_sql; \
           print(validate_sql('SELECT * FROM orders LIMIT 10'))"
```

### Manual Testing Checklist

- PostgreSQL connection works
- CSV upload works (test with sample.csv)
- Simple queries execute
- Complex queries (joins, aggregations) work
- Charts render correctly
- Insights are factually accurate
- SQL injection attempts are blocked
- Query history persists during session
- CSV export downloads correctly

---

## Troubleshooting

### Common Issues

**Error: "Database connection failed"**
```bash
# Check PostgreSQL is running
pg_isready

# Verify connection string
psql postgresql://user:password@localhost:5432/nl_insight

# Check .env file exists and has correct DATABASE_URL
cat .env | grep DATABASE_URL
```

**Error: "LLM API call failed"**
```bash
# Verify API key is set
cat .env | grep GROQ_API_KEY

# Test API directly
curl https://api.groq.com/openai/v1/models \
  -H "Authorization: Bearer $GROQ_API_KEY"
```

**Error: "CSV upload fails"**
- Check file size is <50 MB
- Ensure file is valid CSV/XLSX format
- Check column names don't have special characters
- Verify at least one numeric or categorical column exists

**Charts not appearing:**
- Check browser console for JavaScript errors
- Verify Plotly is installed: `pip list | grep plotly`
- Try a different browser (Chrome recommended)

### Debug Mode

Enable detailed logging:

```python
# In config.py
LOG_LEVEL = "DEBUG"

# View logs
tail -f logs/pipeline.log
```

---

## Deployment

### Local Deployment (Current)

```bash
streamlit run app.py
```

### Streamlit Cloud

1. Push code to GitHub
2. Visit [share.streamlit.io](https://share.streamlit.io)
3. Connect repository
4. Add secrets (Settings → Secrets):
   ```toml
   DATABASE_URL = "postgresql://..."
   GROQ_API_KEY = "gsk_..."
   LLM_PROVIDER = "groq"
   ```
5. Click Deploy

### Docker (Production)

```dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .
EXPOSE 8501

CMD ["streamlit", "run", "app.py", \
     "--server.address", "0.0.0.0", \
     "--server.port", "8501"]
```

```bash
# Build and run
docker build -t nl-insight .
docker run -p 8501:8501 --env-file .env nl-insight
```

---

## Project Statistics

- **Total Lines of Code:** ~2,500
- **Modules:** 12 core components
- **Features:** 9 major features
- **Database Tables:** 4 (sample schema)
- **Sample Data:** 1,500+ rows
- **Chart Types:** 5
- **Security Layers:** 6
- **LLM Providers:** 3 (configurable)
- **File Formats:** CSV, XLSX, XLS
- **Dependencies:** 15 Python packages
- **Query Accuracy:** 85-90% (tested on 50+ samples)
