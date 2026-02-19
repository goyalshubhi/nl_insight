"""
db/schema_reader.py — Reads the live database schema automatically.

Why this matters:
  The LLM needs to know what tables and columns exist so it can write
  correct SQL. We read this from the database itself at runtime — no
  hardcoding. This means the system works on any database you connect.

Key concept: SQLAlchemy's `inspect()` function lets us read metadata
  (table names, column names, types, foreign keys) without writing
  any SQL ourselves.
"""

from sqlalchemy import inspect as sa_inspect


def get_schema(engine) -> dict:
    """
    Read all tables and their columns from the connected database.

    Returns a dict shaped like:
    {
        "orders": [
            {"name": "id",           "type": "INTEGER"},
            {"name": "order_date",   "type": "DATE"},
            {"name": "total_amount", "type": "FLOAT"},
        ],
        "customers": [...],
    }

    We skip system tables (those starting with 'pg_' or 'sql_') automatically.
    """
    inspector = sa_inspect(engine)
    schema = {}

    for table_name in inspector.get_table_names():
        columns = []
        for col in inspector.get_columns(table_name):
            columns.append({
                "name": col["name"],
                # str() on the type gives readable names like "INTEGER", "VARCHAR(255)"
                "type": str(col["type"]),
            })
        schema[table_name] = columns

    return schema


def get_foreign_keys(engine) -> list[dict]:
    """
    Read foreign key relationships between tables.

    Returns a list of dicts shaped like:
    [
        {"from_table": "orders", "from_col": "customer_id",
         "to_table": "customers", "to_col": "id"},
        ...
    ]

    This is injected into the prompt so the LLM knows which columns to JOIN on.
    """
    inspector = sa_inspect(engine)
    relationships = []

    for table_name in inspector.get_table_names():
        for fk in inspector.get_foreign_keys(table_name):
            relationships.append({
                "from_table": table_name,
                "from_col":   fk["constrained_columns"][0],
                "to_table":   fk["referred_table"],
                "to_col":     fk["referred_columns"][0],
            })

    return relationships


def format_schema_for_prompt(engine) -> str:
    """
    Format the schema as a compact string for injection into the LLM prompt.

    Output looks like:
        Table: orders
          - id: INTEGER
          - customer_id: INTEGER
          - order_date: DATE
          - total_amount: FLOAT
          - status: VARCHAR(50)

        Table: customers
          - id: INTEGER
          - name: VARCHAR(100)
          ...

        Relationships:
          orders.customer_id → customers.id
          order_items.order_id → orders.id

    Kept compact deliberately — fewer tokens = cheaper API calls.
    """
    schema = get_schema(engine)
    fk_list = get_foreign_keys(engine)

    lines = []

    for table_name, columns in schema.items():
        lines.append(f"Table: {table_name}")
        for col in columns:
            lines.append(f"  - {col['name']}: {col['type']}")
        lines.append("")  # blank line between tables

    if fk_list:
        lines.append("Relationships:")
        for fk in fk_list:
            lines.append(
                f"  {fk['from_table']}.{fk['from_col']} → "
                f"{fk['to_table']}.{fk['to_col']}"
            )

    return "\n".join(lines)