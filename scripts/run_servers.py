import sys
import os
import subprocess
import time
import signal

base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
python_exe = sys.executable

def main():
    print("==================================================")
    print(" INICIANDO SERVICIOS DEL RETO TECNICO")
    print("==================================================")
    print("-> Iniciando Payment Mock API en puerto 5002...")
    payment_proc = subprocess.Popen([python_exe, os.path.join(base_dir, "payment_service", "app.py")])
    time.sleep(1)

    print("-> Iniciando Order API en puerto 5001...")
    order_proc = subprocess.Popen([python_exe, os.path.join(base_dir, "order_service", "app.py")])

    print("\n[SERVICIOS ACTIVOS]")
    print("  - Order API:        http://127.0.0.1:5001")
    print("  - Payment Mock API: http://127.0.0.1:5002")
    print("\nPresione Ctrl+C en esta terminal para detener ambos servicios.")

    def shutdown(sig, frame):
        print("\nDeteniendo servicios...")
        order_proc.terminate()
        payment_proc.terminate()
        order_proc.wait()
        payment_proc.wait()
        print("Servicios detenidos.")
        sys.exit(0)

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        shutdown(None, None)

if __name__ == "__main__":
    main()
