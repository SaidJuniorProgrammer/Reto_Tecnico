import os
import sqlite3
from datetime import datetime
from typing import Optional, Dict, Any, List

DB_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "orders.db")

class InsufficientStockError(Exception):
    pass

class ProductNotFoundError(Exception):
    pass

class DuplicateIdempotencyKeyError(Exception):
    pass

def get_connection():
    conn = sqlite3.connect(DB_PATH, timeout=10.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn

def init_db():
    conn = get_connection()
    with conn:
        # 1. Tabla de productos / inventario
        conn.execute("""
            CREATE TABLE IF NOT EXISTS products (
                id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                price REAL NOT NULL,
                stock INTEGER NOT NULL CHECK(stock >= 0)
            )
        """)

        # 2. Tabla de pedidos con restricción UNIQUE en clave de idempotencia
        conn.execute("""
            CREATE TABLE IF NOT EXISTS orders (
                id TEXT PRIMARY KEY,
                idempotency_key TEXT UNIQUE NOT NULL,
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL CHECK(quantity > 0),
                total_amount REAL NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('PENDIENTE_PAGO', 'PAGO_INCIERTO', 'PAGADO', 'RECHAZADO')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (product_id) REFERENCES products(id)
            )
        """)

        # 3. Tabla de reservas de inventario
        conn.execute("""
            CREATE TABLE IF NOT EXISTS reservations (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                order_id TEXT NOT NULL,
                product_id TEXT NOT NULL,
                quantity INTEGER NOT NULL,
                status TEXT NOT NULL CHECK(status IN ('RESERVED', 'COMMITTED', 'RELEASED')),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                FOREIGN KEY (order_id) REFERENCES orders(id)
            )
        """)

        # 4. Tabla de registro de respuestas idempotentes (para cachear respuestas exactas)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS idempotency_records (
                idempotency_key TEXT PRIMARY KEY,
                order_id TEXT NOT NULL,
                status_code INTEGER NOT NULL,
                response_json TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

    conn.close()
    seed_default_products()

def seed_default_products():
    """Inserta productos iniciales si la tabla está vacía."""
    conn = get_connection()
    with conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) as count FROM products")
        if cursor.fetchone()["count"] == 0:
            cursor.execute("""
                INSERT INTO products (id, name, price, stock)
                VALUES 
                    ('PROD-001', 'Smartphone Alpha', 500.0, 10),
                    ('PROD-002', 'Laptop Ultra', 1200.0, 5),
                    ('PROD-LIMITED', 'Edición Coleccionista', 150.0, 1)
            """)
    conn.close()

