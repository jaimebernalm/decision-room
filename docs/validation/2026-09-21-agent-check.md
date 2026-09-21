# Paso 1.4: comprobación del agente

**Resultado: infraestructura implementada; evaluación semántica no superada.**
El paso 1.4 no se marca como aceptado y no se conecta todavía la ejecución autónoma
del paso 1.5. No se ha hecho commit, conforme a la instrucción de esta entrega.

## Infraestructura

LangGraph 1.2.12, checkpointer PostgreSQL 3.1.2, Pydantic 2.13.5 y HTTPX 0.28.1
instalados en `.venv`; dependencias completas en `requirements.lock`.

Las pruebas usan PostgreSQL real en una base desechable y un modelo simulado
identificado como tal. Cubren aislamiento por empresa, idempotencia, respuestas
desconocidas/rechazadas, procesos distintos, caída tras guardar una respuesta,
referencias inventadas, salida inválida, fallo de conexión, exclusión de rutas y
archivos de evaluación, cambio de fuentes, bloqueo de sesión, peticiones inciertas,
presupuesto y contratos HTTP. Estas pruebas no validan inteligencia analítica.

La suite completa pasó: **35 tests en 24,089 segundos**, incluidos los 13 nuevos
tests del agente y los 22 existentes de ingesta y sandbox. `pip check` no detectó
incompatibilidades y `git diff --check` no detectó errores de formato.
También se comprobó que el catálogo de las 48
tablas WWI cabe en el límite de contexto (17.833 bytes en la comprobación); esto
no constituye una evaluación de interpretación de WWI con el modelo real.

## Modelo real

LM Studio detectó `qwen3.8-27b-splash`, 27B, cuantización 4 bit. Se arrancó su
servidor solo en `127.0.0.1:1234`. No se instalaron otros modelos ni se contrató
un proveedor externo. Las respuestas y checkpoints quedan bajo PostgreSQL local;
los informes de prueba, en `.local/agent-checks/`, excluidos de Git.

Resultados iniciales que deben conservarse aunque cambie el prompt:

- Chat Completions con la configuración inicial agotó el timeout de 180 segundos.
- API nativa sin razonamiento respondió, pero el primer prompt asumió que `amount`
  era un total de fila. La validación estructural detectó una procedencia de
  confirmación insuficiente, pero no detectó la suposición monetaria incorrecta.
- Con el prompt v2, la ejecución sin razonamiento tardó 102,66 segundos y volvió
  a atribuir al propietario una definición que no había dado. El comprobador del
  caso ambiguo falló por ausencia de la pregunta material. No se hicieron cálculos.
- Con el prompt v2 y razonamiento activado, la primera respuesta volvió a inventar
  la definición de total por fila y además incumplió el contrato de `table_ids`.
  Se solicitó una corrección. La segunda respuesta no pudo interpretarse como una
  respuesta JSON válida; la sesión quedó fallida. El intento completo duró 302,57
  segundos. La primera petición registró 2.459 tokens de salida, de los cuales
  1.143 correspondían a razonamiento, y unos 16,95 tokens/segundo.

Esto demuestra por qué una salida JSON válida y una referencia existente no
garantizan que la interpretación sea verdadera. Estos resultados son de esta
configuración local concreta; no demuestran que todos los modelos Qwen o todos los
modelos locales fallen. Un proveedor externo tampoco queda aprobado por ser externo.

## Siguiente comprobación

Configurar otro modelo, preferiblemente comparar una API alojada, y repetir el
caso ambiguo con precio unitario, total de fila y respuesta desconocida, los casos
diarios y por producto, variantes de columnas y la inspección de WWI. No se
ejecutaron esas comparaciones reales restantes después del fallo básico; los
flujos de respuesta y recuperación sí se probaron con el modelo simulado.

No hay una credencial de proveedor externo configurada. No se han hecho llamadas
a un proveedor de inferencia externo ni se ha publicado información del usuario.
Los informes locales preservan las propuestas incorrectas para poder revisarlas.
