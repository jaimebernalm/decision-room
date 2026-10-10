# Apertura y cierre fluidos del panel derecho

Paso 2.5.26, 6 de octubre de 2026.

El panel anterior aparecía con su anchura final y solo cambiaba de opacidad.
La página se estrechaba al abrirlo y recuperaba su espacio de golpe al terminar
el cierre. Ahora se anima una proporción de apertura durante 280 ms, independiente
de la anchura elegida por el propietario. El contenido del chat conserva su
anchura dentro de un contenedor que lo recorta durante la transición.

El tirador acompaña al borde de la página y desaparece durante el cierre. Los
ajustes de anchura por arrastre o teclado siguen siendo inmediatos. En móvil el
panel se desliza sobre la página, que mantiene su anchura y queda inerte mientras
el chat está abierto; seleccionar contexto devuelve el acceso a la página. El
panel saliente queda inerte y oculto para tecnologías de asistencia. Se conserva
la duración cero cuando `useReducedMotion` indica movimiento reducido.

## Comprobaciones

- `npm --prefix frontend test`: 225 pruebas en 30 archivos, todas pasan. Incluyen
  ajuste de anchura, cierre/reapertura, borradores, mensajes pendientes y selección
  de contexto.
- `npm --prefix frontend run build`: TypeScript y Vite pasan.
- `npm --prefix frontend run lint`: sin errores; 27 avisos existentes. Se mantiene
  también el aviso existente de tamaño de paquetes en la compilación.
- Localhost 8787, escritorio 1280 × 900: las lecturas sucesivas del DOM muestran
  crecimiento gradual del espacio del panel (336,45 → 411,11 px hacia 420 px) y
  reducción gradual al cerrar (101,22 → 3,77 px hacia cero), con la página ocupando
  el espacio restante. El contenido del chat mantiene 420 px durante la apertura.
- Ajuste por teclado: 420 → 444 px inmediatamente, con la proporción de apertura
  estable en 1; vuelta a 420 px. El centro del tirador y el borde de la página
  coinciden en x=852 px tras la compilación final.
- Reapertura durante el cierre: un único panel y el mismo borrador. El borrador
  de prueba se elimina al finalizar; no se envían mensajes ni se crean chats.
- Móvil 390 × 844: panel y página de 390 px, anchura desplazable del documento de
  390 px, desplazamiento horizontal al abrir/cerrar y panel retirado al finalizar.
  Seleccionar contexto y volver al chat funcionan. Se restablece el viewport.
- Revisión de diferencias y `git diff --check` sin incidencias.

La captura permanece en `.local/checks/`, fuera de Git. No se repite la evaluación
del agente ni se modifican contratos backend. La preferencia de movimiento
reducido se conserva en el código, sin cambiar la configuración del sistema.
