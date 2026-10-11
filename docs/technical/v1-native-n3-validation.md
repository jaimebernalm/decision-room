# N3: comprobación de prioridades y una corrección

El escritor conserva su libertad de contenido. Después de guardar un borrador
JSON válido, un comprobador nuevo recibe solo CSV congelados, su manifiesto,
declaraciones del dueño y texto de prioridades ligado al hash del borrador.
No recibe panorama, resultados, sesión del escritor, herramientas MCP ni clave
del proveedor. La configuración de comprobación queda congelada en el perfil.

El comprobador extrae cifras y devuelve citas con posiciones Unicode, método,
resultado y limitaciones. El contrato valida identidad y localización, no la
verdad matemática. Fragmentos numéricos no cubiertos —también fechas y años—
quedan como cobertura pendiente, con resumen separado de las discrepancias.
No se crea una aprobación ni una marca de verificado.

Una discrepancia encola una sola corrección durable en la misma sesión del
escritor: recalcular, cambiar si estaba mal o explicar por qué mantiene la cifra.
Otro contenedor comprueba la revisión final, incluso si sus bytes no cambiaron.
Cada pasada tiene un máximo de 20 llamadas y 300 segundos, dentro de los límites
acumulados y del techo P4 del análisis. No se concede presupuesto adicional.
El límite propio de llamadas del comprobador no aborta al padre; los límites del
padre y la parada por gasto incierto conservan su semántica.

Si el comprobador falla pero el padre sigue activo, el contexto está vigente y
todo uso está resuelto, el borrador válido se entrega con comprobación incompleta
y aviso. Expiración, revocación, parada global o uso incierto conservan el borrador
sin promoverlo. Antes de enviar la corrección y antes de elegir una revisión se
revalidan contexto y uso. Una recuperación nunca reenvía un checker incierto;
conserva sus reservas y detiene el ledger existente si dejó uso pendiente.

La migración 38 es aditiva. Recibos, comprobaciones y selección final conservan
identidad de negocio, run y revisión; los resultados terminales son inmutables.
La selección solo se vuelve vigente después de la entrega del run. Chat incorpora
avisos y fija la identidad del resultado de comprobación. `native-checks.json`
exporta resultados completos y observaciones para auditoría privada, sin tokens.

`native_checks.run_standalone` permite la validación retenida en un run dedicado,
preparado por el ejecutor con techo P4 y transporte sujeto al ledger del lote.
No acepta un trabajo web ni sesión escritora ni ciclo, no crea otra cuota y no
publica un informe. Conserva su recibo y resultado exactos; una repetición solo lee.

## Validación de código

- 128 pruebas focalizadas en PostgreSQL desechable: contrato hostil, recepción,
  ciclo/corrección final, recuperación antes y después del resultado, dos workers,
  contexto, cuotas y proxy delegado con el mismo techo monetario, migraciones dos
  veces, acceso, chat, vistas y regresión del motor HTML. Todas pasan.
- Smoke Docker nuevo: comprobador sin MCP, archivos del escritor, red externa ni
  clave del proveedor; montaje de entrada y recogida de comprobación en runtime
  detenido. Pasa. El outbox real también está incluido en las focalizadas.
- Los fallos del controlador en los tests del ciclo son `SystemExit` inyectados;
  las pruebas Docker existentes cubren SIGKILL y retención de sesión y archivos.
- Sin llamadas reales al proveedor. Los tests usan modelos y respuestas HTTP
  simulados. No acreditan exactitud ni utilidad del comprobador: eso queda para
  la validación retenida y los ensayos N4/N5, con materiales y reglas congelados.
- Legacy sigue por defecto y no hay push ni merge a master.

La comprobación profunda del contexto ocurre en eventos del ciclo y mantiene el
lock de memoria mientras lee hashes; el polling usa la comprobación barata. El
renderizador HTML no participa en la ruta nativa. Las superficies y los avisos
de N2 se integran desde la rama de la vista antes del cierre del conjunto.

## Reparación de formato antes de N4

