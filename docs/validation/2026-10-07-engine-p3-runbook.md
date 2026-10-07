# Guion de ejecución de los pasos 2 y 3 del motor

Fecha: 2026-10-07. Acompaña al preregistro del paso 3
([v4](2026-10-06-engine-p3-preregistration.md)). Este guion no cambia lo
preregistrado: fija los comandos para que la ejecución no se improvise. Nada de
esto se lanza sin la aprobación del presupuesto por el propietario.

## Antes de empezar

- El motor (`codex/agent-engine`) completa sin modelo el recorrido integrado
  `run_report` → `resume_report` → `export_run`, y el export pasa
  `reports.verification_contract.validate` e incluye `informe.contenido.html`.
- El proxy fija `service_tier=default` y registra los componentes de coste por llamada.
- Presupuesto aprobado por el propietario el 2026-10-07: hasta 5 USD para el paso 2
  y hasta 15 USD para el paso 3, con los escenarios y supuestos del documento de
  contrato. No son topes automáticos de factura: si el consumo acumulado se acerca
  al límite, se para y se consulta.
- Entorno, igual que en los lotes anteriores:
  - `DECISION_ROOM_DATABASE_URL`: el clúster local de ensayos;
  - `--runtime-root`: el checkout cuyo `.local` tiene `sandbox-runtime.json`
    (Colima `decision-room`, donde también está la imagen
    `decision-room-opencode:1.18.34`);
  - `--env-file`: el `.env` del checkout principal. Además de la clave, aporta
    ajustes que el manifiesto copia y deben coincidir entre lotes (modelo,
    embeddings `text-embedding-3-small`, búsqueda semántica activada);
  - `TRIALS_OPENCODE_RUNNER`: el `run-opencode.sh` congelado del lote
    `loop-panorama` (hash `1f68448f…`, configuración `9f0a87dc…`).
- Ensayo en seco del 2026-10-07 (brazos `opencode` y `product`, una ronda, sin
  llamadas al modelo): la revisión `c6bda76` migra su base y pasa la comprobación
  del sandbox; el agente en bucle recibe el encargo con panorama y `contexto/`, y la
  cadena el encargo plano; los ajustes efectivos se copian sin secretos.

Flags del brazo `legacy` (prefijo `DECISION_ROOM_`):

```
AGENT_TPM=1800000 OWNER_PRESENTATION=true PANORAMA_OBLIGATION_GUARD=true
RESEARCH_CONTINUITY=true RESEARCH_VALIDATION_RECOVERY=true REVIEW_LOOP_GUARD=true
REVIEW_CONTEXT_BUDGET=false REVIEW_EXPLICIT_CACHE=false REVIEW_STABLE_PREFIX=false
SALES_PANORAMA=false
```

## Paso 2: 3 + 3 ejecuciones reales del motor

```
python -m decision_room.evaluation.trials prepare LOTE-P2 \
  --dataset albor=inputs/albor --dataset bruma=inputs/bruma \
  --systems engine --engine-ref <commit del motor> --repeats 3 --order-seed <semilla> \
  --python <intérprete> --runtime-root <checkout> --env-file <.env>
python -m decision_room.evaluation.trials run LOTE-P2
python -m decision_room.evaluation.trials summary LOTE-P2
```

Se registra por trabajo: entrega en bruto persistida antes de validar, estado
final, consumo (entrada, caché, salida, llamadas, segundos) y coste por componente,
incluidos título, compactación y subagentes. Con esos datos se confirman o
recalibran los topes; cualquier cambio se registra en el preregistro antes del
paso 3.

## Paso 3: 36 ejecuciones

1. Preparar el lote con los tres brazos, la variante del agente en bucle y la semilla:

   ```
   python -m decision_room.evaluation.trials prepare LOTE-P3 \
     --dataset albor=inputs/albor --dataset bruma=inputs/bruma \
     --variant opencode:albor=inputs/albor-panorama \
     --variant opencode:bruma=inputs/bruma-panorama \
     --systems engine,opencode,product --repeats 6 --order-seed <semilla> \
     --engine-ref <commit congelado del motor> --product-ref c6bda76 \
     --product-env DECISION_ROOM_...  (los diez flags de arriba) \
     --python <intérprete> --runtime-root <checkout> --env-file <.env>
   ```

2. Emparejar **antes** de ejecutar nada:
   `python -m decision_room.evaluation.trial_pairs plan LOTE-P3 --seed <semilla>`.
3. Ejecutar: `python -m decision_room.evaluation.trials run LOTE-P3`. Un intento
   perdido se conserva; para los lectores se sustituye una vez con
   `trials abandon LOTE-P3 <trabajo> --reason ...`.
4. Kits, fuera del lote (las claves quedan en el lote):
   - lectores, primero contenido y después artefacto:
     `trial_pairs kit LOTE-P3 KIT-contenido --measure contenido` y
     `trial_pairs kit LOTE-P3 KIT-artefacto --measure artefacto`;
   - juez de señales: `trial_judge kit LOTE-P3 KIT-juez`;
   - auditor: `trial_audit kit LOTE-P3 KIT-auditoria`.
   Si alguna clave lista `marks_not_removed`, ese export no trae la versión sin
   marcas: se corrige el exportador antes de entregar el kit.
5. Puntuar, cada condición por separado:
   - lectores: `trial_pairs score LOTE-P3 --kit KIT-contenido --reader a.json
     --reader b.json`, y lo mismo con `KIT-artefacto` (≥ 2 lectores distintos y 6
     parejas por negocio, medida y rival);
   - juez: `trial_judge score LOTE-P3 juez.json --kit KIT-juez`, con el oráculo
     pasado solo al juez;
   - exactitud: `trial_audit unblind LOTE-P3 auditoria.json --kit KIT-auditoria >
     registro.json` y `trial_accuracy registro.json LOTE-P3`;
   - informes perdidos: `trials summary LOTE-P3`.
6. El brazo `engine` pasa solo si se cumplen las cuatro condiciones del
   preregistro (§6). Si falla alguna, el paso 4 no empieza y se escribe el análisis.

## Quién hace qué

- Claude: preparar, ejecutar, construir kits, desciegar y puntuar.
- Propietario: presupuesto aprobado; lectores elegidos (Claude Opus 5.5 y Codex en
  conversaciones nuevas, con el papel de `LECTOR.md`); abre esas conversaciones solo
  sobre la carpeta de cada kit, fuera del repositorio. Juez y auditor: pendientes.
- Auditor: nuevo, elegido por el propietario, sin acceso a código, claves ni oráculos.
- Astra: el motor congelado y su exportador; no ve kits ni claves.
