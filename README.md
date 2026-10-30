# Reto Técnico: Pedidos, Pagos Simulados e Idempotencia

Este repositorio contiene la solución completa al reto técnico de sistemas distribuidos, idempotencia, resiliencia y persistencia de estados utilizando **Python (Flask)** y **SQLite**.

---

## 👥 Datos del Equipo

- **Integrantes**:
  - Said Fausto Pinto Tamayo
  - Oscar Jordan Gonzabay Muñoz
  - Estalin Gabriel Jaen Garcia
- **Repositorio**: https://github.com/SaidJuniorProgrammer/Reto_Tecnico.git
- **Video Demostrativo (3 a 5 min)**: `[Enlace al video en YouTube / Drive / Loom]`

---

## 🏛️ Arquitectura del Sistema

```
+-------------------+           +-------------------------+           +------------------------------+
|   Postman / Bruno |  ======>  |   Order API (Flask)     |  ======>  |    Payment Mock API (Flask)  |
|                   |           |   http://127.0.0.1:5001 |           |    http://127.0.0.1:5002     |
+-------------------+           +-------------------------+           +------------------------------+
                                             |                                       |
                                             v                                       v
                                    [ orders.db (SQLite) ]                 [ payments.db (SQLite) ]
```

### Separación de Responsabilidades y Persistencia

1. **Order API (`orders.db`)**:
   - Gestiona productos, inventario y pedidos.
   - Asegura la unicidad de transacciones mediante una restricción `UNIQUE` en la columna `idempotency_key`.
   - Controla el inventario atómicamente evitando bajo cualquier circunstancia un stock negativo (`CHECK(stock >= 0)`).
   - Registra reservas temporales (`RESERVED`) que se confirman (`COMMITTED`) tras la aprobación del cobro o se liberan (`RELEASED`) ante un rechazo o compensación.
2. **Payment Mock API (`payments.db`)**:
   - Simula una pasarela de pagos con persistencia propia.
   - Almacena cada cobro con una clave única (`payment_key PRIMARY KEY`).
   - Soporta simulación de aprobación (`APPROVE`), rechazo bancario (`REJECT`) y **timeout posterior al cobro** (`TIMEOUT_AFTER_CHARGE`), donde el pago se almacena en SQLite antes de producirse el fallo de red.

---

## 🔄 Máquina de Estados del Pedido

```
  [ Cliente envía POST /orders ]
                 |
                 v
       ( Reserva de Stock )
                 |
                 v
        [ PENDIENTE_PAGO ]
                 |
      +----------+----------+
      |                     |
 (Pago Aprobado)     (Pago Rechazado)
      |                     |
      v                     v
  [ PAGADO ]           [ RECHAZADO ]
(Reserva COMMITTED)  (Reserva RELEASED + Stock Restituido)
      ^                     ^
      |                     |
      +--- [Reconciliación]-+
                 ^
                 | (Timeout / Respuesta perdida)
                 |
        [ PAGO_INCIERTO ]
```

---

## 📂 Estructura del Proyecto

```
Reto_tecnico/
├── order_service/              # Servicio de Pedidos
│   ├── app.py                  # Endpoints REST (Flask :5001)
│   ├── database.py             # Modelo de datos, transacciones SQLite y stock
│   └── orders.db               # Base de datos persistente SQLite (generada al correr)
├── payment_service/            # Mock de Pasarela de Pagos
│   ├── app.py                  # Endpoints REST (Flask :5002)
│   ├── database.py             # Persistencia de pagos en SQLite
│   └── payments.db             # Base de datos persistente SQLite (generada al correr)
├── postman/                    # Colección y Entorno para Postman
│   ├── Reto_Tecnico_Coleccion.postman_collection.json
│   └── Reto_Tecnico_Entorno.postman_environment.json
├── scripts/                    # Scripts de utilidad y diagnóstico
│   ├── init_databases.py       # Inicializa / reinicia las bases SQLite
│   ├── check_databases.py      # Inspecciona visualmente el estado de SQLite
│   ├── run_servers.py          # Inicia ambos servicios en una sola consola
│   └── start_services.ps1      # Inicia ambos servicios en terminales independientes
├── tests/
│   └── verify_all_cases.py     # Suite automatizada que prueba los 5 casos obligatorios
├── requirements.txt            # Dependencias Python
└── README.md                   # Documentación completa
```

---

## 🚀 Requisitos e Instalación

### 1. Clonar el repositorio y navegar a la carpeta:
```powershell
cd C:\Users\said2\Reto_tecnico
```

### 2. Instalar dependencias:
```powershell
pip install -r requirements.txt
```

### 3. Inicializar bases de datos:
```powershell
python scripts/init_databases.py
```

---

## ⚙️ Ejecución de los Servicios

Puedes iniciar ambos servicios de cualquiera de las siguientes formas:

### Opción A (Recomendada - Un solo comando):
```powershell
python scripts/run_servers.py
```

### Opción B (En ventanas separadas de PowerShell):
```powershell
.\scripts\start_services.ps1
```

### Opción C (Manualmente en dos consolas):
- **Terminal 1 (Mock de Pagos)**:
  ```powershell
  python payment_service/app.py
  ```
- **Terminal 2 (Servicio de Pedidos)**:
  ```powershell
  python order_service/app.py
  ```

---

