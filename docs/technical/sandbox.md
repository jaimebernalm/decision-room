# Ejecución aislada de Python

El paso 1.3 del MVP está implementado. La función `decision_room.execution.execute`
recibe código Python, tablas preparadas, definiciones y una clave de petición.
Devuelve un estado, resultados candidatos y referencias a sus evidencias.
Todavía no hay agente LangGraph: el código de aceptación está escrito a mano.

## Dónde corre

En este Mac: **contenedor Linux → Docker → VM Colima dedicada `decision-room`**.
La VM dispone de 2 CPU, 3 GiB de RAM y un disco virtual de 20 GiB. Se instaló
Colima y el cliente Docker con Homebrew. No hace falta una cuenta de Docker,
servicio de pago o API externa. La VM no cambia el contexto Docker por defecto.

La `.venv` ejecuta el controlador y accede a PostgreSQL. El código recibido corre
solo dentro de un contenedor nuevo, que se elimina al terminar. La VM permanece
encendida hasta detenerla. Tras reiniciar el Mac, hay que arrancarla de nuevo.

```sh
.venv/bin/python scripts/dev/local_postgres.py start
.venv/bin/python scripts/dev/local_sandbox.py start
.venv/bin/python scripts/dev/local_sandbox.py status
.venv/bin/python -m decision_room init
```

Si se recrea el equipo: instalar `brew install colima docker`, preparar la `.venv`
según el README y construir la imagen después de arrancar la VM:

```sh
.venv/bin/python scripts/dev/local_sandbox.py build
```

La construcción necesita internet. Las ejecuciones no tienen red. La imagen
base se fija por digest, las dependencias directas y transitivas por versión,
y cada ejecución utiliza un ID de imagen inmutable, sin descargar otra imagen.
Se registran las versiones reales de Python y paquetes, arquitectura, hashes
de los archivos de construcción y del controlador. Para cambiar bibliotecas,
actualizar intencionalmente los dos archivos de dependencias y reconstruir.
La fijación de versiones no promete resultados numéricos idénticos entre CPU.

Bibliotecas incluidas: **Python 3.12.14, DuckDB 1.5.5, pandas 3.0.6,
PyArrow 25.0.1, NumPy 2.5.3, SciPy 1.18.1, matplotlib 3.11.2, openpyxl 3.1.5,
Seaborn 0.13.2, statsmodels 0.15.0 y scikit-learn 1.9.1**.
No se permite instalar paquetes durante un cálculo. Matplotlib utiliza `Agg`
para producir imágenes sin interfaz gráfica. La biblioteca estándar está disponible.

Seaborn, statsmodels y scikit-learn están preinstalados para gráficos, estadística
y modelos tabulares. Su disponibilidad no incorpora funciones de machine learning
al MVP ni modifica sus límites de ejecución. Se comprueban con un gráfico PNG,
una regresión estadística y un pipeline pequeño de escalado y regresión dentro
del mismo contenedor aislado.

## Uso

Primero, obtener los `table_id` del análisis con `show --details`. Se autorizan
tablas por identificador, no por rutas de archivos elegidas por el código.
Ejemplo ya disponible sobre las tablas de facturas de WWI:

```sh
.venv/bin/python -m decision_room run \
  --business 3fdd7db1-26d5-453d-829e-70b34acb6452 \
  --analysis d708470f-35dc-4f9b-a79c-c1a279ba803b \
  --table sales_invoicelines=a48f304d-dacd-4f54-a938-155bf03bd0ce \
  --table sales_invoices=9f882ebb-af6e-4ea2-ba07-48a5e7d97ad1 \
  --code examples/wwi_calculation.py \
  --request-key mi-calculo-wwi-001
```

`--definitions archivo.json` admite un objeto con definiciones acordadas, por
ejemplo importe con o sin impuestos. `--timeout` permite 1–120 segundos.
Repetir la clave con exactamente la misma petición recupera la ejecución.
Cambiar código, fuentes, definiciones, límites o entorno exige una clave nueva.
Una ejecución fallida o interrumpida tampoco se repite automáticamente.

El futuro agente podrá llamar a esta misma función de Python. La identidad
del negocio deberá proceder de la sesión autenticada del servidor. Estos UUID
y la CLI actual no constituyen autenticación ni permisos de usuarios finales.

## Contrato del código

La carpeta `/inputs` contiene `program.py`, `request.json` y únicamente las
copias Parquet seleccionadas. `dr_runtime` expone `TABLES`, `DEFINITIONS`,
`table_path(alias)`, `connect()` y `write_result(...)`.

```python
from dr_runtime import connect, write_result

query = 'SELECT count(*) FROM sales_invoices'
with connect() as db:
    count = db.execute(query).fetchone()[0]
write_result(
    {'invoice_count': count},
    evidence=[{'metric': 'invoice_count', 'tables': ['sales_invoices'],
               'operation': query}],
)
```

Los valores originales siguen siendo texto en los Parquet: convertir importes
explícitamente, preferentemente con DECIMAL para dinero, y declarar la operación,
uniones y filtros en la evidencia. La columna de procedencia indica el ordinal
del registro CSV; no siempre coincide con la línea física si hay texto multilínea.

`result.json` es obligatorio para completar un cálculo. Contiene `schema_version: 1`,
`metrics` (1–256 valores escalares), `evidence` (cada métrica con sus tablas y
operación) y `notes`. Las referencias opcionales `source_records` deben existir
en las tablas declaradas. Los importes pueden devolverse como cadenas decimales
para conservar precisión. Los nombres de alias usan letras minúsculas, números
y guion bajo, empiezan por letra y tienen como máximo 63 caracteres.

