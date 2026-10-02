# Validación · Idioma, menú local y barra para preguntar · 2.5.20

## Resultado

Se han implementado los cuatro pasos del plan separado. La interfaz admite inglés
(por defecto) y español; el entorno de UX queda con inglés seleccionado. Apariencia
y Language son opciones independientes del menú local. En navegación compacta, la
cabecera de Chats muestra únicamente el + sin círculo, alineado con los demás
iconos tras el ajuste 2.5.20.5. La cabecera de Informes compacta usa una rayita
con nombre accesible que sigue abriendo su biblioteca.

La barra inferior ocupa espacio propio, centrada y accesible, en Inicio, Mi negocio,
bibliotecas, informes, análisis, formularios del negocio y ayuda. Conserva el contexto
y el borrador al cambiar de página. Si existe una conversación plegada, usa su
compositor y sus identidades de envío; abrir el panel muestra ese mismo borrador.
Los chats completos y el onboarding mantienen sus compositores propios. El panel
abierto sustituye la barra inferior para evitar dos compositores activos.

## Comprobaciones por paso

1. **2.5.20.1 — `d83f03a`:** 133 pruebas frontend y compilación. Teclado, menú de
   apariencia, persistencia del tema y cabecera compacta.
2. **2.5.20.2 — `7a05a41`:** 142 pruebas frontend, compilación y lint sin errores.
   Idioma persistente, cambio en caliente, formularios y borradores conservados,
   entradas del catálogo e interpolaciones válidas, fechas y números exactos.
3. **2.5.20.3 — `012db35`:** 128 pruebas backend: idioma (5), conversaciones (52),
   onboarding (18), PDF (3), edición/presentación (13) y transporte/contratos del
   modelo (37). También 143 pruebas frontend y compilación. El idioma se guarda en
   la configuración de cada turno/análisis, se conserva en reintentos y llega a las
   instrucciones del modelo; no se convierte en un hecho de memoria del negocio.
4. **2.5.20.4:** 158 pruebas frontend, compilación y lint sin errores. Doce rutas,
   borradores, selección de contexto, conversación existente, envío doble, error y
   reintento con la misma identidad. Regresión de nombres que parecen números y
   decimales de evidencia sin formatear: no se confunden con valores ya formateados.
   Se amplía el catálogo para errores y estados del servidor observados en QA.

5. **2.5.20.5:** 160 pruebas frontend, compilación y lint sin errores. Catálogo
   sin mezcla de chat/conversación en ambas lenguas, claves heredadas de errores
   compatibles y contenido interpolado intacto. Cambio de idioma en caliente para
   la biblioteca, búsqueda, vacíos y controles de chat. Glosario en el plan técnico.
   En navegador: + abre Nuevo chat; la rayita de Informes abre la biblioteca mediante
   Enter; biblioteca Chats y búsqueda coherentes en inglés/español. El centro del
   +, de los iconos de navegación y de los informes coincide en x = 36 px; antes
   el + quedaba en x = 33 px. Se deja inglés seleccionado. No se hacen peticiones
   nuevas al modelo ni cambios de datos para este ajuste.

## Comprobación visual

Navegador local: Inicio, Mi negocio, biblioteca de informes y conversación completa;
abrir, ampliar, reducir y plegar el mismo chat; barra visible antes/después; menú
local con Appearance/Language separados; inglés/español conservando un borrador;
modo claro/oscuro; navegación compacta y tamaño móvil 390 × 844. El tamaño de
comprobación se restablece al terminar. Los borradores creados para QA se vacían.
Las capturas y registros quedan en el directorio local ignorado, fuera de Git.

## Límites verificados

La prueba real usa la configuración existente OpenAI/GPT-6 Luna y guarda idioma
`en`. Tanto el intento como un reintento explícito reciben HTTP 429 del proveedor.
El turno queda guardado y reintentable; la UI presenta el aviso en inglés. No se
atribuye ese rechazo a la interfaz ni se declara comprobada una respuesta real o un
nuevo informe real en inglés. Los contratos, la propagación, la persistencia y las
exportaciones se comprueban con pruebas locales; la calidad lingüística del modelo
real queda pendiente mientras el proveedor rechace las peticiones.

Sin respuesta a la aclaración opcional sobre traducir el historial, se conserva el
texto de mensajes, informes, datos y nombres existentes. Por eso un informe creado
en español sigue mostrando sus conclusiones en español dentro de la interfaz
inglesa. Los textos nuevos se solicitan en el idioma elegido. Los valores exactos
formateados cambian separadores en pantalla sin alterar cálculos ni identificadores.

La compilación mantiene el aviso existente de tamaño de algunos paquetes. Lint
mantiene avisos de Fast Refresh y efectos; no hay errores. Se revisan los archivos
preparados para Git, sin credenciales, datos de runtime ni rutas personales. Los
commits son locales; no se hace push.
