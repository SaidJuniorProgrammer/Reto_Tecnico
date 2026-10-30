import os
import sqlite3
from datetime import datetime

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "payments.db")

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS payments (
                payment_key TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                amount REAL NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('APPROVED', 'REJECTED')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)
    conn.close()

def get_payment_by_key(payment_key: str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT payment_key, order_id, amount, status, created_at FROM payments WHERE payment_key = ?", (payment_key,))
    row = cursor.fetchone()
    conn.close()
    if row:
        return dict(row)
    return None

def save_payment(payment_key: str, order_id: str, amount: float, status: str):
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT INTO payments (payment_key, order_id, amount, status, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (payment_key, order_id, amount, status, datetime.now().isoformat()))
    conn.close()
    return get_payment_by_key(payment_key)

def list_all_payments():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT payment_key, order_id, amount, status, created_at FROM payments ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def reset_db():
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM payments")
    conn.close()
