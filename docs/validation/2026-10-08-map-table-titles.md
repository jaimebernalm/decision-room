# Títulos de tablas diferenciados

Refinamiento visual de 2.5.5, comprobado el 8 de octubre de 2026.

Los nombres de las tablas del mapa aparecen en negrita y sobre una franja de
fondo muted del tema. Las columnas mantienen su peso normal y fondo background.
El ejemplo de la ayuda usa la misma jerarquía. La configuración del renderizador
incluye la negrita, y el CSS la conserva en los tspan generados por Mermaid.
No se modifica la gramática de datos ni los controles y acciones del mapa.

## Comprobaciones

- 13 pruebas pasan: dibujo, selección, arrastre, teclado, ayuda y marcadores.
- TypeScript/Vite y lint completados; avisos generales anteriores del repositorio
  y tamaño del bundle, sin nuevos avisos en los componentes modificados.
- Navegador con SVG real: título de Ventas con peso 700, columnas con peso 400,
  fondo de cabecera distinto al de filas en claro y oscuro.
- Inspección visual del mapa y del ejemplo en escritorio (1440 píxeles), y de
  las cabeceras en móvil (390 píxeles). Se restaura oscuro y el tamaño nativo.
- Revisión del diff público: código y documentación, sin datos privados,
  credenciales, rutas personales ni archivos generados. Capturas locales ignoradas.

Las demás modificaciones simultáneas del espacio de trabajo quedan fuera de
este incremento.
