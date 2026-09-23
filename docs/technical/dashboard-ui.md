# Inicio y navegación del negocio · integración con 2.5.4

**Estado:** interfaz de `feature/dashboard-ui` integrada con memoria, recuperación y
conversaciones de `feature/business-memory-ux`. Este avance de 2.5.6 no cierra
2.5.6 ni la evaluación integrada de 2.5.7. La ficha y versiones de 2.5.5 ya están implementadas.

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
- **Mi negocio:** ficha de memoria con información, archivos y cambios. Permite
  editar, confirmar y retirar recuerdos, subir CSV sin investigar y elegir versiones.
  Los originales se conservan, y las correcciones retiran resultados afectados.
  Véase [el contrato de 2.5.5](business-dossier.md).
- **Actualización:** Inicio consulta cambios de informes y chats; conserva el texto
  y foco del prompt. Informes actualiza su listado. La ficha se refresca al entrar o mediante «Actualizar ficha», para conservar las ediciones en curso. Una navegación
  nueva descarta respuestas tardías de rutas anteriores.

## Pendiente

- **Resto de 2.5.6:** «Preguntar sobre este hallazgo» con una referencia estructurada
  a la revisión y al hallazgo exactos, y validación conjunta del recorrido. Los
  avisos de versiones anteriores ya se incorporan desde 2.5.5.
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
