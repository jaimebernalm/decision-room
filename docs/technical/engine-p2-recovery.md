# P2: matriz de recuperación y límites

Fecha: 2026-10-07. Revisión de partida: `801ba8c`. La matriz corresponde a las
pruebas guardadas junto a este documento; los resultados del lote real corresponden
a `8b683d6`, no a una ejecución retrospectiva del código posterior.

## Validación local

`python -m unittest discover -s tests -p 'test_engine_*.py' -v`: **117/117**,
113,456 s, con la imagen fijada de OpenCode habilitada; ninguna prueba omitida.
El subconjunto nuevo de fallos y contenedor pasó **9/9** antes de la regresión.
Incluye PostgreSQL real, cálculo Docker real y los cuatro recorridos integrados
de API con proveedor simulado. No se realizaron llamadas facturables.

## Criterio → prueba → resultado

Los nombres siguientes son métodos de `unittest`, dentro de `tests/`. PostgreSQL,
HTTP local, Docker y OpenCode son reales donde se indica. El proveedor de modelos
está simulado en estas pruebas: no se accede a su API ni se consume presupuesto.

| Criterio de «Hecho cuando» de P2 | Prueba y frontera comprobada | Resultado |
| --- | --- | --- |
| Canario del host ausente; sin clave del proveedor ni DNS externo | `test_engine_container.RuntimeTests.test_sigkill_retains_sessions_and_files_without_exposing_host_or_provider_key`: archivo sintético real del host y clave sintética en el entorno del proceso; inspección desde el contenedor de producción con red `none` | Pasa; el agente solo recibe la credencial de su trabajo |
| Rutas ajenas rechazadas con 403 | `test_engine_tunnel.TunnelTests.test_mcp_json_sse_concurrency_and_foreign_routes_without_external_network` y `test_engine_admission.EngineTests.test_http_auth_origin_protocol_and_exact_routes` | Pasan; el túnel y el servicio validan por separado |
| Otro trabajo, otro negocio, revocación, caducidad, snapshot modificado | `test_engine_admission.EngineTests.test_cross_job_business_expired_revoked_and_waiting_denied`, `test_changed_snapshot_aborts_before_admission`, `test_changed_file_bytes_are_detected_even_with_unchanged_metadata` | Pasan, incluyendo bytes cambiados sin modificar metadatos |
| Misma clave/contenido no repite cálculo ni entrega; contenido diferente se rechaza | `test_engine_admission.EngineTests.test_mcp_real_calculation_idempotency_and_cross_job_result_denial`, `test_engine_store.DraftTests.test_identical_retry_and_new_revision_never_replace_previous_raw`, `test_concurrent_delivery_same_key_creates_one_revision` | Pasan; cálculo en sandbox real y entrega en PostgreSQL |
| Cada tope aborta sin perder borrador | `test_engine_faults.FaultTests.test_each_limit_preserves_raw_and_rejects_further_admission` | Pasa para entrada, salida total, salida por petición, llamadas y tiempo activo; exporta los bytes previos tras cada aborto |
| Reservas concurrentes no sobreasignan cuota | `test_engine_admission.EngineTests.test_concurrent_reservations_cannot_over_admit` y `test_engine_faults.FaultTests.test_concurrent_output_reservations_preserve_raw_and_charge_only_admitted_call` | Pasan con hilos concurrentes para entrada y salida; solo una petición admitida |
| Muerte abrupta del contenedor | `test_engine_container.RuntimeTests.test_sigkill_retains_sessions_and_files_without_exposing_host_or_provider_key` | Pasa con `docker kill --signal KILL`, salida 137; copia posterior y restauración en otro contenedor conservan sesión, hijo y archivo |
| Muerte abrupta del controlador | `test_engine_faults.FaultTests.test_sigkill_controller_releases_lock_but_never_replays_uncertain_prompt` | Pasa con proceso real bajo `SIGKILL`, lock PostgreSQL liberado y marcador de envío persistido; no reenvía aunque falte confirmación y reconcilia el mismo ID cuando aparece |
| Muerte abrupta del proxy tras admitir una petición | `test_engine_faults.FaultTests.test_sigkill_http_proxy_then_real_controller_recovery_keeps_unknown_reservation` | Pasa: servidor HTTP real muerto con `SIGKILL`; controlador y runtime reales recuperan como aborto, conservan raw y reserva 70/20, detienen contenedor y no generan otra llamada |
| SSE cortado y reconexión | `test_engine_faults.FaultTests.test_sse_disconnect_then_http_reconnect_retains_raw_and_never_replays_provider`; `test_engine_lifecycle.ClientTests.test_sse_fragmentation_and_eof_require_reconciliation` | Pasan: respuesta parcial sin usage conserva cuota; conexión HTTP nueva recibe 403 tras aborto. El EOF de eventos de sesión exige reconciliar, no reenviar |
| Caída antes y después de persistir entrega | `test_engine_faults.FaultTests.test_sigkill_before_and_after_draft_commit_preserves_exactly_one_retry` | Pasa: `SIGKILL` dentro de la transacción y después del commit. Rollback conserva el borrador anterior; commit conserva los bytes nuevos; retry produce exactamente una revisión y un evento |
| Petición admitida sin usage final | Caso de muerte del proxy anterior; `test_engine_admission.EngineTests.test_unknown_usage_survives_fresh_process`, `test_settlement_releases_only_known_usage_and_is_idempotent` | Pasan; no se devuelve una reserva incierta. Un recibo conocido permite reconciliar consumo pero no reabre el trabajo abortado |
| Copia corrupta | `test_engine_container.RuntimeTests.test_stop_checkpoint_restore_session_and_work_in_new_container`; `test_engine_lifecycle.CheckpointTests.test_corrupt_incomplete_or_path_changing_checkpoint_is_rejected`; `test_engine_questions.QuestionTests.test_corrupt_checkpoint_and_revocation_prevent_activation` | Pasan: corrupción rechazada antes de restaurar/activar; archivo y checkpoint anteriores no se sustituyen |
| Espera/respuesta y exportación integradas | `test_engine_api.RealApiTests.test_real_opencode_waits_and_restores_same_session_with_mock_provider`; `test_real_opencode_delivers_through_mock_responses_and_real_mcp` | Pasan con OpenCode, PostgreSQL, MCP y runtime reales; proveedor simulado |
| 3+3 informes y coste registrado por trabajo | [Lote real de P2](../validation/2026-10-07-engine-p2-runs.md), medido por Claude en `8b683d6` | Seis entregados en siete intentos. El perdido se conserva como perdido; no tenía contenido que recuperar. Lote ≈0,155 USD estimados; con canarios ≈0,17 USD |
| Coste incluye llamadas que pasan por el proveedor configurado, también internas | `test_engine_costs.CostPersistenceTests.test_json_receipt_persists_tier_and_cache_counts`, `test_terminal_sse_receipt_survives_downstream_disconnect`; aislamiento y túnel anteriores | Recibo por llamada, tier efectivo y caché persistidos. Modelo principal/pequeño y sesiones hijas usan el mismo proxy/cuota; no hay exclusión por título, compactación o subagente |

