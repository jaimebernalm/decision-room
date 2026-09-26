# Decision Room UI

React 19 + TypeScript + Vite + Tailwind 4. Componentes oficiales de shadcn/ui
(Radix, preset Nova, base Neutral) y AI Elements, instalados desde sus registros.
La fuente Geist se sirve localmente. Python sigue siendo el servidor y la API.

## Desarrollo

Node.js 22.13 o posterior (se recomienda una versión LTS compatible):

```sh
npm ci --prefix frontend
npm --prefix frontend run dev
```

Vite escucha en localhost y envía `/api` al servidor Python en el puerto 8787.
La sesión pertenece al origen: en la primera visita al servidor Vite hay que
introducir la clave local en la pantalla de acceso. No se incluye en el código.

## Aplicación local y comprobaciones

```sh
npm --prefix frontend run build
npm --prefix frontend test
npm --prefix frontend run lint
.venv/bin/python -m unittest discover -s tests -v
```

La compilación genera `decision_room/web/dist`, ignorado en Git. Python sirve el
HTML y los assets compilados en el mismo origen que `/api`; no hace falta un
servidor Node en producción. `scripts/dev/start_web.py` instala las dependencias
con el lock y compila antes de iniciar la aplicación.

## Componentes y mantenimiento

- `src/components/ui`: código del registro oficial shadcn/ui.
- `src/components/ai-elements`: código del registro oficial AI Elements.
- `src/components/workspace`: pantallas del producto que componen los anteriores.
- `src/lib`: contratos HTTP, borradores, idempotencia y preparación de gráficos.
- `components.json`: aliases, tema y registro `@ai-elements`.
- `licenses`: avisos de shadcn (MIT), Vercel (Apache 2.0) y texto de Apache 2.0.

Ejemplos para añadir componentes desde `frontend/`:

```sh
npx shadcn@latest add button
npx shadcn@latest add @ai-elements/reasoning
```

Los archivos de registro forman parte del proyecto: una actualización debe
revisarse como cambio de código. Adaptaciones locales actuales:

- Texto accesible en español en Sidebar, Dialog y Sheet.
- Message y Reasoning sin plugins de código, matemáticas o Mermaid: las respuestas
  actuales son prosa de negocio. Se mantienen Streamdown y los componentes reales.
- La aplicación desactiva HTML y enlaces externos en las respuestas del modelo.
- PromptInput usa estado controlado para conservar borradores durante fallos y
  evita que un botón de envío deshabilitado atenúe todo el campo editable.
- Reasoning está instalado, pero no se presenta mientras la API no proporcione
  contenido explícito de razonamiento. La espera muestra estados reales.

El script inicial de next-themes se marca como datos inertes porque esta SPA se
monta en el cliente; el efecto del proveedor aplica el tema sin abrir la CSP a
scripts inline. Las rutas se cargan bajo demanda.

Consulta [la migración](../docs/technical/react-ui-migration.md) y
[su validación](../docs/validation/2026-09-26-react-ui-check.md).
