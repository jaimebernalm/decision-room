# Bruma Café en la aplicación habitual · 2 de octubre de 2026

Entrega de 3.9.8.1, solicitada explícitamente para el espacio habitual.

## Integración y alcance

La rama `codex/feature/bruma-web-integration` conserva la síntesis de `a2d55f9`
y añade los ajustes terminados de UI de `8acc0d1` y búsqueda de `acd9953`.
Los commits de integración son `65a2a68` y `cf432da`. El checkout paralelo de UI
no se modifica. No se hace push ni se fusiona esta rama en master.

Se importa únicamente el negocio sintético Bruma Café del experimento guardado,
con 694 registros en 24 tablas y sus archivos. Se valida la inserción completa
con rollback antes de aplicarla. Se conservan UUID, hashes, fuentes, 12 ejecuciones
y aprobación original. El traslado no actualiza ni elimina otros negocios;
seleccionar Bruma en la interfaz cambia explícitamente el negocio activo.
Se añaden dos entradas de informe al negocio y se enlaza su actividad existente.

La aplicación real de esta rama se sirve en `http://127.0.0.1:8787/`, utilizando
la base, almacenamiento y autenticación habituales. La comparación editorial en
8789 se conserva. Se detiene el servidor auxiliar de 8788. El lanzador privado
queda en `.local/bruma-web-integration/web.py`; arrancar el checkout paralelo de
UI no incorpora por sí solo esta rama. No se publica un sitio externo.

## Revisión real y límites

El original queda intacto. La nueva entrada se llama «Bruma Café · síntesis
revisada 3.9.8 (parcial)»: es una versión corregida, no una copia exacta del piloto.
Los cuatro gráficos conservan claves, referencias, series, unidades, precisión,
escalas y codificación del piloto. No se ejecutan cálculos nuevos: las 12
ejecuciones siguen siendo las de la investigación congelada.

La primera revisión terminó limitada por orientación no justificada o redundante.
La siguiente produjo evaluaciones inválidas incluso tras dos reintentos acotados.
Se guardan todas esas respuestas. Una tercera revisión sobre propuesta parcial,
con corrección del analista, obtiene aprobación válida mediante el contrato,
comprobaciones y digest normales. No se fuerza aprobación ni se debilitan controles.
La comprobación con extracto de origen queda condicionada a disponer de él;
coincidir no demuestra causa y discrepar obliga a reconciliar antes de priorizar.

Los intentos consumen 16 respuestas reales del proveedor: 1.633.770 tokens de
entrada y 48.507 de salida; no se observan 429. No se atribuye coste monetario.
El primer lanzador privado rechazó la representación histórica de la configuración
antes de llamar al modelo; se corrigió su reconstrucción. El último lanzador
terminó con una aserción de igualdad tras la aprobación porque el analista había
corregido la propuesta; se inspecciona el resultado final y se valida antes de
incorporarlo a la biblioteca. Esos fallos se mantienen en el registro local.

La aprobación de esta entrega parcial no demuestra estabilidad del revisor ni
mejora consistente de utilidad. No se repite onboarding o investigación y no se
cierra 3.9.7. El negocio y sus datos siguen siendo un escenario sintético.

## Compatibilidad y comprobaciones

Las políticas históricas ausentes o nulas se interpretan como política heredada
para cobertura y digest. Se evita el error al leer informes antiguos sin
reescribir sus opciones ni invalidar aprobaciones. Las regresiones comparan
expresamente hashes para política nula y cero, y ausencia de nuevas obligaciones.
El error de referencias de utilidad identifica pregunta, claves entregadas y
claves recibidas para permitir reparar la evaluación; el requisito sigue intacto.

- 610 pruebas Python completas pasan sobre la primera integración de UI, antes
  del ajuste de compatibilidad y la búsqueda. Después pasan 59 regresiones de
  informes, revisión, cobertura y presentación, y 57 pruebas de conversaciones
  tras incorporar la búsqueda. Las pruebas usan una base temporal independiente.
- 231 pruebas frontend pasan en la integración final; compilación y lint sin
  errores. Permanecen los avisos existentes de lint y tamaño del paquete.
- Ambos informes en 8787: presentación autenticada 200, cuatro gráficos, versión
  aprobada preservada y entrega parcial; PDF válido 200 y actividad 200. Sin
  autenticación, 401; intentar leer Bruma desde otro negocio, 404.
- Navegador en el puerto habitual: negocio Bruma activo, original y revisión en
  la barra lateral, resumen, índice, tres hallazgos, cuatro líneas interactivas y
  orientación condicional visibles. El informe histórico de Papelería también
  se abre al integrar el ajuste. No se añade una nueva inspección móvil en este paso.

Capturas, documentos exportados, respuestas completas, scripts de importación,
configuración y archivos del negocio permanecen en `.local/`, ignorado por Git.
Se revisan diferencias preparadas para credenciales, rutas personales y archivos
generados antes de guardar los commits locales.
