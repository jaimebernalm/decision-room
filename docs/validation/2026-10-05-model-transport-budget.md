# Transporte: espera, presupuesto y deadline — 5 de octubre

Primer paso del [encargo](../technical/panorama-contracts-next-plan.md), sobre
d14c0ed. No modifica contratos analíticos ni las opciones experimentales.

- Un 429 respeta el máximo de Retry-After y resets de tokens (cuenta y proyecto),
  aunque queden tokens: pueden ser insuficientes para la siguiente petición.
  Esperas hasta 300 s, siempre dentro del deadline total; nunca se acorta una
  espera superior. Cuota/facturación siguen sin reintento automático.
- Máximo tres intentos. Tras un 429, un fallo de conexión/protocolo anterior a
  recibir cabeceras puede reintentarse. Un 200 interrumpido y un primer fallo de
  lectura/protocolo siguen siendo inciertos. El 429 anterior no demuestra que el
  siguiente envío no llegó al proveedor: puede duplicarse inferencia, nunca se
  ejecuta una acción de modelo antes de tener una respuesta completa. Se conserva
  usage_unknown; no se presenta ese coste como conocido.
- HTTP asíncrono cancelable con deadline de la llamada completa, incluidas esperas
  y cuerpo. No queda un hilo HTTP ejecutándose tras devolver el timeout.
- Estimación visible por intento: bytes UTF-8 del payload (incluidos esquema y
  correcciones) / 3, redondeado hacia arriba, más presupuesto completo de salida.
  Es estimación conservadora para español/JSON, no tokenización exacta ni factura.
- DECISION_ROOM_AGENT_TPM: 200000 por defecto, 0 desactiva admisión local. Reservas
  SQLite atómicas en el almacenamiento privado comparten una ventana de 60 s entre
  procesos y roles; DECISION_ROOM_AGENT_RATE_POOL permite agrupar modelos con un
  límite compartido. No se guardan prompts ni claves API en ese registro.
  Cada intento reserva; las reservas inciertas/rechazadas expiran sin asumir coste
  cero. Una sola petición estimada mayor que TPM se rechaza antes de enviar.
- El limitador solo conoce este almacenamiento/pool. Otras aplicaciones/cuentas
  compartidas pueden consumir cuota; los resets del proveedor siguen mandando.

Fuente consultada: [documentación oficial de rate limits](https://developers.openai.com/api/docs/guides/rate-limits).
Describe reset de tokens, Retry-After como mínimo y la diferencia entre timeout
por intento y deadline total; no garantiza ausencia de procesamiento tras una
conexión interrumpida.

Validación sin API: tests de reset de 44 s frente a Retry-After de 13 s con saldo
positivo; 429→error de protocolo→éxito; interrupción después de 200; deadline real
con goteo indefinido y cabeceras colgadas; reserva concurrente de dos roles,
expiración, petición sobredimensionada, registro y esquemas existentes.

Comprobados 37 tests unitarios de transporte/esquemas/readiness y 13 de contratos
integrados con PostgreSQL propio: 50 aprobados.
