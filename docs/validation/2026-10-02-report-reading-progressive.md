# 3.8.12.1 · Lectura progresiva del informe e Inicio

Implementado sobre `feature/ui-integration`, conservando los cambios de UI1/UI2.
La rama `feature/report-quality` se inspeccionó en lectura en su estado `646b35c`,
incluidos gráficos, orientación de decisiones y cambios de Inicio. No se modificó
su checkout ni se incorporó su contrato analítico a esta entrega.

## Comportamiento

- Hallazgo, declaración revisada y todos sus gráficos comparten una tarjeta.
  «Ver detalle» queda después de la visualización y abre interpretación, próxima
  comprobación, método, fuentes y valores exactos. Los hallazgos sin gráfico y
  los gráficos sin hallazgo asociado siguen siendo consultables. Las tablas se
  muestran inicialmente como visualización, sin duplicarlas en el detalle.
- «Sobre este informe» es un desplegable discreto en la cabecera con resumen
  completo, negocio, pregunta, cobertura y archivos presentes en la evidencia.
  Periodo, revisión, entrega parcial y limitaciones completas siguen visibles.
- Tres indicadores revisados se muestran inicialmente, conservando el orden del
  informe. Los restantes se consultan en «Más indicadores del informe»; no se
  inventan métricas ni se interpreta su relevancia mediante una heurística nueva.
- Inicio obtiene la conclusión del hallazgo existente del mismo informe, versión,
  trabajo y revisión de presentación. No mezcla conclusiones de otra revisión.
  Cada tarjeta conserva su periodo y muestra la revisión; archivos, cobertura y
  motivos de selección se consultan en el detalle de fuente.
- Un enlace incluye clave del hallazgo, identidad y revisión del informe. Solo
  abre y enfoca el hallazgo si esas referencias coinciden. Si la revisión ha
  cambiado o falta el hallazgo, avisa sin sustituir la referencia para el chat.
- «Lo que destaca» conserva las tarjetas seleccionadas, su contexto y enlace;
  evita repetir la declaración ya visible junto a un gráfico seleccionado. Una
  conclusión que no aparece con un gráfico sigue mostrando su texto completo.
  Editar, fijar/desfijar y ocultar conservan el menú secundario accesible existente,
  las revisiones de escritura y la aceptación explícita de propuestas del agente.
- Selección independiente de gráfico/hallazgo, contenido original, versión,
  unidades originales, códigos, paleta y valores decimales conservados.
  No cambian publicación, retirada, autorización ni exportación del PDF.

## Comprobaciones

- `npm test`: 202 pruebas correctas, 27 archivos. Después del último ajuste del
  párrafo duplicado: 18 pruebas correctas de Home, lectura, idioma y navegación.
  Incluyen gráficos múltiples, tabla, ausencia de gráfico, teclado, evidencias,
  originales, límites completos, selección contextual y revisión incompatible.
- `npm run build`: TypeScript y producción correctos. Advertencia de tamaño de
  algunos chunks; no hay errores de compilación.
- `npm run lint`: sin errores; 27 advertencias en los componentes y utilidades.
- `python -m unittest discover -s tests -p 'test_report_pdf.py'`: 3 correctas;
  contenido completo, valores, paginación y rechazo de evidencia no publicable.
- Navegador con dos informes y datos ficticios en la vista previa local:
  escritorio de 1280×800 y móvil de 390×844. Se revisan tarjeta cerrada/abierta,
  Inicio, método, fuentes, valores exactos, contexto y menús con teclado.
  El desplazamiento relativo del gráfico dentro de la tarjeta permanece en
  178 px antes/después de abrir el detalle. No hay desbordamiento horizontal.
- Seleccionar el gráfico permite adjuntarlo como contexto al compositor sin
  confundirlo con el hallazgo; el adjunto de prueba se retira después. El enlace
  de Inicio abre `sales-growth` en su revisión y enfoca esa misma tarjeta.
- Los dos endpoints PDF devuelven `application/pdf`, firmas válidas y contenido
  íntegro con fuentes y condición ficticia. El botón vuelve al estado disponible
  sin error. El navegador integrado no entregó el evento automatizado de descarga;
  no se confirma una ubicación final de guardado mediante ese evento.
- Capturas y PDF de comprobación permanecen en `.local/report-reading/`, ignorado
  por Git. Los datos de ejemplo y las preferencias existentes no se sustituyen.

## Límites y compatibilidad

No se generan resúmenes nuevos en el cliente ni se usa `reportLead` en el informe.
Una declaración o caption existente puede contener condiciones materiales en
cualquier frase: se conserva completo. Para abreviar esos textos con garantías
haría falta un campo breve validado en el contrato de calidad; este incremento
no presupone que la primera frase sea una conclusión suficiente.

La orientación, escalas y exploración de puntos añadidas en la rama de calidad
requieren su integración posterior. Se conservan los identificadores de hallazgos
y se ofrece `lead` en ReportSection, evitando duplicar esa API. Los cambios en
ReportView/EvidenceChart se superponen con esa rama y deben resolverse alrededor
de esta agrupación al unirlas. No se añade un constructor, filtros que recalculen
informes revisados, llamadas al modelo ni cambios al PDF. No se cierra aceptación
analítica general ni se usa información de un comercio real en esta comprobación.
