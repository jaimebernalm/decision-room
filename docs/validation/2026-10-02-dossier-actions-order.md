# Mi negocio: decidir desde el detalle y ordenar con arrastre

## Resultado

El detalle de una propuesta ofrece Confirmar, Corregir información y Descartar,
con acciones visibles aunque el texto necesite desplazamiento. Los conflictos
ofrecen Resolver conflicto: las versiones y el formulario aparecen en esa misma
ventana, sin abrir otro diálogo. Se conserva revisión, validación, borrador y
guardado explícito; elegir una alternativa no escribe hasta Guardar solución.
Las fechas ambiguas no permiten confirmación directa.

Las decisiones correctas cierran el detalle y actualizan la ficha. Si el dato
sale de Por revisar, el foco vuelve a su nueva fila, desplegando su grupo si
estaba cerrado. Descartar conserva el historial y devuelve el foco al control de
grupos cuando ya no existe la fila. Un fallo permanece visible dentro del detalle.

Personalizar grupos incorpora un asa de arrastre independiente de los campos.
Las cajas se recolocan mientras se arrastra, incluso con la lista desplazada;
se usa una sombra para reconocer la caja movida. Las flechas se conservan y
el asa acepta ↑/↓ con anuncio de posición. El orden se aplica al pulsar Guardar
grupos; cerrar sin guardar descarta el borrador. Se respetan las preferencias
de movimiento reducido y se configura el asa para puntero táctil.

Se usa la biblioteca Motion ya instalada, siguiendo su documentación oficial de
[Reorder](https://motion.dev/docs/react-reorder) y
[asas de arrastre](https://motion.dev/docs/react-use-drag-controls).
No se añade una dependencia ni se cambia el contrato de persistencia.

## Comprobaciones

- Frontend completo: 211 pruebas aprobadas en 27 archivos. La ficha tiene 42
  pruebas, con seis casos nuevos de confirmar/descartar desde el detalle, fallo
  visible, resolución en un único diálogo, corrección de fechas y cancelación,
  y reordenación mediante el teclado del asa. Se comprueban revisión exacta,
  retorno del foco, grupos inicialmente plegados y conservación de IDs,
  descripciones y asignaciones. Pasan las regresiones de edición, conflictos,
  selección contextual, grupos y errores de guardado.
- Compilación TypeScript/Vite correcta; persiste el aviso previo de tamaño del
  paquete de chat. Lint sin errores y con 27 avisos previos en otros archivos.
- Navegador con aplicación compilada y API local ficticia: arrastre nativo en
  escritorio y a 390 × 844, recolocación de cajas, guardado y reapertura del
  orden; arrastre con desplazamiento de la lista y cancelación sin persistir.
  Se restaura el orden original de la demo mediante la interfaz y se comprueba
  que grupos, descripciones y asignaciones son iguales a los iniciales.
- Detalle largo con botones visibles en escritorio/móvil; elección del conflicto
  marca la alternativa, rellena su texto y habilita Guardar solución sin cambiar
  los datos hasta guardar. Se cancela la elección en la demo; el guardado del
  contrato se verifica en las pruebas automatizadas. Documento móvil y ancho
  desplazable: ambos 390 px, sin desbordamiento horizontal.
- Se restablece el tamaño habitual del navegador. Capturas, copia de comprobación
  y estado ficticio permanecen en ubicaciones ignoradas.

## Alcance

Este incremento mantiene el servicio de memoria, la clasificación y los informes.
Las pruebas de navegador usan datos ficticios aislados; no llaman a modelos ni
validan PostgreSQL en esta ronda. El arrastre se verifica con puntero en ancho
móvil; no se ha probado en un teléfono físico.

Plan: [secuencia de ejecución](../technical/business-dossier-ui-plan.md).
