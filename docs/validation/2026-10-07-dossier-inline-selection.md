# Selección visible y edición de grupos en la columna

Incremento del paso 2.5.5, comprobado el 7 de octubre de 2026.

## Comportamiento

- Seleccionar resalta la conexión bajo el puntero y el mapa completo al apuntar
  a su botón. El foco de teclado conserva una indicación equivalente. Pasar el
  ratón no añade contexto; las selecciones y sus estados siguen siendo reversibles.
- Datos → Tablas permite adjuntar una tabla concreta, manteniendo su consulta y
  descarga habituales fuera de la selección. La referencia contiene el análisis,
  la revisión guardada y el identificador de la tabla preparada, resuelto por su
  fuente única. El servidor obtiene el esquema, columnas y cantidad de filas;
  rechaza referencias ajenas, inventadas, obsoletas o no disponibles. No admite
  contenido proporcionado por el cliente como contexto autorizado.
- Personalizar grupos activa la edición dentro de la columna: grupos más oscuros,
  animación breve, asa para ordenar, lápiz para nombre y descripción, × para
  eliminar y + para añadir. Las descripciones también están disponibles al
  apuntar o enfocar el grupo. La animación se desactiva con movimiento reducido.
- Guardar mantiene la revisión, asignaciones, validaciones y errores existentes.
  Cancelar o Escape descarta el borrador y devuelve el foco al control inicial.
  Navegar por un grupo durante la edición no envía el formulario. Eliminar un
  grupo conserva su información; Por revisar y Otros son grupos protegidos.
- Por revisar aparece siempre primero, también a cero; su contador es rojo si
  hay pendientes. Otros muestra el grupo de reserva existente (`ungrouped`),
  incluso vacío, sin migrar ni reclasificar memorias guardadas.
- Mantener el ratón y arrastrar desplaza el contenedor de Datos o Historial cuando
  hay contenido fuera de la vista. Se conserva el orden cronológico del historial.
  El mapa conserva su gesto propio, y enlaces, controles y desplazamiento táctil
  mantienen su interacción. Arrastrar una fila de tabla no abre su vista previa;
  un clic normal sí la abre. Mayús conserva la selección habitual de texto.

## Comprobaciones

1. `npm test -- --reporter=json`: 278 pruebas frontend correctas, incluyendo
   selección/deselección por puntero y teclado, retorno a la tabla de origen,
   modelos obsoletos, preselección sin adjuntar, navegación sin guardado accidental,
   edición, conflictos de revisión, cancelación, orden y conservación de memorias.
   Las pruebas de arrastre cubren umbral, clic posterior, cancelación y exclusión
   de enlaces, mapa, tacto y selección de texto.
2. `npm run build` y `npm run lint`: correctos, sin advertencias nuevas en los
   archivos modificados. Persisten advertencias anteriores de tamaño de bundles
   y de componentes compartidos.
3. `PYTHONPATH=tests .venv/bin/python -m unittest test_data_knowledge test_conversations test_context_references`:
   76 pruebas correctas. Selección exacta, aislamiento entre negocios, revisiones
   obsoletas, envío del contexto a un agente simulado, recarga de adjuntos y
   retirada de referencias tras corregir el modelo. Las pruebas usan bases
   temporales y datos sintéticos.
4. Navegador local: revisión a 1440 × 1000, 390 × 900 y 320 × 900, además de
   390 × 600 para comprobar Datos con desplazamiento. Se corrigió la distribución
   de los campos abiertos y el ancho de las descripciones en pantallas estrechas.
   Sin desbordamiento horizontal a 320 y 390 píxeles. Guardar y Cancelar son
   accesibles al recorrer el contenido.
5. Arrastre real del historial: desplazamiento de 360 píxeles, sin dejar el estado
   de arrastre activo. Arrastre real de Datos: avance de 100 píxeles. Arrastre real
   de grupos: cambió el orden del borrador y Cancelar recuperó el orden guardado.
   Una conexión bajo el puntero mostró resaltado y permaneció sin seleccionar.
   Seleccionar una tabla mostró su adjunto concreto y pudo deshacerse.
6. Capturas y resultados bajo `.local/`, excluidos de Git. Revisión del diff público
   y `git diff --check`, conservando los cambios ajenos al incremento.

## Límites de la comprobación

El arrastre en Datos e Historial se interpreta como desplazamiento de la vista,
no como reordenación de archivos o revisiones. Las pruebas de tamaño móvil se
hicieron redimensionando el navegador; no constituyen pruebas en dispositivos
físicos. El envío de contexto se comprueba con agentes simulados, sin consumir
una llamada a un modelo real ni enviar mensajes desde el negocio local. Los
cambios de grupos probados en el navegador se cancelaron.
