# Entorno de ejecución de Python: plan de construcción

21 de septiembre de 2026. Implementa el paso 1.3 del plan del MVP.

**Estado:** construido y comprobado. Las 22 pruebas de ingesta y ejecución pasan;
los cálculos sobre las 48 tablas WWI coinciden con los CSV originales. Consultar
la [guía operativa](sandbox.md) y el [informe de aceptación](../validation/2026-09-21-sandbox-check.md).

## Diseño

El controlador de Decision Room recibe código, identificadores de tablas y las
definiciones de la investigación. Verifica que pertenecen al negocio y análisis,
comprueba las huellas de los Parquet y prepara únicamente las fuentes autorizadas.
No ejecuta ese código en la `.venv`, ni entrega acceso a PostgreSQL al contenedor.

Cada cálculo se ejecuta en un contenedor Linux efímero. En este Mac, Docker vive
en una VM Colima dedicada (`decision-room`), sin montar el directorio personal
ni el repositorio. Solo se comparte con la VM una carpeta de entradas de ejecución.
El contenedor recibe únicamente el subdirectorio de su ejecución en lectura.

El contrato es independiente de LangGraph: código Python + tablas autorizadas +
definiciones → estado de ejecución + resultados candidatos + archivos + evidencia.
No es un agente ni una herramienta que apruebe conclusiones por sí sola.

## Entorno y controles

- Python 3.12 y dependencias bloqueadas dentro de una imagen Docker versionada.
- DuckDB, pandas, PyArrow, NumPy, SciPy, matplotlib, openpyxl, Seaborn, statsmodels,
  scikit-learn y biblioteca estándar. Las bibliotecas de ML están disponibles sin
  añadir predicción al alcance funcional del MVP.
- Sin red en la ejecución; instalación de paquetes solo durante la construcción
  controlada de la imagen, antes de introducir datos del negocio.
- Usuario sin privilegios, sin capacidades Linux, `no-new-privileges`, seccomp de
  Docker y raíz de solo lectura. Sin socket Docker, secretos, credenciales ni
  almacenamiento de otros análisis.
- Tiempo, CPU, memoria, swap, procesos, descriptores, temporales, archivos y salida
  limitados. Control del plazo tanto dentro como fuera del contenedor.
- Entradas de solo lectura. Escritura únicamente en temporales y salida efímera
  acotada; recogida de salidas antes de que desaparezca el contenedor.
- Validación externa de JSON, nombres, tipos y tamaños de artefactos. No ejecutar
  pickle, HTML, código ni objetos aportados como resultado.
- Código, versiones, huellas de fuentes, definiciones, estado, tiempos, logs y
  artefactos conservados con referencias por negocio y ejecución.
- Interrupciones y ejecuciones abandonadas conservan un estado explícito y pueden
  limpiarse; no se reejecuta automáticamente código ni se publica un resultado dudoso.

## Secuencia y comprobaciones

1. Instalar y arrancar Colima/Docker; construir una imagen reproducible.
2. Crear el ejecutor y su contrato de salida, límites y recogida segura.
3. Añadir persistencia de ejecuciones y evidencias a PostgreSQL y al almacenamiento.
4. Exponer comandos locales y una función que después podrá usar LangGraph.
5. Contrastar cálculos conocidos sobre los CSV de referencia y los Parquet WWI.
6. Probar bloqueo de red, escritura de entradas, archivos ajenos, escalada,
   agotamiento de tiempo/memoria/procesos/salida y resultados mal formados.
7. Documentar uso, recuperación, límites comprobados y camino a despliegue remoto.

## Futuro despliegue

La primera implementación usa un backend Docker local. Un backend remoto deberá
recibir instantáneas autorizadas y devolver el mismo contrato, conservando las
comprobaciones de acceso y procedencia en el controlador. La imagen se puede
construir para ARM64 o AMD64; cada ejecución registra el digest y la arquitectura.
No se promete identidad binaria entre arquitecturas ni determinismo de todo cálculo.

Para un piloto público habrá que elegir y probar aislamiento y operación en el
proveedor: trabajadores separados, control de concurrencia y costes, credenciales
temporales, supervisión duradera y, según el riesgo, microVM o runtime reforzado.
Un contenedor comparte el kernel de su VM; las pruebas locales no demuestran
inmunidad frente a vulnerabilidades del runtime ni equivalen a certificación.

Referencias: [controles de Docker](https://docs.docker.com/engine/containers/run/),
[seguridad del motor](https://docs.docker.com/engine/security/),
[Colima](https://colima.run/docs/).
