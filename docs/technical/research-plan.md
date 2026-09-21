# Paso 1.5: investigación con Python generado

## Decisión y alcance

Se avanza con el agente principal y Qwen local para evaluar el recorrido completo,
manteniendo el fallo de interpretación de `amount` abierto. El revisor y el informe
pertenecen al paso 1.6. Ningún resultado de este paso se publica como verificado.

1. Añadir una fase LangGraph de investigación vinculada a una revisión del plan.
   El mismo agente elige qué investigación abordar, genera código y recibe las
   salidas o errores; no se añade un segundo agente.
2. Exponer únicamente el ejecutor aislado existente. Los alias de tablas y sus
   permisos los controla la aplicación; el modelo no decide rutas del anfitrión,
   imágenes Docker, conexiones, credenciales ni parámetros de aislamiento.
3. Permitir ejecutar, corregir, registrar un candidato, marcar trabajo bloqueado
   y terminar. Separar salida válida del programa, valoración del propio agente
   y revisión independiente futura. Guardar los intentos aunque fallen.
4. Persistir cada acción antes de ejecutarla, enlazarla con código, entorno,
   entradas, métricas y evidencia. Reanudar con checkpoints y claves idempotentes
   sin volver a ejecutar una operación ya completada.
5. Fijar presupuestos pequeños: investigaciones seleccionadas, intentos Python,
   llamadas al modelo, tiempo por ejecución y tamaño del contexto. Mantener los
   resultados completos fuera del prompt y enviar observaciones acotadas.
6. Permitir replantear el análisis con contexto corregido: nueva sesión vinculada
   a la anterior y resultados anteriores marcados como obsoletos. Conservar el
   historial; no reutilizar resultados calculados con definiciones sustituidas.
7. Probar con PostgreSQL y Docker reales: corrección de un error, referencias,
   aislamiento, recuperación, cambios de contexto y límites. Después hacer
   investigaciones pequeñas con el modelo real y contrastar los resultados
   independientemente, sin editar el código que genere.

La compactación automática para investigaciones largas se mantiene pendiente.
Esta entrega acota las investigaciones y carga observaciones limitadas. Un límite
alcanzado se registra; no se presenta como una investigación completa.

Referencias: [persistencia LangGraph](https://docs.langchain.com/oss/python/langgraph/persistence)
y [sandbox existente](sandbox.md).
