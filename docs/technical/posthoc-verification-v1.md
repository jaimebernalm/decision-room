# Verificación posterior a un informe: piloto V1

El propietario autoriza iniciar V1 después del cierre de R0/R1. Se implementa en
un paquete separado, sin modificar sus candidatos congelados ni abrir P4. La
medida sigue el preregistro `2026-10-08-loop-verification-preregistration.md`,
revisión 3 y aclaración de formato, en la rama de evaluación.

## Secuencia

1. Inventario compartido y precisión determinista: implementados y comprobados.
2. Interpretaciones separadas con valor oculto, recetas fundamentadas y recálculo:
   pendiente.
3. Derivada con invariantes, exportación y contabilidad mediante el proxy: pendiente.
4. Desarrollo, congelación y evaluación sellada: pendientes. Las pruebas técnicas
   no acreditan los umbrales del piloto.

El presupuesto conjunto de desarrollo y prueba es de 3 USD conocidos. Una llamada
con coste incierto exige parar y consultar. El auditor y los lectores siguen el
procedimiento separado de evaluación; ningún dato de auditoría se pasa al producto.

## Inventario `posthoc-inventory-v1`

`decision_room.reports.posthoc.inventory.build_inventory(html_path)` abre el HTML
original en un perfil efímero de Chrome, a 1280 px, ejecuta sus scripts y espera a
que el texto del DOM se estabilice. No modifica el archivo ni llama a un modelo.
La captura queda incluida para reproducir y revisar el inventario. Una revisión
posterior de scripts, fuentes o contenido puede cambiar la captura: se comparan
hashes antes de reutilizar un inventario.

- `source_sha256`: hash de los bytes originales.
- `text`: texto canónico del DOM renderizado. Las etiquetas inline no insertan
  separadores; los bloques y las celdas sí. No es el HTML fuente ni `textContent`
  que incluya scripts o elementos ocultos.
- `text_sha256`, `snapshot_sha256`: identidades de texto y captura.
- `occurrences[]`: `id`, `text`, `span: [inicio, fin)`, `kind`, `region`, `parts`
  y `context`. Los offsets de `span` son puntos de código Unicode, como en Python.
  La identidad incluye la versión, los hashes del original y texto, y el span.
  No se colapsan repeticiones: cada ubicación conserva su identidad.
- `parts[]`: camino de índices `childNodes` desde `document.body` y span UTF-16
  dentro de cada nodo de texto. Permite localizar números partidos entre nodos y
  conservar el original al añadir marcas.
- `context.section[]` y, en tablas, `context.table.{caption,column_headers,row_headers}`:
  referencias `{text, span}` al mismo texto canónico. `table.unresolved` indica
  falta de correspondencia. La estructura orienta la interpretación; no acredita
  por sí sola que una fila sea una entidad ni que una celda sea una población.
- `region: chart` identifica texto de SVG/canvas: se conserva en el inventario
  aunque su comprobación esté fuera del catálogo. Píxeles de canvas sin texto DOM
  deben registrarse aparte por el auditor y permanecer en el denominador.

La evaluación utiliza estos mismos ids y spans. El ledger posterior será un mapa
por id con `status`: `verified`, `discrepancy`, `not_checkable` o `uncertain`.
El inventario no descarta años, identificadores ni cifras de gráficos; decidir si
una ocurrencia es una cifra de negocio es una fase separada y trazable.

La captura de texto no sustituye a comprobar visualmente los gráficos ni acredita
su estabilidad. CSS generado, texto dibujado en canvas y controles sin nodo de texto
no son cifras DOM certificables. La evaluación debe conservar esas limitaciones.

## Precisión `posthoc-precision-v1`

El parser recibe el literal original; el intérprete del ámbito no recibe su valor.
Se exige evidencia positiva de la convención española y ausencia de formatos
contradictorios. `1.234` solo no acredita miles. No se consulta el recalculado para
resolver formato, unidad, escala o ámbito.

La comparación se hace en la escala mostrada, con medio lejos de cero: `1,2 M`
compara el recalculado dividido por un millón a un decimal. Los recuentos y sumas
enteras sin abreviar exigen igualdad exacta. La dirección fundamentada en el texto
se comprueba además del valor y no borra un signo explícito contradictorio.

## Comprobaciones de la primera pieza

`python -m unittest discover -s tests -p test_posthoc_inventory.py -v`: nueve casos,
con Chrome real para contenido dinámico/oculto, tablas y SVG; fixtures para nodos
inline, Unicode/UTF-16, identidades repetidas y reglas adversarias de precisión.
Sin proveedor facturable y sin inspeccionar el conjunto de prueba de V1.
