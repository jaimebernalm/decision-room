# Validación de Mi negocio y versiones de datos · 23 de septiembre de 2026

## Alcance

Se implementa 2.5.5 en la interfaz integrada: ficha de memoria, mantenimiento
compartido con el chat, ingesta independiente, originales descargables y versiones
explícitas. No incluye Excel, combinación general de tablas, paginación de grandes
fichas ni políticas de contexto permanente para agentes especializados.

## Pruebas automatizadas

- Suite completa: **241 pruebas Python correctas**. Tras la revisión final,
  **74 pruebas dirigidas** de ficha, contexto, conversaciones y web también pasan.
- Pruebas JavaScript existentes del dashboard: **7 correctas**, más comprobación
  de sintaxis de ambos archivos de interfaz.
- Nueve casos nuevos sobre PostgreSQL real en `tests/test_dossier.py`: edición
  concurrente, corrección/retirada compartida, confirmación y fechas, aislamiento,
  idempotencia y descarga, carga sin modelo ni informe, versiones, búsqueda y
  vigencia, CSV erróneo, recuperación tras interrumpir la preparación, HTTP y
  reentrada de migración.
- Se comprueba un informe aprobado de verdad por la cadena con modelo controlado:
  una actualización conserva exactamente su exportación; una corrección retira
  exportación y dashboard y dirige a elegir los datos actuales.

La concurrencia utiliza dos escritores sobre la misma revisión. La recuperación
interrumpe después de preparar y antes de publicar la relación de versiones.
Archivos con filas parcialmente repetidas producen conjuntos separados, nunca
una suma automática. Las comprobaciones controladas verifican contratos; no son
una evaluación de calidad general del modelo.

## Modelo real

```sh
.venv/bin/python scripts/evaluate_conversations.py --dossier --output .local/dossier-real-check
```

Recorrido sintético con `gpt-6-luna`: **6 comprobaciones correctas**, 105,2 segundos,
11 llamadas de enrutamiento de chat (además del trabajo analítico y de memoria).

1. Una declaración se recuerda en otra conversación.
2. Un CSV cargado desde el servicio de la ficha produce el total revisado **80**,
   sin volver a subirlo ni publicar un informe automáticamente.
3. El agente recupera y explica la evidencia existente y abre el informe solicitado.
4. Una contradicción resuelta desde la ficha se reutiliza en otra conversación y
   se retira la respuesta anterior afectada.
5. Una hipótesis histórica se recupera semánticamente y se cita como antecedente.
6. El CSV corregido produce el total revisado **100** en una nueva conversación;
   el informe anterior no se entrega como resultado válido.

Los registros detallados y las bases temporales quedan fuera de Git; las bases de
la evaluación se eliminan al terminar. Las cifras son referencias sintéticas,
no información de un cliente ni aceptación de todos los casos del producto.

## Navegador

Entorno aislado con negocio y CSV sintéticos. Comprobados:

- Estado vacío, alta y edición de memoria, texto de procedencia y alcance.
- Dos pestañas: la revisión antigua devuelve conflicto y conserva el texto escrito.
- Retirada e historial con las tres revisiones conservadas.
- Carga independiente y corrección con las dos versiones y originales disponibles;
  la versión corregida pierde el botón de reutilización.
- Archivo mal formado: error legible y versión anterior todavía disponible.
- Abrir un chat desde una versión y consultar la memoria corregida.
- Navegación móvil a 390 × 844, sin desbordamiento horizontal y con controles de
  negocio/chat accesibles; presentación de escritorio revisada visualmente.

La ficha se actualiza por navegación o con «Actualizar ficha», evitando sustituir
un formulario durante la edición. Los periodos son declaraciones del propietario;
no hay detección automática de solapamientos entre filas. Los errores o interrupciones
no autorizan la suma de datos ni el recálculo automático de informes.
