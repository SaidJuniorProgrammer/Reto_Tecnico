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

def main():
    print("==================================================")
    print("Inicializando Bases de Datos SQLite...")
    print("==================================================")

    order_db.init_db()
    order_db.reset_db()
    print(f"[OK] Base de datos 'orders.db' creada/reiniciada en: {order_db.DB_PATH}")

    payment_db.init_db()
    payment_db.reset_db()
    print(f"[OK] Base de datos 'payments.db' creada/reiniciada en: {payment_db.DB_PATH}")

    print("\nProductos iniciales disponibles:")
    for p in order_db.list_products():
        print(f"  - [{p['id']}] {p['name']} | Precio: ${p['price']} | Stock inicial: {p['stock']}")

    print("\nInicializacion completada con exito.")

if __name__ == "__main__":
    main()
