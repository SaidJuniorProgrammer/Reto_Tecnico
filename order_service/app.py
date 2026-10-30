import os
import uuid
import logging
import requests
from flask import Flask, request, jsonify, render_template
from database import (
    init_db,
    get_product,
    list_products,
    get_order_by_key,
    get_order_by_id,
    get_reservation_for_order,
    create_order_with_reservation,
    update_order_status,
    save_idempotency_record,
    get_idempotency_record,
    list_orders,
    list_reservations,
    reset_db,
    InsufficientStockError,
    ProductNotFoundError,
    DuplicateIdempotencyKeyError
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [OrderService] %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__, template_folder="templates")
init_db()

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Idempotency-Key"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

PAYMENT_SERVICE_URL = os.environ.get("PAYMENT_SERVICE_URL", "http://127.0.0.1:5002")
PAYMENT_TIMEOUT_SECONDS = float(os.environ.get("PAYMENT_TIMEOUT_SECONDS", "2.0"))

@app.route("/", methods=["GET"])
def index():
    accept = request.headers.get("Accept", "")
    if "application/json" in accept and "text/html" not in accept:
        return jsonify({
            "service": "Order API",
            "status": "ONLINE",
            "message": "Servicio de Pedidos y Gestion de Idempotencia activo."
        }), 200
    return render_template("index.html")

@app.route("/mock-payments", methods=["GET"])
def proxy_mock_payments():
    try:
        r = requests.get(f"{PAYMENT_SERVICE_URL}/payments", timeout=2.0)
        return jsonify(r.json()), r.status_code
    except Exception as e:
        return jsonify({"count": 0, "payments": [], "error": str(e)}), 200

@app.route("/favicon.ico", methods=["GET"])
def favicon():
    return "", 204

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "UP", "service": "Order API"}), 200

@app.route("/products", methods=["GET"])
def products():
    prods = list_products()
    return jsonify({"products": prods}), 200

def perform_reconciliation(order: dict) -> dict:
    """
    Consulta al Payment Mock API para resolver el estado de un pedido en PAGO_INCIERTO.
    NUNCA vuelve a cobrar a ciegas.
    """
    idempotency_key = order["idempotency_key"]
    order_id = order["id"]
    logger.info(f"Iniciando reconciliación de pedido '{order_id}' con clave '{idempotency_key}'...")

    try:
        resp = requests.get(
            f"{PAYMENT_SERVICE_URL}/payments/{idempotency_key}",
            timeout=PAYMENT_TIMEOUT_SECONDS
        )
        if resp.status_code == 200:
            payment_info = resp.json()
            payment_status = payment_info.get("status")
            if payment_status == "APPROVED":
                logger.info(f"Reconciliación: El cobro fue efectivamente APROBADO en el mock. Actualizando pedido a PAGADO.")
                updated = update_order_status(order_id, "PAGADO", reservation_status="COMMITTED")
                return {
                    "reconciled": True,
                    "resolution": "PAGADO",
                    "payment_info": payment_info,
                    "order": updated,
                    "message": "Pago verificado y aprobado en el servicio de pagos. Pedido marcado como PAGADO."
                }
            elif payment_status == "REJECTED":
                logger.info(f"Reconciliación: El cobro fue RECHAZADO en el mock. Liberando reserva de inventario.")
                updated = update_order_status(order_id, "RECHAZADO", release_stock=True)
                return {
                    "reconciled": True,
                    "resolution": "RECHAZADO",
                    "payment_info": payment_info,
                    "order": updated,
                    "message": "Pago verificado como rechazado. Reserva de inventario liberada exitosamente."
                }
        elif resp.status_code == 404:
            logger.warning(f"Reconciliación: El cobro no existe en el mock de pagos. Liberando reserva.")
            updated = update_order_status(order_id, "RECHAZADO", release_stock=True)
            return {
                "reconciled": True,
                "resolution": "RECHAZADO_NO_COBRADO",
                "order": updated,
                "message": "No se encontró registro de cobro en la pasarela. Pedido rechazado y reserva liberada."
            }
        else:
            logger.error(f"Error inesperado al consultar pasarela: {resp.status_code}")
            return {
                "reconciled": False,
                "order": order,
                "message": f"No se pudo consultar el servicio de pagos (HTTP {resp.status_code}). Continúa en PAGO_INCIERTO."
            }
    except requests.exceptions.RequestException as e:
        logger.error(f"Falla de comunicación al intentar reconciliar pedido '{order_id}': {e}")
        return {
            "reconciled": False,
            "order": order,
            "message": f"Servicio de pagos no disponible durante la reconciliación: {str(e)}"
        }

