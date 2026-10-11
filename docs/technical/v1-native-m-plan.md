# Plan M: que el informe nativo supere al HTML

Fecha: 11 de octubre de 2026. Continúa el [plan del informe v1 nativo](v1-native-report-plan.md)
después del piloto N4 ([resultados](../validation/2026-10-11-n4-results.md)).

## Objetivo del dueño

Terminar con el informe nativo (`blocks-v1`) como salida de v1. Frente al HTML actual (`html-v1`)
debe tener:
- **mejor resultado:** los mismos hallazgos o más, y menos errores;
- **mejor apariencia y mejor interactividad;**
- **sin texto extra:** nada de frases técnicas repetidas ni notas que no ayudan a decidir.

## Decisiones del dueño (11 de octubre de 2026)

- **Regla de parada.** Una llamada con coste desconocido detiene solo su intento y se cobra a su
  reserva máxima. El ledger se para globalmente a la segunda llamada incierta. El tope de gasto no
  cambia. Sustituye a la regla anterior, que paró F5, F5b, F5c y N4.
- **Plan aprobado:** se ejecuta con Astra.
- **Presupuesto de API:** los 15 USD autorizados para N3–N5 cubren también este plan. Se han
  gastado 0,797 USD.
- **Sin cambios:**
  - legacy sigue siendo el motor por defecto hasta que decida el dueño;
  - nada se sube a GitHub ni se fusiona con master sin que lo pida;
  - nunca aparece «Revisado» en v1;
  - nada específico de los negocios de prueba entra en el producto.

## Qué enseñó N4 (2 parejas; solo orientativo)

- **Lectores:** los 4 eligieron `html-v1`.
  - El nativo «se lee como un listado de tablas».
  - Las notas del comprobador hacían dudar de las cifras.
  - En la clínica, `html-v1` encontró que la puntuación de una profesional cae desde junio, porque
    comparó cada profesional con su propia evolución mes a mes.
- **Exactitud:** `html-v1` tuvo 2 errores materiales en la clínica. El agente escribió a mano el
  ancho de cada barra del SVG: los valores de la etiqueta eran correctos y los anchos no. El
  nativo evita ese dibujo manual, porque la plataforma dibuja a partir de los datos; siguen
  siendo posibles errores en los datos, en su selección o en el componente.
- **El texto era distinto en cada brazo.** Fueron ejecuciones separadas, así que el resultado
  mezcla formato y suerte del análisis. Con una sola repetición no se pueden separar.
- **Parada:** el flujo de una llamada del comprobador quedó más de 120 s sin datos tras un HTTP 200
  y el proxy cortó a los 122 s. Sin uso conocido, la regla anterior paró el lote entero.

## Fases

### M1. Fiabilidad de los ensayos (Astra; revisa Claude)

1. **Política nueva del ledger, versionada y opcional al crearlo.** Los ledgers anteriores no
   cambian.
   - Una llamada incierta se cobra a su reserva y marca como detenido **solo su ámbito** (el
     intento).
   - Ese ámbito no puede volver a enviar nada.
   - A la segunda llamada incierta del ledger se detiene todo.
   - El tope global, el tope por ámbito y los demás límites quedan igual.
2. **Motor.** Las comprobaciones de «hay algo incierto» pasan a ser por ejecución:
   - `admission`, `native_checks` y `provider_budget` rechazan solo la ejecución afectada;
   - las demás continúan mientras el ledger no esté detenido.
3. **Tiempo de espera.** El límite de inactividad del flujo del proveedor pasa de 120 s a 300 s,
   siempre acotado por el tiempo que le queda a la ejecución.
4. **Conciliación (investigar, sin compromiso).** Si el flujo se corta después de recibir el
   identificador de la respuesta, ver si se puede consultar después el uso real de forma segura.
   Solo se implementa si no añade reenvíos ni riesgo.
5. **Ejecutor de ensayos.** `product_trial.py` sigue con el siguiente intento cuando se detiene
   uno solo, y registra la pérdida y su motivo.
6. **Pruebas:**
   - un flujo que se queda en silencio;
   - una llamada incierta, que detiene solo su intento;
   - una segunda llamada incierta, que lo detiene todo;
   - un ledger antiguo, que mantiene su regla.

### M2. Contenido del nativo (Claude; el comprobador, Astra)

