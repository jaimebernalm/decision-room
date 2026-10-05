# P1a v2 — apertura y decisiones obligatorias

Sobre el transporte 00e0e7b, en la misma cadena de d14c0ed. Misma opción
`DECISION_ROOM_SALES_PANORAMA=true`; las revisiones nuevas guardan
`sales_panorama_contract=2`. Las revisiones antiguas conservan su contrato.

1. Web, HTML y PDF abren con Panorama generado por código a partir del snapshot
   congelado: cantidades por canal, ventanas con su explicación, mayor aumento y
   descenso por canal/producto-canal y alertas de huecos. No requiere citas del
   redactor para aparecer. Las cifras exactas, referencias y operaciones quedan
   en review.json/internal.html. No se interpreta un hueco como ventas cero.
2. Nombres del catálogo congelados con columna, tabla y hash de origen. Solo
   relaciones verificadas que preservan filas y claves unívocas; integridad
   comprobada al leer. Sin catálogo válido no se inventa un nombre: los códigos
   opacos se señalan como canales/productos sin nombre verificado.
3. `panorama_dispositions` es un objeto con una propiedad obligatoria por hueco
   expuesto por el calculador. Cada propiedad elige prioridad enlazada a un
   hallazgo o descarte con motivo concreto. Conserva la selección/cotas del
   calculador original y sus recuentos; no afirma que la selección sea exhaustiva.
4. Cada hallazgo incluye `panorama_priority`: alternativa relevante, explicación
   relativa al objetivo y al menos una métrica actual del panorama. Una vista
   descriptiva puede justificar que no establece prioridad de actuación.
5. El esquema impone claves exactas de huecos, campos no nulos, forma de cada
   disposición, longitud de motivos y referencias actuales del panorama. El
   controlador verifica además que claim_key apunta a un hallazgo de la MISMA
   respuesta. Esa relación entre valores hermanos no es expresable con $data en
   el subconjunto JSON Schema del proveedor; no se afirma paridad semántica total.
   Un motivo largo tampoco prueba que sea concreto o útil: lo juzga el revisor.
6. Panorama compacto primero en la petición efectiva (la serialización canónica
   ordenada se mantiene para hashes). No duplica SQL, código ni operaciones; el
   detalle queda como evidencia citable. El revisor ve las disposiciones y no
   debe exigir reescribir la apertura que impone el controlador.
7. El hash de aprobación incluye el panorama completo y sus catálogos, aunque el
   redactor no los cite. No permite alterar el bloque después de aprobar.

Validación: 36 pruebas Python (contrato, integración real de importación,
presentación, PDF, esquemas estrictos), 11 pruebas React y build de producción.
Además pasaron 49 pruebas de panorama/esquemas/transporte. Incluye CSV sintético
con cabecera fecha,canal_id,producto_id,unidades, fechas entrecomilladas con hora,
hueco conocido y catálogo cuyo enlace se verifica sobre los archivos completos.
Sin llamadas reales al modelo. Calidad editorial y elección de prioridades
pendientes de la medición por parejas del usuario; P1b todavía separado.