def get_product(product_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, stock FROM products WHERE id = ?", (product_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def list_products() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, name, price, stock FROM products")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_order_by_key(idempotency_key: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.id, o.idempotency_key, o.product_id, o.quantity, o.total_amount, o.status, 
               o.created_at, o.updated_at, p.name as product_name
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.idempotency_key = ?
    """, (idempotency_key,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_order_by_id(order_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.id, o.idempotency_key, o.product_id, o.quantity, o.total_amount, o.status, 
               o.created_at, o.updated_at, p.name as product_name
        FROM orders o
        JOIN products p ON o.product_id = p.id
        WHERE o.id = ?
    """, (order_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_reservation_for_order(order_id: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, order_id, product_id, quantity, status, created_at, updated_at FROM reservations WHERE order_id = ?", (order_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_order_with_reservation(order_id: str, idempotency_key: str, product_id: str, quantity: int, total_amount: float) -> Dict[str, Any]:
    """
    Operación atómica:
    1. Verifica existencia del producto.
    2. Descuenta stock atómicamente asegurando que stock >= quantity (nunca negativo).
    3. Registra el pedido en estado 'PENDIENTE_PAGO' con clave de idempotencia única.
    4. Registra la reserva en estado 'RESERVED'.
    """
    now = datetime.now().isoformat()
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            # 1. Comprobar producto
            cursor.execute("SELECT id, stock FROM products WHERE id = ?", (product_id,))
            prod = cursor.fetchone()
            if not prod:
                raise ProductNotFoundError(f"Producto '{product_id}' no encontrado.")

            # 2. Descuento atómico de stock (condicional)
            cursor.execute(
                "UPDATE products SET stock = stock - ? WHERE id = ? AND stock >= ?",
                (quantity, product_id, quantity)
            )
            if cursor.rowcount == 0:
                raise InsufficientStockError(f"Stock insuficiente para producto '{product_id}'. Stock disponible: {prod['stock']}, Solicitado: {quantity}")

            # 3. Crear pedido
            try:
                cursor.execute("""
                    INSERT INTO orders (id, idempotency_key, product_id, quantity, total_amount, status, created_at, updated_at)
                    VALUES (?, ?, ?, ?, ?, 'PENDIENTE_PAGO', ?, ?)
                """, (order_id, idempotency_key, product_id, quantity, total_amount, now, now))
            except sqlite3.IntegrityError as e:
                # Si falló por clave duplicada
                raise DuplicateIdempotencyKeyError(f"Clave de idempotencia duplicada: {idempotency_key}") from e

            # 4. Crear registro de reserva
            cursor.execute("""
                INSERT INTO reservations (order_id, product_id, quantity, status, created_at, updated_at)
                VALUES (?, ?, ?, 'RESERVED', ?, ?)
            """, (order_id, product_id, quantity, now, now))

    finally:
        conn.close()

    return get_order_by_id(order_id)

def update_order_status(order_id: str, new_status: str, reservation_status: Optional[str] = None, release_stock: bool = False) -> Dict[str, Any]:
    """
    Actualiza el estado del pedido y gestiona la reserva:
    - Si release_stock=True: libera la reserva solo si estaba en 'RESERVED', sumando el stock de vuelta.
    - Si reservation_status='COMMITTED': confirma la reserva definitiva del pedido pagado.
    """
    now = datetime.now().isoformat()
    conn = get_connection()
    try:
        with conn:
            cursor = conn.cursor()
            # 1. Actualizar estado del pedido
            cursor.execute("""
                UPDATE orders 
                SET status = ?, updated_at = ?
                WHERE id = ?
            """, (new_status, now, order_id))

            # 2. Manejo de reserva
            if release_stock:
                # Comprobar si hay una reserva en estado 'RESERVED' para liberar una sola vez
                cursor.execute("""
                    SELECT id, product_id, quantity, status 
                    FROM reservations 
                    WHERE order_id = ? AND status = 'RESERVED'
                """, (order_id,))
                res = cursor.fetchone()
                if res:
                    # Marcar reserva como RELEASED
                    cursor.execute("""
                        UPDATE reservations
                        SET status = 'RELEASED', updated_at = ?
                        WHERE id = ?
                    """, (now, res["id"]))
                    # Reintegrar stock al producto
                    cursor.execute("""
                        UPDATE products
                        SET stock = stock + ?
                        WHERE id = ?
                    """, (res["quantity"], res["product_id"]))

            elif reservation_status == "COMMITTED":
                cursor.execute("""
                    UPDATE reservations
                    SET status = 'COMMITTED', updated_at = ?
                    WHERE order_id = ? AND status = 'RESERVED'
                """, (now, order_id))

    finally:
        conn.close()

    return get_order_by_id(order_id)

def save_idempotency_record(idempotency_key: str, order_id: str, status_code: int, response_json: str):
    conn = get_connection()
    with conn:
        conn.execute("""
            INSERT OR REPLACE INTO idempotency_records (idempotency_key, order_id, status_code, response_json, created_at)
            VALUES (?, ?, ?, ?, ?)
        """, (idempotency_key, order_id, status_code, response_json, datetime.now().isoformat()))
    conn.close()

def get_idempotency_record(idempotency_key: str) -> Optional[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT idempotency_key, order_id, status_code, response_json, created_at FROM idempotency_records WHERE idempotency_key = ?", (idempotency_key,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def list_orders() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT o.id, o.idempotency_key, o.product_id, o.quantity, o.total_amount, o.status, 
               o.created_at, o.updated_at, p.name as product_name
        FROM orders o
        JOIN products p ON o.product_id = p.id
        ORDER BY o.created_at DESC
    """)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def list_reservations() -> List[Dict[str, Any]]:
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT id, order_id, product_id, quantity, status, created_at, updated_at FROM reservations ORDER BY created_at DESC")
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def reset_db():
    conn = get_connection()
    with conn:
        conn.execute("DELETE FROM idempotency_records")
        conn.execute("DELETE FROM reservations")
        conn.execute("DELETE FROM orders")
        conn.execute("DELETE FROM products")
    conn.close()
    seed_default_products()
