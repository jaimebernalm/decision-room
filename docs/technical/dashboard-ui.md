# Inicio y navegación del negocio · integración con 2.5.4

**Estado:** interfaz de `feature/dashboard-ui` integrada con memoria, recuperación y
conversaciones de `feature/business-memory-ux`. Este avance de 2.5.6 no cierra
2.5.5 ni la evaluación integrada de 2.5.7.

## Recorridos conectados

- **Inicio:** muestra una sola revisión publicable, su periodo, hallazgos y gráficos
  respaldados. El selector cambia de informe sin mezclar revisiones; cada enlace
  abre el informe y, cuando corresponde, el hallazgo exacto. El servidor comprueba
  evidencia y memoria bajo los mismos bloqueos que la exportación del informe.
- **Prompt:** crea una conversación y envía su primer mensaje mediante los contratos
  existentes. No exige otro CSV. Conserva borrador y claves de creación/envío ante
  recargas o respuestas perdidas; un reintento reutiliza el chat y el mensaje.
  Si el usuario navega mientras se envía, la respuesta no le cambia de pantalla.
- **Sugerencias:** consultar el contexto del negocio y, cuando hay conjuntos
  disponibles, descubrir los datos. Rellenan el prompt para que el usuario pueda
  editarlo antes de enviarlo. No inventan cifras, periodos ni capacidades.
- **Barra lateral:** Inicio, Informes, Mi negocio, Nueva pregunta y chats reales.
  Los análisis mantienen su propio historial. Nueva pregunta abre la creación de
  chat, con selección opcional de datos; no repite el formulario del negocio.
- **Informes:** permite continuar análisis, abrir resultados y volver al chat de
  origen. Los resultados analíticos de chat aparecen en la biblioteca solamente
  después de solicitar su informe. Los cambios de memoria retiran resultados
  afectados también del dashboard.
- **Mi negocio:** consulta y edición del perfil ya persistido, acceso a los CSV
  aportados y cambio de negocio. «Analizar un CSV nuevo» abre la ingesta existente.
  Los trabajos de chat reutilizan datos: no se cuentan como archivos nuevos ni
  muestran un enlace de descarga que el backend rechazaría.
- **Actualización:** Inicio consulta cambios de informes y chats; conserva el texto
  y foco del prompt. Informes y Mi negocio actualizan sus listados. Una navegación
  nueva descarta respuestas tardías de rutas anteriores.

## Pendiente

- **2.5.5:** ficha de memoria estructurada, edición/retirada de recuerdos, resolución
  completa de propuestas/conflictos, carga de archivos independiente de análisis,
  conjuntos y versiones explícitos. El perfil actual no sustituye esa ficha.
- **Resto de 2.5.6:** «Preguntar sobre este hallazgo» con una referencia estructurada
  a la revisión y al hallazgo exactos, y estados derivados de las nuevas versiones
  de datos de 2.5.5. No se ofrece todavía un botón que prometa esa vinculación.
- Los gráficos permiten consultar valores y evidencia; no ofrecen filtros que
  recalculen resultados. La aceptación funcional completa corresponde a 2.5.7.

## Comprobación

```sh
node --check decision_room/web/static/app.js
node --test tests/test_dashboard_ui.cjs
.venv/bin/python -m unittest discover -s tests
```

Las pruebas JavaScript cubren la entrega durable del prompt, doble envío,
respuestas perdidas, cambio de pantalla/negocio y borradores. Las pruebas de
PostgreSQL y HTTP comprueban selección, aislamiento, publicación explícita desde
chat y retirada tras cambios de memoria. Véase la
[validación de integración](../validation/2026-09-23-dashboard-integration.md).
