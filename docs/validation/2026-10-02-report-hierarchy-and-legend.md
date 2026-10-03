# Jerarquía de hallazgos y leyenda · 2 de octubre de 2026

Paso 3.9.8.2, solicitado al revisar Bruma Café en la aplicación habitual.

Los títulos de hallazgos pasan de 16 px a 20 px, y 24 px desde el tamaño
pequeño de escritorio. La numeración crece de 28 a 32 px. Los títulos de gráficos
conservan su tamaño, para distinguir la conclusión de su evidencia visual.

El selector de periodo desaparece en gráficos sin `details` guardados, como los
cuatro de Bruma. Hover y tooltip siguen disponibles. Las tablas completas y
valores exactos permanecen en el detalle del hallazgo, y en gráficos independientes.
Si hay desglose adicional, el acceso por teclado se conserva en «Ver desglose
por periodo», plegado inicialmente y con un placeholder explícito. No se
elimina evidencia ni se altera la navegación existente hacia hallazgos o desgloses.

En líneas agrupadas, las series visibles tienen fondo oscuro, texto claro y un
ojo abierto. Las ocultas se muestran atenuadas, con texto tachado y ojo cerrado.
El tooltip del botón explica «Mostrar» u «Ocultar», y la ayuda de la leyenda
explica el clic. `aria-pressed` y el nombre accesible indican el estado. La última
serie visible permanece activa; el botón explica esa condición. Ocultar y
restaurar son cambios locales de vista: las tablas conservan todos los valores.
Los textos nuevos están traducidos a inglés y español.

## Comprobaciones

- 233 pruebas frontend en 30 archivos pasan. Las regresiones comprueban ausencia
  del selector redundante, desglose por teclado, ocultar/restaurar, bloqueo de la
  última serie, navegación sin llamadas y precisión de cifras guardadas.
- Compilación TypeScript/Vite correcta y lint sin errores. Permanecen avisos
  existentes de lint y tamaño del paquete. No se modifican componentes generales
  para eliminar avisos ajenos a este incremento.
- Bruma en `http://127.0.0.1:8787/`: tres títulos a 24 px, cuatro gráficos sin
  selectores de periodo y leyendas oscuras. Al ocultar Café de origen el estado
  pasa a no pulsado, cambia a fondo claro y aparece texto tachado con la acción
  de mostrar; restaurarlo devuelve el estado pulsado. Se deja el informe abierto
  con todas las series visibles. Captura de demostración en `.local/`, fuera de Git.
- Inspección en el tamaño habitual del navegador. No se realiza una nueva prueba
  móvil en este paso. No se llaman modelos, recalculan datos o cambian aprobaciones.

Se revisan los archivos preparados antes del commit local; fuentes y capturas
privadas permanecen fuera de Git. No se hace push.
