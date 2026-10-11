# F4 (Claude): vista, recepción y descarga

Rama `claude/v1-view` desde `9bd7469`. Se integra con el navegador aislado de Astra
(`codex/v1-engine-path`) al final de F4. Sin llamadas a modelos, sin push.

## Decisión: solo instantánea, nunca el HTML del agente en la vista

El plan proponía `<iframe sandbox="allow-scripts" srcdoc>` con el HTML del agente, sujeto a la
puerta de navegación de §7. **La puerta falló y la vista se retira** (plan §6: «F4 bloquea esa
vista o usa una instantánea estática»).

- **Primer cambio:** marco sin scripts (`sandbox=""`). Un `srcdoc` hereda la CSP del producto
  (`script-src 'self'` sin `'unsafe-inline'`), así que los scripts del informe no correrían de
  todos modos, y los lectores de los ensayos juzgaron capturas estáticas.
- **Fallo demostrado** (Astra, Chrome real por CDP, HTML sintético propio, CSP real del
  producto):
  - sin scripts, `<svg><a href="#"><animate attributeName="href" values="http://ORIGEN/escape"
    …/>` pasa la recepción;
  - al pulsar, el marco navegó a una ruta del propio origen, permitida por `frame-src 'self'`.
- **Comprobación descartada:** el `meta refresh` sin scripts no navegó.
- **No se repara con otra lista de prohibiciones:** se retira la vista provisional del bruto.

**Política `v1-snapshot-only-1`.** El dueño ve la instantánea del navegador aislado. Es HTML
propio de la plataforma con imágenes PNG, sin marcado, CSS ni URLs del agente, mostrado en el
marco sin scripts y acompañado del texto canónico. Antes de que exista, la vista queda «en
preparación». Si el renderizado falla, «bloqueada». El bruto se conserva y se descarga como
adjunto.

La suite hostil en Chrome real no corre en este entorno: Chrome headless no termina, ni
siquiera con páginas triviales. La regresión nativa del clic SMIL, con sumidero en el mismo
origen, queda en la rama de Astra.

## Qué ve el dueño

1. Si la recepción bloquea: «Presentación bloqueada», con motivo neutro y texto canónico si
   existe.
2. Si hay una instantánea lista: la instantánea en el marco sin scripts y, debajo, «Texto del
   informe» (texto canónico, seleccionable).
3. Si el renderizado terminó sin instantánea o falló: «Presentación bloqueada».
4. En otro caso: «Preparando la vista».

El marco lleva su propia CSP antes de cualquier contenido:
`default-src 'none'; img-src data:; style-src 'unsafe-inline'; font-src data:; base-uri 'none';
form-action 'none'`. Hereda además la CSP de la página (`frame-src 'self'`).

**Recepción** (`decision_room/reports/presentation.py`, pura y sin efectos). Bloquea:

- texto vacío, más de 256 KiB, UTF-8 inválido o bytes NUL;
- los elementos `base`, `iframe`, `frame`, `frameset`, `object`, `embed`, `applet`, `link`,
  `portal` y `meta` (salvo `charset` y `viewport`);
- el atributo `srcdoc`;
- URLs con esquema o `//` en atributos de URL, salvo `data:image/` y `#`;
- `url()` y `@import` en CSS que no sean `data:` o `#`;
- cualquier URL en atributos que no sea `#fragmento` o `data:image/…`, también las relativas.
  Los caracteres de control y espacios se quitan antes de comprobarla, como hace el navegador.

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
  - política de recepción, caso por caso, incluidos los casos señalados por Astra: viewport
    con `http-equiv`, URLs relativas, esquemas con tabulador o salto de línea, `srcset`, `ping`
    y `data:` que no sea imagen;
  - el HTML del agente nunca es contenido del marco;
  - modos de la vista;
  - prioridad de la instantánea;
  - texto canónico con recepción bloqueada;
  - superficie web: marco, adjunto con cabeceras, PDF 409, `/report` 409, informe con scripts
    en espera sin `srcdoc`, sin descarga en legacy.
- Frontend: `engine-report.test.tsx` comprueba el iframe con `sandbox=""` y `srcdoc`, el texto
  canónico, y que ni «pending» ni «blocked» se enmarcan.

Pendiente en esta rama: el chat fase 1 y el cierre.
