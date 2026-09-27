# Validación de la migración React y componentes oficiales

26 de septiembre de 2026 · paso 2.5.8 · rama `codex/feature-ui-ux`.

## Resultado

La interfaz utiliza las fuentes oficiales de shadcn/ui y AI Elements, instaladas
con el CLI de shadcn y el registro de AI Elements. React sustituye al renderer
anterior en todas las pantallas. Python sirve la compilación Vite y mantiene los
servicios, la autenticación, los bloqueos de publicación y los contratos durables.

## Pruebas automatizadas

- TypeScript y Vite: compilación de producción correcta. Rutas bajo demanda;
  entrada principal de aproximadamente 312 kB / 95 kB gzip. Vite informa de un
  chunk de chat de aproximadamente 504 kB; se carga al abrir esa funcionalidad.
- Vitest + Testing Library: **20 pruebas correctas**. Recuperación de respuestas
  perdidas, idempotencia, doble envío, borradores, navegación durante peticiones,
  selección del identificador de análisis, cola, onboarding, confirmación de
  borrado, prosa sin HTML activo, precisión revisada y huecos temporales.
- Regresión Python: **275 pruebas correctas** en la ejecución completa, incluidas
  fronteras HTTP, negocios, memoria, conversaciones, análisis y publicación.
- Proyección React añadida: **3 pruebas adicionales correctas** sobre todas las
  conclusiones, valores exactos, fuentes públicas, exclusión de logs privados,
  rechazo de evidencia inválida y contratos de tabla.
- Los tests HTTP verifican los assets compilados y rechazan recorridos fuera de
  `dist`. Los informes JSON se retiran tras invalidación igual que sus exportaciones.
- Oxlint: sin errores; 14 avisos en código de los registros oficiales (exportaciones
  para Fast Refresh y patrones de hooks/componentes de esas bibliotecas).
- Auditoría npm al instalar dependencias: sin vulnerabilidades conocidas.
- `git diff --check`: correcto. Archivos generados y datos privados fuera de Git.

## Navegador y operación local

Comprobaciones con el servidor Python, PostgreSQL y modelo controlado en una base
de pruebas separada del espacio del propietario:

- Inicio y apertura del informe completo, método y evidencia numérica.
- Creación de conversación, envío y recepción de respuesta, compositor fijo.
- Pantallas a 390 × 844 y escritorio; navegación móvil, tema claro/oscuro y diálogos.
- Declaración de memoria desde el diálogo y aparición de la revisión guardada.
- Subida de CSV sintético desde el selector nativo, importación y versión disponible.
- Gráficos de barras/líneas con el contrato público de pruebas, tooltip y expansión
  por teclado de la tabla de valores exactos. Sin desbordamiento de la página móvil.
- Identificada y corregida la ausencia del TooltipProvider requerido por Sidebar.
- Corregida la selección de datasets: la API de catálogo entrega el ID de tabla y
  el ID de análisis por separado; las conversaciones reciben el segundo.

El proceso local anterior seguía ejecutando una versión previa a las rutas de chat
y dashboard. Se comprobó que no había trabajos activos, se guardó una copia privada
de la base y se reinició con su configuración de modelo existente. El arranque
normal aplicó las migraciones ya incluidas en el proyecto. Se verificaron respuestas
200 en inicio, workspace, chats, ficha y dashboard; el negocio y su informe existentes
se muestran en la nueva interfaz. Se abrió la aplicación en el navegador de Codex.

Esta validación comprueba interfaz y contratos. Las respuestas del modelo controlado
no constituyen una nueva evaluación de calidad analítica. Reasoning queda instalado
sin contenido ficticio mientras la API no entregue razonamiento explícito.

## Reproducción

```sh
npm ci --prefix frontend
npm --prefix frontend run build
npm --prefix frontend test
npm --prefix frontend run lint
.venv/bin/python -m unittest discover -s tests -v
```
