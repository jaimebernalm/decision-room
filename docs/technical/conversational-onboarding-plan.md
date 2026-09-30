# Paso 3.4 — Onboarding conversacional

Estado: implementado y validado el 27 de septiembre de 2026.

[Evidencia y límites](../validation/2026-09-27-conversational-onboarding.md).

## Decisiones de producto

Conversación guiada con tarjetas y progreso. Recorrido corto y adaptable; contexto
opcional omitible. El mismo chat continúa después del primer informe. Confirmación
explícita del alcance antes de ejecutar. Los analistas paralelos pertenecen a 3.5;
la evaluación comparativa amplia pertenece a 3.6.

## Base revisada

La base es `feature/insights-pipeline`, incluidos 3.3 y 3.3.1. El onboarding React
anterior utilizaba formularios y crea un trabajo desde un lote preparado. El chat ya
persiste mensajes, revisa respuestas, consulta memoria/catálogo y delega cálculos.
Las vistas de datos dependían de un trabajo; ahora pueden abrirse también
antes de crear el informe. La memoria captura una pregunta explícita; las preguntas
naturales de respuestas nuevas necesitan conservar esa relación estructuralmente.

## Implementación

1. Persistir una sesión por negocio con conversación, etapa, revisión, objetivo
   original/opciones, conjunto de datos, propuesta y encargo confirmado. Mutaciones
   idempotentes, control de concurrencia, autorización por negocio y recuperación.
2. Reutilizar el asistente/revisor del chat con instrucciones adicionales de
   onboarding y salida estructurada para pregunta y propuesta. El servidor controla
   etapas y autorización de análisis. Guardar pregunta/respuesta/omisión con contexto.
3. Integrar objetivos combinables y texto libre, archivos, preguntas contextualizadas
   y alcance editable en el mismo recorrido. Reutilizar componentes de chat y subida.
4. Confirmar un encargo versionado, crear un único trabajo asociado al chat y conservar
   informe/aclaraciones/historial al pasar a la plataforma. No alterar trabajos antiguos.
5. Verificar persistencia, cambios de objetivo, dos negocios, omisiones, datos visibles,
   reenvíos/interrupciones, errores y entrega completa/parcial. Ejecutar pruebas de
   regresión, recorrido real con modelo y comprobación visual escritorio/móvil.

## Criterios de aceptación

- No repetir información ya aportada ni exigir contexto opcional para avanzar.
- Una pregunta sobre datos abre la tabla/columna correcta, incluso antes del informe.
- Objetivo libre y opciones persistentes; propuesta basada en archivos inspeccionados.
- Editar o cambiar fuentes invalida la propuesta anterior; confirmar captura el encargo.
- Ningún mensaje o decisión del modelo inicia el primer análisis sin confirmación.
- Recargar o reenviar no duplica chats ni informes; aislamiento entre negocios.
- Informe revisado y conversación continúan con evidencia y límites visibles.
- Documentar resultados observados y límites; no contar pruebas simuladas como calidad
  del modelo ni marcar completado sin evidencia del recorrido integrado.


## Contrato implementado

- Migración 21: `onboarding_sessions` y `onboarding_events`, una sesión por negocio,
  revisiones optimistas y claves idempotentes con comparación del contenido.
- API autenticada `/api/onboarding/start`, `/session`, `/change` y `/data`.
  El negocio activo se fija por petición y se comprueba al escribir.
- Etapas `goal → data → scope → report → complete`; cambiar objetivo o archivos y
  responder a una pregunta invalidan la propuesta anterior. El encargo confirmado
  incluye el objetivo original, opciones, propuesta revisada, fuentes, aclaraciones
  y snapshot de procedencia. No se reemplaza por un resumen sin el original.
- El primer turno reutiliza la fuente de memoria del perfil, procesándola antes de
  tomar contexto. Las opciones del objetivo son un encargo de este informe, no
  prioridades permanentes del negocio extraídas automáticamente.
- `conversation-v12` añade instrucciones de etapa al mismo asistente y revisa su
  pregunta/propuesta como contenido visible. Máximo tres preguntas opcionales;
  definiciones esenciales pueden reducir el alcance cuando no se conocen.
- El catálogo y sus herramientas existentes permiten inspeccionar y consultar los
  datos. Las referencias de tabla/columna deben pertenecer a una inspección del
  turno y estar autorizadas para la ejecución actual.
- `Crear mi informe` crea trabajo y turno asociado en una transacción. La propuesta
  debe seguir vigente. El informe utiliza el planificador, analista y revisor ya
  existentes; sus preguntas y resultados aparecen en la misma conversación.
- La entrega inicial muestra un resumen breve con evidencia expandible y enlace
  al informe. `Continuar en mi espacio` conserva chat, objetivo e historial y
  finaliza el modo onboarding. El encargo sigue disponible como fuente posterior.
- Borradores locales, subida por bloques, aceptación de importaciones parciales,
  recuperación explícita y mensajes diferenciados para errores/cambios de contexto.
  Tras recargar durante una subida, el navegador debe volver a seleccionar los
  archivos locales; se conservan sus nombres y el identificador de subida.
- Las rutas de trabajos del onboarding anterior permanecen disponibles; los chats
  y negocios existentes no se incorporan automáticamente al nuevo recorrido.


### Corrección tras la prueba manual: pregunta histórica y revisión

El revisor recibe `draft` y `proposed_guide` como única salida candidata. La
pregunta que motivó la respuesta del propietario se presenta por separado como
`previous_question_context`; no se vuelve a presentar como una pregunta activa
ni dentro de la cita `owner_message`. El turno original mantiene íntegra su
procedencia. `answered` describe el envío de texto libre, no una confirmación
semántica: «no lo sé» sigue expresando incertidumbre.

Una nueva pregunta repetida sigue sujeta a rechazo. Las preguntas del alcance son
objetivos del informe, no solicitudes adicionales de respuesta al propietario.
Si se agotan las revisiones, el aviso identifica ese límite y permite reintentar;
no se presenta como una petición incierta al proveedor.
