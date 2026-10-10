# Ejemplo de tablas relacionadas

Datos totalmente sintéticos creados para probar la interfaz de Mi negocio.
No contienen ventas, proveedores ni información de clientes reales.

- `ventas.csv`: 12 líneas de venta; `producto_id` enlaza con productos.
- `productos.csv`: 5 productos; `proveedor_id` enlaza con proveedores.
- `proveedores.csv`: 3 proveedores ficticios.

Las dos conexiones son muchos a uno, con todas las referencias presentes y
sin multiplicar filas. El significado está declarado para este ejemplo.
Las conexiones de cualquier otro conjunto siguen sus propias comprobaciones.

Para añadirlos a un negocio local, ejecuta con su identificador:

```sh
.venv/bin/python scripts/dev/add_demo_tables.py --business-id UUID
```

El script utiliza el flujo normal de subida de carpetas, guarda los originales,
prepara las tablas y sus relaciones. Crea un conjunto independiente llamado
«Ejemplo: ventas, productos y proveedores». Repetirlo reutiliza el mismo conjunto
y conserva las aclaraciones o cambios posteriores.