El controlador comprueba forma y referencias. **`completed` significa ejecución
finalizada; `verification: pending` significa que el análisis aún no está aprobado.**
La presencia de evidencia no demuestra que el cálculo o la interpretación sean
correctos. El supervisor interno comparte permisos con el código; toda su salida
se trata como no confiable. La contención de recursos reside en Docker y el host.

Además pueden escribirse artefactos `.csv`, `.json`, `.png` y `.parquet` directamente
en `/output`, sin subcarpetas. Se rechazan rutas relativas ascendentes, duplicados,
enlaces, tipos especiales y extensiones de código/HTML/pickle. Las firmas PNG y
Parquet son un filtro básico, no una garantía sobre todo su contenido. Se guardan
como bytes; no se ejecutan ni se abren automáticamente. Una futura interfaz deberá
escapar textos y ofrecer descargas seguras, especialmente CSV con fórmulas.

## Límites y separación

| Recurso | Límite inicial |
| --- | --- |
| Ejecuciones simultáneas | 1 por base de metadatos, con bloqueo PostgreSQL |
| CPU / memoria | 1 CPU / 768 MiB, sin swap adicional |
| Tiempo | 30 s por defecto, máximo 120 s; vigilancia externa con 10 s de margen |
| Procesos / descriptores | 64 / 128 |
| Tablas / entradas | 64 tablas / 512 MiB de Parquet copiados |
| Código / definiciones | 128 KiB / 64 KiB |
| `/tmp` / `/output` | tmpfs de 128 MiB / 32 MiB; cuentan también para la memoria |
| Archivos devueltos | 16, máximo 2 MiB cada uno y 4 MiB en conjunto |
| Logs / transporte total | 64 KiB por flujo en el supervisor / 6 MiB de protocolo |

El límite de tiempo se refiere a la computación; copias de entrada y operaciones
de control Docker añaden tiempo. Cada operación Docker tiene además un plazo de
20 segundos. Los fallos del motor pueden requerir recuperación posterior.

Usuario Linux 10001, capacidades eliminadas, `no-new-privileges`, seccomp estándar,
AppArmor del motor local y raíz de solo lectura. El único bind mount es la entrada
de esa ejecución, de solo lectura. No se monta PostgreSQL, el repositorio, el
directorio personal ni el socket Docker. El cliente Docker del controlador usa
configuración vacía propia para no inyectar proxies ni credenciales personales.
Los dispositivos virtuales del contenedor y `/dev/shm` (16 MiB) son privados;
las pruebas de memoria/procesos no equivalen a una auditoría del kernel.

## Qué se guarda y cómo recuperar

- `sandbox/`: Dockerfile, bibliotecas bloqueadas y ayudantes internos.
- `decision_room/execution.py`: autorización de tablas, snapshots, persistencia.
- `decision_room/docker_backend.py`: creación, límites, supervisión y eliminación.
- `decision_room/execution_contract.py`: validación externa de salidas.
- PostgreSQL: tablas nuevas `executions` y `execution_artifacts`, migración 2.
- `.local/storage/<negocio>/analyses/<análisis>/executions/<ejecución>/`:
  código exacto y artefactos privados. Metadatos, hashes, definiciones, logs y
  resultados candidatos quedan en PostgreSQL; las entradas conservan referencias
  a los Parquet privados existentes y sus hashes.
- `.local/sandbox-inputs/`: copias efímeras de entrada, borradas al acabar.
- `.local/sandbox-runtime.json`: ID de imagen y versiones de esta instalación.
- Colima guarda VM e imágenes en su perfil dentro de `~/.colima`.

Consultar ejecuciones:

```sh
.venv/bin/python -m decision_room executions \
  --business 3fdd7db1-26d5-453d-829e-70b34acb6452 \
  --analysis d708470f-35dc-4f9b-a79c-c1a279ba803b
.venv/bin/python -m decision_room show-execution \
  --business 3fdd7db1-26d5-453d-829e-70b34acb6452 --execution ID_DE_EJECUCION
```

Ctrl+C registra interrupción y limpia el contenedor cuando el controlador puede
cerrarse normalmente. Si se mata el controlador o cae Docker, arrancar el motor
y ejecutar:

```sh
.venv/bin/python -m decision_room recover-executions \
  --business 3fdd7db1-26d5-453d-829e-70b34acb6452
```

Recuperación se niega a actuar mientras haya un controlador activo. Elimina solo
contenedores con la etiqueta de ejecución esperada, limpia entradas temporales y
marca las ejecuciones abandonadas como interrumpidas. Si la limpieza no se puede
confirmar, la ejecución permanece abierta con aviso, sin resultado aprobado.
Para apagar la VM al terminar: `scripts/dev/local_sandbox.py stop` con la `.venv`.

## Verificación y siguiente etapa

```sh
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/checks/check_sandbox_wwi.py --request-key nueva-comprobacion-001
```

Las pruebas requieren PostgreSQL y Docker locales. Crean una base PostgreSQL
temporal y la eliminan; la comprobación WWI guarda evidencia real en el análisis.
Véase [el informe de aceptación](../validation/2026-09-21-sandbox-check.md).

El próximo paso es **1.4: agente LangGraph, preguntas y recuperación del análisis**.
El contrato del ejecutor se puede conservar al crear un backend remoto que
transfiera snapshots y resultados. Este backend solo admite un socket Docker
local: no basta con cambiar una URL para ejecutar en la nube. El instalador actual
está hecho para macOS; la imagen Linux permite preparar un trabajador Linux/AMD64
o ARM64, que deberá probarse en ese destino.

Antes de exponerlo a clientes faltan autenticación, trabajos duraderos, cuotas por
usuario, retención de archivos, monitorización y evaluación del aislamiento del
proveedor. El prototipo local usa un kernel Linux compartido entre contenedores
dentro de una VM; un servicio público puede requerir microVMs o un runtime reforzado.
