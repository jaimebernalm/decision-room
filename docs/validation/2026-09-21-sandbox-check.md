# Comprobación del entorno aislado de Python

21 de septiembre de 2026. Paso 1.3 del MVP. Ejecución real en macOS ARM64,
Colima 0.10.3, Docker Engine 29.5.2, contenedor Linux y Python 3.12.14.

## Resultado

La herramienta ejecuta Python con tablas autorizadas, produce resultados
estructurados, conserva evidencia y limita los recursos del cálculo. No hay
agente ni revisión analítica automática implementados; todos los resultados
siguen registrados como candidatos con `verification: pending`.

Imagen utilizada:
`sha256:d8c1e8c798d30be62d71b2da2ab6670eec024ef80c4ff53a8b5e345f33ec0a8e`.
El manifiesto local conserva versiones transitivas, arquitectura y hashes de
construcción; cada ejecución registra además los hashes del controlador.

## Prueba con datos

El caso pequeño de ventas diarias devuelve **73.784,10**, idéntico a la referencia.
La prueba completa entrega al mismo contenedor las **48 tablas / 4.713.833 filas**
de WWI, verifica todos los recuentos y calcula importes y una unión entre facturas
y sus líneas. Un lector CSV de la biblioteca estándar y `decimal.Decimal`, fuera
del ejecutor, calculan independientemente los valores esperados:

| Comprobación | Resultado |
| --- | ---: |
| Líneas de factura | 228.265 |
| Líneas después de unir con facturas | 228.265 |
| Suma de ExtendedPrice | 198.043.439,45 |
| Suma de TaxAmount | 25.782.098,25 |
| Importe sin impuestos | 172.261.341,20 |

Coincidencia exacta; no se añadieron filas por la unión. La prueba utiliza el
esquema conocido de este ejemplo ficticio, no demuestra inferencia de relaciones.

Ejecución completa final: `5b555b18-3d5a-4530-8a1e-ee2f6e0c877a`, en el negocio
`3fdd7db1-26d5-453d-829e-70b34acb6452`, análisis
`d708470f-35dc-4f9b-a79c-c1a279ba803b`.
Se volvió a leer la evidencia desde PostgreSQL y se verificaron los hashes del
código y de los artefactos almacenados. También se probó el comando `run` con las
dos tablas de facturas. Informe legible por máquina: `.local/sandbox-wwi-check.json`.

## Pruebas de restricciones y fallos

Suite completa: **22 pruebas superadas** (11 de ingesta y 11 de contrato/ejecución).
Después de ampliar el caso de acceso a tablas de otro negocio, las 11 pruebas
de ejecución volvieron a pasar. Usan PostgreSQL temporal y contenedores reales.

- Lectura de tablas autorizadas, importación de las siete bibliotecas y cálculo
  con DuckDB: correctos.
- UID 10001, capacidades efectivas nulas, seccomp y `no-new-privileges`: comprobados
  desde dentro. Red desactivada, memoria/swap, límite de procesos, raíz de solo
  lectura y único montaje de entrada: comprobados también por Docker desde fuera.
- Escritura en tablas, código de entrada e imagen: denegada. Repositorio y socket
  Docker: ausentes. Variable secreta de prueba del host: no transmitida.
- Conexión TCP fuera del contenedor: bloqueada.
- Bucle infinito: `timed_out`; asignación de 2 GiB: `resource_limit` por OOM.
- Creación excesiva de procesos: `EAGAIN`; llenado de `/output`: `ENOSPC`.
- Archivo de más de 2 MiB: escritura detenida; 17 archivos: salida rechazada.
- Enlace simbólico, rutas ascendentes, extensiones ejecutables, JSON con claves
  duplicadas/no finitos, evidencia ajena o incompleta: rechazados.
- Escritura de más de 6 MiB directamente al canal del supervisor: cortada por el
  controlador externo. Supervisor bloqueado en FIFO: cortado por su plazo externo.
- Repetición de petición: misma ejecución; petición cambiada con la misma clave:
  rechazada. Tabla de otro negocio y acceso a su ejecución: rechazados.
- Parquet alterado: detectado antes de crear el contenedor, por SHA-256.
- Interrupción del controlador: estado explícito; contenedor abandonado con etiqueta
  válida: eliminado por recuperación. Fallo simulado de limpieza: ejecución abierta
  recuperable, sin presentar un resultado como terminado.
- Tras los cálculos y fallos controlados se comprueba la eliminación del contenedor
  y de las entradas efímeras. Código y artefactos válidos permanecen en almacenamiento.

## Repetir y alcance

```sh
.venv/bin/python scripts/dev/local_postgres.py start
.venv/bin/python scripts/dev/local_sandbox.py start
.venv/bin/python -m decision_room init
.venv/bin/python -m unittest discover -s tests -v
.venv/bin/python scripts/checks/check_sandbox_wwi.py --request-key otra-comprobacion-001
```

La primera construcción de imagen se hace con `scripts/dev/local_sandbox.py build`.
Tras cambiar código, entorno o fuentes, utilizar una nueva clave de comprobación.

Estas pruebas validan el alcance local y los casos indicados. No son una auditoría
de seguridad, un ensayo de evasiones del kernel ni una validación de despliegue
multiusuario. El código sigue pudiendo producir una interpretación errónea dentro
de sus datos autorizados. El despliegue remoto, autenticación, colas duraderas y
revisión del análisis quedan para las siguientes entregas.

Siguiente paso del plan: **1.4, agente principal LangGraph con preguntas,
persistencia y pausa/reanudación**.

## Ampliación de bibliotecas — 21 de septiembre de 2026

Se incorporaron **Seaborn 0.13.2, statsmodels 0.15.0 y scikit-learn 1.9.1**,
con sus dependencias transitivas fijadas en `sandbox/requirements.lock` y sin
cambiar las versiones previamente instaladas. La nueva imagen activa es
`sha256:10887b6b9ae5d6218c01c35dc3abfb4b70403fe6e49ac726c3a6e4111a7a69b7`.
La imagen y ejecución WWI documentadas arriba pertenecen a la comprobación inicial.

La construcción pasó `pip check`. Las **11 pruebas de ejecución** volvieron a
pasar en 19,156 segundos con la nueva imagen, incluyendo un PNG de barras con
Seaborn, una regresión por fórmula con statsmodels y un pipeline de StandardScaler
y LinearRegression con scikit-learn. Ambos modelos recuperan la relación sintética
`y = 2x + 1`, dentro de los mismos límites y sin red. También pasó el cálculo CSV
de referencia de 73.784,10. Registro local: `.local/sandbox-libraries-tests.log`.

Las bibliotecas quedan disponibles; esta ampliación no añade predicciones ni
otras funciones de machine learning al alcance del MVP.
