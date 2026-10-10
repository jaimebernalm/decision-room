# Ejemplo dibujado en la ayuda del mapa

Refinamiento visual del paso 2.5.5, comprobado el 8 de octubre de 2026.

Dentro de «Cómo leer este mapa», el ejemplo textual se sustituye por dos tablas
con datos ficticios: tres ventas (V-01, V-02 y V-03) comparten producto_id P-01,
correspondiente a un único cuaderno. Una conexión dibujada sitúa las tres puntas
junto a Ventas y la raya junto a Productos; conserva los círculos usados por el
mapa para indicar posibles ausencias de coincidencia.

La figura tiene título accesible, tablas HTML y explicación en español/inglés.
Usa colores del tema y consultas del contenedor para disponer las tablas en
horizontal o vertical según el espacio disponible. No registra contexto ni
modifica datos, relaciones, selección o controles del mapa real.

## Comprobaciones

- 13 pruebas pasan en data-model-diagram, data-model-selection y data-model-markers.
- Compilación TypeScript/Vite y lint completados; persisten los avisos generales
  anteriores del repositorio y de tamaño del bundle, sin avisos en el nuevo componente.
- Navegador: ejemplo completo en claro y oscuro a 1440 píxeles de ancho;
  adaptación vertical a 320 píxeles, sin desbordamiento en la figura o sus tablas.
- Apertura y cierre de la ayuda con Enter: aria-expanded cambia false/true.
- Se restaura el tema oscuro y el tamaño nativo del navegador, dejando la ayuda abierta.
- Revisión del diff público: solo código, traducciones y documentación; datos
  ficticios, sin credenciales, rutas personales ni archivos generados.

Capturas y registros quedan en .local/ y no se incluyen en Git.
