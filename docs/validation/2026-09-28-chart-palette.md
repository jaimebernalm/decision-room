# 3.8.11 · Paleta fija y tooltips legibles

## Cambios

- Seis tonos de azul suaves: `#367da5`, `#89bbd7`, `#28658a`, `#62a1c5`,
  `#4c8db3` y `#b3d1e3`. La definición JSON compartida alimenta las series
  de React, las proyecciones del backend y los gráficos de exportación HTML.
  Los gráficos simples utilizan el primer tono de esa misma definición.
- Asignación determinista por serie y resolución de colisiones dentro de los
  seis tonos disponibles. Si hay más etiquetas en un informe, se reutilizan
  colores de la paleta; se elimina la generación de colores HSL adicionales.
  El frontend descarta colores antiguos ajenos a la paleta.
- Tooltip común para barras agrupadas, barras simples y líneas: categoría
  completa, unidad sin repeticiones y valores exactos. Texto con salto de línea,
  ancho limitado al contenedor y posición horizontal dentro de la tarjeta.
  Los cambios son de presentación y no recalculan ni reescriben evidencia.

## Validación

- **15 pruebas Python pasan**: `test_chart_layout` y `test_client_report`.
  Incluyen correspondencia entre colores web/exportados, estabilidad frente al
  orden de entrada y 40 etiquetas sin producir colores fuera de la paleta.
- **107 pruebas frontend pasan**, con regresiones del contenido del tooltip:
  títulos y series largas, unidad una sola vez y decimales exactos.
- TypeScript/Vite compila. Lint sin errores; conserva avisos anteriores de
  componentes compartidos. `git diff --check` limpio.
- Bruma Café guardado: sigue aprobado y publicable; sus cuatro gráficos se
  proyectan y exportan usando exclusivamente los seis tonos compartidos.
- Navegador real en escritorio y a **390 × 844 px**: leyenda y tooltip legibles.
  En móvil, el tooltip medido ocupa 302 px, dentro del ancho de la tarjeta,
  sin desbordamiento de título, unidad, nombres de series o valores. El ancho
  del documento permanece en 390 px.
- La primera comprobación móvil detectó que Recharts situaba el tooltip dentro
  del área de barras y lo desplazaba fuera de la tarjeta. Se corrigió anclando
  su posición horizontal al contenedor completo y se repitió la comprobación.
  La unidad extensa del informe se muestra completa una sola vez, seguida de
  junio/julio/agosto con los valores guardados.

Las pruebas de navegador usan datos sintéticos existentes de Bruma Café.
No ha sido necesaria una nueva generación del informe ni una llamada al modelo.
Los registros locales quedan fuera de Git.
