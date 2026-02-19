"""
data/seed_db.py — Create tables and seed the nl_insight database.

Run this ONCE before starting the app:
    python data/seed_db.py

What this creates:
    customers    (~200 rows)
    products     (~50 rows)
    orders       (~800 rows, last 2 years)
    order_items  (~1600 rows)

Uses Faker to generate realistic-looking data so demo questions
like "which city had the most orders?" return meaningful answers.

Safe to re-run — it drops and recreates tables each time.
"""

import sys
import os
import random
from datetime import datetime, timedelta

from faker import Faker
from sqlalchemy import text

# Allow running from project root: python data/seed_db.py
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from db.connector import get_engine, test_connection

fake = Faker("en_IN")   # Indian locale — gives Indian names, cities
random.seed(42)          # Reproducible fake data
Faker.seed(42)


# ── Schema Definition ─────────────────────────────────────────────────────────

CREATE_TABLES_SQL = """
DROP TABLE IF EXISTS order_items CASCADE;
DROP TABLE IF EXISTS orders CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS customers CASCADE;

CREATE TABLE customers (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(100) NOT NULL,
    email       VARCHAR(150) UNIQUE NOT NULL,
    city        VARCHAR(80),
    state       VARCHAR(80),
    signup_date DATE NOT NULL
);

CREATE TABLE products (
    id          SERIAL PRIMARY KEY,
    name        VARCHAR(150) NOT NULL,
    category    VARCHAR(80) NOT NULL,
    price       NUMERIC(10, 2) NOT NULL,
    stock_qty   INTEGER DEFAULT 0
);

CREATE TABLE orders (
    id              SERIAL PRIMARY KEY,
    customer_id     INTEGER REFERENCES customers(id),
    order_date      DATE NOT NULL,
    status          VARCHAR(30) NOT NULL,
    total_amount    NUMERIC(12, 2) NOT NULL
);

CREATE TABLE order_items (
    id          SERIAL PRIMARY KEY,
    order_id    INTEGER REFERENCES orders(id),
    product_id  INTEGER REFERENCES products(id),
    quantity    INTEGER NOT NULL,
    unit_price  NUMERIC(10, 2) NOT NULL
);
"""


# ── Seed Data ─────────────────────────────────────────────────────────────────

CATEGORIES = ["Electronics", "Clothing", "Books", "Home & Kitchen", "Sports", "Beauty"]

PRODUCT_NAMES = {
    "Electronics":    ["Wireless Earbuds", "USB-C Hub", "Mechanical Keyboard", "Webcam HD", "Smart Speaker", "Portable Charger", "LED Monitor", "Gaming Mouse"],
    "Clothing":       ["Cotton T-Shirt", "Denim Jeans", "Formal Shirt", "Sports Shorts", "Winter Jacket", "Casual Hoodie"],
    "Books":          ["Python Cookbook", "Data Science Handbook", "Clean Code", "SQL for Analysts", "The Pragmatic Programmer"],
    "Home & Kitchen": ["Coffee Maker", "Air Fryer", "Non-stick Pan", "Electric Kettle", "Blender", "Toaster"],
    "Sports":         ["Yoga Mat", "Resistance Bands", "Skipping Rope", "Water Bottle", "Dumbbells 5kg"],
    "Beauty":         ["Face Wash", "Moisturizer SPF50", "Shampoo 500ml", "Serum Vitamin C", "Lip Balm"],
}

STATUSES = ["completed", "completed", "completed", "shipped", "pending", "cancelled"]
# "completed" is listed 3× so it appears ~50% of the time — more realistic


def generate_customers(n=200) -> list[dict]:
    customers = []
    for _ in range(n):
        signup = fake.date_between(start_date="-3y", end_date="-1m")
        customers.append({
            "name":        fake.name(),
            "email":       fake.unique.email(),
            "city":        fake.city(),
            "state":       fake.state(),
            "signup_date": signup,
        })
    return customers


