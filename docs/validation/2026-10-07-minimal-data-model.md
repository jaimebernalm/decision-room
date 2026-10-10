# Relaciones con lectura mínima — 7 de octubre de 2026

## Petición y resultado

El propietario pidió simplificar lo situado debajo del mapa para usuarios no
técnicos: no entendía los controles de métricas/relaciones ni el segundo mapa
que mostraba una sola tabla. Consideraba útil Conexiones y comprobaciones.

La vista principal conserva el mapa y ese desplegable. Se elimina la repetición
de botones de tablas debajo del mapa; siguen disponibles en búsqueda e historial
para seleccionar cualquiera, también cuando el mapa está limitado a doce tablas.
La revisión exacta se consulta en el mismo desplegable.

Las definiciones y los controles opcionales se agrupan en «Ajustar cómo usamos
estos datos», cerrado inicialmente. «Conectar dos tablas» y «Aclarar un cálculo»
tienen una explicación y un ejemplo concreto de beneficio y gastos. No aparece
una sección vacía de métricas. Los cálculos guardados se conservan y pueden
consultarse también en revisiones de solo lectura.

Un conjunto con una sola tabla muestra una frase que explica la ausencia de
conexiones y un botón para ver su tabla. No dibuja otro mapa ni repite un título
de conexiones. Los detalles muestran información disponible, sin múltiples
avisos de descripción/granularidad pendientes ni contadores de cero duplicados.
Las columnas y claves se consultan dentro de sus detalles desplegables.

Al seleccionar una conexión, se muestra su significado y estado. Sus columnas,
cardinalidad, cifras de comparación y origen se consultan en «Ver comprobaciones».
Los detalles de tablas/conexiones se pueden cerrar. Se mantienen los avisos sobre
preparaciones antiguas e informes afectados y las protecciones de revisión.

## Validación

- `npm --prefix frontend test`: 246 pruebas correctas en 33 archivos.
- `npm --prefix frontend run build`: TypeScript y compilación correctos.
- `npm --prefix frontend run lint`: sin errores; conserva avisos existentes.
- Pruebas de conjunto con una sola tabla: explicación sin diagrama, apertura
  de columnas y cierre de detalles.
- Pruebas de selección de más de doce tablas, foco, acceso a evidencia técnica,
  corrección con revisión exacta y edición deshabilitada al consultar historia.
- Pruebas de aclaraciones opcionales: controles inicialmente ocultos, formulario
  para conectar tablas, ejemplo de cálculo, validación de selección de tablas
  y guardado de definición con revisión 3. Definiciones históricas conservadas
  sin controles de creación o corrección cuando son de solo lectura.
- Navegador local: controles reducidos bajo el mapa, formulario de cálculo abierto
  y cancelado sin guardar, acceso a la tabla del conjunto original y cierre.
  El aviso de dos informes afectados permanece visible.
- Móvil de 390 × 844: ancho del documento 390 px y un único lienzo para los dos
  conjuntos existentes. Sin desbordamiento horizontal. Tamaño normal restaurado.
- Revisión de diferencias y archivos preparados para Git: sin estado local,
  credenciales, rutas personales ni artefactos generados.

Las capturas y registros permanecen en `.local/checks/2026-10-07-minimal-data*`,
ignorados por Git. No se modifica la inferencia, los datos guardados ni la
aceptación de la entrega 3. Los controles técnicos completos siguen disponibles
cuando el propietario abre las aclaraciones o comprobaciones correspondientes.
