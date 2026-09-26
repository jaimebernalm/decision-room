# Inicio como dashboard — paso 2.5.14

## Comportamiento entregado

Inicio muestra una selección de indicadores, gráficos y hallazgos, actividad
pendiente y cobertura de datos. Se elimina el bloque «Tu último informe» y la
lectura completa del informe en esta página. Cada tarjeta conserva periodo,
limitaciones y enlace a la fuente revisada. No se suman lotes ni se fabrican
comparaciones, alertas o métricas que no existan.

La selección inicial es determinista y se identifica como tal. El propietario
puede personalizarla, fijar y ocultar tarjetas. Se guarda por negocio en
PostgreSQL y sobrevive a recargas y reinicios. Se permiten hasta cinco
indicadores, dos gráficos y tres hallazgos; puede haber menos si los datos
no permiten más. Las tarjetas fijadas conservan su fuente, incluso cuando
esta deja de estar entre las veinte más recientes.

«Proponer selección» llama al modelo configurado con contexto del negocio,
hechos declarados con su alcance temporal y candidatos revisados. Su respuesta
solo puede elegir IDs existentes y explicar su utilidad. La propuesta aparece
en un diálogo y requiere «Aplicar propuesta». Los fijados se conservan y los
ocultos no reaparecen. Abrir Inicio no llama al modelo. Una propuesta pendiente
se reutiliza mientras sus datos y contexto sigan vigentes.

Las cifras y series siguen viniendo de la proyección validada del informe,
nunca de la respuesta editorial del modelo. Una fuente retirada desaparece
incluso si estaba fijada. Cambios de evidencia/contexto invalidan propuestas;
las revisiones de preferencias evitan que una propuesta lenta sobrescriba
una edición del propietario.

Los componentes son los shadcn ya instalados: Card, Button, Dialog, Checkbox,
Collapsible y Chart con Recharts. La serie principal usa azul `#367da5` en
claro y `#8dc5e5` en oscuro. Los tokens se comparten con informes y chat;
se mantienen las tablas accesibles de valores exactos y los huecos temporales.

## Comprobaciones

- Regresión Python: **284 pruebas** correctas antes de añadir el caso final de
  edición concurrente. Después, **7 pruebas dirigidas** de dashboard correctas,
  incluidas la concurrencia y la conservación de fuentes fijadas fuera del límite.
- Las pruebas dirigidas usan PostgreSQL aislado, una revisión aprobada por el
  flujo de prueba y modelos controlados. Cubren autenticación HTTP, aislamiento
  por negocio, persistencia, retirada, IDs inventados, límites, fijados/ocultos,
  caducidad y aplicación explícita. No se confunden con evaluación del modelo.
- Frontend: **31 pruebas** correctas, incluidas fuente/periodo, fijados en el
  editor y propuesta sin aplicación anticipada. TypeScript/Vite compilan.
  Lint sin errores; permanecen los avisos previos en componentes oficiales.
  Permanece el aviso previo del fragmento de chat de aproximadamente 504 kB.
- Navegador local: dashboard real, personalización, fijado conservado tras
  recarga, propuesta revisable, modo claro/oscuro y móvil de 390 × 844 sin
  desbordamiento horizontal. Tabla de valores y gráficos comprobados.
- Dos propuestas con **GPT-6 Luna real**. La primera seleccionó únicamente
  gráficos; se aclaró que un indicador resumen y su evolución se complementan.
  La segunda conservó el indicador fijado y eligió dos gráficos, respetando
  los IDs y límites. No cambió la selección al cerrar el diálogo. Esta prueba
  acotada verifica integración, no aceptación general de relevancia editorial.
- Revisión de diferencias y archivos a incorporar para excluir estado local,
  claves, datos privados y compilaciones generadas.

## Alcance y límites

El catálogo considera las veinte fuentes revisadas más recientes y las fuentes
adicionales fijadas. De cada informe toma los indicadores y gráficos validados
y hasta tres hallazgos de la proyección existente. Con pocos datos se muestran
pocas tarjetas. La información de pruebas puede ser histórica: se presenta su
periodo, sin llamarla «hoy» ni inferir que representa la situación actual.

La elección del agente es editorial y revisable. No crea nuevas métricas ni
actualiza automáticamente una tarjeta con otro lote porque tenga un título
parecido. Para incorporar un nuevo periodo se revisa la selección. Las tarjetas
siguen la revisión vigente de su fuente; fijarlas no permite saltarse controles
de validez. No hay generación periódica de propuestas en segundo plano.

## Contrato técnico

- `GET /api/home`: catálogo vigente, selección, fijados, ocultos, actividad,
  fuentes, revisión y huella de evidencia/contexto; propuesta si sigue vigente.
- `POST /api/home/preferences`: negocio, revisión, huella, IDs seleccionados y
  fijados, o `apply_proposal: true`. Conflictos devuelven 409.
- `POST /api/home/suggest`: negocio; generación estructurada y validada,
  comprobación de cambios antes de persistir y revisión optimista.
- Esquema 16: tabla `web_home_layouts`, aislada por `business_id`. No guarda
  copias de cifras o series. El endpoint anterior `/api/dashboard` se conserva
  por compatibilidad, pero el nuevo Inicio ya no lo utiliza.

## Corrección del acceso + en el estado vacío

El signo + del estado «Elige qué quieres tener a la vista» era decorativo.
Ahora es un Button de shadcn con nombre accesible «Añadir tarjetas al dashboard»
y abre el mismo selector que Personalizar. Respeta el bloqueo durante guardados.
Comprobados clic y Enter en el navegador, sin modificar la selección guardada.
Pasan las 31 pruebas de frontend y la compilación TypeScript/Vite.
