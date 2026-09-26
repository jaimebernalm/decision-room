# Asistente flotante — 26 de septiembre de 2026

## Alcance

Paso 2.5.9: compositor inferior superpuesto al contenido del negocio, compacto,
redondeado y plegable en «Pregunta algo» a la derecha. Composición de los
componentes oficiales ya instalados: AI Elements PromptInput, shadcn InputGroup,
Button y Collapsible. Referencias consultadas:
[Prompt Input](https://elements.ai-sdk.dev/components/prompt-input),
[Button](https://ui.shadcn.com/docs/components/button) y
[Collapsible](https://ui.shadcn.com/docs/components/collapsible).

Se retira el selector «Datos para esta conversación». Los accesos desde un
hallazgo o una versión de datos conservan su contexto explícito, con etiqueta
compacta y acción de quitarlo. Los borradores siguen separados por negocio.
La preferencia de plegado persiste; «Nuevo chat» abre la barra y enfoca el campo.
El chat abierto conserva su compositor propio. El acceso inicial, la creación
y el cambio de negocio no muestran la barra de otro negocio.

## Comprobaciones

- `npm --prefix frontend test`: 22 pruebas aprobadas. Incluyen conservación de
  borrador, plegado/restauración y foco, contexto de análisis sin selector,
  protección frente a redirección tardía y navegación con una sola página y
  un solo asistente. Se añadió regresión del conflicto de claves entre hermanos
  detectado y corregido durante la comprobación visual.
- `npm --prefix frontend run build`: TypeScript y producción correctos.
  Persiste el aviso previo del fragmento de chat de aproximadamente 504 kB.
- `npm --prefix frontend run lint`: sin errores; 14 avisos previos en componentes
  oficiales y su hook móvil.
- Navegador local, escritorio: barra sobre los gráficos tras desplazar el
  contenido 1.928 px; botón plegado a la derecha. Inicio, Informes y Nuevo chat
  conservan un solo contenido y un compositor después de la corrección.
- Vista de 390 × 844: sin desbordamiento horizontal, barra dentro de la
  pantalla, botón plegado a 12 px del borde derecho. Restauración de borrador
  y foco comprobadas. Vista de escritorio restaurada y borrador de prueba borrado.
- `git diff --check`: sin errores.

No se cambia el backend ni los contratos de envío. Los envíos se validan con
respuestas simuladas; esta comprobación visual no requiere nuevas llamadas al
modelo ni modificar los datos del negocio.
