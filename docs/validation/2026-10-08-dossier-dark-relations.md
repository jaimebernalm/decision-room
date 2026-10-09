# Diagrama de relaciones en modo oscuro

Refinamiento del paso 2.5.5, comprobado el 8 de octubre de 2026.

1. Reproducción visual del fallo: Mermaid dibujaba las filas y el contorno de cada
   tabla mediante paths con fondos blancos y bordes claros literales. Los círculos
   de cardinalidad también conservaban un relleno blanco. Las reglas previas solo
   adaptaban los rectángulos, el texto y parte de las líneas.
2. Corrección mediante CSS del mapa: fondos de paths y círculos con `--background`,
   bordes con `--border` y marcadores con `--primary`. Se conserva la transparencia
   de las líneas y el acento de selección, hover y foco. No cambian datos ni
   comportamiento del diagrama.
3. Navegador real a 1440 × 1100: tablas, columnas y conexiones legibles en oscuro;
   fondos de filas y círculos calculados como `oklch(0.145 0 0)` y texto claro.
   Selección de tabla con fondo teñido y borde de acento. Cambio a claro y vuelta
   a oscuro sin recargar ni reemplazar el nodo del SVG: los fondos se actualizan
   con las variables del tema. Se retiró la selección temporal de prueba.
4. Revisión a 390 × 900: fondo correcto, sin desbordamiento horizontal. Se restauró
   el tamaño habitual y se dejó el mapa abierto en oscuro. Capturas locales en
   `.local/visual-checks/`, excluidas del repositorio.
5. Regresión: 11 pruebas de diagrama y selección correctas, incluidos arrastre,
   zoom, teclado, referencias, modelos pendientes de actualización y conexiones.
   Compilación, lint y `git diff --check` correctos; permanecen avisos anteriores
   del proyecto, sin avisos nuevos en el archivo modificado.
6. Revisión para publicación: únicamente CSS y documentación, sin credenciales,
   datos privados, rutas personales ni capturas en el commit. Se conservan los
   cambios preparados del usuario en otros archivos.
