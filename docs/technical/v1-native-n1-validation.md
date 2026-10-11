# N1: recepción y registro nativo

El trabajo opt-in captura `engine_kind=opencode, engine_format=blocks`. Legacy y el perfil HTML histórico conservan el valor por defecto y sus contratos. Subida, lote y conjunto preparado comparten la selección inmutable. El encargo cambia la entrega a `/work/informe.json`; conserva el párrafo analítico y deja libre el contenido y orden de los bloques.

La imagen recoge los bytes antes de analizarlos, con la misma recepción durable de 256 KiB, identificación por hash e historial. El perfil congela los hashes del validador stdlib y de su guía, instalados de solo lectura en `/inputs`. Un módulo distinto al capturado impide instalar entradas; no se sustituye silenciosamente por una nueva versión.

La migración 37 amplía el origen del registro a `engine_blocks`. El proyector crea derivados inmutables con política y versión propias en la misma transacción de adopción. No se encola ni ejecuta Chrome. JSON inválido conserva el recibo y queda bloqueado. La vista devuelve `mode=blocks` y `checks.state=unknown`; N1 no promueve una revisión nativa a vigente. Esa selección depende de N3. Chat recuperará únicamente una revisión vigente y su texto canónico, con origen e identidad propios, sin sesiones ni evidencia legacy inventadas.

La exportación conserva `draft.raw`, recibo, sesión, cuotas y `informe.raw.json` como bytes exactos. Los informes HTML previos conservan su exportación y renderizador.

Validación con PostgreSQL desechable y proveedores simulados, sin clave API:
- 74 pruebas existentes de registro, derivados, recepción, jobs, brief, espera y chat pasan.
- 24 pruebas de formato, ruta nativa y techo USD pasan: dos workers adoptan el mismo recibo; esquema aplicado dos veces; recibo malformado y acceso a negocio/revisión ajenos; exportación exacta; flujo web a recibo y proyección; CLI y guía congelados; selección inmutable en lote y dataset; default legacy.
- Las dos importaciones inexistentes de la primera invocación (`test_engine_ceiling`, `test_engine_provider_budget`) se corrigieron usando el módulo real `test_engine_usd_budget`; no fueron fallos de producto.

Pendientes: N2 presenta los bloques y exporta PDF; N3 añade comprobador, corrección y publicación; N4/N5 miden calidad y pérdidas. Las pruebas simuladas no acreditan la calidad del nuevo encargo.