Un borrador recibido con formato inválido puede consumir la misma vuelta única
para repararlo. El outbox conserva un texto fijo y una lista limitada de rutas y
causas del validador; no reproduce valores del informe. Se usa la misma sesión,
los mismos límites y las mismas guardas al enviar. Después se ejecuta la
comprobación final: una discrepancia restante lleva aviso, sin un tercer turno.
Un segundo borrador inválido termina sin publicación y conserva ambos recibos.
El hash de las instrucciones de reparación queda congelado en el perfil.

57 pruebas de contrato/ciclo/recepción/brief/techo monetario pasan tras este
cambio, incluidas reparación válida con discrepancia final y dos borradores
inválidos. La integración anterior pasa 57 pruebas de superficies/ejecutor/PDF y
320 de UI, TypeScript, Vite y oxlint (con advertencias ya existentes). La pasada
completa inicial se interrumpió al integrar cambios durante su ejecución; la
repetición congelada encontró montajes de sandbox no visibles en la VM. Ninguna
se presenta como una regresión completa exitosa de esta variante.

## Smoke real y ajustes antes de congelar N4

Claude ejecutó un smoke del producto sobre 688ab50, anterior a la reparación de
formato. Su metadato declara entrega, corrección y publicación en 323 segundos,
45 llamadas y 0,206 USD de catálogo. No acredita la exactitud de los cálculos.
El comprobador final calculó el hash del fichero de prioridades en lugar de
copiar el campo revision_sha256, por una ambigüedad de las instrucciones. El
resultado se conservó como incompleto y el informe llevó el aviso correspondiente.

Las instrucciones ahora exigen copiar literalmente el campo, sin calcular ningún
hash; el parser sigue rechazando cualquier identidad distinta. El perfil congela
el hash nuevo de las instrucciones. El estado añadido al texto del chat se expresa
en español. Al cambiar el proyector, las revisiones ya derivadas conservan su
proyección, versiones y hash canónico; ni lectura ni adopción repetida las recalculan.

La regresión completa congelada en fba8fc4 ejecutó 898 pruebas en 627 segundos:
cero fallos de aserción y un error. El smoke del renderizador HTML usaba un fixture
sin origin al llamar a reading.view. Se corrigió indicando engine_html en el
fixture; no se cambia el despacho del producto para ocultar ese error. Esta pasada
no se declara exitosa; la repetición sobre el conjunto corregido se registra aparte.

## Regresión e integración del trabajador de derivados

La repetición congelada en bdb5063 pasa 911 pruebas Python en 729,474 segundos,
sin fallos, errores ni omitidos. También pasan 320 pruebas de UI, TypeScript,
Vite y oxlint, con las advertencias existentes. Esta cifra corresponde al código
anterior al arreglo de aislamiento que se describe a continuación.

La revisión visual de Claude sobre una copia desechable del smoke encontró que
el trabajador HTML encolaba revisiones nativas y cambiaba sus versiones de
derivación. El arreglo de 513b674 filtra los documentos engine_html en refresco,
selección de trabajo, ejecución, encolado, reclamación y ambos escritores raster.
La lectura nativa rechaza inventarios ajenos. La selección del chat revalida
vigencia bajo el lock compartido del documento, después del lock de memoria del
envío, y usa la proyección guardada con avisos propios, de antecesores y de
descendientes. No reinterpreta revisiones históricas con otro proyector.

La integración pasa 71 pruebas focalizadas en PostgreSQL y Docker. Una prueba
adicional reproduce un trabajo raster residual de un documento nativo: no se
reclama ni cambian sus intentos; los escritores directos rechazan la operación;
la revisión queda idéntica y su vista nativa sigue disponible. Pasa. La regresión
completa congelada en 579a04b pasa 920 pruebas en 643,860 segundos, sin fallos,
errores ni omitidos. Este conjunto incluye el aislamiento y la selección; los
ajustes posteriores de presentación tienen su validación focalizada aparte.

## Puerta de calidad pendiente

N3 está implementado y probado como código, pero no acreditado por la validación
retenida exigida por el plan. El lote N4 activó la parada global del ledger ante
una llamada HTTP 200 con uso desconocido. Se conservan el borrador, la llamada
incierta y su reserva; no se promueve la revisión del run abortado ni se reabre
el ledger. El piloto queda incompleto y la validación sembrada no se ejecutó.
N5 no se inicia porque N4 no pasó su puerta. Legacy sigue por defecto.
