# Cierre de campos y alta consistente

Refinamiento del paso 2.5.5, comprobado el 7 de octubre de 2026.

- Cada grupo abierto tiene un botón Cerrar. Recoge los campos conservando los
  cambios del borrador y devuelve el foco al lápiz. Guardar sigue aplicando los
  cambios al negocio mediante la revisión existente.
- El formulario de nuevo grupo usa el mismo fondo gris y esquinas que los grupos
  en edición. Su × cancela únicamente la creación pendiente, limpia sus campos y
  devuelve el foco a Nuevo grupo, sin descartar los demás cambios.
- Se retiraron los botones de subir y bajar de los campos abiertos. El orden sigue
  disponible por arrastre y con ↑/↓ sobre el asa; se actualizó su ayuda accesible.

## Validación

1. Suite frontend: 279 pruebas correctas, incluyendo cierre y reapertura conservando
   el nombre, cancelación independiente del alta, retorno de foco, guardado del
   resto del borrador y orden desde el asa con teclado.
2. `npm run build`, `npm run lint` y `git diff --check`: correctos; sin advertencias
   nuevas en los archivos modificados. Permanecen avisos anteriores del proyecto.
3. Navegador local: vista conjunta del grupo abierto y formulario gris a
   1440 × 1200; cierre independiente y revisión a 390 × 900 y 320 × 900, sin
   desbordamiento horizontal. Se cancelaron los borradores de prueba y se restauró
   el tamaño habitual del navegador. Captura en `.local/visual-checks/`, fuera de Git.
4. La primera ejecución completa tuvo un fallo intermitente en una prueba existente
   de paginación de vistas de datos; la repetición completa pasó. No se modificó
   la vista de datos para este incremento.

Solo cambió la presentación y el manejo local de los campos. No se modificaron
contratos del servidor ni datos del negocio durante la comprobación visual.
