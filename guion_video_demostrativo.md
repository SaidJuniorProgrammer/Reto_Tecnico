# 🎬 Guion Técnico para Video Demostrativo (3 a 5 Minutos)

**Proyecto:** Reto Técnico - Pedidos, Pagos Simulados e Idempotencia  
**Duración Total Estimada:** 4 minutos y 30 segundos  
**Plataforma de Grabación recomendada:** OBS Studio, Google Meet, Zoom o Loom  
**Requisito previo:** Tener ejecutándose `python scripts/run_servers.py` y el navegador abierto en `http://127.0.0.1:5001/`.

---

## ⏱️ Estructura Temporal del Video

| Minuto | Integrante | Tema | Caso del Reto |
|---|---|---|---|
| **0:00 - 0:45** | **Integrante 1** | Introducción, Arquitectura y Estado Inicial | Presentación general |
| **0:45 - 1:45** | **Integrante 2** | Flujo Exitoso e Idempotencia | **Caso 1 y Caso 2** |
| **1:45 - 3:05** | **Integrante 3** | El Caso Crítico: Timeout y Recuperación | **Caso 3 (Punto Clave Rúbrica)** |
| **3:05 - 4:00** | **Integrante 1** | Pago Rechazado y Control de Stock Negativo | **Caso 4 y Caso 5** |
| **4:00 - 4:30** | **Los 3 Integrantes** | Conclusión Técnica y Cierre | Respuestas de la Rúbrica |

---

## 🎙️ Libreto Detallado por Integrante

---

### 🔹 BLOQUE 1: Introducción y Arquitectura (0:00 – 0:45)
**Responsable:** `Integrante 1`  
`[EN PANTALLA: Mostrar la interfaz web en http://127.0.0.1:5001/ con el botón "Reset DB" recién presionado para ver todo limpio].`

> **Integrante 1:**  
> "Hola a todos, bienvenidos. Somos el equipo conformado por **[Nombre 1]**, **[Nombre 2]** y **[Nombre 3]**, y hoy vamos a presentar la solución al reto técnico de **Pedidos, Pagos Simulados e Idempotencia**."
>
> *(Señala con el cursor el encabezado y las insignias de estado)*  
> "El problema que resolvemos es crítico en sistemas distribuidos: ¿qué ocurre cuando un cobro se procesa en el banco, pero la respuesta de red se pierde antes de llegar a nuestra tienda?
>
> Para resolverlo, construimos dos microservicios en Flask con persistencia independiente en SQLite:
> 1. La **Order API** en el puerto 5001, conectada a `orders.db`, encargada del inventario, pedidos y reservas.
> 2. Y la **Payment Mock API** en el puerto 5002, conectada a `payments.db`, que simula una pasarela bancaria.
>
> En pantalla pueden ver nuestro panel de control en tiempo real. Tenemos un stock inicial de 10 unidades de *Smartphone Alpha* y 1 unidad especial de *Edición Coleccionista*.  
> Ahora, mi compañero **[Nombre 2]** demostrará el flujo exitoso y la idempotencia."

---

### 🔹 BLOQUE 2: Flujo Exitoso e Idempotencia (0:45 – 1:45)
**Responsable:** `Integrante 2`  
`[EN PANTALLA: Integrante 2 interactúa con el botón "Caso 1" y luego con "Caso 2"].`

> **Integrante 2:**  
> "Gracias. Vamos a comenzar ejecutando el **Caso 1: Flujo Exitoso**."
>
> *(Hace clic en el botón verde **'Caso 1: Flujo Exitoso'**)*  
> "Al presionar el botón, la Order API recibe la solicitud con una clave de idempotencia única.  
> Observen lo que acaba de suceder en tiempo real:
> 1. El stock de *Smartphone Alpha* bajó automáticamente de 10 a 9 unidades.
> 2. En la tabla de pedidos, se creó el pedido en estado **PAGADO** con reserva confirmada en estado `COMMITTED`.
> 3. Y abajo, en el registro del Mock de Pagos, vemos exactamente un cobro registrado como **APPROVED**.  
> El visor HTTP confirma una respuesta `201 Created`."
>
> *(Pausa breve y apunta al botón del Caso 2)*  
> "Ahora demostraremos el **Caso 2: Repetición de la misma solicitud (Idempotencia)**.  
> ¿Qué pasa si el cliente o la red reenvían exactamente el mismo pedido con la misma clave de idempotencia?"
>
> *(Hace clic en el botón cian **'Caso 2: Repetir Solicitud'**)*  
> "¡Listo! Observen la consola: recibimos un código `200 OK` con la propiedad `idempotent_replay: true`.  
> Y lo más importante para la rúbrica:  
> - El stock se mantiene intacto en 9 unidades.  
> - No se creó un segundo pedido.  
> - Y en la tabla de pagos del Mock, **seguimos teniendo un único cobro**.  
> Esto está garantizado por la restricción `UNIQUE` en SQLite sobre la clave de idempotencia."
>
> "Ahora, **[Nombre 3]** explicará el caso más desafiante: el timeout posterior al cobro."

---

