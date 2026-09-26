# Informes y secuencia de nuevo chat — 26 de septiembre de 2026

Paso 2.5.12 del plan.

## Cambios

- La tarjeta de la tabla pierde el espacio superior/inferior: tabla y contenedor
  comparten límites. La cabecera no cambia de fondo al pasar el cursor; cada fila
  de datos cambia completa, también al recibir foco dentro. La flecha no añade
  otro fondo independiente. En móvil se ocultan fecha y flecha redundante; el
  título y la fila siguen abriendo el elemento.
- Los enlaces del listado y del panel lateral abren directamente los informes
  disponibles y sus versiones históricas. Los trabajos en curso también aparecen
  en Informes y abren la vista de progreso/aclaraciones existente. Los estados
  retirado o desactualizado mantienen su acceso a recuperación; no se presentan
  como informes vigentes. Cuando la vista de trabajo recibe `publishable`, abre
  automáticamente el informe. La autorización para publicar sigue en el servidor.
- Cabecera sin nombre/ruta duplicados, separadores ni etiqueta «Local». Conserva
  menú, cambio de tema y flecha de vuelta en vistas de detalle: informe a biblioteca,
  informe de chat a conversación, conversación a historial. Se retira «Volver»
  junto a imprimir.
- La barra pasa al centro en 240 ms; título y recientes permanecen ocultos pero
  conservan su espacio hasta terminar el movimiento. En una visita directa,
  sin transición compartida, se revelan tras 320 ms. Movimiento reducido muestra
  el contenido sin espera. El borrador conserva el contrato anterior.

## Validación

- 27 pruebas de frontend aprobadas, incluyendo destinos según estado, apertura
  desde biblioteca y desde un trabajo ya publicable, regreso desde la cabecera y
  contenido de nuevo chat inicialmente oculto con el campo de texto disponible.
- Compilación TypeScript/producción correcta; lint sin errores. Persisten los
  14 avisos previos de los componentes oficiales y el aviso del fragmento de chat
  de unos 504 kB.
- Navegador: pulsar una celda de estado abrió directamente el informe revisado;
  la flecha devolvió a Informes. Tabla y tarjeta tienen exactamente el mismo
  rectángulo en escritorio. Cabecera sin texto repetido ni líneas.
- Transición observada: mientras la barra todavía tenía transformación vertical,
  el título estaba oculto; al finalizar, transformación nula y título visible.
- Revisión a 390 × 844, con el tamaño habitual restaurado al terminar.
- `git diff --check` sin errores. No se cambian datos ni servicios del backend.

## Nomenclatura unificada: paso 2.5.13

- Una sola sección «Informes», sin «Todos los análisis» ni «Ver análisis».
  Navegación principal: Inicio, Conversaciones, Informes y Mi negocio. Los
  accesos recientes quedan como Chats recientes e Informes recientes.
- Acciones «Crear informe», campo «Título del informe», búsqueda «Buscar
  informes», columna «Informe» y enlaces del chat «Ver informe». Estados de la
  biblioteca: En preparación, Necesita tu respuesta, Disponible y los estados
  existentes de interrupción, retirada o cambio de contexto.
- Los mensajes sobre la actividad de la IA pueden seguir hablando de análisis.
  No se renombra el contrato de almacenamiento ni se crean resultados nuevos.
- La antigua ruta `#analyses` resuelve a la misma biblioteca y activa Informes
  en el menú. Los enlaces existentes a trabajos conservan su funcionamiento.
- 28 pruebas aprobadas, incluida compatibilidad del listado antiguo y apertura
  directa del resultado; compilación correcta, lint sin errores con los avisos
  previos. Navegador: los cuatro destinos principales, biblioteca unificada y
  formulario «Crear informe» con su campo «Título del informe» verificados.
