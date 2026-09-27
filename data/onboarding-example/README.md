# Negocio ficticio para probar el onboarding

Datos sintéticos creados para esta demostración. No contienen información de un
negocio real. Selecciona `ventas.csv` en el segundo paso; también puedes elegir
esta carpeta para comprobar que se omite el README.

## Nombre del negocio

Papelería Horizonte

## Cuéntanos qué haces

Somos una papelería de barrio. Vendemos cuadernos, bolígrafos y mochilas en una
única tienda. Queremos entender cómo cambian las ventas y el margen por categoría.
El archivo de prueba contiene todas las ventas de julio y agosto de 2026 de este
negocio ficticio. Cada fila agrupa las ventas de una categoría en una fecha.
Los importes están en euros y no incluyen IVA. El coste corresponde únicamente a
los productos vendidos; no incluye alquiler, salarios ni otros gastos. No hay
devoluciones en este ejemplo.

## Qué te gustaría entender

Compara julio y agosto: ¿cuánto cambian las ventas y el margen bruto? ¿Qué
categorías explican el crecimiento?

## Nombre del informe

Ventas y margen · julio–agosto 2026

## Columnas

- `fecha`: fecha de la venta, en formato AAAA-MM-DD.
- `categoria`: categoría del producto.
- `unidades`: unidades vendidas en esa fila.
- `ventas_sin_iva_eur`: ingreso total de la fila, no precio unitario.
- `coste_producto_eur`: coste total de los productos vendidos en esa fila.

El margen bruto se calcula como ventas menos coste de producto. Su porcentaje es
margen bruto dividido entre ventas. No equivale al beneficio neto.

## Resultados de referencia

| Mes | Ventas | Coste de producto | Margen bruto |
| --- | ---: | ---: | ---: |
| Julio | 615,00 € | 330,00 € | 285,00 € |
| Agosto | 1.035,00 € | 558,00 € | 477,00 € |

Las ventas aumentan 420,00 € (68,29 %). El margen bruto aumenta 192,00 € (67,37 %).
Las mochilas aportan 240,00 € del aumento de ventas. Son datos muy pequeños para
comprobar el recorrido; no permiten inferir estacionalidad ni tendencias futuras.
