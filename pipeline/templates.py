"""
pipeline/templates.py — Schema-aware analytics templates.

Instead of hardcoding templates for one specific database, this module
analyzes the connected database schema and generates appropriate templates
dynamically.

Design philosophy:
  Pattern detection + template generation = works on ANY database.
  
Key concept: We detect patterns (customer data, time-series, etc.) and
generate templates that use the actual column names from the schema.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from db.schema_reader import get_schema
from logger import log


def detect_schema_patterns(schema: dict) -> dict:
    """
    Analyze a database schema and detect common data patterns.
    
    Three-tier detection strategy:
      1. Keyword matching (fast, covers 70-80% of cases)
      2. If nothing found → generic fallback
      3. If user opts in → LLM analysis (slow but universal)
    
    Args:
        schema: Dict from get_schema() — {table_name: [columns]}
    
    Returns:
        Dict of detected patterns with metadata:
        {
            "patterns": ["customer_data", "time_series", ...],
            "tables": {...},
            "columns": {...},
        }
    """
    if not schema:
        return {"patterns": ["generic"], "tables": {}, "columns": {}}
    
    patterns = []
    
    # Get first table (primary table for generic queries)
    first_table = list(schema.keys())[0]
    
    # Collect all columns across all tables
    all_columns = {}
    for table_name, columns in schema.items():
        all_columns[table_name] = {
            "numeric": [],
            "date": [],
            "categorical": [],
            "all_names": []
        }
        
        for col in columns:
            col_name = col['name'].lower()
            col_type = col['type'].upper()
            
            all_columns[table_name]["all_names"].append(col['name'])
            
            # Numeric detection
            if any(t in col_type for t in ['INT', 'FLOAT', 'NUMERIC', 'DECIMAL', 'REAL', 'DOUBLE']):
                # Skip ID columns
                if 'id' not in col_name or col_name.endswith('_count') or col_name.endswith('_amount'):
                    all_columns[table_name]["numeric"].append(col['name'])
            
            # Date detection
            if any(t in col_type for t in ['DATE', 'TIME', 'TIMESTAMP']) or any(k in col_name for k in ['date', 'time', 'created', 'updated']):
                all_columns[table_name]["date"].append(col['name'])
            
            # Categorical detection (strings that aren't IDs)
            if any(t in col_type for t in ['CHAR', 'TEXT', 'STRING']):
                if 'id' not in col_name:
                    all_columns[table_name]["categorical"].append(col['name'])
    
    # ── TIER 1: Keyword-based pattern detection ────────────────────────────────
    first_table_cols = all_columns[first_table]
    all_col_names = [c.lower() for c in first_table_cols["all_names"]]
    
    # Pattern 1: Customer/user data
    if any(keyword in all_col_names for keyword in ['customer', 'client', 'user', 'name', 'email']):
        patterns.append("customer_data")
        log("TEMPLATE", "Detected customer data pattern")
    
    # Pattern 2: Product/inventory data
    if any(keyword in all_col_names for keyword in ['product', 'item', 'sku', 'price', 'stock', 'inventory']):
        patterns.append("product_data")
        log("TEMPLATE", "Detected product data pattern")
    
    # Pattern 3: Sales/revenue data
    if any(keyword in all_col_names for keyword in ['revenue', 'sales', 'amount', 'total', 'price']):
        patterns.append("revenue_data")
        log("TEMPLATE", "Detected revenue data pattern")
    
    # Pattern 4: Time-series (date + numeric columns)
    if first_table_cols["date"] and first_table_cols["numeric"]:
        patterns.append("time_series")
        log("TEMPLATE", "Detected time-series pattern")
    
    # Pattern 5: Categorical + numeric (for aggregations)
    if first_table_cols["categorical"] and first_table_cols["numeric"]:
        patterns.append("categorical_numeric")
        log("TEMPLATE", "Detected categorical+numeric pattern")
    
    # ── TIER 2: Check if we found anything useful ──────────────────────────────
    # If we only detected generic structural patterns (time_series, categorical_numeric)
    # but no domain-specific patterns, try LLM analysis
    domain_patterns = [p for p in patterns if p in ["customer_data", "product_data", "revenue_data"]]
    
    if not domain_patterns and patterns:
        # We have structural patterns but no domain understanding
        # Keep the structural patterns and try LLM for domain context
        log("TEMPLATE", "Only structural patterns found, attempting LLM analysis")
        llm_patterns = _detect_patterns_with_llm(schema, first_table, all_columns)
        if llm_patterns:
            patterns.extend(llm_patterns)
    elif not patterns:
        # ── TIER 3: LLM Fallback for completely unknown schemas ────────────────
        log("TEMPLATE", "No patterns detected via keywords, attempting LLM analysis")
        llm_patterns = _detect_patterns_with_llm(schema, first_table, all_columns)
        if llm_patterns:
            patterns = llm_patterns
        else:
            patterns.append("generic")
    
    return {
        "patterns": patterns if patterns else ["generic"],
        "tables": all_columns,
        "first_table": first_table,
    }


def _detect_patterns_with_llm(schema: dict, first_table: str, all_columns: dict) -> list[str]:
    """
    Use LLM to analyze schema and detect domain patterns.
    
    This is called only when keyword matching finds nothing useful.
    Adds 2-3 seconds latency but works on any schema.
    
    Args:
        schema: Full schema dict
        first_table: Name of primary table
        all_columns: Analyzed columns from detect_schema_patterns
    
    Returns:
        List of detected patterns, or empty list if LLM fails
    """
    try:
        from llm.gemini_client import call_llm
        
        # Build a compact schema description for the LLM
        table_cols = all_columns[first_table]
        col_list = ", ".join(table_cols["all_names"][:10])  # First 10 columns only
        
        prompt = f"""Analyze this database schema and identify what domain/industry it belongs to.

