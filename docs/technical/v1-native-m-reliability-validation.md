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
