# Importación local de CSV

La primera pieza del MVP recibe varios CSV como un único análisis de un negocio.
Conserva los originales, prepara un Parquet por CSV y guarda el catálogo en
PostgreSQL. No interpreta todavía el negocio, descubre relaciones, ejecuta código
generado por IA ni produce un informe comercial.

## Qué se guarda

| Lugar | Contenido |
|---|---|
| PostgreSQL: `businesses` | Nombre y descripción del negocio |
| PostgreSQL: `analyses` | Lote, negocio, título, fechas y estado |
| PostgreSQL: `sources` | Archivos, nombres originales, huellas SHA-256, tamaños, referencias, configuración de preparación e incidencias |
| PostgreSQL: `prepared_tables` | Referencia al Parquet, filas, columnas, perfil básico, procedencia y versión del lector |
| Almacenamiento privado | Copias originales y tablas Parquet |

`schema_versions` es una tabla técnica de migraciones. Las filas de ventas,
productos o inventario no se copian a tablas de PostgreSQL. El perfil conserva
solo cinco filas de muestra, con textos limitados a 200 caracteres por celda;
el Parquet conserva los valores completos. Una muestra no es el conjunto analítico.

Por defecto, los datos de PostgreSQL están en `.local/postgres/` y los archivos
en `.local/storage/`. Ambas rutas quedan fuera de Git. Las referencias de archivos
son relativas al almacenamiento y están separadas por identificador de negocio.
La ubicación puede cambiar con `DECISION_ROOM_STORAGE`; la conexión, con
`DECISION_ROOM_DATABASE_URL`. No se copia automáticamente el almacenamiento al
cambiar esa variable: debe conservarse o migrarse el contenido referenciado.

## Arranque

Desde la raíz del repositorio:

```sh
.venv/bin/python -m pip install -r requirements.txt
.venv/bin/python scripts/dev/local_postgres.py start
.venv/bin/python -m decision_room init
```

En este Mac se usan los binarios oficiales de Postgres.app 2.9.6, PostgreSQL 18.6,
descargados en `.tools/postgres/`. Su SHA-256 se comprobó frente al publicado en
la release; la procedencia está en `.tools/postgres/provenance.json`.
No se instaló una aplicación global, servicio de inicio ni modificación de PATH.
Homebrew quedó disponible después de que el usuario resolviera la licencia de Xcode.

En una instalación nueva de macOS se puede ejecutar
`.venv/bin/python scripts/dev/install_local_postgres.py`, o establecer
`DECISION_ROOM_PG_BIN` con la carpeta de binarios de PostgreSQL ya instalada.
Para otro servidor, configurar `DECISION_ROOM_DATABASE_URL` y ejecutar `init`.

El servidor local usa un socket Unix privado, autenticación `peer` con el usuario
del sistema y ninguna escucha TCP. Es una herramienta local de desarrollo: no
hay todavía cuentas web ni autorización de usuarios del producto. La separación
de negocios se comprueba en el servicio, en las referencias a archivos y mediante
claves foráneas compuestas; no se presenta como un despliegue multiusuario listo
para datos de clientes. El usuario local de desarrollo administra esta base.

Para gestionar el servidor:

```sh
.venv/bin/python scripts/dev/local_postgres.py status
.venv/bin/python scripts/dev/local_postgres.py stop
.venv/bin/python scripts/dev/local_postgres.py restart
```

## Uso

Crear un negocio devuelve su identificador:

```sh
.venv/bin/python -m decision_room create-business --name 'Mi tienda' --description 'Papelería y regalos'
.venv/bin/python -m decision_room businesses
```

Los siguientes comandos usan los identificadores reales de la prueba WWI:

```sh
.venv/bin/python -m decision_room import --business 3fdd7db1-26d5-453d-829e-70b34acb6452 --title 'Wide World Importers' --directory data/wide-world-importers/exports/csv
.venv/bin/python -m decision_room analyses --business 3fdd7db1-26d5-453d-829e-70b34acb6452
.venv/bin/python -m decision_room show --business 3fdd7db1-26d5-453d-829e-70b34acb6452 --analysis d708470f-35dc-4f9b-a79c-c1a279ba803b
.venv/bin/python -m decision_room show --business 3fdd7db1-26d5-453d-829e-70b34acb6452 --analysis d708470f-35dc-4f9b-a79c-c1a279ba803b --details
.venv/bin/python -m decision_room resume --business 3fdd7db1-26d5-453d-829e-70b34acb6452 --analysis d708470f-35dc-4f9b-a79c-c1a279ba803b
```

Se puede sustituir `--directory` por una lista de rutas CSV. La selección de
carpeta incluye los CSV de ese nivel, sin recorrer subcarpetas. En una base nueva
hay que usar los identificadores que devuelvan sus propios comandos.