def generate_products() -> list[dict]:
    products = []
    for category, names in PRODUCT_NAMES.items():
        for name in names:
            # Price ranges vary by category
            if category == "Electronics":
                price = round(random.uniform(499, 9999), 2)
            elif category in ("Clothing", "Beauty", "Sports"):
                price = round(random.uniform(199, 1999), 2)
            elif category == "Books":
                price = round(random.uniform(299, 799), 2)
            else:
                price = round(random.uniform(599, 4999), 2)

            products.append({
                "name":      name,
                "category":  category,
                "price":     price,
                "stock_qty": random.randint(0, 500),
            })
    return products


def generate_orders_and_items(
    customer_ids: list[int],
    products: list[dict],
    n_orders: int = 800,
) -> tuple[list[dict], list[dict]]:
    orders = []
    items = []

    for order_idx in range(n_orders):
        # Spread orders across the last 2 years
        order_date = fake.date_between(start_date="-2y", end_date="today")
        customer_id = random.choice(customer_ids)
        status = random.choice(STATUSES)

        # 1–4 line items per order
        n_items = random.randint(1, 4)
        chosen_products = random.sample(products, k=min(n_items, len(products)))

        order_total = 0.0
        order_item_rows = []
        for prod in chosen_products:
            qty = random.randint(1, 3)
            unit_price = prod["price"]
            order_total += qty * unit_price
            order_item_rows.append({
                "order_idx":  order_idx,   # placeholder, replaced after INSERT
                "product_id": prod["id"],
                "quantity":   qty,
                "unit_price": unit_price,
            })

        orders.append({
            "customer_id":  customer_id,
            "order_date":   order_date,
            "status":       status,
            "total_amount": round(order_total, 2),
            "_items":       order_item_rows,   # carry items alongside for easy insert
        })

    return orders


# ── Main ──────────────────────────────────────────────────────────────────────

def seed():
    engine = get_engine()

    ok, msg = test_connection(engine)
    if not ok:
        print(f"❌ {msg}")
        sys.exit(1)
    print(f"✅ {msg}")

    with engine.begin() as conn:

        # 1. Create tables
        print("Creating tables...")
        conn.execute(text(CREATE_TABLES_SQL))

        # 2. Insert customers
        print("Inserting customers...")
        customer_data = generate_customers(200)
        conn.execute(
            text("INSERT INTO customers (name, email, city, state, signup_date) "
                 "VALUES (:name, :email, :city, :state, :signup_date)"),
            customer_data,
        )
        customer_ids = [
            row[0] for row in conn.execute(text("SELECT id FROM customers")).fetchall()
        ]

        # 3. Insert products
        print("Inserting products...")
        product_data = generate_products()
        conn.execute(
            text("INSERT INTO products (name, category, price, stock_qty) "
                 "VALUES (:name, :category, :price, :stock_qty)"),
            product_data,
        )
        # Re-fetch with IDs assigned by the DB
        raw_products = conn.execute(
            text("SELECT id, name, category, price FROM products")
        ).fetchall()
        products_with_ids = [
            {"id": r[0], "name": r[1], "category": r[2], "price": float(r[3])}
            for r in raw_products
        ]

        # 4. Insert orders + order_items
        print("Inserting orders and order items...")
        orders = generate_orders_and_items(customer_ids, products_with_ids, n_orders=800)

        for order in orders:
            result = conn.execute(
                text("INSERT INTO orders (customer_id, order_date, status, total_amount) "
                     "VALUES (:customer_id, :order_date, :status, :total_amount) "
                     "RETURNING id"),
                {
                    "customer_id":  order["customer_id"],
                    "order_date":   order["order_date"],
                    "status":       order["status"],
                    "total_amount": order["total_amount"],
                },
            )
            order_id = result.fetchone()[0]

            for item in order["_items"]:
                conn.execute(
                    text("INSERT INTO order_items (order_id, product_id, quantity, unit_price) "
                         "VALUES (:order_id, :product_id, :quantity, :unit_price)"),
                    {
                        "order_id":   order_id,
                        "product_id": item["product_id"],
                        "quantity":   item["quantity"],
                        "unit_price": item["unit_price"],
                    },
                )

    # Summary
    with engine.connect() as conn:
        for table in ("customers", "products", "orders", "order_items"):
            count = conn.execute(text(f"SELECT COUNT(*) FROM {table}")).scalar()
            print(f"  {table}: {count} rows")

    print("\n✅ Database seeded successfully. You can now run: streamlit run app.py")


if __name__ == "__main__":
    seed()