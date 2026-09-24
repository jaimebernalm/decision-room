# Paso 2.5.1: identidad persistente del negocio

**Fecha:** 23 de septiembre de 2026.  
**Resultado:** incrementos A–D implementados y comprobados. Los pasos 2.5.2–2.5.7 siguen pendientes.  
**Plan:** [ejecución incremental](../technical/business-memory-implementation.md#251-un-negocio-persistente).

## Cambios realizados

- Esquema 8: registro de negocios del propietario local, selección persistente, revisión del perfil y avance del onboarding. La migración conserva identificadores y evidencia; selecciona automáticamente un único negocio web anterior y exige elegir cuando existen varios, aunque compartan nombre. Los negocios creados únicamente por CLI no se incorporan.
- Servicio de negocio separado de la creación de trabajos. El nombre y la descripción se guardan antes de subir archivos o llamar al modelo. Se pueden editar y recuperar tras reiniciar; los formularios antiguos no sobrescriben una revisión nueva.
- Formulario y selector adaptados. Otro análisis reutiliza el negocio activo y solicita su propia pregunta, título y CSV. Cada trabajo conserva el nombre y contexto utilizados al enviarlo.
- Listado, detalle, respuestas, reintentos, informes y descargas limitados al negocio seleccionado. El trabajador continúa un trabajo del negocio original aunque cambie la selección.
- Un mismo CSV reutiliza el lote y permite investigaciones independientes. La recuperación busca el lote exacto por contenido/configuración; no el último del negocio. Repetirlo con otro nombre no modifica las fuentes del informe anterior.
- El arranque comprueba la disponibilidad del puerto antes de migrar. Detener las instancias antiguas que usen esa base antes de actualizar, incluso si escuchan en otro puerto.

Archivos principales: esquema, servicios de ingesta y web, nuevo módulo `web/business.py`, rutas HTTP, formulario JavaScript, entrada del servidor y pruebas de migración/web. Véase la [guía web actualizada](../technical/web.md).

## Pruebas automatizadas ejecutadas

```sh
.venv/bin/python -m unittest discover -s tests -v
node --check decision_room/web/static/app.js
git diff --check
```

**155 pruebas correctas en 68,571 segundos**, incluidas 27 pruebas web y 4 de migración. PostgreSQL y sandbox reales; respuestas de los roles controladas en la suite. Sintaxis JavaScript y comprobación de diferencias correctas.

| Escenario | Resultado |
|---|---|
| Migración vacía, repetida, un negocio web y negocios CLI | Identidades y selección correctas, sin duplicación |
| Varios negocios históricos con igual nombre | Conservados por separado; selección explícita |
| Fallo forzado dentro de la migración | Transacción revertida; reintento correcto sin pérdida |
| Informe aprobado anterior a esquema 8 | HTML, evidencia, identificadores, originales y checkpoints conservados |
| Guardado sin modelo y lectura desde otro proceso | Perfil y selección recuperados |
| Ediciones/reenvíos concurrentes y formularios obsoletos | Conflicto explícito o reintento idempotente |
| Dos preguntas con el mismo CSV | Mismo negocio/lote, sesiones y revisiones independientes |
| CSV repetido con otro nombre | Informe anterior sigue publicable |
| Interrupción tras importar y posterior lote diferente | Recuperación del lote exacto |
| Cambio de negocio y acceso por identificador ajeno | Rutas bloqueadas; trabajador mantiene su ámbito |
| Segundo arranque sobre un puerto ocupado | No ejecuta migración |

## Recorrido real en el navegador

Se utilizó una base y almacenamiento temporales separados de los datos de trabajo, el CSV público [ventas diarias](../../data/reference-cases/01-daily-sales/input/sales.csv) y `gpt-6-luna` mediante el proveedor OpenAI. Se creó un negocio ficticio desde la interfaz, se guardó su descripción y se enviaron dos preguntas. El contexto delimitaba ventas parciales registradas, sin interpretar fechas ausentes como ventas cero ni atribuir causas no observadas.

| Pregunta | Referencia independiente | Resultado y tiempo |
|---|---|---|
| Comparar 1–14 y 15–28 de abril de 2016 | 34.137,85 y 39.646,25; diferencia 5.508,40; 12 fechas por periodo | Informe publicable, valores coincidentes; 57,43 s |
| Total y máximo diario registrado | Total 73.784,10; máximo 8.569,05 el 28 de abril de 2016; 24 fechas | Informe publicable, valores coincidentes; 70,38 s |

Un cálculo separado con `csv` y `Decimal` contrastó los valores de las 17 métricas registradas en las observaciones de ambas investigaciones. Los dos informes superaron sus controles de publicación. Compartieron negocio y lote, con sesiones distintas; los originales descargados coincidieron byte a byte con el CSV.

También se comprobó cambiar el nombre del negocio sin alterar el contexto del informe anterior, reiniciar el servidor y recuperar perfil e informes, crear otro negocio vacío y volver al primero. La interfaz se revisó en escritorio y a 390 × 844: sin desbordamiento horizontal y con edición del perfil utilizable. La consola del navegador no mostró errores.

Los logs, respuestas completas, identificadores de prueba y almacenamiento de esta sesión permanecen en `.local/`, excluidos de Git. Los dos casos reales demuestran este recorrido; no sustituyen la evaluación semántica integrada de 2.5.7 ni cierran los límites analíticos previos.

## Límites y siguiente paso

No se ha migrado la base privada de trabajo durante estas pruebas; la migración se aplicará al iniciar la aplicación actualizada. Sigue siendo un propietario local, sin autenticación multiusuario. Editar el perfil se aplica a nuevos análisis: aún no hay memoria estructurada, propagación de correcciones entre sesiones, chat ni nuevo dashboard.

**Siguiente incremento:** 2.5.2.A, contrato y persistencia de memoria versionada. El commit local de cierre es el que incorpora este informe; su hash se comunica al entregar el paso.
