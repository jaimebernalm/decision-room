# Bienvenida y onboarding de primera visita

27 de septiembre de 2026 · paso 2.5.15.

## Recorrido

- `#welcome` presenta el producto y permite empezar o entrar al espacio. Se puede
  visitar sin sesión y desde un negocio existente. La ilustración está identificada
  como ejemplo y no utiliza cifras privadas.
- Sin negocios, la entrada abre la bienvenida. `#onboarding` empieza un negocio
  nuevo y `#business-new` conserva compatibilidad con los enlaces anteriores.
- El recorrido tiene tres pasos: contexto del negocio, selección de datos y
  revisión del primer informe. Usa una cabecera propia, sin navegación del
  dashboard, chats recientes ni selector de negocios.
- El contexto se guarda en el servicio existente y puede editarse al volver al
  primer paso. Los archivos seleccionados se conservan al navegar hacia atrás
  dentro del recorrido. Tras recargar, se conserva el texto y se explica que los
  archivos sin enviar deben seleccionarse otra vez.
- El tercer paso muestra el negocio, los archivos y el objetivo opcional antes
  de iniciar el informe. La carga reutiliza el servicio de entregas de datos;
  sus claves se conservan hasta recibir la respuesta de creación del informe.
- Las aclaraciones, los errores recuperables y el progreso son los del trabajo
  real. Solo un informe publicable abre su resultado en el espacio habitual.
- Un negocio con contexto guardado y sin informes reanuda la selección de datos
  al entrar a Inicio. Un enlace de onboarding de otro negocio queda bloqueado.

## Comprobaciones

- TypeScript y Vite: compilación correcta. El onboarding se carga bajo demanda.
  Permanece el aviso de tamaño del chunk de chat preexistente.
- Lint: sin errores ni avisos nuevos en los componentes de este paso; continúan
  los avisos existentes de componentes compartidos.
- Suite de frontend: 41 pruebas aprobadas, incluidas ocho específicas del nuevo
  onboarding. Cubren entrada sin sesión y conservación de la intención de empezar,
  bienvenida con un negocio existente sin mutaciones, negocio → datos → resumen
  → aclaraciones, navegación atrás, respuesta perdida al crear negocio y al crear
  informe, recuperación después de recargar, bloqueo por negocio distinto y
  apertura del primer resultado publicado. Una carpeta mixta comprueba el recuento
  de archivos omitidos, los archivos fallidos y la continuación con las tablas
  disponibles tras mostrar el resultado de la preparación parcial.
- Regresión del servicio web: 32 pruebas aprobadas sobre creación, autenticación,
  idempotencia, recuperación, aislamiento y publicación.
- Navegador con servidor Python, base temporal, archivos sintéticos y modelo
  controlado: acceso desde la bienvenida, creación del negocio, selector nativo,
  resumen, envío, aclaraciones y publicación. También se comprueba la integración
  del onboarding con la carga por entregas y la creación desde datos preparados.
- Revisión visual de bienvenida y formulario a 390 px y 1280 px; sin
  desbordamiento horizontal. El foco pasa al contenido del nuevo paso y las
  acciones conservan etiquetas accesibles.

La comprobación móvil detectó que los inputs nativos de archivos, visualmente
ocultos, ampliaban el ancho de la página. Se corrige su ocultación y se comprueba
que los botones siguen abriendo el selector. Tab desde el contenido enfoca
«Seleccionar archivos»; el selector y los pasos siguen disponibles por teclado.

Se corrigió en la comprobación HTTP la lectura del resultado de `/api/business`:
su contrato entrega `{business: ...}`. La prueba React usa ese contrato. La
creación conserva además el identificador de petición y la selección original
del negocio, de modo que una respuesta perdida no convierte el reintento en otro
negocio.

## Límites

El acceso sigue siendo el del espacio local mediante clave. No se ha añadido
registro comercial con correo. La validación con modelo controlado comprueba
el recorrido y la integración, no la calidad de un nuevo modelo analítico. Los
límites y la validación de grandes entregas de datos pertenecen al trabajo de
carga de carpetas; este paso verifica su conexión con el primer informe.

## Reproducción

```sh
npm --prefix frontend test
npm --prefix frontend run build
npm --prefix frontend run lint
.venv/bin/python -m unittest discover -s tests -p test_web.py
```

Los servidores, bases y archivos empleados para la comprobación visual son
temporales y están separados del espacio del propietario. No se incorporan al
repositorio.
