# Paso 1.4: plan de implementación

El agente principal del MVP interpreta los datos y propone investigaciones. Este
paso termina con un plan provisional, no con cálculos ni un informe. La ejecución
de Python corresponde al paso 1.5 y la revisión al 1.6.

1. Definir un contrato de interpretación, procedencia, investigaciones y preguntas
   materiales. Diferenciar observado, inferido, confirmado y pendiente.
2. Mostrar al modelo el catálogo del lote y permitirle seleccionar perfiles y
   muestras acotadas. Los archivos de evaluación nunca entran en su contexto.
3. Conectar un modelo mediante una interfaz intercambiable. Empezar con LM Studio
   en localhost; conservar modelo y parámetros por sesión. El cliente del modelo
   corre en la aplicación, fuera del contenedor de Python sin red.
4. Construir un grafo LangGraph con inspección, propuesta, pausa y actualización
   tras las respuestas. Guardar checkpoints en PostgreSQL, junto con sesiones,
   revisiones, preguntas, respuestas y llamadas. Recuperar desde otro proceso.
5. Exponer comandos de terminal con ámbito de empresa, claves de idempotencia y
   límites. La aplicación valida referencias y bloquea investigaciones dependientes
   de respuestas ausentes o desconocidas. Las propuestas del modelo no son hechos
   verificados automáticamente.
6. Probar persistencia y fallos con un modelo simulado; comprobar por separado el
   comportamiento del modelo real con los casos de referencia y el catálogo WWI.

La API de LM Studio permite desarrollar sin contratar un proveedor. Un piloto
puede usar una API externa o un modelo alojado en nuestros servidores. Cada cambio
de modelo requiere repetir la evaluación; compatibilidad HTTP no garantiza igual
calidad. No se incluye despliegue público ni autenticación web en este paso.

No se hará commit de este trabajo, siguiendo la instrucción de esta entrega.
