# Plan M: fiabilidad del proveedor

M1 se implementa por cambios locales y con proveedores simulados, sin llamadas a la API.

## Política del ledger

La política opcional `scope_uncertainty` se fija al crear un ledger nuevo. Conserva
los topes y reserva por envío el sobre máximo del modelo: 1.050.000 tokens de
entrada y 128.000 de salida, 0,3585 USD de catálogo. La primera llamada sin uso
conocido conserva su reserva y detiene su ámbito; la segunda detiene el ledger
entero. Las liquidaciones repetidas no cuentan dos veces. Modelo o nivel de
servicio distinto y uso fuera de rango detienen globalmente a la primera.

La política de rechazos HTTP explícitos sigue siendo una opción separada. No se
reabre ningún ledger detenido ni se modifica la política de un ledger anterior.
El snapshot conserva `uncertain` como indicador agregado y añade ámbitos
inciertos, ámbitos detenidos e incertidumbre global; `scope_state` permite que
los consumidores comprueben exclusivamente su ámbito en la política nueva.
La recuperación de reservas huérfanas requiere haber detenido su controlador;
las cobra como inciertas sin reenviar ni liberar su coste.

Validación inicial: 21 pruebas de `test_api_budget` con SQLite y PostgreSQL
locales y transporte simulado. Incluye primera y segunda incertidumbre,
reapertura del archivo, callback repetido, dos liquidaciones concurrentes,
rechazo HTTP, recuperación, topes y las pruebas de la política anterior.

## Motor y ejecutor

El motor comprueba el ámbito `engine:<run>` del ledger compartido antes de
operar. Antes de publicar también exige uso resuelto del propio ámbito, sin
confundir una llamada pendiente o incierta de otro intento con la propia. El
ledger P4 por ejecución conserva su política: solo contiene esa ejecución.
La recuperación del comprobador, tras detener su runtime, reconcilia las
reservas huérfanas tanto en P4 como en el ledger del lote.

El spec del ejecutor fija `scope_uncertainty` y `ledger_version`; reutilizar un
ledger exige que coincidan política, cuotas y topes. El resultado registra el
ámbito detenido, su incertidumbre y el motivo. No se continúa un intento detenido
ni se vuelve a enviar su pregunta. Otro intento puede operar tras la primera
incertidumbre, hasta la segunda. Los intentos y recibos anteriores se conservan.

El timeout de lectura inactiva pasa a 300 s, limitado por el tiempo restante del
run. Conexión y pool tienen un máximo de 10 s y escritura de 30 s, todos limitados
por ese mismo tiempo restante. La prueba simula `response.created` seguido de
ReadTimeout, comprueba los parámetros entregados a HTTPX y verifica las reservas
y la continuación de otro run. No espera 300 s ni acredita la latencia real del
proveedor.

## Investigación de recuperación por ID

La API tiene GET de Responses por ID, pero `store` controla su almacenamiento
para recuperarla después. El proxy del producto fuerza `store=false`. Por ello
no se incorpora polling ni se da por recuperable un flujo cortado; tampoco se
habilita almacenamiento de contenido para intentar recuperarlo. Esta conclusión
es una limitación de la ruta actual, no una prueba de una consulta real.

Fuentes oficiales consultadas el 11 de octubre de 2026:
[creación](https://developers.openai.com/api/reference/resources/responses/methods/create),
[recuperación](https://developers.openai.com/api/reference/resources/responses/methods/retrieve),
[almacenamiento](https://developers.openai.com/api/docs/guides/migrate-to-responses).

Validación de integración: 97 pruebas de ledger, techo P4, admisión, ciclo del
comprobador, ejecutor, jobs y lifecycle con PostgreSQL desechable y proveedores
simulados. No hubo gasto de API. La revisión pública del commit no incluye datos
privados, credenciales, rutas personales ni archivos de runtime.

## M2: comprobación de datos no monetarios

El prompt congelado del comprobador exige inspeccionar todos los CSV y sus
columnas antes de clasificar una cifra como no comprobable. Incluye recuentos,
estados, duraciones, puntuaciones, medias, tasas y agrupaciones por persona,
categoría y periodo. Pide ejecutar el recálculo independiente y documentar
población, nulos, numerador, denominador, filtros y ventanas. Conserva los límites
cuando falta una definición; no infiere unidades ni atribuye causalidad.

El esquema de salida `priority-check-1` no cambia. El nuevo hash del prompt se
congela en el perfil de los nuevos runs. Los resultados históricos no se
reinterpretan; una ejecución con otro prompt congelado no puede iniciar una
comprobación con este código.

64 pruebas de comprobador, contrato, bloques, recepción y brief pasan. La prueba
no monetaria proporciona al runtime simulado solo su CSV de observaciones,
estados y puntuaciones: recalcula dos recuentos y una media y conserva la
discrepancia con la media afirmada, ligada a la cita de la revisión exacta.
Esto acredita transporte, aislamiento y contrato; no acredita que el modelo
real encuentre todas las cifras ni que sus cálculos sean correctos. Esa
comprobación de calidad sigue pendiente de los ensayos.
