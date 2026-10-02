# Navegación y controles del chat · 2.5.19

## Contexto y decisiones acordadas

El sidebar repite las bibliotecas de Conversaciones e Informes en la navegación
principal y en sus listas recientes. El botón grande de Nuevo chat domina una
aplicación cuyo punto de partida es el negocio. El chat lateral se cierra arriba,
pero se recupera abajo; la vista completa no ofrece un control inverso claro para
volver al panel. El selector de negocios y la apariencia también necesitan una
ubicación estable.

El usuario ha aceptado mantener Inicio y Mi negocio como accesos principales,
agrupar Chats e Informes con enlaces directos, colocar un + junto a Chats y mostrar
Ver todos al superar el límite de la lista. Las cabeceras de los grupos conservan
acceso a sus bibliotecas para no perder sus herramientas. El resto de páginas,
informes, datos y funciones permanece igual.

Se utiliza el patrón de selector superior y menú inferior de
[shadcn sidebar-07](https://ui.shadcn.com/blocks/sidebar), consultado mediante
`npx shadcn add sidebar-07 --dry-run` y `--view`. Se adaptan únicamente las piezas
solicitadas; no se reemplazan componentes compartidos ni se importa el dashboard
de ejemplo. No existe un perfil de usuario en este entorno local: el menú inferior
identifica el espacio real, sin nombres, correos ni acciones de cuenta ficticios.

## Pasos, en orden

1. **2.5.19.1 — Una sección por biblioteca.** Retirar Conversaciones e Informes de
   la navegación principal. Grupos Chats e Informes con accesos directos, biblioteca
   en la cabecera y Ver todos cuando excedan seis chats o cinco informes. Mantener
   el elemento activo aunque quede fuera de los recientes. Comprobar rutas, estados
   vacíos, límites, selección y acceso a todas las herramientas de las bibliotecas.
2. **2.5.19.2 — Nuevo chat junto al grupo.** Sustituir el botón grande superior por
   un + accesible junto a Chats, también en navegación compacta. Conservar el flujo
   real de nueva conversación y sus borradores; no crear chats al abrir el compositor.
   Comprobar teclado, modo compacto y contexto limpio al empezar uno nuevo.
3. **2.5.19.3 — Abrir y cerrar arriba a la derecha.** Un control superior abre o
   recupera el panel y su botón de cierre ocupa la misma zona. Retirar el acceso
   flotante inferior. Conservar conversación, borrador, contexto seleccionado,
   anchura y coordinación con la navegación. Comprobar cerrar/reabrir y móvil.
4. **2.5.19.4 — Ampliar y reducir como acciones inversas.** Flechas hacia fuera
   para ampliar el panel; flechas hacia dentro para reducir la conversación completa
   al panel. Recuperar su página de origen y posición sin crear ni enviar mensajes.
   Mantener la apertura en panel desde los menús de otros chats. Comprobar ida y
   vuelta, borradores, referencias y conversación abierta directamente.
5. **2.5.19.5 — Apariencia en el menú inferior.** Adaptar el menú de `nav-user`
   para el espacio local, con Claro, Oscuro y Automático y la ayuda existente.
   Retirar el botón de tema superior. Conservar la persistencia y compatibilidad
   con preferencias del sistema. Comprobar menú, selección y navegación compacta.
6. **2.5.19.6 — Selector de negocios en la cabecera.** Adaptar `team-switcher`:
   nombre del negocio activo como cabecera única y lista de negocios al desplegar.
   Usar el cambio de negocio existente, con feedback de error y sin mezclar datos
   ni borradores. Conservar gestión y creación de negocios. Revisar al final las
   seis funciones en escritorio, móvil y ambos temas.

Cada paso se prueba, se revisa y se guarda en un commit local separado. No se
publica en GitHub salvo petición explícita del usuario.

## Estado

- 2.5.19.1 completado: bibliotecas sin duplicación, límites y selección conservados.
  Validación: 123 pruebas de frontend y compilación correctas.
- 2.5.19.2 completado: + accesible junto a Chats, también compacto; apertura
  sin crear conversaciones y borrador conservado. 124 pruebas y compilación correctas.
- 2.5.19.3 completado: apertura y reapertura en la barra superior, cierre alineado,
  sin acceso flotante ni espacio inferior reservado. 124 pruebas y compilación;
  apertura/cierre verificados en navegador y continuidad de borradores en pruebas.
- 2.5.19.4 completado: flechas inversas y retorno a la página y posición de origen,
  con borrador intacto y sin envíos; apertura directa usa última página o Inicio.
  Validación: 126 pruebas y compilación correctas.
- 2.5.19.5 completado: menú inferior del espacio local con Claro, Oscuro,
  Automático y ayuda; sin botón de tema superior. 130 pruebas y compilación,
  incluida persistencia de las tres opciones y navegación por teclado.
- 2.5.19.6 completado: cabecera única con selector directo de negocios reales,
  gestión y creación, espera del servidor y errores recuperables. 133 pruebas,
  compilación y lint sin errores; aceptación en escritorio, iconos, móvil y temas.

Los seis pasos están completos. Véase la
[validación y sus límites](../validation/2026-09-30-navigation-and-chat.md).
