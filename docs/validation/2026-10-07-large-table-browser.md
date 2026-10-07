# Consulta de tablas grandes — 2.5.34

## Comportamiento

El diálogo de una tabla ofrece búsqueda literal (sin distinguir mayúsculas),
filtro por columna y condiciones Contiene, Es igual a, Sin valor y Con valor.
Sin valor incluye NULL y texto vacío; Es igual a compara el valor original exacto.
La búsqueda espera 350 ms tras escribir. Aplicar combina filtro y búsqueda;
el botón de limpieza los retira. No altera tablas, preguntas ni informes.

Se solicitan bloques de 50 filas y hasta 12 columnas. Solo se dibujan hasta
24 filas y dos espaciadores; la caché mantiene como máximo seis bloques, más
la última respuesta de metadatos. Al volver a una zona descartada se relee.
Ir a fila permite saltar directamente al ordinal deseado. Los segmentos de
50.000 filas evitan alturas superiores a los límites de scroll del navegador;
los botones de filas permiten cambiar de segmento. Las columnas conservan
su navegación, y el filtro puede actuar sobre columnas que no estén visibles.

Sin filtros, el servidor selecciona un intervalo del ordinal de origen: elimina
OFFSET y ordena solo ese bloque. Con filtros, continúa después del último ordinal
mostrado y pide una fila extra para saber si hay más, sin repetir un COUNT completo.
Los identificadores de columna se validan contra el catálogo y se escapan; los
valores siempre son parámetros, incluidos comillas, %, guiones bajos y SQL escrito.
La disponibilidad y el negocio se comprueban antes de cada lectura.

La caché de integridad contiene como máximo 128 verificaciones correctas en
memoria del proceso. Su clave incluye ruta, dispositivo, inode, tamaño, mtime/ctime
con precisión de nanosegundos y hash esperado. Cada consulta verifica esa identidad;
una modificación, sustitución, cambio del hash o reinicio exige nuevo SHA-256.
Se comprueba además que la identidad no cambió durante la consulta. No contiene
filas ni evita comprobaciones de negocio/estado. Un error de acceso, disponibilidad
o integridad vacía los datos visibles; errores temporales permiten reintentar.
Consultas sustituidas y cierres cancelan la petición e ignoran respuestas antiguas.

## Medición y comprobaciones

- Importación real por el flujo CSV habitual: 1.000.000 filas, cinco columnas,
  64.614.478 bytes de CSV sintético; consulta de primera página, mitad, final,
  continuación y última fila. Dos ejecuciones dieron 24,48–46,36 ms por bloque
  en este equipo. Son tiempos de función con PostgreSQL/DuckDB, no latencia
  completa de navegador ni una garantía para todos los archivos.
- Segunda ejecución: primera 46,36 ms, mitad 38,18 ms, último bloque 31,35 ms,
  siguiente 41,58 ms y fila final 34,10 ms. Búsqueda y filtro combinados más
  continuación: 128,89 ms en total. SHA-256 se ejecuta una sola vez para las
  siete consultas de esa prueba, mientras el archivo permanece inmutable.
- 60 pruebas backend distintas pasan: 46 de web, once de dossier y tres de
  tablas grandes. Incluyen paginación/orden, continuidad sin duplicados,
  búsqueda literal, NULL/vacíos, límites, filtros inválidos, aislamiento,
  procedencia y modificación/sustitución/hash tras calentar la caché.
- 267 pruebas frontend pasan: salto directo a la fila 1.000.000, filas virtuales
  limitadas, carga al desplazar, descarte/relectura de bloques, fin de resultados,
  debounce, filtro combinado, columnas ocultas, errores, limpieza, cancelación
  y conservación del contexto/foco. Suite completa, build y lint revisados.
- Navegador real: Productos filtra categoría Escritura y conserva filas originales
  1, 3 y 5; búsqueda Cuaderno más categoría Cuadernos muestra solo la fila 2.
  Móvil 390×844: diálogo de 358 px, página de 390 px, tabla de 814 px contenida
  en una región de 324 px. Formularios de filtros en dos filas; viewport restaurado.
  Capturas locales en `.local/checks/large-table-final.jpg` y
  `.local/checks/large-table-mobile.jpg`. Los datos sintéticos grandes son
  temporales y no se añaden al negocio del propietario ni a Git.

## Límites

No se han medido archivos de varios GB, 256 columnas ni alta concurrencia.
La primera consulta tras reiniciar verifica todo el archivo. Una búsqueda puede
leer muchas filas/columnas; la paginación por cursor evita las filas anteriores,
pero no crea un índice de texto. Las consultas conservan un hilo, 256 MB de límite
DuckDB y 256 MB de espacio temporal configurado. Los resultados filtrados se
recorren progresivamente; el salto arbitrario de fila corresponde a la vista sin
filtros. No se muestra un total de coincidencias hasta conocer el final.

Las celdas conservan el límite de 500 caracteres del visor previo. Se presentan
en una línea para mantener altura constante y su texto disponible aparece al
pasar el ratón; la descarga conserva el contenido completo. El visor tradicional
de evidencias y preguntas mantiene sus botones de paginación y referencias.
