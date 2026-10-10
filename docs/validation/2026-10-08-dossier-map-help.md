# Lectura de las relaciones

Refinamiento del paso 2.5.5, comprobado el 8 de octubre de 2026.

1. Se contrastó el código y el SVG real con la
   [notación ER documentada por Mermaid](https://mermaid.js.org/syntax/entityRelationshipDiagram).
   El marcador de varias filas se dibujaba con curvas cerradas, poco reconocibles
   como las tres puntas convencionales. Además, el tamaño de los marcadores dependía
   del grosor de la línea, que aumenta al seleccionar o enfocar una relación.
2. Se normalizan sus geometrías en el SVG conservando IDs, extremos y semántica
   uno/varios y cero/uno existentes. Las tres puntas son rectas; `userSpaceOnUse`
   evita que crezcan con el grosor de la línea. El zoom continúa escalando el mapa.
   Se mantienen los colores del tema y los círculos existentes. Los mínimos siguen
   siendo conservadores: el servicio mide unicidad y coincidencias, no establece
   obligatoriedad de negocio.
3. Cómo leer este mapa aparece plegado por defecto. Explica rayas, tres puntas,
   círculos, líneas discontinuas y zoom, con un ejemplo cotidiano. Se puede abrir
   y cerrar con ratón o teclado. Al enfocar o pasar por una conexión, se muestra
   siempre su cardinalidad en palabras junto a su descripción, columnas y estado;
   una descripción personalizada ya no oculta la explicación uno/varios.
4. Suite frontend completa: 284 pruebas correctas. Incluye conservación de mínimos,
   máximos, IDs y referencias a ambos extremos de los marcadores; ayuda plegada,
   cierre con teclado y cardinalidad junto a una descripción propia. Se mantienen
   las pruebas existentes de selección, referencias, actualización, arrastre y zoom.
   Compilación, lint y `git diff --check` correctos, sin avisos nuevos en estos archivos.
5. Navegador real: símbolos y ayuda comprobados a 1440 × 1400 en oscuro y en claro;
   explicación de conexión mediante foco de teclado, conservando el texto del negocio.
   A 390 × 900, ayuda desplegable y sin desbordamiento horizontal. Se restauró
   el tamaño habitual y el modo oscuro. Capturas en `.local/visual-checks/`, fuera de Git.
6. Revisión pública: código, traducciones, documentación y pruebas con ejemplos
   sintéticos; sin credenciales, datos privados, rutas personales ni archivos generados.
   Se preservan los cambios previamente preparados del usuario en otros archivos.

No cambian el modelo guardado, su cardinalidad medida, las referencias de contexto
ni contratos del servidor. La ayuda distingue cómo encajan los datos actuales de
las reglas obligatorias del negocio.
