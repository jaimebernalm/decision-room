# P3 — Presentación comprensible para el dueño

Base actual `5d3087c`; rama `codex/feature/report-owner-presentation-v2`.
Se integra la implementación P3 anterior (`cefd8e7`) sin cambiar el diagnóstico
analítico ni consultar los datos de ensayo para desarrollar reglas.
[Plan](../technical/report-presentation-plan.md). Sin llamadas reales al modelo.

## Activar el candidato

- Control: `DECISION_ROOM_OWNER_PRESENTATION=false` (predeterminado).
- P3: `DECISION_ROOM_OWNER_PRESENTATION=true`, antes de cargar `Config`.
- API: `review.start(..., owner_presentation=True)`; `False` explícito prevalece
  sobre la configuración. `None` hereda la configuración cargada.
- CLI: `review-start --owner-presentation`.

La opción se guarda en `agent_reviews.options`, participa en la huella de petición,
se conserva al reanudar/reiniciar y decide la presentación de ese informe. Cambiar
la variable no transforma informes ya aprobados. Crear una revisión nueva y usar
una request key nueva para cambiar de brazo. Reiniciar el proceso web si se desea
cambiar la configuración de las futuras revisiones.

P3 no activa continuidad ni recuperación de validación: `DECISION_ROOM_RESEARCH_CONTINUITY` sigue siendo una opción
independiente, al igual que `DECISION_ROOM_RESEARCH_VALIDATION_RECOVERY`. Para atribuir efectos, mantener iguales investigación, fuentes,
objetivo, modelo y presupuestos entre brazos. El lanzador puede revisar la misma
investigación congelada con P3 apagada y encendida usando claves diferentes.

## Cambios

1. Redactor y revisor reciben instrucciones P3 bajo `owner-presentation-v1`: respuesta
   primero, títulos explicativos, etiquetas del negocio, números legibles, motivo
   de los periodos comparados y cautelas generales centralizadas. Se reemplazan dos
   instrucciones antiguas que prometían mostrar marcadores/contadores internos.
   Contexto, prompt, esquema y correcciones siguen en la auditoría existente.
2. El feedback editorial señala ubicaciones con posibles identificadores internos,
   jerga y exceso de decimales; pide comprobar el motivo de las comparaciones.
   No constituye evidencia, no aprueba ni bloquea automáticamente, ni reescribe
   hechos. La detección de coincidencias textuales es una ayuda al revisor.
3. Web, HTML y PDF omiten el rótulo genérico de entrega parcial. Conservan el estado
   real y la cobertura en los datos. Las explicaciones de respuestas incompletas
   aparecen en límites; ocultar un rótulo no transforma una respuesta parcial en
   completa. Las condiciones de las recomendaciones se mantienen junto a ellas.
4. Cifras visibles: normalmente hasta dos decimales sin ceros finales, con separador
   de miles. Los valores pequeños conservan cifras significativas, sin mostrar
   cero para un valor distinto de cero. No cambia ningún cálculo ni valor fuente.
   Los cambios de precisión que guarde expresamente el dueño siguen prevaleciendo.
5. Las limitaciones explícitas de cada orientación pasan a una sección única con
   las limitaciones del informe y la cobertura pendiente. Se eliminan únicamente
   duplicados exactos normalizados; no se borran frases de hallazgos por heurística.
   En React la sección está después de los hallazgos, siempre visible.
6. Las fuentes ofrecen nombres de indicadores disponibles y cifras legibles;
   identificadores, operaciones y cifras originales están en un segundo desplegable.
   Las tablas de gráficos conservan los valores originales en detalle opcional.
   PDF conserva estos datos en un anexo final; el HTML de CLI usa la misma
   proyección y catálogo verificado que la web. Las auditorías originales permanecen.
7. La sustitución de códigos usa el catálogo completo y verificado ya existente.
   P3 extiende su aplicación a pies, orientaciones, límites, detalles y leyendas,
   manteniendo alineadas coordenadas y estilos. No se adivinan nombres ni se
   cambian referencias numéricas. Si el catálogo no permite identificar un nombre,
   se conserva el código y se pide al agente explicar la limitación.

No cambia el contrato JSON del informe ni se añaden migraciones. P3 no incorpora
nuevas reglas de prioridad, investigaciones, modelos, presupuestos ni lógica por
negocio. Puede utilizar los cálculos de revisión ya autorizados para consultar una
etiqueta comprobable, sin ampliar permisos ni inventar datos.

## Comprobaciones

- 86 pruebas Python sobre `5d3087c`: continuidad, recuperación y su independencia de P3, formatos, datos inmutables, cobertura parcial honesta,
  centralización de límites, prompts, feedback, HTML/PDF, catálogos completos,
  colisiones, edición manual, idiomas y persistencia/reanudación.
- La matriz de esquemas estrictos incluye P3: 59 contextos / 110 peticiones
  simuladas cubren los diez productores. Todos los objetos mantienen
  `additionalProperties: false` y todas las propiedades obligatorias, también
  tras insertar recuperación de memoria.
- 32 pruebas de frontend (seis archivos): lectura, idioma, cifras, teclado, apertura del detalle
  técnico y tablas con nombres y códigos originales bajo demanda.
- Compilación Python, build TypeScript/Vite y `git diff --check` correctos.
  Vite mantiene su aviso de tamaño de fragmentos, sin error de compilación.
- Inspección en navegador de la vista React con un fixture genérico: sin marcador
  parcial ni SQL a primera vista; fuentes accesibles y segundo desplegable con
  valores originales y operación. En esta integración se revisa además el HTML
  sintético a 1280 y 390 píxeles: leyendas completas sin solapamiento, sin
  desbordamiento global ni errores de consola. El gráfico exportado conserva
  su ancho mínimo y desplazamiento dentro de su contenedor en móvil.
  Comprobada extracción del PDF, etiquetas completas y el orden de
  conclusiones/límites antes del anexo.

Los tests integrados usan PostgreSQL, almacenamiento, temporales y VM Docker propios.
Se reutilizan dependencias y una imagen inmutable verificada; los modelos son
simulados. No se usan datasets, informes ni oráculos de los ensayos. La vista de
prueba no se incorpora al producto como informe real.

## Límite de lo demostrado

Se comprueba el comportamiento de presentación y que las instrucciones llegan a
los roles correctos. No se ha demostrado todavía que un modelo escriba mejor: el
motivo de una comparación, las etiquetas en prosa y la eliminación de cautelas
semánticamente repetidas requieren la nueva redacción y revisión. No se maquillan
informes antiguos mediante sustituciones arbitrarias de texto. Pendiente medir P3
con el lanzador y lectores a ciegas, conservando exactitud, incertidumbre y utilidad.

## Adaptación a la base con recuperación

Se conservan las correcciones de `af64f48` y la recuperación optativa de `5d3087c`.
La revisión congela P3 de forma independiente; se prueba también la recepción de
evidencia de una investigación parcial recuperada, sin alterar la marca de
parcialidad ni el requisito de revisión. El formato de auditoría de investigación
sigue conservando la respuesta `{decision: ...}`.

En las exportaciones P3, las leyendas de líneas usan nombres completos, una entrada
por fila y ajuste por ancho medido, con una muestra del color y trazo. Evita cortar
por un prefijo común y confundir series distintas; el control conserva su render.
HTML añade un nombre accesible al gráfico. Los fixtures tienen nombres genéricos
largos, series sintéticas y magnitudes pequeñas; no reutilizan señales de negocios.
