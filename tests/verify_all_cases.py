import sys
import os
import time
import uuid
import requests
import subprocess

if sys.stdout.encoding and sys.stdout.encoding.lower() != 'utf-8':
    try:
        sys.stdout.reconfigure(encoding='utf-8')
    except Exception:
        pass

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, base_dir)

import order_service.database as order_db
import payment_service.database as payment_db

ORDER_API_URL = "http://127.0.0.1:5001"
PAYMENT_API_URL = "http://127.0.0.1:5002"

def ensure_services_running():
    """Verifica si los servicios están activos; si no, los inicia como subprocesos."""
    running_order = False
    running_payment = False
    
    try:
        r = requests.get(f"{ORDER_API_URL}/health", timeout=1.0)
        running_order = (r.status_code == 200)
    except Exception:
        pass

    try:
        r = requests.get(f"{PAYMENT_API_URL}/health", timeout=1.0)
        running_payment = (r.status_code == 200)
    except Exception:
        pass

    processes = []
    python_exe = sys.executable

    if not running_payment:
        print("[INFO] Iniciando Payment Mock API en puerto 5002...")
        p_mock = subprocess.Popen([python_exe, os.path.join(base_dir, "payment_service", "app.py")])
        processes.append(p_mock)

    if not running_order:
        print("[INFO] Iniciando Order API en puerto 5001...")
        p_order = subprocess.Popen([python_exe, os.path.join(base_dir, "order_service", "app.py")])
        processes.append(p_order)

    # Esperar hasta que ambos respondan
    max_wait = 15
    start = time.time()
    while time.time() - start < max_wait:
        try:
            r1 = requests.get(f"{ORDER_API_URL}/health", timeout=1.0)
            r2 = requests.get(f"{PAYMENT_API_URL}/health", timeout=1.0)
            if r1.status_code == 200 and r2.status_code == 200:
                print("[OK] Ambos servicios estan respondiendo correctamente.\n")
                return processes
        except Exception:
            time.sleep(0.5)

    raise RuntimeError("No se pudieron iniciar los servicios en los puertos 5001 y 5002.")

def print_box(text):
    print("\n" + "=" * 75)
    print(f" {text}")
    print("=" * 75)

