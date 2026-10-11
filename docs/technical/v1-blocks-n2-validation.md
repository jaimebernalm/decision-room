# N2: presentación nativa de v1 (validación)

Fase N2 del [plan del informe v1 nativo](v1-native-report-plan.md), sobre el formato de
[N0](v1-blocks-n0.md). Valida la interfaz, no la calidad de los informes: eso lo miden N4 y N5.

## Qué se construyó

| Pieza | Archivos |
|---|---|
| Vista nativa | `frontend/src/components/workspace/engine-blocks.tsx` y `frontend/src/lib/blocks-format.ts` |
| PDF | `decision_room/reports/blocks_pdf.py` |
| Chat | `context_references.resolve_engine_block`; `ENGINE_ORIGINS` en `chat_agent`, `conversations`, `memory/retrieval` y `observability/collector` |
| Inicio (D2) | `web/home.py` (`engine_figures`, `disputed`) y `home.tsx` |

**Vista nativa:**
- tarjetas de cifra con la diferencia y el porcentaje calculados por la plataforma;
- gráficos de barras, columnas, líneas con varias series y huecos, y barras de cambio con eje
  cero, más la tabla de «Ver valores»;
- un tipo de gráfico desconocido se muestra como tabla;
- tablas con los decimales de cada celda;
- prioridades numeradas y avisos;
- aviso de cifra en revisión en el bloque, en sus antecesores y en sus descendientes;
- lista de cifras no comprobables y resumen de cobertura;
- selección para el chat por `block_id`, solo sobre la revisión vigente.

**PDF:**
- plantilla de la plataforma con todo el texto escapado;
- gráficos vectoriales con leyenda en filas y tabla de valores exactos;
- los mismos avisos que en la pantalla.

**Chat:**
- la selección `engine_block` se resuelve con el lock compartido del documento, comprobando que
  sea la revisión vigente y leyendo la proyección almacenada;
- el texto lleva sus avisos y se trata como afirmación del agente, nunca como evidencia revisada;
- en los cuatro módulos de `ENGINE_ORIGINS`, `engine_blocks` se trata como v1 y nunca se decora como
  legacy.

**Inicio (D2):**
- cifras de la revisión vigente, rotuladas «Informe v1 · cifra sin revisión»;
- aviso de disputa o de comprobación incompleta;
- se vuelve a comprobar que la revisión siga vigente dentro del lock.

## Pruebas

| Batería | Pruebas |
|---|---|
| vitest | 320 (`engine-blocks.test.tsx` 6, `home.test.tsx` 7) |
| tsc y oxlint | sin avisos nuevos |
| Python `test_engine_blocks` | 15 |
| `test_blocks_pdf` | 4 |
| `test_native_home` | 9 |

`test_native_home` cubre:
- tarjetas;
- retirada entre el listado y la lectura;
- discrepancia no localizada;
- aislamiento del renderizador;
- selección bajo discrepancias de prioridad y de descendientes, con comprobación incompleta y con
  un proyector nuevo sin volver a interpretar el JSON.

Las baterías de conversaciones conservan los mismos fallos preexistentes de entorno que la base.

## Revisión visual (solo interfaz)

1. **Los 12 informes v1 de F5 convertidos a bloques.**
   - Conversión semiautomática del HTML leído como texto (`.local/f5/html_to_blocks.py`, privado),
     conservando textos y números, errores incluidos.
   - Los 12 son válidos.
   - Herbolario-1 (con aviso simulado en la cifra 636) y clínica-3 se revisaron en una página de
     vista previa local con `BlocksReport`:
     - prioridades numeradas;
     - aviso junto a la cifra;
     - barras de cambio con eje cero;
     - tablas largas y líneas con huecos.
   - La conversión no mide calidad y los HTML del ensayo no se suben al repositorio.
2. **PDF.** Se rasterizó con PDFKit (`scripts/f5/pdf_pages.swift`) y se revisó a ojo:
   - leyendas;
   - huecos en líneas;
   - columnas;
   - tablas;
   - avisos ámbar.
3. **Aplicación real.** El servidor web de la rama se ejecutó sobre una copia de la base del smoke
   de N4 (`dr_view_n2b`), sin clave de modelo:
   - el informe nativo se ve con los componentes de la plataforma;
   - `/api/jobs/<id>/pdf` devuelve `application/pdf`;
   - `/api/jobs/<id>/raw` devuelve `informe.json` como adjunto `application/json`;
   - el inicio no muestra tarjetas porque ese informe no tiene bloques `cifra`.

**Incidente encontrado en esta revisión.** En una primera copia (`dr_view_n2`, conservada para
diagnóstico), el worker del renderizador HTML procesó los documentos `engine_blocks` y sobrescribió
su política de presentación. Rompía la vista y el inicio. Se corrigió en `513b674`:
- el renderizador solo toca documentos `engine_html` en cada punto de entrada y de escritura;
- `native_store` falla de forma cerrada ante un inventario ajeno.

**Evidencia.** Las capturas de esta revisión están en el registro local de la sesión, fuera de Git.

## Límites

- La revisión visual cubre unos pocos informes y no es una prueba de usabilidad con personas.
- Los gráficos de los informes convertidos de F5 se reconstruyen solo cuando sus valores exactos
  estaban en el HTML; los demás se omitieron en la conversión.
