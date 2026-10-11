# Contrato de estados y ciclo del informe nativo

Complemento de [N0: formato de bloques](v1-blocks-n0.md). La especificación ejecutable única es `decision_room/engine/blocks.py` (informe-bloques-1). La vista usa `mode=blocks`, con la proyección y checks.state explícito. No hay dos esquemas.

Datos validados, comprobación terminada y ejecución entregada son estados distintos. N1/N2 no hacen vigente un informe nativo sin N3. Los recibos brutos e IDs históricos se conservan. Derivados inmutables por negocio/documento/revisión/hash bruto/esquema/proyector/política; publicación bajo guardas F1.

## Ciclo de N3 y decisiones de producto

Autor → borrador durable → comprobador aislado → como máximo una corrección en la sesión escritora → comprobación final → revisión elegida. La cobertura y los resultados se ligan a la revisión exacta. Se conserva todo recibo, sin reutilizar resultados sobre bytes nuevos.

Autor/comprobador/corrección comparten el techo P4 y límites acumulados. No hay saldo adicional ni modificación de la parada por incertidumbre. Sin cuota del padre, uso incierto, parada del ledger, expiración o contexto revocado: conservar borrador y no promoverlo. Si el comprobador falla por su propio plazo, formato o fallo mientras el padre sigue activo y el contexto está vigente, conservar la comprobación incompleta durable y presentar el borrador válido con aviso visible. No se reabre un padre abortado. Una discrepancia tras corrección se presenta con aviso explícito, sin ocultarla ni indicar «Revisado». Los casos no comprobables quedan visibles como tales.

Inicio incorpora tarjetas solo después de N3, desde la revisión vigente y sin ocultar avisos, en un cambio separado. Los ensayos N3–N5 requieren presupuesto y preregistro propios; ni la conversión manual de F5 ni los proveedores simulados acreditan calidad general. No se cambia el motor por defecto por aprobar pruebas de código.

## Comprobación de salida

N1: validación hostil y límites, recepción/repetición, migración dos veces, históricos intactos, export JSON, ningún renderizador. N2: gráficos y tabla fieles, selección por block_id, chat sin evidencia inventada, PDF escapado, extremos y regresión legacy. N3: recuperación y concurrencia, una corrección, comprobación final y techo compartido; validación retenida aparte. N4 mide lectura, señales, exactitud y pérdidas de la variante completa; N5 compara con legacy.