@app.route("/orders", methods=["POST"])
def create_order():
    # Obtener clave de idempotencia del header o del body
    idempotency_key = request.headers.get("Idempotency-Key")
    data = request.get_json(silent=True) or {}
    
    if not idempotency_key:
        idempotency_key = data.get("idempotency_key")
        
    if not idempotency_key:
        return jsonify({
            "error": "Clave de idempotencia obligatoria. Envíela en el header 'Idempotency-Key' o en el body como 'idempotency_key'."
        }), 400

    # 1. Comprobar si ya existe un pedido con esa clave de idempotencia
    existing_order = get_order_by_key(idempotency_key)
    if existing_order:
        logger.info(f"Recepción de solicitud repetida con clave '{idempotency_key}'. Estado actual: {existing_order['status']}")
        
        # Si el estado quedó incierto, la repetición del pedido dispara la recuperación automática
        if existing_order["status"] == "PAGO_INCIERTO":
            logger.info("El pedido estaba en PAGO_INCIERTO. Procediendo a recuperar estado con el servicio de pagos...")
            rec_result = perform_reconciliation(existing_order)
            return jsonify({
                "idempotent_replay": True,
                "action": "AUTOMATIC_RECONCILIATION",
                "result": rec_result
            }), 200

        # Si ya está en un estado final (PAGADO o RECHAZADO), se devuelve el resultado ya conocido
        reservation = get_reservation_for_order(existing_order["id"])
        return jsonify({
            "idempotent_replay": True,
            "message": "Operación ya procesada previamente. No se duplicaron pedidos, reservas ni cobros.",
            "order": existing_order,
            "reservation": reservation
        }), 200

    # 2. Nueva intención de compra
    product_id = data.get("product_id", "PROD-001")
    quantity = int(data.get("quantity", 1))
    simulation_mode = (data.get("simulation_mode") or "APPROVE").upper()

    # Validar producto y calcular monto
    prod = get_product(product_id)
    if not prod:
        return jsonify({"error": f"Producto '{product_id}' no encontrado"}), 404

    total_amount = round(prod["price"] * quantity, 2)
    order_id = f"ORD-{uuid.uuid4().hex[:8].upper()}"

    # 3. Reservar inventario y crear pedido en PENDIENTE_PAGO de forma atómica
    try:
        order = create_order_with_reservation(
            order_id=order_id,
            idempotency_key=idempotency_key,
            product_id=product_id,
            quantity=quantity,
            total_amount=total_amount
        )
        logger.info(f"Pedido '{order_id}' creado y reserva confirmada temporalmente en 'PENDIENTE_PAGO'.")
    except InsufficientStockError as e:
        logger.warning(f"Intento de compra rechazado por falta de stock: {e}")
        return jsonify({
            "error": "Stock insuficiente",
            "message": str(e),
            "product_id": product_id,
            "available_stock": prod["stock"],
            "requested_quantity": quantity
        }), 400
    except DuplicateIdempotencyKeyError:
        # Carrera de concurrencia: si otro hilo insertó la misma clave
        existing = get_order_by_key(idempotency_key)
        return jsonify({
            "idempotent_replay": True,
            "order": existing,
            "message": "Operación registrada concurrentemente."
        }), 200

    # 4. Iniciar pago con el servicio Payment Mock
    payment_payload = {
        "payment_key": idempotency_key,
        "order_id": order_id,
        "amount": total_amount,
        "simulation_mode": simulation_mode
    }

    try:
        logger.info(f"Llamando a Payment Mock para pedido '{order_id}' (modo={simulation_mode}, timeout={PAYMENT_TIMEOUT_SECONDS}s)...")
        payment_response = requests.post(
            f"{PAYMENT_SERVICE_URL}/payments",
            json=payment_payload,
            timeout=PAYMENT_TIMEOUT_SECONDS
        )

        # Caso Pago Aprobado
        if payment_response.status_code == 200:
            updated_order = update_order_status(order_id, "PAGADO", reservation_status="COMMITTED")
            reservation = get_reservation_for_order(order_id)
            logger.info(f"Pedido '{order_id}' PAGADO exitosamente. Reserva 'COMMITTED'.")
            return jsonify({
                "status": "PAGADO",
                "message": "Pedido creado y pago aprobado con éxito.",
                "order": updated_order,
                "reservation": reservation,
                "payment": payment_response.json()
            }), 201

        # Caso Pago Rechazado
        elif payment_response.status_code == 400:
            # Compensación inmediata: liberar reserva
            updated_order = update_order_status(order_id, "RECHAZADO", release_stock=True)
            reservation = get_reservation_for_order(order_id)
            logger.info(f"Pago rechazado por el banco para pedido '{order_id}'. Reserva liberada ('RELEASED').")
            return jsonify({
                "status": "RECHAZADO",
                "message": "El pago fue rechazado. La reserva de inventario ha sido liberada.",
                "order": updated_order,
                "reservation": reservation,
                "payment": payment_response.json()
            }), 400

        else:
            # Respuesta inesperada
            logger.warning(f"Respuesta no controlada del mock: HTTP {payment_response.status_code}")
            updated_order = update_order_status(order_id, "PAGO_INCIERTO")
            return jsonify({
                "status": "PAGO_INCIERTO",
                "message": "Respuesta ambigua de la pasarela de pagos. Requiere reconciliación.",
                "order": updated_order
            }), 502

    except (requests.exceptions.Timeout, requests.exceptions.ConnectionError) as exc:
        # 5. CASO FALLA / TIMEOUT: La respuesta se perdió o tardó demasiado
        logger.error(
            f"FALLA DE RED O TIMEOUT al contactar Payment Mock para pedido '{order_id}'. "
            f"El cobro pudo haberse procesado en el mock. Marcando pedido como 'PAGO_INCIERTO'."
        )
        updated_order = update_order_status(order_id, "PAGO_INCIERTO")
        reservation = get_reservation_for_order(order_id)
        
        return jsonify({
            "status": "PAGO_INCIERTO",
            "error": "Timeout al esperar confirmación de pago.",
            "order_id": order_id,
            "idempotency_key": idempotency_key,
            "order": updated_order,
            "reservation": reservation,
            "instructions": "La pasarela no respondió a tiempo. El cobro podría haberse efectuado. "
                           "Consulte el pedido en GET /orders/<id> o reenvíe la solicitud con la misma clave para reconciliar."
        }), 504

