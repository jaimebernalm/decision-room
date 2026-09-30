# 3.8.9 — Correcciones tras la auditoría de observabilidad

## Alcance

Seguimiento de `2026-09-28-live-investigation-audit.md`. Se corrigen los defectos
observados en Bruma Café (datos ficticios), sin aprobar resultados antiguos ni
borrar las generaciones anteriores.

## Cambios

- Antes de congelar el contexto de un informe web se procesan las fuentes de
  memoria pendientes. Se vuelve a comprobar su estado bajo el bloqueo del negocio
  al crear el manifiesto. Una extracción fallida o incierta requiere recuperación
  explícita; no se oculta ni se interpreta como memoria vacía.
- Una modificación real posterior sigue invalidando los análisis afectados. Se
  registra `context.invalidated`; la vista pública explica el cambio y enlaza a
  la recuperación. El informe anterior conserva su historial y restricciones.
- El chat publica hitos de preparación y revisión. Un proceso terminado sin
  actividad disponible no promete que aparecerán comprobaciones futuras.
- Migración 26: finalización real de `chat_calls` y `chat_answer_reviews`. Las
  llamadas históricas sin ese dato permanecen sin hora de fin; no se inventan
  duraciones al reconstruirlas.
- Los agentes producen un `activity_label` breve en el contrato existente. Las
  ramas y sus cálculos usan esos títulos; el historial antiguo tiene un nombre
  neutral. Las consultas distinguen enfoque inicial, prioridades y entrega.
  No se vuelcan las preguntas técnicas ni conclusiones provisionales en el título.
- El monitor presenta el intercambio explícito del analista con el planificador,
  su justificación y siguientes pasos, encargo, resultados, evidencia, código y
  uso. El JSON técnico se abre opcionalmente. Se mantiene la selección por evento
  exacto y la autorización independiente. No expone pensamiento privado del modelo.
- En pantalla estrecha, seleccionar un evento lleva al detalle. En escritorio,
  cronología y detalle tienen columnas y desplazamiento independientes.
- El historial público separa las tareas y descendientes de versiones sustituidas.
- Una vista que falla al cargar muestra recuperación mediante recarga. Comprobado
  también con una pestaña real que conservaba un chunk de la versión anterior.

## Incidencias encontradas en la repetición real

1. El nuevo campo opcional heredado por `Followup` necesitaba incluirse en el
   esquema estricto del proveedor. Se corrigieron planificación e investigación
   y se añadió una comprobación del contrato transmitido.
2. Un subanalista generó una clave de métrica con un error de escritura. El
   validador rechazó correctamente el candidato, pero su corrección no bastó.
   El esquema ahora limita `metric_keys` a claves de las últimas ejecuciones
   completadas; la validación por investigación permanece. Los mensajes de
   corrección identifican las claves inexistentes. No se modificaron cifras ni
   respuestas guardadas para hacer pasar la revisión.

## Validación automatizada

- 117 pruebas de actividad, captura integrada, autorización/monitor, chat y web:
  pasan con PostgreSQL y sandbox reales.
- 74 pruebas adicionales de onboarding conversacional, memoria, contexto y
  contratos: pasan.
- 28 pruebas de contrato del proveedor, acciones y rondas de investigación:
  pasan tras la corrección de referencias de métricas. Hay solapamiento con el
  conjunto anterior; no sumar estos conjuntos como pruebas únicas.
- 97 pruebas UI: pasan. TypeScript y build de producción: pasan. Lint sin
  errores; conserva avisos preexistentes de componentes compartidos. El build
  conserva el aviso preexistente de tamaño de algunos chunks.
- 7 pruebas finales del monitor tras añadir las etiquetas de los actores: pasan.
- Nuevas regresiones: perfil aplicado antes del manifiesto, corrección posterior
  que sí invalida, memoria incierta que bloquea sin perder archivos, tiempos del
  chat y reconstrucción idempotente sin inventarlos, hitos de chat, explicación de
  contexto anterior, intercambio estructurado, JSON opcional, recuperación de
  vista y separación de versiones anteriores.

## Demostración real

Se reintenta el mismo trabajo de Bruma mediante la API normal de recuperación en
la preview aislada. Se mantiene la traza y se crea una sesión sucesora. Las dos
interrupciones anteriores quedan documentadas en esa traza; no se limpia su
historial para presentar una ejecución artificialmente perfecta.

Los registros detallados y datos generados permanecen en `.local/evaluation/live-38/`
(ignorados por Git). La preview original no se migró ni se reinició.

Resultado final: `completed`, `publishable=true`, sin motivo de contexto obsoleto,
9 memorias en el manifiesto inicial de la sesión sucesora y ninguna fuente de
memoria pendiente. `history_complete=true`. El informe se sirve con HTTP 200
(44.024 bytes de HTML). Se volvió a comprobar tras reiniciar únicamente la preview
para cargar la última presentación de etiquetas de actores.

Se verificaron en navegador:

- La conversación real que antes mostraba un proceso vacío ahora muestra
  «Respuesta preparada» y «Respuesta revisada».
- Durante la investigación se vieron tareas concretas, cálculo, redacción y
  revisión; al aprobarse, la vista pasó al informe revisado con «Ver proceso».
- «Ver datos» abrió las filas relacionadas en un panel sin abandonar el proceso.
- El monitor permite leer intercambios de la generación anterior y de la
  sucesora, con explicación y siguientes pasos, y mantiene las siete ramas de
  ambas generaciones. Las etiquetas no desaparecen al paginar eventos.
- Distribución de dos columnas a 1.440 px; a 390 px, anchura del documento y
  viewport coinciden (sin desbordamiento horizontal). Se restauró el tamaño.
- La pestaña que tenía un chunk antiguo mostró la pantalla de recuperación y
  volvió a la plataforma mediante su botón de recarga.

Una llamada de chat nueva con el modelo real terminó correctamente: preparación
1,259 s y revisión 0,655 s, ambas con fin posterior al inicio. Las llamadas antiguas
sin hora registrada mantienen ese dato desconocido.

El revisor pidió varias correcciones antes de aprobar. La recuperación está
comprobada; no se presenta esta ejecución como libre de errores ni como prueba
comparativa de calidad o eficiencia analítica. Esa evaluación queda separada de
las correcciones de observabilidad.