## Alcance preciso de la recuperación

La recuperación es conservadora. No promete terminar cada informe tras cualquier
caída: una petición con consumo desconocido aborta y mantiene su reserva. Un envío
marcado pero no observado no se repite. El controlador comprueba mensajes por
polling; no depende del SSE de eventos para decidir si reenvía un prompt. La prueba
SSE de reconexión del proxy confirma rechazo seguro, no continuación de una
respuesta del proveedor a mitad de generación.

La prueba de muerte del controlador mata el proceso que posee el lock y envía el
prompt, con transporte de sesión simulado en esa frontera. La prueba de muerte del
proxy recupera con el controlador y contenedor reales. La muerte del contenedor se
prueba con sesiones e hijos reales sin petición de modelo en curso; el caso de
consumo incierto en curso se cubre separadamente con la muerte del proxy. No se
presenta esta composición como una campaña de fallos con modelos facturables.

Solo se pueden conservar bytes ya recibidos/persistidos, archivos en volúmenes
conservados o mensajes recuperables de OpenCode. Una copia ilegible o una
restauración incompleta requieren intervención; no se silencian ni se sobrescriben.
Las copias verifican integridad y tienen límites de tamaño. No se ensaya aquí la
pérdida física del disco o de PostgreSQL. Los volúmenes detenidos todavía necesitan
una política de retención y cuota de disco antes de explotación continuada.

El coste es una estimación de catálogo, no facturación confirmada. Las pruebas de
recibos no demuestran que el lote haya activado cada tipo de llamada interna. Si
falta usage, tier o un precio conocido, la exportación conserva esa incertidumbre;
no la convierte en coste cero. La causa del intento real perdido sigue sin
identificarse; `801ba8c` añade etapa, clase y diagnóstico saneado para próximos casos.

## Topes y paso siguiente

Se mantienen los topes de P2: 3.000.000 tokens de entrada, 64.000 de salida, 8.000
por llamada, 60 llamadas y 1.200 segundos activos. El lote llegó a 1,95 M de
entrada, 44.302 de salida, 41 llamadas y 419 segundos. El código de A2 añade trabajo
de verificación: esta evidencia no demuestra todavía que los topes sean suficientes
para su puerta de calidad. Cualquier ajuste se registra antes de congelar P3.

P3 sigue abierto: la recuperación y seis entregas no prueban exactitud, calidad ni
cobertura general del verificador. Las cifras procedentes de recetas no admitidas
o de prosa libre siguen sin certificación semántica automática.