@app.route("/orders/<order_id>", methods=["GET"])
def get_order(order_id):
    order = get_order_by_id(order_id)
    if not order:
        return jsonify({"error": f"Pedido '{order_id}' no encontrado"}), 404

    reservation = get_reservation_for_order(order_id)
    return jsonify({
        "order": order,
        "reservation": reservation
    }), 200

@app.route("/orders/<order_id>/reconcile", methods=["POST"])
def reconcile_endpoint(order_id):
    """
    Endpoint explícito para reconciliar pedidos que quedaron en PAGO_INCIERTO.
    Consulta el estado en el Payment Mock y actualiza el pedido sin cobrar de nuevo.
    """
    order = get_order_by_id(order_id)
    if not order:
        return jsonify({"error": f"Pedido '{order_id}' no encontrado"}), 404

    if order["status"] != "PAGO_INCIERTO":
        return jsonify({
            "message": f"El pedido ya se encuentra en un estado definitivo: {order['status']}",
            "order": order,
            "reservation": get_reservation_for_order(order_id)
        }), 200

    result = perform_reconciliation(order)
    return jsonify(result), 200

@app.route("/orders", methods=["GET"])
def list_all_orders():
    orders = list_orders()
    return jsonify({
        "count": len(orders),
        "orders": orders
    }), 200

@app.route("/reservations", methods=["GET"])
def list_all_reservations():
    reservations = list_reservations()
    return jsonify({
        "count": len(reservations),
        "reservations": reservations
    }), 200

@app.route("/admin/reset", methods=["POST"])
def reset():
    reset_db()
    logger.info("Base de datos de órdenes reseteada con productos por defecto.")
    return jsonify({
        "message": "Base de datos de órdenes reseteada correctamente",
        "products": list_products()
    }), 200

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5001, debug=False)