## 🖥️ Panel de Control Web Interactivo

Una vez iniciados los servicios, abre en cualquier navegador:
👉 **[http://127.0.0.1:5001/](http://127.0.0.1:5001/)**

Desde este panel podrás:
- **Monitorear inventario en tiempo real**: Visualiza el stock de cada producto y sus descuentos/compensaciones inmediatas.
- **Ejecutar los 5 casos con 1 clic**: Botones directos para disparar cada escenario de la rúbrica.
- **Reconciliación interactiva**: En el Caso 3 (timeout tras cobro), verás el pedido en estado ámbar `PAGO_INCIERTO` y podrás presionar el botón **"Reconciliar"** para verificar el pago y transicionarlo a `PAGADO` sin duplicar cobros a ciegas.
- **Auditoría visual de bases de datos**: Muestra en tiempo real las tablas de `orders.db` y `payments.db`.
- **Botón Reset DB**: Para reiniciar las bases de datos a su estado original al instante.

---

## 🧪 Verificación Automatizada (100% de los Casos)

Hemos creado una suite de prueba automatizada que ejecuta, valida y genera un informe de los 5 casos obligatorios de la rúbrica:

```powershell
python tests/verify_all_cases.py
```

Para verificar en cualquier momento el contenido exacto de las bases de datos SQLite en disco:
```powershell
python scripts/check_databases.py
```

---

## 📋 Demostración de los 5 Casos Obligatorios (Postman)

Importa en Postman los dos archivos ubicados en la carpeta `postman/`:
1. `Reto_Tecnico_Coleccion.postman_collection.json`
2. `Reto_Tecnico_Entorno.postman_environment.json`

### Caso 1: Flujo Exitoso
- **Acción**: `POST http://127.0.0.1:5001/orders`
  - **Header**: `Idempotency-Key: CLAVE-PRUEBA-CASO-1`
  - **Body**: `{"product_id": "PROD-001", "quantity": 1, "simulation_mode": "APPROVE"}`
- **Resultado Esperado**: HTTP `201 Created`. Pedido en estado `PAGADO`, reserva `COMMITTED`, stock descontado en 1 unidad. En `payments.db` se registra 1 cobro `APPROVED`.

### Caso 2: Repetición de la Misma Solicitud (Idempotencia)
- **Acción**: Reenviar exactamente la misma petición con la misma cabecera `Idempotency-Key: CLAVE-PRUEBA-CASO-1`.
- **Resultado Esperado**: HTTP `200 OK`. Retorna `idempotent_replay: true` y los datos del pedido previo.
- **Comprobación en SQLite**: No se crea un segundo pedido, no se genera una nueva reserva, el inventario permanece idéntico y `payments.db` conserva exactamente 1 cobro (cero duplicaciones).

### Caso 3: Respuesta Perdida tras el Cobro y Recuperación
- **Acción 3.1 (Falla)**: `POST http://127.0.0.1:5001/orders`
  - **Header**: `Idempotency-Key: CLAVE-PRUEBA-CASO-3`
  - **Body**: `{"product_id": "PROD-001", "quantity": 1, "simulation_mode": "TIMEOUT_AFTER_CHARGE"}`
  - **Resultado**: HTTP `504 Gateway Timeout`. El pedido queda en estado `PAGO_INCIERTO`. La reserva permanece retenida (`RESERVED`) para proteger el producto.
- **Acción 3.2 (Comprobación en Mock)**: `GET http://127.0.0.1:5002/payments/CLAVE-PRUEBA-CASO-3`
  - **Resultado**: HTTP `200 OK`. Se comprueba que el mock **efectivamente registró el cobro como `APPROVED`** en SQLite antes de perder la respuesta.
- **Acción 3.3 (Recuperación segura)**: `POST http://127.0.0.1:5001/orders/:order_id/reconcile` (o reenviando el pedido con la misma clave).
  - **Resultado**: HTTP `200 OK`. El backend consulta el mock, descubre que el cobro existe y fue aprobado, y transiciona el pedido a `PAGADO` y la reserva a `COMMITTED`. **Nunca se vuelve a cobrar a ciegas**.

### Caso 4: Pago Rechazado y Compensación
- **Acción**: `POST http://127.0.0.1:5001/orders`
  - **Header**: `Idempotency-Key: CLAVE-PRUEBA-CASO-4`
  - **Body**: `{"product_id": "PROD-001", "quantity": 1, "simulation_mode": "REJECT"}`
- **Resultado Esperado**: HTTP `400 Bad Request`. Pedido en estado `RECHAZADO`.
- **Compensación**: La reserva pasa a `RELEASED` y el stock se restituye automáticamente una sola vez. No se pierden unidades.

### Caso 5: Otra Intención de Compra y Control de Stock Negativo
- **Acción 5.1**: Pedido para `PROD-LIMITED` (stock inicial = 1) con clave `CLAVE-PRUEBA-CASO-5-A`.
  - **Resultado**: HTTP `201 Created`. Stock pasa a 0.
- **Acción 5.2**: Pedido para el mismo producto con una clave distinta `CLAVE-PRUEBA-CASO-5-B` (otra intención de compra).
  - **Resultado**: HTTP `400 Bad Request` ("Stock insuficiente"). El stock permanece en 0 (garantizado por la restricción `CHECK(stock >= 0)` en SQLite).

---
