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
- La regresión Python completa del conjunto está en marcha; no se declara pasada
  hasta que termine. Legacy sigue por defecto y no hay push ni merge a master.

La comprobación profunda del contexto ocurre en eventos del ciclo y mantiene el
lock de memoria mientras lee hashes; el polling usa la comprobación barata. El
renderizador HTML no participa en la ruta nativa. Las superficies y los avisos
de N2 se integran desde la rama de la vista antes del cierre del conjunto.
