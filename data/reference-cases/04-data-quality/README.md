# Casos controlados de calidad de datos

Variantes pequeñas derivadas de los casos públicos 01 y 03 de Microsoft Wide
World Importers. Se conserva la atribución y licencia del conjunto original.
Son alteraciones de prueba, no errores atribuidos al conjunto de Microsoft.

- `duplicates`: convierte importe unitario por cantidad a total de línea, añade
  identificadores ordinales y repite exactamente la primera fila.
- `missing-values`: misma conversión, vacía los importes de las filas 3 y 8.
- `returns`: misma conversión, añade la fila 5 como devolución con cantidad e
  importe negativos e identificador R1. No simula un ticket completo.
- `invalid-dates`: copia el caso diario; invalida la fecha de la fila 1, vacía
  la fecha de la fila 2 y cambia el importe de la fila 3 por texto no numérico.

Los contextos definen cómo tratar cada incidencia, sin revelar cifras esperadas.
El evaluador calcula las referencias con CSV/Decimal fuera del contexto del agente.
Procedencia original: [provenance.json](../provenance.json).
