# F4 (Claude): vista, recepción y descarga

Rama `claude/v1-view` desde `9bd7469`. Se integra con el navegador aislado de Astra
(`codex/v1-engine-path`) al final de F4. Sin llamadas a modelos, sin push.

## Decisión: marco sin scripts

El plan proponía `<iframe sandbox="allow-scripts" srcdoc>`. La vista usa `sandbox=""`, sin
scripts, por tres razones:

- Un iframe `srcdoc` hereda la política de la página. La CSP del producto tiene
  `script-src 'self'` sin `'unsafe-inline'`, así que los scripts en línea del informe quedarían
  bloqueados igualmente, y una meta CSP no puede aflojar la heredada.
- Los lectores de los ensayos juzgaron capturas estáticas.
- Los gráficos SVG en línea de v1 se pintan sin JS.

Para un informe cuyos gráficos se dibujan con JS, la vista espera la instantánea del
navegador aislado. Esa instantánea es HTML propio de la plataforma con imágenes PNG, sin
marcado, CSS ni URLs del agente. Política: `v1-frame-noscript-1`.

## Qué ve el dueño

1. Si hay una instantánea lista: la instantánea en el marco sin scripts, con «Texto del
   informe» (texto canónico, seleccionable) debajo.
2. Si no la hay, la recepción pasa y el HTML no tiene scripts ni manejadores `on*`: el bruto en
   el marco sin scripts, como vista provisional.
3. Si el HTML tiene scripts: «Preparando la vista» mientras se renderiza. Si el renderizado
   falla, «Presentación bloqueada».
4. Si la recepción bloquea: «Presentación bloqueada» con motivo neutro. El texto canónico se
   muestra si existe.

El marco lleva su propia CSP antes de cualquier contenido:
`default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src data:; base-uri 'none';
form-action 'none'`. Hereda además la CSP de la página (`frame-src 'self'`).

**Recepción** (`decision_room/reports/presentation.py`, pura y sin efectos). Bloquea:

- texto vacío, más de 256 KiB, UTF-8 inválido o bytes NUL;
- los elementos `base`, `iframe`, `frame`, `frameset`, `object`, `embed`, `applet`, `link`,
  `portal` y `meta` (salvo `charset` y `viewport`);
- el atributo `srcdoc`;
- URLs con esquema o `//` en atributos de URL, salvo `data:image/` y `#`;
- `url()` y `@import` en CSS que no sean `data:` o `#`.

La vista la calcula al leer. Al integrar, el worker de Astra la registra con `set_presentation`.

**Alrededor del marco:**

- título y estado de la entrega;
- «PDF no disponible todavía» (P9);
- descarga del HTML original como adjunto: `application/octet-stream`, `Content-Disposition:
  attachment`, `Content-Security-Policy: sandbox`. Nunca se sirve como página ni se presenta
  como versión saneada;
- detalles técnicos plegados;
- sin edición;
- nunca «Revisado».

`/report` (HTML de página completa) sigue respondiendo 409 para informes v1, y `/pdf` responde
409 con «PDF no disponible todavía».

## Pruebas

- `tests/test_engine_view.py`:
  - política de recepción, caso por caso;
  - modos de la vista;
  - prioridad de la instantánea;
  - texto canónico con recepción bloqueada;
  - superficie web: marco, adjunto con cabeceras, PDF 409, `/report` 409, informe con scripts
    en espera sin `srcdoc`, sin descarga en legacy.
- Frontend: `engine-report.test.tsx` comprueba el iframe con `sandbox=""` y `srcdoc`, el texto
  canónico, y que ni «pending» ni «blocked» se enmarcan.

Pendiente en esta rama: la suite hostil en Chrome real, el chat fase 1 y el cierre.
