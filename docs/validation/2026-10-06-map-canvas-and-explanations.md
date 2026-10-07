# Lienzo y explicaciones de conexiones — 6 de octubre de 2026

## Cambio solicitado

Se elimina del dibujo la etiqueta genérica repetida «dato», que no aportaba
significado al usuario. Mermaid conserva internamente el token que requiere
su sintaxis; el renderizado oculta y retira la columna de tipos y sus divisores.
Se mantienen nombres de columnas, bordes de filas y claves declaradas válidas.

El diagrama se centra dentro de un lienzo contenido con fondo de puntos. Puede
desplazarse libremente mediante arrastre, incluso sin ampliar el zoom. La escala
inicial ajusta todo el gráfico al espacio disponible y «Ajustar» restaura escala
y posición. El límite de ampliación pasa a cuatro veces la escala ajustada.
Las flechas del teclado desplazan el lienzo cuando tiene el foco.

Las líneas y sus etiquetas muestran una explicación al pasar el puntero.
También se muestra al enfocar una conexión con teclado; Escape la cierra.
La explicación usa la descripción guardada o una frase sobre cómo corresponden
las filas, indica las columnas comparadas y señala conexiones propuestas o
descartadas. Los nombres se presentan como texto. No se infieren nuevos vínculos
ni se presentan propuestas como confirmaciones.

El arrastre utiliza captura de puntero al superar cuatro píxeles de movimiento.
Su clic final no abre una tabla o conexión accidentalmente. Se gestionan salida,
cancelación y pérdida de captura; un clic posterior vuelve a seleccionar.

## Comprobaciones

- `npm --prefix frontend test`: 244 pruebas correctas en 33 archivos.
- `npm --prefix frontend run build`: TypeScript y compilación correctos.
- `npm --prefix frontend run lint`: sin errores; avisos existentes conservados.
- Pruebas del componente: retirada de tipos y divisores conservando nombres,
  arrastre en escala inicial, supresión del clic final, selección posterior,
  desplazamiento con teclado, zoom y ajuste sin nuevo renderizado Mermaid,
  cancelación de puntero, explicación por puntero/foco, incertidumbre y clic
  sobre etiqueta. Se conservan pruebas del parser real y revisiones históricas.
- Navegador de escritorio: desplazamiento físico de 50 × 20 px reflejado en
  el lienzo, zoom y ajuste, selección desde la etiqueta y explicación visible
  mediante puntero y Tab. No hay etiquetas de tipo genérico en el SVG mostrado.
- Navegador móvil de 390 × 844: ancho del documento 390 px, lienzo de 282 ×
  380 px, disposición vertical y arrastre de 20 × 20 px dentro del mapa.
  Restaurado el tamaño normal del navegador al terminar.

Capturas y registros locales: `.local/checks/2026-10-06-map-canvas-*`, ignorados
por Git. Revisadas las diferencias y los archivos preparados para publicación.

## Alcance

No modifica datos ni relaciones guardadas, revisiones, inferencia o controles
de validación. No añade dependencias. Se reutiliza el ejemplo sintético existente.
En pantallas pequeñas, el ajuste inicial reduce el tamaño de las tablas para
mostrar todo el mapa; se puede ampliar y arrastrar para leer las columnas.
Las explicaciones visibles se acotan para mantenerlas breves; la descripción
completa sigue disponible en los detalles y en el texto accesible de la conexión.