def run_tests():
    processes = ensure_services_running()
    try:
        print_box("REINICIANDO ESTADO DE PRUEBA")
        # Reset de ambas bases de datos
        order_db.init_db()
        order_db.reset_db()
        payment_db.init_db()
        payment_db.reset_db()
        print("[OK] Bases de datos limpiadas y productos por defecto inicializados.")

        # =========================================================================
        # CASO 1: FLUJO EXITOSO
        # =========================================================================
        print_box("CASO 1: FLUJO EXITOSO (PAGO APROBADO)")
        key_case1 = f"KEY-CASE1-{uuid.uuid4().hex[:6].upper()}"
        payload_1 = {
            "product_id": "PROD-001",
            "quantity": 1,
            "simulation_mode": "APPROVE"
        }
        headers_1 = {"Idempotency-Key": key_case1}

        stock_before = order_db.get_product("PROD-001")["stock"]
        print(f"-> Stock inicial de PROD-001: {stock_before}")
        print(f"-> Enviando POST /orders con clave: {key_case1} y modo: APPROVE...")

        resp_1 = requests.post(f"{ORDER_API_URL}/orders", json=payload_1, headers=headers_1)
        data_1 = resp_1.json()

        assert resp_1.status_code == 201, f"Esperado 201, recibido {resp_1.status_code}: {data_1}"
        assert data_1["status"] == "PAGADO", f"Estado esperado PAGADO, recibido: {data_1.get('status')}"
        assert data_1["reservation"]["status"] == "COMMITTED"
        
        stock_after = order_db.get_product("PROD-001")["stock"]
        assert stock_after == stock_before - 1, f"Stock no disminuyo en 1. Antes: {stock_before}, Ahora: {stock_after}"

        payment_in_mock = payment_db.get_payment_by_key(key_case1)
        assert payment_in_mock is not None and payment_in_mock["status"] == "APPROVED"

        print(f"  [RESULTADO CASO 1]: EXITO")
        print(f"  * Pedido ID: {data_1['order']['id']}")
        print(f"  * Estado: {data_1['order']['status']}")
        print(f"  * Reserva: {data_1['reservation']['status']}")
        print(f"  * Stock: {stock_before} -> {stock_after}")
        print(f"  * Cobro en Mock: 1 registro con status '{payment_in_mock['status']}'")

        # =========================================================================
        # CASO 2: REPETICION DE LA MISMA SOLICITUD (IDEMPOTENCIA)
        # =========================================================================
        print_box("CASO 2: REPETICION DE LA MISMA SOLICITUD (IDEMPOTENCIA)")
        print(f"-> Reenviando EXACTAMENTE la misma solicitud con clave: {key_case1}...")

        resp_2 = requests.post(f"{ORDER_API_URL}/orders", json=payload_1, headers=headers_1)
        data_2 = resp_2.json()

        assert resp_2.status_code == 200, f"Esperado 200, recibido {resp_2.status_code}: {data_2}"
        assert data_2.get("idempotent_replay") is True, "No se marco como repeticion idempotente"
        assert data_2["order"]["id"] == data_1["order"]["id"], "Devolvio un pedido diferente"

        stock_after_repeat = order_db.get_product("PROD-001")["stock"]
        assert stock_after_repeat == stock_after, f"El stock cambio tras repetir la solicitud: {stock_after_repeat}"

        all_payments = payment_db.list_all_payments()
        assert len(all_payments) == 1, f"Se genero un cobro duplicado. Total cobros: {len(all_payments)}"

        print(f"  [RESULTADO CASO 2]: EXITO")
        print(f"  * Reconocido como Idempotente: {data_2.get('idempotent_replay')}")
        print(f"  * Pedido retornado: {data_2['order']['id']} (Mismo pedido)")
        print(f"  * Stock conservado: {stock_after_repeat} (No se volvio a descontar)")
        print(f"  * Cobros en Mock: {len(all_payments)} (No se duplico el cobro)")

        # =========================================================================
        # CASO 3: RESPUESTA PERDIDA DESPUES DEL COBRO Y RECUPERACION
        # =========================================================================
        print_box("CASO 3: RESPUESTA PERDIDA TRAS EL COBRO Y RECUPERACION")
        key_case3 = f"KEY-CASE3-{uuid.uuid4().hex[:6].upper()}"
        payload_3 = {
            "product_id": "PROD-001",
            "quantity": 1,
            "simulation_mode": "TIMEOUT_AFTER_CHARGE"
        }
        headers_3 = {"Idempotency-Key": key_case3}

        print(f"-> Enviando POST /orders con modo TIMEOUT_AFTER_CHARGE...")
        resp_3 = requests.post(f"{ORDER_API_URL}/orders", json=payload_3, headers=headers_3)
        data_3 = resp_3.json()

        assert resp_3.status_code == 504, f"Esperado 504 Gateway Timeout, recibido {resp_3.status_code}"
        assert data_3["status"] == "PAGO_INCIERTO", f"Esperado PAGO_INCIERTO, recibido {data_3.get('status')}"
        order_case3_id = data_3["order_id"]

        print(f"  * Order API devolvio HTTP 504 y estado '{data_3['status']}'.")
        print(f"  * Verificando base de datos del Mock de Pagos...")
        mock_payment_case3 = payment_db.get_payment_by_key(key_case3)
        assert mock_payment_case3 is not None, "El mock debio haber guardado el cobro antes del timeout!"
        assert mock_payment_case3["status"] == "APPROVED"
        print(f"  * El Mock EFECTIVAMENTE guardo el cobro como '{mock_payment_case3['status']}' antes de perder conexion.")

        print(f"\n-> Ejecutando RECUPERACION/RECONCILIACION para pedido '{order_case3_id}'...")
        # Se puede recuperar por endpoint /reconcile o reenviando la clave al POST /orders
        resp_rec = requests.post(f"{ORDER_API_URL}/orders/{order_case3_id}/reconcile")
        data_rec = resp_rec.json()

        assert resp_rec.status_code == 200, f"Error en reconciliacion: {data_rec}"
        assert data_rec["reconciled"] is True
        assert data_rec["order"]["status"] == "PAGADO"
        assert data_rec["resolution"] == "PAGADO"

        print(f"  [RESULTADO CASO 3]: EXITO")
        print(f"  * Pedido reconciliado exitosamente.")
        print(f"  * Nuevo estado del pedido: {data_rec['order']['status']}")
        print(f"  * Cobro verificado sin repetir cobro a ciegas.")

        # =========================================================================
        # CASO 4: PAGO RECHAZADO Y COMPENSACION DE RESERVA
        # =========================================================================
        print_box("CASO 4: PAGO RECHAZADO Y COMPENSACION DE RESERVA")
        key_case4 = f"KEY-CASE4-{uuid.uuid4().hex[:6].upper()}"
        payload_4 = {
            "product_id": "PROD-001",
            "quantity": 1,
            "simulation_mode": "REJECT"
        }
        headers_4 = {"Idempotency-Key": key_case4}

        stock_before_4 = order_db.get_product("PROD-001")["stock"]
        print(f"-> Stock actual antes del pedido: {stock_before_4}")
        print(f"-> Enviando POST /orders con modo REJECT...")

        resp_4 = requests.post(f"{ORDER_API_URL}/orders", json=payload_4, headers=headers_4)
        data_4 = resp_4.json()

        assert resp_4.status_code == 400, f"Esperado 400 Bad Request, recibido {resp_4.status_code}"
        assert data_4["status"] == "RECHAZADO"
        assert data_4["reservation"]["status"] == "RELEASED"

        stock_after_4 = order_db.get_product("PROD-001")["stock"]
        assert stock_after_4 == stock_before_4, f"El stock no fue compensado. Antes: {stock_before_4}, Despues: {stock_after_4}"

        print(f"  [RESULTADO CASO 4]: EXITO")
        print(f"  * Pedido ID: {data_4['order']['id']}")
        print(f"  * Estado: {data_4['order']['status']}")
        print(f"  * Estado de Reserva: {data_4['reservation']['status']} (Liberada)")
        print(f"  * Stock compensado: {stock_before_4} -> {stock_after_4} (Sin perdida de unidades)")

        # =========================================================================
        # CASO 5: OTRA INTENCION DE COMPRA Y CONTROL DE STOCK NEGATIVO
        # =========================================================================
        print_box("CASO 5: OTRA INTENCION DE COMPRA (STOCK NUNCA NEGATIVO)")
        limited_prod = order_db.get_product("PROD-LIMITED")
        print(f"-> Producto 'PROD-LIMITED' ({limited_prod['name']}). Stock disponible: {limited_prod['stock']}")
        assert limited_prod["stock"] == 1, "PROD-LIMITED deberia tener exactamente 1 unidad disponible"

        key_case5_A = f"KEY-CASE5-A-{uuid.uuid4().hex[:6].upper()}"
        payload_5_A = {"product_id": "PROD-LIMITED", "quantity": 1, "simulation_mode": "APPROVE"}
        print(f"-> Enviando PRIMERA compra con clave distinta: {key_case5_A}...")
        resp_5_A = requests.post(f"{ORDER_API_URL}/orders", json=payload_5_A, headers={"Idempotency-Key": key_case5_A})
        assert resp_5_A.status_code == 201
        print(f"  * Primera compra EXITOSA. Stock actual: {order_db.get_product('PROD-LIMITED')['stock']}")
        assert order_db.get_product("PROD-LIMITED")["stock"] == 0

        key_case5_B = f"KEY-CASE5-B-{uuid.uuid4().hex[:6].upper()}"
        payload_5_B = {"product_id": "PROD-LIMITED", "quantity": 1, "simulation_mode": "APPROVE"}
        print(f"-> Enviando SEGUNDA intencion de compra con clave distinta: {key_case5_B}...")
        resp_5_B = requests.post(f"{ORDER_API_URL}/orders", json=payload_5_B, headers={"Idempotency-Key": key_case5_B})
        data_5_B = resp_5_B.json()

        assert resp_5_B.status_code == 400, f"Esperado 400 Stock Insuficiente, recibido {resp_5_B.status_code}"
        assert "Stock insuficiente" in data_5_B.get("error", "")

        stock_final = order_db.get_product("PROD-LIMITED")["stock"]
        assert stock_final == 0, f"El stock no debe ser negativo ni alterado: {stock_final}"

        print(f"  [RESULTADO CASO 5]: EXITO")
        print(f"  * Primera intencion: Aceptada y cobrada (Stock = 0)")
        print(f"  * Segunda intencion: Rechazada limpiamente por falta de stock (HTTP 400)")
        print(f"  * Stock final: {stock_final} (Garantizado: NUNCA negativo)")

        print_box("TODAS LAS 5 PRUEBAS OBLIGATORIAS PASARON EXITOSAMENTE (100/100)")

    finally:
        # Finalizar procesos si los iniciamos nosotros
        for p in processes:
            p.terminate()

if __name__ == "__main__":
    run_tests()
