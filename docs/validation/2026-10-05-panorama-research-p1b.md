# P1b — panorama antes de investigar

Tercer paso del [encargo](../technical/panorama-contracts-next-plan.md), sobre
`df6ce59` (P1a v2 más vinculación de sus cifras no citadas al hash de aprobación).
Opción propia `DECISION_ROOM_SALES_PANORAMA_RESEARCH=true`, apagada por defecto.
En Python: `Config(..., sales_panorama_research=True)`.

## Activación y aislamiento

Activar antes de crear una **planificación nueva**. Al crear la sesión, se prepara
el panorama sin modelo y se congela con sus catálogos y hashes en el snapshot de
fuentes. La opción se fija en esa sesión: cambiar la variable de entorno no
reescribe un plan ni una investigación en curso. Para comparar, crear una sesión
nueva con la opción desactivada. No hay migración ni fusión de datos entre ramas.
`sales_panorama` sigue siendo independiente: controla P1a en redacción/entrega;
para medir el conjunto, activar ambas opciones. El plan de referencia ya guardado
no recibe silenciosamente señales ni obligaciones nuevas.

## Contrato y proceso

- Planificador inicial, planificador de negocio, investigador y workers reciben
  primero el mismo panorama compacto. Las peticiones efectivas preservan ese
  orden en OpenAI y en el protocolo local. SQL/código completo no se duplica en
  el resumen. Los hashes mantienen su serialización canónica.
- `Proposal.panorama_plan`: una propiedad obligatoria por hueco y mayor cambio
  expuesto por el panorama. Puede investigar (pregunta concreta + tarea enlazada)
  o descartar con un motivo. Una tarea puede abarcar varias señales relacionadas.
- El esquema cierra las claves y diferencia las dos ramas. El controlador exige
  que el enlace exista y que la tarea pueda leer la tabla de esa señal. Vuelve a
  comprobarlo al iniciar investigación; no se admite un plan sin cobertura.
  Como en P1a v2, la integridad entre valores hermanos se comprueba en código;
  no se promete que el esquema pruebe relevancia o causalidad. El motivo y la
  pregunta se juzgan semánticamente en las fases siguientes.
- El investigador elige los cálculos y ampliaciones con los tools y presupuestos
  existentes. El panorama orienta; no se hace pasar por una ejecución propia ni
  incrementa el contador de intentos de Python. Sus cálculos nuevos se registran
  por el contrato normal. Compatible con continuidad y delegación.
- El planificador de negocio ve las disposiciones del plan y las señales. El
  prompt distingue la cobertura impuesta por el controlador de la elección de
  prioridades, y permite descartes razonados. No obliga a que gane la mayor cifra.
- El snapshot vuelve a verificar integridad y pertenencia de fuentes/catálogos al
  reanudar planificación, investigación y revisión. Nunca usa un oráculo externo.

## Pruebas

**66 pruebas Python aprobadas**: P1b, importación/persistencia de P1a, paridad de
continuidad, esquemas estrictos, transporte, contexto de revisión y contratos.
Incluyen PostgreSQL y almacenamiento propios, Docker propio y modelos simulados.

La prueba de P1b importa CSV entrecomillado con cabecera
`fecha,canal_id,producto_id,unidades` y fecha `2025-01-01 00:00:00`. Un artículo
sintético tiene un hueco en un canal y filas en otro. Comprueba:

1. panorama disponible con huecos y cambios;
2. rechazo de plan sin una señal, tarea inventada, tabla ajena o motivo vacío;
3. esquema estricto en planificación, investigación con/sin continuidad, worker
   y planificador de negocio;
4. cálculo real en sandbox de fechas exactas del hueco y siete filas en otro
   canal durante ese tramo; evidencia registrada y cierre conservado;
5. reanudación sin modificar el snapshot aunque se apague la opción;
6. sesión de control sin panorama y versiones de prompt auditadas.

No se han hecho llamadas reales al modelo. Estas pruebas verifican capacidades y
contratos, no que el modelo elija una investigación útil ni la calidad comparativa.
Los ensayos reales y la activación por defecto siguen pendientes del usuario.

## Rebase sobre las correcciones de contexto, 5 de octubre

P1b se reaplica sobre `26fcdc4` (que incluye `011131f` y `cb3fd58`), en una rama
nueva, sin fusionar ni cambiar las opciones por defecto. Se conservan ambas rutas
de configuración, las versiones auditadas de cada fase y el prefijo estable con
panorama también en el protocolo local. La revisión sigue excluyendo el snapshot
de orientación al comprobar cambios en las fuentes originales.

El ensayo local combinado importa un CSV entrecomillado con hora y hueco, planifica,
investiga con continuidad y revisa con P3, panorama, ambos guardianes, presupuesto
en tokens y prefijo estable. Comprueba la adaptación del contrato de disposiciones,
aprobación, evidencia y reanudación sin llamadas adicionales. Las llamadas de cada
fase mantienen su versión correspondiente, en vez de atribuir P1b al revisor.

## Segundo rebase tras el piloto

Base `32ae3ac`: metadatos explícitos de series, clave de caché por revisión,
evidencia delante del sufijo variable y lint estricto/citas literales. Rebase en
`codex/feature/panorama-research-series-integrated`, sin cambios en P1b ni opciones
nuevas por defecto. 44 pruebas locales tras el rebase, incluido el recorrido combinado;
sin llamadas al modelo. La base conserva 112 regresiones aprobadas (con solapamiento
entre ambas suites; no son 156 tests distintos).
