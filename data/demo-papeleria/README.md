# Papelería ficticia para probar varias fuentes

Los dos CSV de esta carpeta son sintéticos y no contienen datos de clientes reales. Acompañan al [CSV de ventas del caso de referencia](../reference-cases/03-ambiguous-amount/input/sales.csv), cuya atribución se conserva en el repositorio.

| Archivo | Alcance | Relación con ventas |
| --- | --- | --- |
| `sales.csv` del caso de referencia | Doce líneas seleccionadas de abril de 2016 | Cada línea tiene `product_id=1`; `amount` necesita aclaración antes de calcular. |
| `productos.csv` | Catálogo ficticio de cinco artículos | `product_id` permite identificar el artículo de las líneas de ventas. Los otros cuatro productos no aparecen en ese extracto. |
| `gastos_local.csv` | Gastos ficticios de todo el local en abril de 2016 | No tiene clave de venta ni de producto. Su alcance mensual y total del negocio no coincide con el extracto parcial de ventas. |

Ejemplo de descripción del negocio: «Papelería La Esquina está en Valencia, cerca de un colegio. Abrimos de lunes a sábado, de 9:00 a 14:00 y de 16:30 a 20:00. Vendemos material escolar, artículos de oficina y pequeños regalos. Nos visitan familias, estudiantes y comercios del barrio. Septiembre suele ser el mes más ocupado por la vuelta a clase».

La interfaz actual del primer informe acepta un CSV. Tras terminarlo, «Mi negocio → Datos y archivos» permite guardar los otros por separado, pero no combina tablas de distintos conjuntos. Estos archivos preparan una prueba futura de unión explícita por `product_id` y de rechazo de una comparación de beneficio sin ventas completas. No se debe restar `gastos_local.csv` al extracto parcial para declarar beneficio o pérdida.
