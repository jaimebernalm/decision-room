# Inicio y navegación del negocio · 2.5.6

**Estado:** 2.5.6 implementado y validado sobre la integración del dashboard y la
ficha/versiones de 2.5.5. La evaluación integrada de 2.5.7 sigue pendiente.

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
  Los análisis mantienen su propio historial. Nueva pregunta usa el mismo compositor
  que Inicio: crea el chat al enviar. Mi negocio permite adjuntar una versión antes
  de enviar, visible en el compositor y en la conversación.
- **Informes:** permite continuar análisis, abrir resultados y volver al chat de
  origen. Los resultados analíticos de chat aparecen en la biblioteca solamente
  después de solicitar su informe. Los cambios de memoria retiran resultados
  afectados también del dashboard. La biblioteca diferencia revisiones históricas
  y retiradas, e incorpora búsqueda y filtros de estado.
- **Mi negocio:** ficha de memoria con información, archivos y cambios. Permite
  editar, confirmar y retirar recuerdos, subir CSV sin investigar y elegir versiones.
  Los originales se conservan, y las correcciones retiran resultados afectados.
  Véase [el contrato de 2.5.5](business-dossier.md).
- **Actualización:** Inicio consulta cambios de informes y chats; conserva el texto
  y foco del prompt. Informes actualiza su listado. La ficha se refresca al entrar o mediante «Actualizar ficha», para conservar las ediciones en curso. Una navegación
  nueva descarta respuestas tardías de rutas anteriores.

## Referencias y presentación

- El cliente envía `finding_reference` con `report_id`, `report_version` (hash de la
  revisión aprobada) y `claim_key`. El servidor comprueba negocio, publicación y
  conjunto, y deriva las fuentes a partir de las ejecuciones citadas. Se guarda en
  el JSON del mensaje existente; no exige migración ni duplica el informe.
- La referencia llega al contexto de conversación como punto de partida. El agente
  debe abrir el informe mediante la recuperación existente. Una investigación nueva
  recibe la referencia y una dependencia de esa revisión; una retirada invalida su uso.
  No se sustituye silenciosamente la versión elegida por la más reciente.
- Los reintentos exactos reutilizan mensaje y referencia incluso si se retiró después
  de persistir; la retirada sigue impidiendo publicar su contenido. Cambiar la referencia
  con la misma clave de envío se rechaza.
- El chat usa la misma proyección verificada que Inicio para cifras y gráficos,
  filtrada por los hallazgos elegidos. Las respuestas anteriores se proyectan al leerlas
  solo si su revisión y hash siguen vigentes. No hay una nueva redacción libre de cifras.
- La actividad consulta últimos mensajes, incluidos los cálculos aún no publicados,
  sin reconstruir todos los gráficos de todas las conversaciones. La biblioteca mantiene
  la publicación explícita de informes. `presentation_status=withdrawn` permite distinguir
  una retirada sin modificar el estado de recuperación del trabajo analítico.
- El compositor ocupa espacio propio al pie del contenido. El botón de cabecera lleva
  el foco al campo. Se conservan borradores y referencias entre navegación/recargas;
  el título se acorta sin modificar el mensaje. El onboarding no inicia el refresco de Inicio.

## Pendiente

- Evaluación integrada de 2.5.7. Los gráficos muestran evidencia guardada; no ofrecen
  filtros que recalculen resultados ni combinan revisiones incompatibles.

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

La ronda de cierre incluye referencias estructuradas, interfaz móvil, modelo real,
onboarding y regresiones. Véase [validación de 2.5.6](../validation/2026-09-23-daily-ux-check.md).
