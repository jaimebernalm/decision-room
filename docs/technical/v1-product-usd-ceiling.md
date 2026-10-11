# Techo durable por informe v1

Estado: variante de producto `html-v1-budget-1`, preparada aparte del ensayo F5b.
Legacy sigue por defecto. No habilita la adopción ni modifica sus materiales,
resultados o límites congelados.

## Contrato

Los trabajos opencode nuevos de las tres vías de creación y del chat congelan
`usd_ceiling` en `engine_config.profile`. `DECISION_ROOM_ENGINE_USD_CAP` define el
techo en USD (1,00 por defecto; precisión máxima de seis decimales). Se rechazan
modelos sin tarifa fijada y techos que no permiten reservar una llamada completa.
El perfil opt-in de preguntas usa `html-v1-questions-budget-1` con el mismo techo.
Los límites de tokens, llamadas y tiempo siguen aplicándose por separado.

Al crear el run, bajo los locks de memoria y clave de petición, se crea una sola
vez un ledger privado exclusivo por negocio y UUID de run. Se publica antes del
run en PostgreSQL; un fallo de la transacción puede dejar un ledger huérfano,
que no autoriza llamadas y no se reutiliza. Una repetición de la misma petición
devuelve el run original. Ni un worker, una reanudación, un cambio de entorno ni
la pérdida del archivo recrean su saldo. Un archivo ausente, un symlink o una
política distinta impiden enviar, incluso para contar la entrada.

La pasarela envuelve la frontera real de envío con `agent.api_budget`. Cada
generación reserva **1.050.000 tokens de entrada y 128.000 de salida**, los
máximos publicados del modelo, a las tarifas Standard máximas del catálogo
congelado: 0,25 y 0,75 USD/millón. La reserva es **0,3585 USD**. No depende de la
cuenta previa de entrada ni del límite de salida solicitado, que puede ser menor.
`BEGIN IMMEDIATE` suma todas las reservas y cargos antes de permitir el envío:
dos workers o varias llamadas en vuelo no pueden gastar el mismo saldo libre.

Con uso completo válido se sustituye la reserva por una cota conservadora del
uso (entrada valorada como escritura de caché). Si el uso excede los límites de
admisión, el motor aborta; el ledger ya reservó los máximos del modelo. Ante una
respuesta incompleta, uso desconocido o modelo/tier inesperado, conserva toda
la reserva y detiene nuevos envíos. Una caída deja la reserva pendiente. El
controlador conserva su política de incertidumbre y no reenvía automáticamente.
Los rechazos HTTP usan la política conservadora original para este perfil;
no se introduce el tratamiento de reintentos del ledger de F5b.

Por tanto, la suma de cargos confirmados y reservas pendientes no supera el techo
**bajo el modelo, máximos y tarifas congelados**. No es una factura ni una garantía
sobre cambios futuros de precios, recargos o incumplimientos de esos máximos por
el proveedor. La cota y las estimaciones de catálogo se exportan separadas. Si
falta el ledger, la cota es desconocida, nunca cero. Puede quedar saldo sin usar:
si no cabe la reserva máxima siguiente, se rechaza antes de enviar aunque la
llamada hubiera costado menos en la práctica.
Con un techo de 1,00 USD y sin llamadas pendientes, el envío siguiente solo se
admite si los cargos previos no superan 0,6415 USD. El cargo final puede superar
esa cifra al liquidar la última llamada; el techo total continúa siendo 1,00 USD.

Las preguntas al dueño no reinician el saldo. Los días esperando no consumen el
contador de tiempo del ledger; el límite de tiempo activo del motor permanece
autoritativo. Si además existe el ledger compartido del ensayo, ambas reservas
se realizan antes del mismo envío y ambas registran su uso.

Los perfiles históricos y el bootstrap directo explícito conservan su contrato
anterior, sin añadirles un techo que nunca fue registrado. Se exportan como
`not_configured`. Esto incluye los runs y materiales congelados de F5/F5b. El
techo nuevo se exige en la selección de trabajos nuevos del producto, sin
relanzar ni actualizar trabajos existentes.

## Validación

Proveedores falsos y PostgreSQL real, sin gasto de API:

- Cuenta de entrada de un token seguida de uso de los máximos del modelo:
  la reserva completa precede al envío y el motor aborta por exceso de su cuota.
- Dos envíos concurrentes bajo un techo que solo admite uno: uno se envía y el
  otro se rechaza antes de tocar el proveedor.
- Reserva pendiente tras caída y repetición de la creación: mismo run, mismo
  cargo, sin nueva concesión; exportación explícita de la incertidumbre.
- Ledger ausente, corrupto o sustituido por otra política: ningún envío ni recreación;
  exportación con cota desconocida.
- Ledger del run y ledger del ensayo: un único envío, cargo coherente en ambos.
- Espera de ocho días y otro run: saldo original conservado y saldo independiente.
- Cap congelado en creación, relectura con entorno distinto, techos imposibles,
  valores no finitos o precisión excesiva rechazados.
- SIGKILL real del proceso durante un envío a un proveedor falso: la reserva
  ya está confirmada antes del envío y sobrevive íntegra al proceso muerto.

La pasada focal comprende 100 pruebas (presupuesto, trabajos, admisión, preguntas,
espera web, ejecutor, verificador y recepción HTML), todas correctas. Después de
añadir el caso SIGKILL se repiten 29 pruebas de techo, recepción y ledger, todas
correctas. La regresión completa nativa ejecuta 838 pruebas Python en PostgreSQL
y Docker: todas correctas, sin omitidas (734,077 s). Esta pasada arrancó antes de
añadir el campo de exportación, endurecer el parseo decimal y la lectura de un
ledger corrupto, y añadir el caso SIGKILL; las pasadas focales anteriores se
ejecutan después de esos cambios. No se presenta como una pasada completa sobre
el árbol final.

Una nueva pasada completa sobre `10f3933`, que ya incluye todos esos cambios y
la corrección del mensaje final del chat, ejecuta **839 pruebas Python en
553,399 s**, todas correctas y sin omitidas, con PostgreSQL y Docker nativos.
Usa proveedores falsos y no consume API. Claude revisa el código del techo en
`840d74b` y reproduce las ocho pruebas de P4 y las del ledger en una copia limpia;
su revisión técnica es conforme. Esto no convierte el ensayo F5 incompleto en
una autorización de adopción: legacy sigue por defecto.

UI sin cambios: 313 pruebas correctas, TypeScript/Vite correctos y oxlint sin
errores (27 avisos existentes). Vite conserva el aviso de tamaño de chunks.
`git diff --check` correcto y revisión pública de archivos preparados para el
commit sin credenciales, rutas personales ni archivos generados grandes.
