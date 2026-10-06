# Coincidencias de Chats y grupos de Datos

Paso 2.5.27, 6 de octubre de 2026.

La biblioteca de Chats resalta en negrita las coincidencias en títulos y
fragmentos. El texto original se conserva: la búsqueda de `cuant` resalta tanto
`cuant` como `cuánt`. La comparación ignora mayúsculas y marcas diacríticas,
localiza todas las coincidencias literales y conserva los grafemas originales.
Se renderizan nodos de texto y `<strong>`, sin interpretar HTML de los mensajes.

Las pestañas Información, Datos e Historial de Mi negocio tienen 40 px de altura,
texto de 14 px y menos relleno horizontal. Datos se divide, por elección del
propietario, en Archivos, Tablas y Relaciones. Los tres grupos se pueden plegar
de forma independiente y mantienen la estética de Información. Archivos tiene
un `+` independiente en la cabecera que abre el formulario de subida existente.

Los archivos originales, tablas y relaciones se identifican por conjunto y
versión. Se mantienen periodos, estados de corrección/sustitución/preparación,
descargas originales y preparadas, y la selección de la versión exacta al
preguntar. Las tablas que fallaron no ofrecen descarga y las versiones corregidas
no ofrecen la acción de preguntar. Las relaciones conservan su visor existente.

## Comprobaciones

- `npm --prefix frontend test`: 233 pruebas en 31 archivos, todas pasan. Incluyen
  mayúsculas, tildes compuestas/descompuestas, caracteres literales, múltiples
  coincidencias, HTML escapado y respuestas tardías; grupos independientes,
  subida sin desplegar un grupo plegado, descargas y versiones corregidas.
- `npm --prefix frontend run build`: TypeScript y Vite pasan.
- `npm --prefix frontend run lint`: sin errores; 27 avisos existentes. Se mantiene
  el aviso existente de tamaño de paquetes en la compilación.
- Localhost 8787, escritorio 1280 × 900: coincidencias `cuant` y `cuánt` con peso
  de fuente 600; pestañas de 40 px y texto de 14 px; tres grupos visibles. El `+`
  abre el diálogo de subida conservando Archivos plegado; se cierra sin subir.
- Móvil 390 × 844: pestañas y grupos visibles, documento y anchura desplazable de
  390 px, sin desbordamiento horizontal. Se restablece el viewport al terminar.
- Revisión de diferencias y `git diff --check` sin incidencias.

Las capturas permanecen en `.local/checks/`, fuera de Git. No se suben archivos,
se envían mensajes ni se cambia el contrato backend.
