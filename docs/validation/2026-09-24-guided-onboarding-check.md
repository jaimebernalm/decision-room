# Primer informe guiado · comprobación del 24 de septiembre de 2026

## Alcance

La entrada local conduce a un onboarding independiente del dashboard: contexto
del negocio, primer CSV y elección de informe, aclaraciones del agente, progreso
y primer informe revisado. Una fila `web_onboarding` identifica solo a los
negocios creados por este recorrido y conserva el trabajo y su cierre. Los
negocios anteriores no quedan inscritos automáticamente.

## Comprobaciones

- **Automáticas:** 33 pruebas web Python, incluidas migración y transición
  persistente del onboarding; 15 pruebas JavaScript; comprobación de sintaxis de
  ambos archivos JavaScript y `git diff --check`.
- **Navegador, modelo real:** en una base aislada, se completaron negocio y CSV
  de ejemplo sin mostrar la navegación del dashboard. Qwen formuló una
  aclaración sobre el grano y `sales_ex_tax`; la respuesta se guardó y el
  análisis continuó. Una recarga recuperó la etapa de progreso. El revisor pidió
  ajustes y luego una petición a Qwen agotó el tiempo de espera (`ReadTimeout`).
  El onboarding mostró el fallo y permitió reintentar desde el checkpoint. El
  reintento volvió a agotar el tiempo durante la revisión. Este caso no se
  cuenta como informe terminado.
- **Navegador, modelo controlado:** el caso de ventas del repositorio produjo
  un informe publicable después de dos aclaraciones. El informe se mostró
  dentro del paso 3, con enlace a la evidencia. «Entrar a mi espacio» abrió
  Inicio con el informe y sus hallazgos; una recarga mantuvo Inicio. Este caso
  comprueba el recorrido de interfaz, no la calidad analítica del modelo real.
- **Estados adversos:** la API rechaza el cierre antes de un informe publicable,
  impide crear un trabajo ajeno al onboarding pendiente y permite empezar con
  otro archivo si el trabajo anterior queda bloqueado. El envío tiene clave
  idempotente y el trabajo anterior se conserva.
- **Diseño:** comprobación visual en escritorio y a 390 px. En móvil, el tercer
  paso conserva el progreso, el motivo del fallo y ambas acciones de recuperación
  sin mostrar la navegación del dashboard.

## Límites

El primer informe usa un CSV UTF-8 de hasta 20 MB. Otros archivos pueden
añadirse después desde «Mi negocio»; no se combinan automáticamente en el
primer informe. Las preguntas dependen de las ambigüedades reales y un informe
puede quedar bloqueado si la evidencia no basta. El acceso es mediante clave
local; no hay registro por correo ni cuentas multiusuario.
