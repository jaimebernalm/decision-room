# Integración del dashboard con memoria y conversaciones

**Fecha:** 23 de septiembre de 2026.  
**Resultado:** dashboard integrado con las funcionalidades existentes hasta 2.5.4.
Es un avance de 2.5.6; no cierra la ficha/archivos de 2.5.5 ni 2.5.7.

## Comprobaciones

- **232 pruebas de Python aprobadas**, con PostgreSQL real y regresión completa
  (`.venv/bin/python -m unittest discover -s tests`, 111 segundos). Incluyen
  selección de informe, autenticación, aislamiento por negocio, publicación
  explícita desde chat y retirada del dashboard tras correcciones de memoria.
- **7 pruebas JavaScript aprobadas** (`node --test tests/test_dashboard_ui.cjs`):
  primer mensaje sin CSV, respuesta de creación perdida, respuesta de envío
  perdida, doble envío, navegación/cambio de negocio durante la petición,
  conservación de borradores y sugerencias acordes con los datos disponibles.
  Un reintento de mensaje usa el identificador de chat ya persistido, incluso
  si el agente ha seleccionado datos desde el primer intento.
- Sintaxis JavaScript, revisión estática de los módulos Python nuevos/modificados
  comprobados y `git diff --check` correctos.
- **Modelo real gpt-6-luna: 5/5 comprobaciones**, 10 llamadas del enrutador y
  85,6 segundos, mediante `scripts/evaluate_conversations.py` con base aislada:
  memoria entre chats, cálculo revisado de 80 sobre datos existentes, explicación
  e informe vinculado, corrección con invalidación y recuperación semántica de
  una hipótesis con cita original. Es regresión del backend, no una evaluación
  de calidad general del producto.

## Navegador

Con datos sintéticos se comprobó Inicio vacío y con dos informes revisados,
selección de informe y cambio de sus enlaces, navegación a Mi negocio y su
formulario de edición, acceso móvil a conversaciones, envío desde el prompt,
persistencia del borrador tras recargar y aparición del mensaje/respuesta en el
chat. Se inspeccionó la presentación en escritorio y a 390 × 844.

La revisión detectó que la navegación móvil escondía el acceso a los chats;
se añadió un acceso visible al plegar la barra lateral. En pantallas de poca
altura el prompt pasa al flujo de la página para permitir acceder al contenido.
Los informes de chats ya no ofrecen una descarga de archivo propio inexistente.

Se reinició la vista previa local, tras comprobar que no tenía trabajos activos,
y se verificó el nuevo Inicio con su base de datos original. Los datos sintéticos
de las pruebas y registros del modelo permanecen en almacenamiento local ignorado.

## Límites

La vista Mi negocio actual permite editar el perfil y acceder a archivos ya
aportados. La ficha completa de recuerdos y la gestión de versiones pertenecen
al siguiente paso. No se ofrece todavía «Preguntar sobre este hallazgo» con una
referencia estructurada; tampoco filtros que recalculen gráficos. Estos límites
se mantienen explícitos en el plan y en el contrato del dashboard.
