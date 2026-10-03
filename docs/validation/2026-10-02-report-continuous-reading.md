# Lectura continua y leyenda discreta · 2 de octubre de 2026

Paso 3.9.8.3. El propietario rechaza la leyenda negra y encuentra que la cadena
de «Ver detalle» y «Cómo se ha calculado» hace más pesada la lectura.

## Presentación

Los nombres de series tienen fondo transparente, sin borde de botón permanente
y con fondo gris al pasar por encima. Solo una serie oculta muestra un ojo
cerrado y texto atenuado. Se conservan acciones de mostrar/ocultar, el estado
accesible y el límite de mantener una serie visible. La ayuda general pasa a
lectores de pantalla; el título del botón explica la acción disponible.

Pasar por una serie de la leyenda resalta su curva: conserva su identidad de
color, lo mezcla con el color de texto para oscurecerlo y aumenta el grosor a
3 px. Las otras curvas y puntos bajan su opacidad a 0,35. Las curvas y puntos
resaltan a su vez el nombre en la leyenda. Al salir se restaura la vista; el
foco por teclado conserva el énfasis mientras permanece activo. Una serie
oculta no activa ese énfasis. No se modifican valores, periodos, escala, tablas
ni definición guardada del gráfico.

Los hallazgos mantienen títulos grandes y pasan a secciones continuas, con
separadores finos, sin borde de tarjeta alrededor. El pie de ancho completo
«Ver detalle» se sustituye por un enlace pequeño «Datos y fuentes». Al abrirlo
se muestran juntos interpretación, base del análisis, archivos, métricas,
operaciones y tablas exactas. Método y fuentes ya no requieren otro clic;
las tablas embebidas tampoco. En gráficos independientes se conserva el acceso
a valores exactos, y las tablas que son la visualización principal siguen
visibles. Un hallazgo sin detalle no ofrece un control vacío.

La prosa revisada, condiciones y límites se conservan completos. No se genera
una nueva síntesis ni se cambian aprobaciones. No se usan modelos.

## Comprobaciones

- 236 pruebas frontend pasan en 30 archivos. Nuevas regresiones cubren énfasis
  y limpieza al salir, exclusión de series ocultas, evidencia sin mutaciones,
  apertura única de método y cifras, y ausencia de controles vacíos. Se actualizan
  las pruebas de idioma, navegación y lectura para el nuevo acceso único.
- Compilación TypeScript/Vite correcta y lint sin errores. Persisten avisos
  existentes de lint y tamaño del paquete.
- Bruma Café en `http://127.0.0.1:8787/`: leyenda transparente en reposo, títulos
  y gráficos visibles en secciones. Se comprueba ocultar/restaurar con clic.
  Señalar un punto real de Café de la casa destaca su nombre, oscurece la curva,
  aplica grosor 3 y atenúa las otras cinco curvas a 0,35. Al restaurar una serie
  desde su nombre, la captura muestra el nombre con gris y su curva resaltada.
- Una sola apertura de «Datos y fuentes» del primer hallazgo muestra la base
  del análisis; no existe un botón anidado de método. Se deja el informe con
  detalles cerrados, todas las series visibles y sin selectores redundantes.
- Inspección en el tamaño habitual del navegador; no se añade una nueva prueba
  móvil. Las capturas quedan en `.local/`, fuera de Git.

Se revisan los cambios preparados para credenciales, rutas personales y archivos
privados antes del commit local. No se hace push.
