# Límite de enums del esquema de investigación

Base: `f60278d`. Corrección de transporte independiente de P3, sin cambios en
preguntas, cálculos, validadores de evidencia o presupuestos de investigación.

1. En continuidad, `metric_keys` está prohibido para nuevas acciones (`maxItems: 0`).
   No copiar el enum global en cada rama: no restringe ninguna respuesta válida.
2. Tras inyectar memoria y adaptar el esquema para OpenAI, contar los valores de
   **todas las apariciones** de enums, también en `$defs` y `anyOf`. No deduplicar
   valores iguales ni expandir `$ref`.
3. Si se excede el límite, representar los enums de texto mayores con patrones de
   alternativas literales escapadas. Preservan exactamente las claves permitidas
   y las demás restricciones del campo, incluidos longitud y ejecución padre.
   Se agrupan por longitud exacta para rechazar también un salto de línea añadido,
   sin usar lookahead ni otras extensiones de regex. Los esquemas
   pequeños no cambian por esta adaptación; no se truncan listas de claves.
4. Un guardián local impide enviar cualquier esquema que aún exceda 1.000 valores,
   o el límite de 15.000 caracteres de un enum de texto con más de 250 valores.
   El fallo local es explícito y anterior a credenciales, HTTP y consumo de API.
   La auditoría de peticiones conserva el esquema efectivo adaptado.

Se elige una representación equivalente en vez de `string` sin restricción:
no introducir respuestas permitidas por el esquema que el validador rechazaría
por una clave desconocida. Las reglas de referencias siguen siendo por ejecución
y candidato, y los controles existentes de continuidad y ampliación se conservan.

Validación: 71 tests sin red. Incluyen todos los productores de esquemas, contexto
con memoria, 1.200 métricas en 15 ejecuciones, un conjunto de más de 1.000 claves,
paridad de claves válidas/inventadas/cruzadas, caracteres especiales, límites
1.000/1.001, detención previa a HTTP y contratos de continuidad existentes.
No se ha probado la compilación del patrón por el proveedor con una llamada real;
la medición del lanzador confirmará ese extremo. Se usa el `pattern` documentado
por [OpenAI Structured Outputs](https://developers.openai.com/api/docs/guides/structured-outputs).
