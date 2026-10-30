import logging
import time
from flask import Flask, request, jsonify
from database import init_db, get_payment_by_key, save_payment, list_all_payments, reset_db

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [PaymentMock] %(message)s"
)
logger = logging.getLogger(__name__)

app = Flask(__name__)
init_db()

@app.after_request
def add_cors_headers(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Idempotency-Key"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response

@app.route("/", methods=["GET"])
def index():
    return jsonify({
        "service": "Payment Mock API",
        "status": "ONLINE",
        "message": "Pasarela de pagos simulada con soporte de idempotencia y timeouts.",
        "endpoints": {
            "GET /health": "Verificar salud del servicio",
            "POST /payments": "Procesar pago (simulation_mode: APPROVE | REJECT | TIMEOUT_AFTER_CHARGE)",
            "GET /payments/<payment_key>": "Consultar estado de un pago por clave",
            "GET /payments": "Listar todos los pagos registrados",
            "POST /admin/reset": "Reiniciar base de datos"
        }
    }), 200

@app.route("/favicon.ico", methods=["GET"])
def favicon():
    return "", 204

@app.route("/health", methods=["GET"])
def health():
    return jsonify({"status": "UP", "service": "Payment Mock API"}), 200

@app.route("/payments", methods=["POST"])
def process_payment():
    data = request.get_json(silent=True) or {}
    payment_key = data.get("payment_key")
    order_id = data.get("order_id")
    amount = data.get("amount")
    simulation_mode = (data.get("simulation_mode") or "APPROVE").upper()

    if not payment_key or not order_id or amount is None:
        return jsonify({
            "error": "Campos obligatorios faltantes: payment_key, order_id, amount"
        }), 400

    # 1. Comprobar idempotencia en el servicio de pagos
    existing = get_payment_by_key(payment_key)
    if existing:
        logger.info(f"Solicitud repetida con clave '{payment_key}'. Devolviendo estado previo: {existing['status']}")
        return jsonify({
            "payment_key": existing["payment_key"],
            "order_id": existing["order_id"],
            "amount": existing["amount"],
            "status": existing["status"],
            "created_at": existing["created_at"],
            "idempotent_replay": True,
            "message": f"Pago ya procesado anteriormente con resultado: {existing['status']}"
        }), 200

    logger.info(f"Procesando nuevo pago para orden '{order_id}', clave '{payment_key}', monto ${amount}, modo '{simulation_mode}'")

    # 2. Simulación: TIMEOUT DESPUÉS DEL COBRO (Caso crítico de falla)
    if simulation_mode == "TIMEOUT_AFTER_CHARGE":
        # Se guarda el cobro como APROBADO en SQLite ANTES de fallar la conexión
        saved = save_payment(payment_key, order_id, float(amount), "APPROVED")
        logger.warning(
            f"Cobro registrado exitosamente en SQLite para la clave '{payment_key}'. "
            f"Simulando pérdida de respuesta / timeout (pausa de 3.5 segundos)..."
        )
        time.sleep(3.5)
        # Si el cliente esperó, devuelve el pago, pero Order API ya habrá disparado timeout
        return jsonify({
            "payment_key": saved["payment_key"],
            "order_id": saved["order_id"],
            "amount": saved["amount"],
            "status": saved["status"],
            "simulated_timeout": True,
            "message": "Cobro registrado pero la respuesta tardó más de lo tolerado."
        }), 200

    # 3. Simulación: PAGO RECHAZADO
    elif simulation_mode == "REJECT":
        saved = save_payment(payment_key, order_id, float(amount), "REJECTED")
        logger.info(f"Pago rechazado registrado en SQLite para orden '{order_id}'.")
        return jsonify({
            "payment_key": saved["payment_key"],
            "order_id": saved["order_id"],
            "amount": saved["amount"],
            "status": "REJECTED",
            "message": "Pago rechazado por fondos insuficientes o política bancaria."
        }), 400

    # 4. Simulación: FLUJO EXITOSO (APROBADO)
    elif simulation_mode == "APPROVE":
        saved = save_payment(payment_key, order_id, float(amount), "APPROVED")
        logger.info(f"Pago aprobado exitosamente para orden '{order_id}'.")
        return jsonify({
            "payment_key": saved["payment_key"],
            "order_id": saved["order_id"],
            "amount": saved["amount"],
            "status": "APPROVED",
            "message": "Pago aprobado con éxito."
        }), 200

    else:
        return jsonify({
            "error": f"Modo de simulación '{simulation_mode}' no válido. Use 'APPROVE', 'REJECT' o 'TIMEOUT_AFTER_CHARGE'."
        }), 400

@app.route("/payments/<payment_key>", methods=["GET"])
def get_payment(payment_key):
    payment = get_payment_by_key(payment_key)
    if not payment:
        logger.info(f"Consulta de pago no encontrado con clave '{payment_key}'.")
        return jsonify({
            "error": "No existe registro de pago para la clave especificada",
            "payment_key": payment_key
        }), 404

    logger.info(f"Consulta de pago encontrada: clave '{payment_key}' -> estado '{payment['status']}'")
    return jsonify({
        "payment_key": payment["payment_key"],
        "order_id": payment["order_id"],
        "amount": payment["amount"],
        "status": payment["status"],
        "created_at": payment["created_at"]
    }), 200

@app.route("/payments", methods=["GET"])
def list_payments():
    payments = list_all_payments()
    return jsonify({
        "count": len(payments),
        "payments": payments
    }), 200

@app.route("/admin/reset", methods=["POST"])
def reset():
    reset_db()
    logger.info("Base de datos de pagos reseteada.")
    return jsonify({"message": "Base de datos de pagos limpiada correctamente"}), 200

if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5002, debug=False)
