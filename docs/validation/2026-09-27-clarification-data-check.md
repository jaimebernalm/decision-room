# Aclaraciones con los datos a la vista

## Corrección

Una opción escrita podía enviarse junto con la disposición `unknown`. La
planificación conservaba esa dependencia sin resolver y bloqueaba las operaciones
que necesitaban su definición. La pregunta podía ser pertinente aunque el aviso
posterior sugiriera equivocadamente que hacía falta un archivo más completo.

- Una respuesta escrita habilita «Guardar respuesta» y deshabilita la opción de
  no disponer del dato, con una explicación visible. El servidor rechaza la
  combinación de texto con `unknown` o `declined`.
- El detalle conserva las referencias de las preguntas y muestra el texto de
  las preguntas contestadas, que antes llegaba como un objeto sin renderizar.
- Si una aclaración no disponible bloquea la planificación, se explica el motivo
  y se permite revisar y confirmar un nuevo contexto. Se crea otro informe con
  los mismos datos mediante el servicio existente, conservando el intento y la
  respuesta originales. No se transforma automáticamente una respuesta antigua
  en una definición confirmada. Los reintentos conservan su clave de envío.

## Vista de datos

En el informe, onboarding y chat, una pregunta analítica abre «Datos para
responder». Se selecciona la tabla referenciada y se destacan las columnas
mencionadas. Las preguntas de revisión sin referencias estructuradas muestran
el selector de tablas y no inventan una asociación con una columna.

La vista lee las tablas preparadas del informe (incluidas las procedentes de
Excel), con 50 filas y 12 columnas por página. Conserva el orden y el número de
registro de origen; distingue nulos de texto vacío. Las celdas se limitan a 500
caracteres, con aviso visible. Permite cambiar tabla y página sin perder una
respuesta escrita. No presenta una muestra como una agregación o un resultado.

La ruta exige sesión, comprueba negocio e informe y solo admite tablas de ese
análisis. Verifica la integridad del Parquet antes de mostrar filas; no expone
rutas locales ni ejecuta consultas SQL aportadas por el cliente. La verificación
puede tardar más con archivos grandes. La vista no sondea el archivo cada pocos
segundos.

## Validación

- 35 pruebas del servicio web: referencias, aislamiento entre negocios, acceso
  HTTP autenticado, tabla ajena, paginación, celdas largas, columnas, nulos,
  integridad y respuesta contradictoria, además de las regresiones existentes.
- 49 pruebas React, con cuatro pruebas nuevas sobre vista abierta, columna destacada,
  paginación sin perder el borrador, confirmación, respuesta desconocida,
  recuperación con el mismo conjunto de datos y preguntas en chat.
- Compilación TypeScript/Vite y lint focalizado.
- Comprobación visual en navegador con servidor real, base temporal, modelo
  controlado y datos sintéticos: tabla abierta, selección de respuesta y
  recuperación HTTP con el mismo archivo. Revisado a 390 y 1280 px. No es una
  evaluación de calidad del modelo.

```sh
.venv/bin/python -m unittest discover -s tests -p test_web.py
npm --prefix frontend test
npm --prefix frontend run build
```
