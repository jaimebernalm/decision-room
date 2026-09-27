# Migración de UI a componentes React oficiales

26 de septiembre de 2026 · rama `codex/feature-ui-ux`.

## Decisión

Usar React 19, TypeScript, Vite y Tailwind 4 para la interfaz completa. Mantener
Python, PostgreSQL, LangGraph y los contratos HTTP de negocio, análisis y chat.
shadcn/ui y AI Elements entregan código fuente que se incorpora al proyecto;
instalarlo con su CLI es una forma oficial de utilizar los componentes reales.
El MCP de shadcn consulta el mismo ecosistema de registros. Para esta migración
se utiliza el CLI, sin modificar la configuración global del asistente.

Referencias: [Vite](https://ui.shadcn.com/docs/installation/vite),
[MCP](https://ui.shadcn.com/docs/mcp),
[AI Elements](https://elements.ai-sdk.dev/docs/setup),
[Reasoning](https://elements.ai-sdk.dev/components/reasoning).

## Inventario y sustitución

| Superficie actual | Sustitución |
| --- | --- |
| HTML construido en app.js/dossier.js | Componentes y estado React, rutas hash compatibles |
| Barra lateral, móvil y confirmación de borrado | Sidebar/Sheet y AlertDialog de shadcn |
| Tarjetas, botones, filtros y formularios | Card, Button, Input, Select, Tabs, Checkbox y Label |
| SVG de gráficos y listas de valores | Chart de shadcn con Recharts y Table accesible |
| Conversación y compositor | Conversation, Message, PromptInput y Suggestion de AI Elements |
| Fuentes y detalle progresivo | Sources y Collapsible oficiales |
| Inicio, biblioteca, ficha y versiones | Vistas React sobre las API existentes |
| Detalle y aclaraciones de análisis | Formularios React con los mismos identificadores y revisiones |
| Archivos estáticos sin compilación | Vite produce `decision_room/web/dist`, servido por Python |

El contenido de Reasoning requiere una salida explícita del proveedor. No se
infiere ni inventa a partir de esperas. Los indicadores operativos muestran
únicamente estados y actividad ya emitidos por el servidor.

## Contratos conservados

- Autenticación por cookie HttpOnly; intercambio inicial del fragmento de acceso;
  mismo origen, protección CSRF, límites de archivo y CSP.
- Negocio activo, revisión optimista del perfil, ámbitos y versiones de datos.
- Borradores e identificadores idempotentes ante doble envío o respuesta perdida.
- Cola, aclaraciones, recuperación, correcciones, historial y borrado de chats.
- Referencias a hallazgos con hash de revisión y versión de datos elegida.
- Informes publicados tras revisión, retirada por cambios de contexto y evidencia.
- Formularios persistentes durante refrescos y rechazo de respuestas tardías tras
  navegar o cambiar de negocio.

## Comprobación

Compilación TypeScript/Vite, pruebas de contratos del cliente y de componentes,
regresión Python/HTTP, inspección de dependencias y comprobación visual de las
pantallas principales en escritorio y móvil. Los datos de demostración para las
pruebas permanecen separados del espacio del propietario.


## Integración realizada

La aplicación web completa usa React: acceso, selección y perfil de negocios,
inicio, listados, chat, subida de análisis, aclaraciones, informes, ficha, datos
y versiones, correcciones e historial. Se eliminó el renderer anterior.

`GET /api/jobs/:id/presentation` y
`GET /api/chats/:chat/presentation/:turn` entregan el informe completo para React.
Reutilizan los mismos bloqueos, comprobaciones de publicación y versiones que
el exportador. El HTML autónomo se conserva únicamente como vista imprimible.
La nueva proyección contiene todas las conclusiones, métodos, siguientes pasos,
fuentes y valores; excluye programas, logs internos y rutas de almacenamiento.

Los gráficos oficiales de shadcn se apoyan en Recharts: barras con referencia
cero, líneas con distancias temporales reales y cortes ante días ausentes, y
contratos de tabla sin conversión artificial a gráfico. Tooltips y tablas usan
las cadenas decimales revisadas en servidor. No se inventan métricas para llenar
espacios vacíos.

No fue necesario migrar Python a JavaScript ni incorporar Next.js. El MCP de
shadcn es opcional para futuras búsquedas; el CLI ya instaló las fuentes reales.
Versiones reproducibles en `frontend/package-lock.json`, configuración de
registros en `frontend/components.json` y avisos de licencia en
`frontend/licenses/`. Detalles operativos y adaptaciones en
[frontend/README.md](../../frontend/README.md).

Resultados: [validación de la migración](../validation/2026-09-26-react-ui-check.md).