TABLE: {first_table}
COLUMNS: {col_list}

Based on the column names, what kind of data is this? Choose ALL that apply:
- customer_data (if it tracks customers, users, clients)
- product_data (if it tracks products, items, inventory)
- revenue_data (if it tracks sales, revenue, transactions)
- employee_data (if it tracks employees, staff, HR)
- iot_sensor_data (if it tracks sensor readings, measurements)
- healthcare_data (if it tracks patients, medical records)
- educational_data (if it tracks students, courses, grades)
- logistics_data (if it tracks shipping, delivery, warehouses)
- generic (if it doesn't fit any specific domain)

Return ONLY a comma-separated list of patterns. No explanation.
Example: customer_data, revenue_data"""

        response = call_llm(prompt).strip().lower()
        
        # Parse the response
        detected = []
        for pattern in response.split(','):
            pattern = pattern.strip()
            if pattern in ["customer_data", "product_data", "revenue_data", "employee_data", 
                          "iot_sensor_data", "healthcare_data", "educational_data", "logistics_data"]:
                detected.append(pattern)
                log("TEMPLATE", f"LLM detected pattern: {pattern}")
        
        return detected if detected else []
        
    except Exception as e:
        log("TEMPLATE_LLM_ERROR", f"LLM analysis failed: {e}")
        return []


def generate_templates_for_schema(engine) -> list[dict]:
    """
    Generate appropriate templates based on the connected database schema.
    
    Args:
        engine: SQLAlchemy engine
    
    Returns:
        List of template dicts with id, category, title, question, description
    """
    schema = get_schema(engine)
    analysis = detect_schema_patterns(schema)
    
    patterns = analysis["patterns"]
    first_table = analysis["first_table"]
    table_cols = analysis["tables"].get(first_table, {})
    
    templates = []
    
    # Get convenient references to column lists
    numeric_cols = table_cols.get("numeric", [])
    date_cols = table_cols.get("date", [])
    categorical_cols = table_cols.get("categorical", [])
    
    first_numeric = numeric_cols[0] if numeric_cols else None
    first_date = date_cols[0] if date_cols else None
    first_categorical = categorical_cols[0] if categorical_cols else None
    
    # ── TIME SERIES TEMPLATES ──────────────────────────────────────────────────
    if "time_series" in patterns and first_date and first_numeric:
        templates.append({
            "id": "trend_over_time",
            "category": "📈 Trends",
            "title": f"{first_numeric.replace('_', ' ').title()} Over Time",
            "question": f"Show {first_numeric} by {first_date} over time.",
            "description": f"Visualize how {first_numeric} changes over time"
        })
        
        templates.append({
            "id": "monthly_summary",
            "category": "📈 Trends",
            "title": "Monthly Summary",
            "question": f"Show total {first_numeric} grouped by month.",
            "description": "Monthly aggregation for trend analysis"
        })
    
    # ── CATEGORICAL + NUMERIC TEMPLATES ────────────────────────────────────────
    if "categorical_numeric" in patterns and first_categorical and first_numeric:
        templates.append({
            "id": "top_by_category",
            "category": "🏆 Rankings",
            "title": f"Top 10 by {first_categorical.replace('_', ' ').title()}",
            "question": f"Show top 10 {first_categorical} by total {first_numeric}.",
            "description": f"Highest {first_numeric} across different {first_categorical}"
        })
        
        templates.append({
            "id": "breakdown_by_category",
            "category": "📊 Breakdown",
            "title": f"Distribution by {first_categorical.replace('_', ' ').title()}",
            "question": f"Show total {first_numeric} grouped by {first_categorical}.",
            "description": f"Break down {first_numeric} by {first_categorical}"
        })
        
        if len(categorical_cols) >= 2:
            second_categorical = categorical_cols[1]
            templates.append({
                "id": "multi_dimension",
                "category": "📊 Breakdown",
                "title": f"Multi-Dimensional View",
                "question": f"Show {first_numeric} by {first_categorical} and {second_categorical}.",
                "description": f"Compare across {first_categorical} and {second_categorical}"
            })
    
    # ── REVENUE-SPECIFIC TEMPLATES ─────────────────────────────────────────────
    if "revenue_data" in patterns:
        revenue_col = next((c for c in numeric_cols if any(k in c.lower() for k in ['revenue', 'amount', 'total', 'sales'])), first_numeric)
        
        if revenue_col:
            templates.append({
                "id": "total_revenue",
                "category": "💰 Revenue",
                "title": "Total Revenue Summary",
                "question": f"What is the total {revenue_col}?",
                "description": "Overall revenue figure"
            })
            
            if first_categorical:
                templates.append({
                    "id": "revenue_by_segment",
                    "category": "💰 Revenue",
                    "title": f"Revenue by {first_categorical.replace('_', ' ').title()}",
                    "question": f"Show {revenue_col} grouped by {first_categorical}, ordered from highest to lowest.",
                    "description": f"Revenue breakdown by {first_categorical}"
                })
    
    # ── CUSTOMER-SPECIFIC TEMPLATES ────────────────────────────────────────────
    if "customer_data" in patterns:
        customer_col = next((c for c in categorical_cols if 'customer' in c.lower() or 'client' in c.lower() or 'name' in c.lower()), first_categorical)
        
        if customer_col and first_numeric:
            templates.append({
                "id": "top_customers",
                "category": "👥 Customers",
                "title": "Top Customers",
                "question": f"Show top 10 {customer_col} by total {first_numeric}.",
                "description": "Your most valuable customers"
            })
        
        # Count distinct customers
        if customer_col:
            templates.append({
                "id": "customer_count",
                "category": "👥 Customers",
                "title": "Customer Count",
                "question": f"How many unique {customer_col} are there?",
                "description": "Total customer base size"
            })
    
    # ── PRODUCT-SPECIFIC TEMPLATES ─────────────────────────────────────────────
    if "product_data" in patterns:
        product_col = next((c for c in categorical_cols if any(k in c.lower() for k in ['product', 'item', 'sku'])), first_categorical)
        
        if product_col and first_numeric:
            templates.append({
                "id": "top_products",
                "category": "📦 Products",
                "title": "Best Selling Products",
                "question": f"Show top 10 {product_col} by total {first_numeric}.",
                "description": "Most popular products"
            })
        
        # Stock/inventory if available
        stock_col = next((c for c in numeric_cols if any(k in c.lower() for k in ['stock', 'inventory', 'quantity'])), None)
        if stock_col:
            templates.append({
                "id": "low_stock",
                "category": "📦 Products",
                "title": "Low Stock Alert",
                "question": f"Show {product_col} where {stock_col} is less than 50.",
                "description": "Items that may need restocking"
            })
    
    # ── EMPLOYEE/HR-SPECIFIC TEMPLATES ─────────────────────────────────────────
    if "employee_data" in patterns:
        employee_col = next((c for c in categorical_cols if any(k in c.lower() for k in ['employee', 'staff', 'name'])), first_categorical)
        dept_col = next((c for c in categorical_cols if 'department' in c.lower() or 'dept' in c.lower()), None)
        
        if employee_col and first_numeric:
            templates.append({
                "id": "top_employees",
                "category": "👥 Employees",
                "title": "Top Performers",
                "question": f"Show top 10 {employee_col} by {first_numeric}.",
                "description": "Highest performing employees"
            })
        
        if dept_col and first_numeric:
            templates.append({
                "id": "by_department",
                "category": "👥 Employees",
                "title": "Metrics by Department",
                "question": f"Show total {first_numeric} grouped by {dept_col}.",
                "description": "Performance breakdown by department"
            })
    
    # ── IOT/SENSOR-SPECIFIC TEMPLATES ──────────────────────────────────────────
    if "iot_sensor_data" in patterns:
        sensor_col = next((c for c in categorical_cols if any(k in c.lower() for k in ['sensor', 'device', 'machine'])), first_categorical)
        reading_col = next((c for c in numeric_cols if any(k in c.lower() for k in ['temperature', 'reading', 'value', 'measure'])), first_numeric)
        
        if sensor_col and reading_col and first_date:
            templates.append({
                "id": "sensor_trends",
                "category": "🔌 IoT",
                "title": f"{reading_col.replace('_', ' ').title()} Trends",
                "question": f"Show {reading_col} over time for each {sensor_col}.",
                "description": "Sensor reading patterns over time"
            })
        
        if reading_col:
            templates.append({
                "id": "anomaly_readings",
                "category": "🔌 IoT",
                "title": "Unusual Readings",
                "question": f"Show {reading_col} values that are significantly higher or lower than average.",
                "description": "Detect anomalous sensor readings"
            })
    
    # ── LOGISTICS-SPECIFIC TEMPLATES ───────────────────────────────────────────
    if "logistics_data" in patterns:
        shipment_col = next((c for c in categorical_cols if any(k in c.lower() for k in ['shipment', 'delivery', 'tracking'])), first_categorical)
        status_col = next((c for c in categorical_cols if 'status' in c.lower()), None)
        
        if status_col:
            templates.append({
                "id": "delivery_status",
                "category": "🚚 Logistics",
                "title": "Delivery Status Breakdown",
                "question": f"Show count of shipments by {status_col}.",
                "description": "Overview of shipment statuses"
            })
        
        if first_date and first_numeric:
            templates.append({
                "id": "delivery_performance",
                "category": "🚚 Logistics",
                "title": "Delivery Performance",
                "question": f"Show {first_numeric} by {first_date} to track delivery trends.",
                "description": "Logistics metrics over time"
            })
    
    # ── GENERIC TEMPLATES (ALWAYS AVAILABLE) ───────────────────────────────────
    templates.append({
        "id": "preview_data",
        "category": "🔍 General",
        "title": "Preview Data",
        "question": f"Show the first 10 rows from {first_table}.",
        "description": "Quick look at your data"
    })
    
    if first_numeric:
        templates.append({
            "id": "summary_stats",
            "category": "🔍 General",
            "title": f"{first_numeric.replace('_', ' ').title()} Statistics",
            "question": f"What are the minimum, maximum, and average values of {first_numeric}?",
            "description": "Basic descriptive statistics"
        })
    
    if len(numeric_cols) >= 2:
        templates.append({
            "id": "correlation",
            "category": "🔍 General",
            "title": f"Compare {numeric_cols[0]} vs {numeric_cols[1]}",
            "question": f"Show {numeric_cols[0]} and {numeric_cols[1]} side by side.",
            "description": "Compare two metrics"
        })
    
    log("TEMPLATE", f"Generated {len(templates)} templates for schema with patterns: {patterns}")
    return templates


def get_all_templates(engine):
    """
    Main entry point: generate templates for the connected database.
    
    Args:
        engine: SQLAlchemy engine
    
    Returns:
        List of template dicts
    """
    return generate_templates_for_schema(engine)


def get_template_by_id(template_id: str, engine):
    """Get a specific template by its ID."""
    templates = get_all_templates(engine)
    for t in templates:
        if t["id"] == template_id:
            return t
    return None


def get_templates_by_category(engine) -> dict:
    """
    Group templates by category for UI display.
    
    Returns:
        {
            "📈 Trends": [template1, template2, ...],
            "🏆 Rankings": [...],
            ...
        }
    """
    templates = get_all_templates(engine)
    grouped = {}
    for t in templates:
        category = t["category"]
        if category not in grouped:
            grouped[category] = []
        grouped[category].append(t)
    return grouped