### 🔹 BLOQUE 3: El Caso Crítico - Timeout tras Cobro y Recuperación (1:45 – 3:05)
**Responsable:** `Integrante 3`  
`[EN PANTALLA: Integrante 3 hace clic en "Caso 3: Timeout tras Cobro", muestra el estado ámbar, baja a la tabla de pagos y luego hace clic en "Reconciliar"].`

> **Integrante 3:**  
> "Gracias. Este es el núcleo del problema planteado por el docente: el **Caso 3: Timeout posterior al cobro**."
>
> *(Hace clic en el botón amarillo **'Caso 3: Timeout tras Cobro'**)*  
> "Observen que la solicitud tarda unos segundos... y la Order API nos devuelve un error `504 Gateway Timeout`.  
> Miren el estado en la tabla: el pedido quedó en color ámbar como **PAGO_INCIERTO**."
>
> *(Señala el stock y la tabla del mock)*  
> "Noten dos detalles de arquitectura cruciales:  
> Primero, el stock se descontó de 9 a 8 unidades porque la reserva está protegida en estado `RESERVED`.  
> Segundo, si miramos abajo en el **Payment Mock API**, el cobro **SÍ quedó registrado exitosamente como APPROVED**. El banco sí cobró, pero la respuesta nunca llegó a la tienda."
>
> *(Enfoca el cursor sobre el botón brillante **'Reconciliar'**)*  
> "Un backend ingenuo reintentaría el cobro y cobraría dos veces al cliente. Nuestro sistema **NUNCA cobra a ciegas**.  
> Al presentarse una incertidumbre, el sistema ofrece reconciliación. Voy a hacer clic en **Reconciliar**."
>
> *(Hace clic en el botón **'Reconciliar'** en la fila del pedido)*  
> "¡Miren lo que ocurrió al instante!  
> La Order API hizo una consulta de lectura `GET /payments/{key}` al Mock, descubrió que el cobro ya existía aprobado, y actualizó el pedido a **PAGADO** y la reserva a **COMMITTED**.  
> Y como pueden ver en la tabla de cobros, **sigue existiendo un solo cobro**. Recuperamos la coherencia del sistema sin duplicar efectos."
>
> "Le devuelvo la palabra a **[Nombre 1]** para los casos de rechazo y control de stock."

---

### 🔹 BLOQUE 4: Pago Rechazado y Control de Stock Negativo (3:05 – 4:00)
**Responsable:** `Integrante 1`  
`[EN PANTALLA: Integrante 1 hace clic en "Caso 4" y luego en "Caso 5"].`

> **Integrante 1:**  
> "Continuamos con el **Caso 4: Pago Rechazado y Compensación**."
>
> *(Hace clic en el botón rojo **'Caso 4: Pago Rechazado'**)*  
> "Aquí forzamos que el banco rechace la transacción. La pasarela responde `400 Bad Request` con estado `REJECTED`.  
> Inmediatamente, la Order API ejecuta la compensación: marca el pedido como **RECHAZADO**, pasa la reserva a `RELEASED` y **restituye el stock de forma automática**. El stock vuelve a quedar exactamente igual, demostrando que la reserva se libera una sola vez."
>
> *(Apunta a la tarjeta de Edición Coleccionista con 1 unidad)*  
> "Por último, evaluamos el **Caso 5: Otra intención de compra y control de stock negativo**."
>
> *(Hace clic en el botón púrpura **'Caso 5: Agotar Stock'**)*  
> "Para este caso usamos el producto *Edición Coleccionista*, del cual solo quedaba 1 unidad.  
> El sistema ejecutó dos solicitudes con claves de idempotencia diferentes:  
> 1. La primera clave representó una compra legítima: se aprobó, y el stock disponible bajó a **0**.  
> 2. Inmediatamente después, una segunda clave distinta intentó comprar la misma unidad agotada.  
> La consola muestra un error `400 Stock Insuficiente`.  
> Gracias a la restricción `CHECK (stock >= 0)` en SQLite, garantizamos que el inventario **nunca quede en números negativos**."

---

### 🔹 BLOQUE 5: Respuestas a las Preguntas de la Rúbrica y Cierre (4:00 – 4:30)
**Responsables:** `Los 3 Integrantes en cámara / micrófono`  
`[EN PANTALLA: Mostrar la vista general del panel con los 4 pedidos y los 4 cobros alineados, o una terminal ejecutando 'python scripts/check_databases.py'].`

> **Integrante 2:**  
> "Para finalizar y dar respuesta exacta a las conclusiones solicitadas en la rúbrica:  
> **¿Qué estado guardamos para recuperarnos?**  
> Guardamos el estado `PAGO_INCIERTO` en `orders.db` manteniendo la reserva retenida, mientras que en `payments.db` se conservó el registro `APPROVED` indexado por la clave de pago."

> **Integrante 3:**  
> "**¿Cómo comprobamos que no hubo efectos duplicados?**  
> Lo comprobamos mediante la restricción `UNIQUE` en base de datos, el protocolo de reconciliación por consulta antes de cualquier reintento, y la auditoría final: 4 intenciones únicas de compra produjeron exactamente 4 cobros y 4 pedidos, con cero duplicaciones."

> **Integrante 1:**  
> "El código fuente completo, las instrucciones de ejecución, la colección exportada de Postman y la suite de pruebas automatizadas están disponibles en nuestro repositorio.  
> ¡Muchas gracias por su atención!"
