# 2.5.37 — Transiciones del objetivo

## Secuencia

1. **Tarjetas y objetivo.** Al seleccionar, recoger la cuadrícula con altura y
   opacidad animadas. Mostrar el objetivo compacto junto al campo y «Cambiar»
   para volver a elegir. Conservar el texto, el contexto y la intención de envío.
   En próximos objetivos, ofrecer continuar como pregunta sin enviar el borrador.
2. **Texto y accesibilidad.** Fundido breve del título y del ejemplo vacío del
   campo; mantener el mismo textarea y detener la animación al escribir. Salidas
   de tarjetas fuera del teclado y del árbol accesible, foco consistente al elegir
   y al abrir/cerrar, Escape para cerrar. Sin esperas con movimiento reducido.
3. **Validación y cierre.** Comprobar selección, reapertura y cierre, borradores,
   teclado, futuros, recarga, rutas antiguas, idiomas y reintentos. Build/lint y
   navegador en escritorio/móvil; revisión y commit local. Sin selector de tablas.

Estado: completado y validado el 2026-10-08.

## Resultado y validación

- Cuadrícula recogida/reabierta en 260 ms; objetivo compacto y «Cambiar» junto
  al campo. Foco en la tarjeta seleccionada al abrir y en el mensaje al elegir
  o cerrar, incluido Escape. Los controles salientes quedan inertes y ocultos
  del árbol accesible durante la transición.
- Título y etiqueta con fundido/desplazamiento breve; ejemplo vacío en 160 ms.
  El textarea permanece montado, con su borrador y contexto. Escribir cancela
  el fundido del ejemplo; movimiento reducido evita desplazamientos y esperas.
- Futuros conservan «Próximamente» y envío bloqueado. «Continuar como pregunta»
  conserva el texto y cambia el objetivo sin enviar ni ejecutar funciones futuras.
- 300 pruebas frontend correctas en 39 archivos. Incluyen reapertura, Escape,
  mismo campo/borrador, cancelación al escribir, movimiento reducido, futuros,
  traducción y regresiones de envío/reintentos y rutas anteriores.
- Build y lint correctos, con los avisos existentes de tamaño de chunks y lint.
  Revisión del diff y archivos públicos, sin datos locales añadidos a Git.
- Navegador en escritorio 1280×720 y móvil 390×844: un solo campo, foco y texto
  conservados, objetivos y reapertura correctos, sin desbordamiento horizontal.
  Capturas y registros locales en `.local/checks/goal-motion-*`, fuera de Git.
