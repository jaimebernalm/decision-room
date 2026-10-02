# Navegación y continuidad del chat · 30 de septiembre de 2026

Implementación del [plan 2.5.19](../technical/navigation-and-chat-plan.md), en
seis pasos con commits locales. Se adapta el selector de negocios y el menú
inferior de sidebar-07 sobre los componentes existentes. El comando shadcn se
consultó con `--dry-run` y `--view`: no se sobrescribieron las primitivas compartidas
ni se importaron páginas, dependencias o datos del dashboard de ejemplo.

## Comprobaciones por paso

| Paso | Comportamiento comprobado | Pruebas frontend | Commit local |
| --- | --- | --- | --- |
| 2.5.19.1 | Grupos únicos, bibliotecas, límites, vacíos y elemento activo fuera de los recientes | 123 | `4f599ac` |
| 2.5.19.2 | + junto a Chats; abrir sin crear; borrar contexto al empezar un chat nuevo y recuperar el borrador al continuar | 124 | `01d712d` |
| 2.5.19.3 | Apertura superior, cierre/reapertura con conversación, borrador y contexto intactos; sin acceso flotante | 124 | `7ade104` |
| 2.5.19.4 | Ampliar/reducir, informe y posición originales, borrador sin enviar, origen guardado y fallback a Inicio | 126 | `08d15b7` |
| 2.5.19.5 | Claro/Oscuro/Automático persistentes, selección marcada, teclado, Escape y ayuda | 130 | `c68a154` |
| 2.5.19.6 | Lista real de negocios; espera del servidor, error recuperable y cambio entre espacios sin mezclar chats ni borradores | 133 | Commit de cierre de este paso |

En cada paso pasó `npm run build`. La comprobación final ejecutó `npm test --
--reporter=dot` (22 archivos, 133 pruebas), `npm run build`, `npm run lint` y
`git diff --check`. Lint terminó sin errores; mantiene advertencias de los
componentes existentes sobre Fast Refresh y efectos de React. La compilación
mantiene el aviso de tamaño del paquete del chat. No se modificaron backend,
modelo, cálculos, archivos de datos ni presentación de los informes.

## Aceptación visual

Comprobado en el navegador local, con la interfaz y los datos de pruebas existentes:

- Sidebar expandido: negocio como cabecera única, Inicio/Mi negocio, grupos
  Chats/Informes, + discreto y menú inferior del espacio local.
- Sidebar compacto: selector superior e inferior por iconos; bibliotecas y +
  permanecen accesibles incluso cuando las listas no necesitan Ver todos.
- Tema oscuro desde el menú inferior; se volvió al tema claro original.
- Informe abierto desde el sidebar: abrir un chat guardado en panel, ampliar y
  reducir retorna al mismo informe; cerrar muestra el control de continuar arriba.
- Pantalla móvil de 390 × 844: drawer con grupos y menús, chat como panel completo
  con ampliar/cerrar arriba y acceso a su compositor. Se restauró el viewport de
  escritorio al terminar.
- Capturas conservadas localmente en el directorio ignorado `.local/screenshots`.

## Límites de la validación

El entorno contiene un solo negocio de pruebas. La selección real entre dos
negocios y su fallo se cubren con pruebas de integración de App y del selector,
con respuestas del servidor simuladas. No se crearon negocios adicionales ni se
enviaron mensajes durante la aceptación visual. La conservación de una posición
no nula del informe se verifica en la prueba de ida/vuelta (140), además del
retorno visual a la ruta original. Automático se valida como preferencia persistente
`system`, usando el proveedor de temas ya existente.

El menú inferior representa el espacio local porque no hay cuenta de usuario en
esta aplicación. No se añadieron acciones ficticias de perfil, facturación o salida.