1. **Encargo del nativo, solo con indicaciones genéricas:**
   - comparar cada segmento con su propia evolución en el tiempo y situar cuándo empieza un cambio;
   - separar los componentes de una cifra cuando se comportan distinto;
   - en cada prioridad, contar primero en prosa qué pasa, después la evidencia (cifra, gráfico) y
     después qué comprobar y qué hacer según el resultado;
   - usar las tablas como apoyo, no como cuerpo, y no repetir en texto lo que ya dice una tabla.
2. **Sin texto extra.**
   - Ninguna frase técnica del comprobador en el cuerpo del informe.
   - La cobertura y las cifras no comprobables quedan en el desplegable de detalles, redactadas
     para el dueño: qué significa y si cambia algo.
   - Una discrepancia que siga tras la corrección sigue visible junto a su cifra (D1).
3. **Comprobador fuera de ventas (Astra).** Que también aborde datos de citas, encuestas o
   cualquier tabla, sin nada específico de los negocios de prueba.

### M3. Apariencia e interactividad (Claude)

1. **Gráficos:**
   - barras y columnas **apiladas**, el tipo que el HTML usó y que la plataforma no tiene;
   - valores exactos al pasar el ratón o con el teclado, que ya existen;
   - mostrar u ocultar series desde la leyenda;
   - alternar entre gráfico y datos.
2. **Tablas:** ordenar por columna; las largas, plegadas con «ver todas».
3. **Composición:**
   - resumen arriba con las tarjetas de cifra;
   - cada prioridad como una unidad visual, con su texto y su evidencia juntos;
   - menos aire de «listado».
4. **PDF:** la misma composición que la web, sin gráficos partidos entre páginas.
5. **Chat:** seleccionar cualquier bloque y preguntar, que ya existe; revisar que funcione con los
   tipos nuevos.

### M4. Prueba de presentación con el mismo contenido (sin API de OpenAI)

- Se transcriben a bloques los dos informes `html-v1` de N4, con el mismo texto y las mismas cifras.
- Un script verifica que el texto canónico conserva todas las cifras del original.
- Lectores Opus nuevos ven capturas de **la vista web** de las dos versiones, en orden equilibrado.
- **Puerta:**
  - el nativo debe ganar al menos 2 de 4 decisiones;
  - si no, se vuelve a M3 con sus motivos, como mucho dos veces;
  - si sigue sin ganar, se informa al dueño antes de gastar API.

### M5. Piloto repetido (unos 3–4 USD)

- 2 negocios × 5 repeticiones × 2 brazos = 20 informes: `blocks-v1` con M1–M3 frente a `html-v1`
  actual.
- Preregistro congelado antes de lanzar.
- **Lectores:** en cada pareja, un dueño y un asesor ven las dos vistas web. Son 20 decisiones.
- **Criterios:**

| Criterio | Nativo | Detalle |
|---|---|---|
| (a) Entregas | Pierde como mucho 1 más que el HTML | Las paradas del proveedor se cuentan aparte |
| (b) Exactitud | 0 errores críticos y no más errores materiales que el HTML | |
| (c) Lectura | Elegido en al menos 10 de 20 decisiones | El objetivo «mejor» es al menos 12 de 20 |
| (d) Hallazgos | Media de señales al menos igual a la del HTML − 0,5, por negocio | |
| (e) Coste | No más del doble que el HTML | |
| (f) Comprobador | 0 falsas alarmas en las cifras correctas examinadas | |

- **Veredicto:** «mejor» si se cumplen todos y (c) llega a 12 de 20; «no peor» si se cumplen todos
  con (c) entre 10 y 11; «no pasa» en cualquier otro caso.

### M6. Ensayo final contra legacy

Si M5 da «mejor», el nativo se compara con legacy por la ruta de producto (el N5 preparado). Después
el dueño decide si pasa a ser el valor por defecto.

## Reparto y coordinación

| Fase | Responsable | Revisión | Archivos principales |
|---|---|---|---|
| M1 | Astra | Claude | `agent/api_budget.py`, `engine/proxy.py`, `engine/admission.py`, `engine/native_checks.py`, `engine/provider_budget.py`, `scripts/checks/product_trial.py` |
| M2 (encargo, sin texto extra) | Claude | Astra | `engine/brief.py`, `engine/blocks.py` (`FORMAT_GUIDE`), vista y PDF |
| M2 (comprobador) | Astra | Claude | `engine/native_checks.py` y su prompt |
| M3 | Claude | Astra | `frontend/src/components/workspace/engine-blocks.tsx`, `reports/blocks_pdf.py` |
| M4–M6 | Claude | Astra | preregistros, ejecución y evaluación |

Rama: `claude/v1-native-m`, creada desde `codex/v1-native-reports` (`48131e0`). Solo local.
