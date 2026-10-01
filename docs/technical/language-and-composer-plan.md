# Idioma, menú local y barra para preguntar · 2.5.20

## Contexto

Tras aprobar 2.5.19, el usuario pide cuatro ajustes: en navegación compacta,
un solo + con círculo en la cabecera de Chats; Apariencia como opción dentro del
menú inferior, junto con Idioma; una versión completa en inglés de la aplicación;
y una barra centrada para preguntar en las páginas del negocio, conservando el
control superior del panel. Se implementan y prueban por pasos con commits locales.

Español e inglés serán seleccionables y persistentes. Al terminar se seleccionará
inglés en el entorno solicitado. No se modifican identificadores, cifras ni datos
subidos para cambiar el idioma. La traducción de contenido histórico está pendiente
de la aclaración solicitada al usuario; el trabajo de interfaz puede avanzar.

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

## Estado

- 2.5.20.1 completado: + circular compacto y Apariencia como submenú.
  Pasan 133 pruebas frontend y compilación, incluida persistencia y teclado.
- 2.5.20.2–2.5.20.4 pendientes.

No se hace push sin una petición explícita.