La salida final es JSON; el progreso va a stderr, por lo que se puede guardar el
JSON con una redirección. Código de salida 0: preparación completa; 2: lote
parcial o fallido; 1: error de configuración o solicitud.

## Lectura y fidelidad

- CSV UTF-8, con o sin BOM, y una fila de encabezados.
- Detección inicial de coma, punto y coma, tabulador o barra vertical. `--delimiter`
  permite fijar `,`, `;`, `|` o `tab` cuando la detección no es adecuada.
- Columnas originales almacenadas como texto en Parquet. Esto conserva ceros
  iniciales, escala decimal y precisión de fechas. Los indicios de tipo se calculan
  sobre una muestra y no confirman el significado de una columna.
- Los importes y fechas deberán convertirse explícitamente al consultar, después
  de validar su significado y formato. Esta versión no normaliza monedas ni fechas.
- Campos vacíos sin comillas se representan como NULL; `""` conserva texto vacío.
  Es la convención registrada de este lector, no una deducción del significado
  comercial de un vacío. Nunca se reemplazan por cero.
- Encabezados vacíos o repetidos se rechazan sin renombrarlos silenciosamente.
- Filas mal formadas y codificación no admitida producen una incidencia visible.
- Tablas sin filas, negativos, duplicados y cadenas con saltos de línea se conservan.
- Cada fila preparada lleva una columna interna con el número de registro lógico
  del CSV, empezando en 1 y excluyendo la cabecera y separadores en blanco. No es
  necesariamente el número de línea física: una celda puede contener saltos de línea.
- Los datos originales se copian sin modificar y se protegen contra escritura.
  El archivo se prepara primero en una ruta temporal y se publica de forma atómica.

Los límites iniciales están en `Config`: 100 archivos por lote, 2 GiB por archivo,
8 GiB por lote, 256 columnas y 10 millones de filas por archivo. DuckDB tiene
512 MB de memoria configurada, búfer CSV de 64 MiB y hasta 2 GB de espacio temporal.
Son límites iniciales de desarrollo, no capacidades certificadas ni un aislamiento
de seguridad para Python generado. La implementación de ese entorno es el paso siguiente.

## Reenvío, versiones y recuperación

La identidad de un lote usa negocio, conjunto de huellas de contenido y versión/
configuración del preparador. Reenviar exactamente el mismo lote, incluso en otro
orden, recupera el mismo análisis. Archivos idénticos dentro del lote se identifican
explícitamente en `duplicate_inputs`; sus nombres quedan como alias, sin sumar las
filas dos veces. Cambiar un título al reenviar no renombra la revisión guardada.

Si cambia el contenido de un archivo se crea otro lote/análisis y se conserva el
anterior. Si dos análisis comparten un archivo idéntico, `also_in_analyses` lo señala.
No se detecta todavía el solapamiento semántico entre archivos de distinto contenido:
resúmenes y detalle, archivos parcialmente solapados o distintas versiones no se
combinan ni se deduplican por sus filas. Tampoco se unen automáticamente tablas
actuales e históricas. Pertenecer al mismo negocio no demuestra una relación de unión.

Cada fuente puede estar `staged`, `ready` o `failed`. El lote puede estar
`importing`, `ready`, `partial` o `failed`. Aquí `ready` significa que los archivos
están preparados, no que haya un informe analítico terminado.

`resume` utiliza las copias guardadas; no requiere los archivos de subida iniciales.
Conserva las tablas correctas, comprueba huellas y reintenta las pendientes. Puede
reconstruir un Parquet perdido o alterado a partir del original verificado. Un
original alterado se marca como fallo. Un bloqueo de PostgreSQL evita dos
preparadores simultáneos sobre el mismo análisis. Los archivos copiados antes de
un fallo de registro pueden quedar sin referencia; la limpieza y retención se
implementarán antes del piloto, sin borrar automáticamente originales ahora.

## Comprobaciones

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/checks/verify_wwi_ingestion.py --business 3fdd7db1-26d5-453d-829e-70b34acb6452 --analysis d708470f-35dc-4f9b-a79c-c1a279ba803b
```

Las pruebas de integración crean y eliminan una base de datos temporal propia;
necesitan un usuario de desarrollo con permiso `CREATEDB`. No borran el negocio WWI.
El verificador WWI conoce las respuestas originales para comparar todas las celdas
y una unión conocida. Esa información de referencia no se utiliza en el importador.

Resultados de la primera prueba: [verificación del lote WWI](../validation/2026-09-21-ingestion-check.md).

Documentación técnica utilizada: [CSV en DuckDB](https://duckdb.org/docs/stable/data/csv/overview),
[PostgreSQL initdb](https://www.postgresql.org/docs/18/app-initdb.html),
[herramientas de Postgres.app](https://postgresapp.com/documentation/cli-tools.html).
