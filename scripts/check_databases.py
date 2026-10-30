import sys
import os

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)

import order_service.database as order_db
import payment_service.database as payment_db

def print_separator(title=""):
    print("\n" + "=" * 70)
    if title:
        print(f" {title.upper()} ")
        print("=" * 70)

def main():
    print_separator("INSPECCION DE BASE DE DATOS: ORDER API (orders.db)")
    
    # 1. Productos y Stock
    print("\n--- INVENTARIO / PRODUCTOS ---")
    products = order_db.list_products()
    print(f"{'ID':<15} | {'NOMBRE':<25} | {'PRECIO':<10} | {'STOCK':<8}")
    print("-" * 65)
    for p in products:
        print(f"{p['id']:<15} | {p['name']:<25} | ${p['price']:<9.2f} | {p['stock']:<8}")

    # 2. Pedidos
    print("\n--- PEDIDOS REGISTRADOS ---")
    orders = order_db.list_orders()
    if not orders:
        print("  (No hay pedidos registrados aún)")
    else:
        print(f"{'ORDER ID':<16} | {'IDEMPOTENCY KEY':<28} | {'ESTADO':<15} | {'CANT':<5} | {'TOTAL':<8}")
        print("-" * 80)
        for o in orders:
            print(f"{o['id']:<16} | {o['idempotency_key']:<28} | {o['status']:<15} | {o['quantity']:<5} | ${o['total_amount']:<7.2f}")

    # 3. Reservas de Inventario
    print("\n--- RESERVAS DE INVENTARIO ---")
    reservations = order_db.list_reservations()
    if not reservations:
        print("  (No hay reservas registradas aún)")
    else:
        print(f"{'ID':<5} | {'ORDER ID':<16} | {'PRODUCT ID':<15} | {'CANT':<5} | {'ESTADO':<12}")
        print("-" * 65)
        for r in reservations:
            print(f"{r['id']:<5} | {r['order_id']:<16} | {r['product_id']:<15} | {r['quantity']:<5} | {r['status']:<12}")

    print_separator("INSPECCION DE BASE DE DATOS: PAYMENT MOCK (payments.db)")
    payments = payment_db.list_all_payments()
    if not payments:
        print("  (No hay cobros registrados aún en el mock)")
    else:
        print(f"{'PAYMENT KEY':<28} | {'ORDER ID':<16} | {'ESTADO':<10} | {'MONTO':<8} | {'FECHA':<20}")
        print("-" * 90)
        for p in payments:
            print(f"{p['payment_key']:<28} | {p['order_id']:<16} | {p['status']:<10} | ${p['amount']:<7.2f} | {p['created_at']:<20}")

    print_separator("RESUMEN GENERAL")
    print(f"Total pedidos en SQLite:        {len(orders)}")
    print(f"Total reservas en SQLite:       {len(reservations)}")
    print(f"Total cobros en Mock SQLite:    {len(payments)}")
    print("=" * 70 + "\n")

if __name__ == "__main__":
    main()
