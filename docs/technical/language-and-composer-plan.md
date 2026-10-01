# Idioma, menú local y barra para preguntar · 2.5.20

## Contexto

Tras aprobar 2.5.19, el usuario pide cuatro ajustes: en navegación compacta,
un solo + con círculo en la cabecera de Chats; Apariencia como opción dentro del
menú inferior, junto con Idioma; una versión completa en inglés de la aplicación;
y una barra centrada para preguntar en las páginas del negocio, conservando el
control superior del panel. Se implementan y prueban por pasos con commits locales.

Español e inglés serán seleccionables y persistentes. Al terminar se seleccionará
inglés en el entorno solicitado. No se modifican identificadores, cifras ni datos
subidos para cambiar el idioma. Se ha solicitado una aclaración sobre el contenido histórico. Mientras no llegue
una indicación distinta, se aplica inglés a la interfaz y al contenido nuevo;
los mensajes, nombres, informes y datos ya guardados conservan su texto original.

## Pasos

1. **2.5.20.1 — Menú y navegación compacta.** Ocultar el acceso a la biblioteca de
   Chats en su cabecera compacta y centrar un + con círculo; mantener el acceso
   completo en navegación expandida y las conversaciones. Apariencia se convierte
   en un submenú con Claro/Oscuro/Automático; la ayuda permanece independiente.
   Probar accesibilidad, menú, persistencia y navegación compacta.
2. **2.5.20.2 — Interfaz bilingüe completa.** Crear catálogo central de traducciones,
   preferencia de idioma persistente y opción Idioma en el menú inferior. Traducir
   controles, accesibilidad, formularios, vacíos, errores, ayuda, onboarding,
   bibliotecas, proceso, editor y vistas de datos. Localizar fechas/números de UI.
   Mantener contratos y datos estables. Probar cambios en caliente, persistencia,
   cobertura del catálogo, inglés y español en las páginas representativas.
3. **2.5.20.3 — Idioma del contenido nuevo.** Según la aclaración del usuario,
   aplicar el idioma seleccionado a nuevas respuestas, preguntas e informes,
   propagándolo explícitamente hasta el servidor y sus agentes. No convertir esta
   preferencia de interfaz en un hecho del negocio ni alterar datos históricos.
   Probar validación, persistencia por petición, aislamiento y generación.
4. **2.5.20.4 — Compositor en las páginas del negocio.** Barra inferior centrada
   dentro del marco del espacio de trabajo, sin cubrir contenido. Las conversaciones
   completas y el onboarding conservan sus compositores propios. Al abrir el panel,
   la escritura se realiza en él. Mantener borrador, contexto, negocio, envío único,
   errores y continuidad. Probar las rutas, móvil, tema y recorrido completo en inglés.

5. **2.5.20.5 — Terminología y navegación compacta.** Usar chat/chats en ambas
   interfaces, incluida ayuda, errores y accesibilidad; conservar claves compatibles
   y textos del usuario. Quitar el círculo del + y alinearlo con los demás iconos.
   Reemplazar el icono duplicado de la cabecera de Informes por una rayita accesible
   que siga abriendo la biblioteca. Probar ambos idiomas, navegación y geometría real.

## Glosario

| Concepto | Español | Inglés |
| --- | --- | --- |
| Intercambio con el asistente | Chat / Chats | Chat / Chats |
| Crear un chat | Nuevo chat | New chat |
| Documento de resultados | Informe / Informes | Report / Reports |
| Página principal | Inicio | Home |
| Espacio del negocio | Mi negocio | My business |

Análisis designa el proceso; informe, su documento. Los títulos y mensajes escritos
por el usuario conservan sus palabras. Las claves de traducción y campos técnicos
existentes pueden mantener sus nombres para compatibilidad.

## Estado

- 2.5.20.1 completado: + circular compacto y Apariencia como submenú.
  Pasan 133 pruebas frontend y compilación, incluida persistencia y teclado.
- 2.5.20.2 completado: interfaz bilingüe, preferencia persistente, fechas y números
  exactos según idioma. Pasan 142 pruebas frontend, compilación y lint sin errores.
  Comprobados en navegador los menús separados y las vistas Inicio/Mi negocio en inglés.
  Los textos históricos del negocio conservan su idioma original.
- 2.5.20.3 completado: idioma por petición, guardado en turnos/análisis y utilizado
  por el modelo en textos nuevos; onboarding y etiquetas de exportación bilingües.
  Los reintentos mantienen su idioma y las preferencias no alteran hechos ni textos
  históricos. Pasan 128 pruebas backend y 143 frontend, además de compilación.
- 2.5.20.4 completado: barra centrada en las páginas del negocio, composición
  compartida con el chat plegado, contexto y borrador conservados, un solo envío.
  Pasan 158 pruebas frontend, compilación y lint sin errores; comprobados escritorio,
  móvil, ambos temas, cambio de idioma y continuidad del panel.

- 2.5.20.5 completado: glosario coherente en controles, ayuda, accesibilidad y
  errores de servidor; + sin círculo y alineado con los iconos; cabecera de Informes
  compacta con una rayita que abre la biblioteca. Pasan 160 pruebas frontend,
  compilación y lint sin errores; comprobadas ambas lenguas y navegación con teclado.

Los cuatro pasos originales quedan terminados. La prueba con el proveedor real recibe HTTP 429
y no permite comprobar una respuesta nueva real en inglés. Los textos históricos
permanecen en su idioma original. Véanse [validación y límites](../validation/2026-09-30-language-and-composer.md).

No se hace push sin una petición explícita.
