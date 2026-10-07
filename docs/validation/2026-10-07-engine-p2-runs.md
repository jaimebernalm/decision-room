# Ejecuciones reales del paso 2 del motor

Fecha: 2026-10-07. Paso 2 del plan de implementación del motor (v3): el sistema
`engine` completa 3 + 3 trabajos reales (Albor y Bruma) con la entrega persistida
en bruto antes de validarse y el coste por trabajo registrado. Presupuesto aprobado
por el propietario: hasta 5 USD.

## Configuración

- Motor: `codex/agent-engine` en `8b683d6`, imagen OpenCode `33ead825…`, proxy con
  `service_tier=default` fijado y coste estimado por llamada.
- Modelo `gpt-6-luna`, esfuerzo `low`. Topes: 3 M de entrada, 64 k de salida, 8 k
  por petición, 60 llamadas, 1.200 s activos.
- Encargo plano (sin la frase de `contexto/panorama.md`), los mismos CSV que los
  lotes anteriores. Orden con semilla `20261008`.
- Verificación mínima del paso 2: corrige referencias aritméticas, pero marca todas
  las cifras como no verificadas. La verificación semántica es del paso 3.

## Canarios: tres fallos encontrados antes del lote

Cada canario fue un único trabajo real en Albor. Cada uno destapó un fallo que las
pruebas con proveedor simulado no veían, y se corrigió antes de seguir.

| Revisión | Resultado | Causa | Arreglo |
| --- | --- | --- | --- |
| `fcf6b9c` | Sin informe; el agente lo dice y no inventa cifras | OpenCode bloqueaba la lectura del manifiesto de tablas (`external_directory`) | `93f366a`: excepción solo para `/inputs/*`, el resto sigue denegado |
| `93f366a` | Informe, pero 4 de 5 cálculos fallidos | La herramienta `consulta` no explicaba cómo leer las tablas | `8b683d6`: contrato del sandbox y ejemplo ejecutable en la descripción |
| `8b683d6` | Informe con cálculos | — | Se lanza el lote |

Coste de los dos primeros canarios: 0,012 USD.

## Lote `p2-engine-c`

| Trabajo | Estado | Segundos | Llamadas | Entrada (caché) | Salida | Coste estimado (USD) |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| albor-1 | entregado | 212 | 32 | 1.007.128 (949.730) | 18.171 | 0,0258 |
| bruma-1 | entregado | 85 | 12 | 229.979 (196.915) | 6.574 | 0,0094 |
| bruma-2 | entregado | 164 | 23 | 612.877 (558.877) | 14.872 | 0,0198 |
| albor-2 | entregado | 419 | 41 | 1.952.976 (1.843.774) | 44.302 | 0,0542 |
| albor-3 | entregado | 208 | 32 | 1.004.247 (944.490) | 14.712 | 0,0243 |
| bruma-3 | **perdido** | 14 | 0 | 0 | 0 | 0 |
| bruma-3r1 | entregado | 170 | 26 | 710.820 | 16.324 | 0,0213 |

- 6 informes entregados de 7 intentos. El intento perdido se conserva y cuenta como
  perdido; el reintento no lo convierte en entrega original.
- Coste estimado del lote: 0,155 USD, sin llamadas sin precio. Con los canarios,
  unos 0,17 USD de los 5 aprobados. Es una estimación de catálogo, no una factura.
- Ninguna pregunta al propietario.
- Cada exportación conserva borrador en bruto, documento verificado, registro de
  verificación, informe con y sin marcas, sesión y llamadas al proxy.

## Qué falló y qué queda pendiente

- **bruma-3:** fallo del controlador 0,4 s después de crear la sesión, antes del
  primer mensaje (sin llamadas al modelo). El motor no registraba qué excepción;
  Astra añade etapa, tipo y motivo de catálogo al diagnóstico. El reintento con la
  misma revisión entregó: fue transitorio.
- **Formato de los resultados del sandbox:** en el lote, 28 cálculos completados, 19
  con resultado inválido y 6 fallidos. El agente tropieza con las reglas de forma del
  resultado. El diagnóstico que lo corrige (`9012876`) es posterior a la revisión del
  lote y entrará en el paso 3.

## Calibración de topes

El trabajo más pesado (albor-2) usó el 68 % de las llamadas, el 65 % de la entrada,
el 69 % de la salida y el 35 % del tiempo. Los topes se mantienen para el paso 2.
Antes del paso 3 se revisan con el motor que verifica más cifras, y cualquier
cambio se registra en el preregistro antes de medir.

## Qué no mide este paso

No juzga la calidad ni la exactitud de los informes: con la verificación mínima,
ninguna cifra sale verificada. Eso es la puerta del paso 3.
