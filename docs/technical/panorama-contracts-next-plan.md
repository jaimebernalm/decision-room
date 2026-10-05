# Transporte, P1a v2 y P1b — encargo del 5 de octubre de 2026

Base: d14c0ed. Misma cadena, sin fusionar ni publicar. Sin llamadas reales al
modelo ni acceso a datos/oráculos de ensayos. Cambios genéricos, tests sintéticos.
Los resultados comunicados por el usuario (sección 16, bfcb422) motivan estas
intervenciones, pero no se utilizan para ajustar reglas de negocio.

1. **Transporte**, commit independiente: respetar el mayor plazo de Retry-After
   y reset de tokens tras 429; recuperación acotada de conexión tras rechazo;
   límite de tiempo total cancelable; estimación y reserva de tokens compartida
   entre llamadas/roles para el límite TPM configurado. No confundir respuesta
   parcialmente recibida con rechazo. Tests sin proveedor real.
2. **P1a v2**, misma opción sales_panorama: apertura Panorama determinista desde
   snapshot congelado, nombres de catálogo verificados, totales/comparación/regla/
   cambios/huecos breves, auditoría separada. Contrato obligatorio de disposición
   de cada hueco y comparación de cada prioridad con evidencia del panorama.
   Panorama compacto al principio del contexto; detalles solo como evidencia.
   Comunicar commits 1 y 2 en cuanto estén listos, mientras sigue el paso 3.
3. **P1b**, opción propia apagada por defecto: panorama compacto al principio
   del contexto de planificación e investigación. Plan con pregunta o descarte
   concreto para cada hueco y mayor cambio; validación en controlador. Permitir
   profundización con cálculos, sin reglas específicas de un negocio.

Garantías transversales: esquema y validación coherentes en cada contexto; el
revisor no bloquea texto impuesto por el sistema; evidencia y decisiones
trazables; formato CSV real con fecha entrecomillada y hora, y hueco detectado,
en las pruebas. Congelación y opciones preservan la comparación por parejas.
No diseñar aún el negocio reservado. No activar opciones por defecto ni fusionar.

Pasos 1 y 2 implementados y validados; paso 3 pendiente. Véanse las notas de validación del 5 de octubre. Registrar validación y limitaciones de cada
paso en documentación antes de su commit. La utilidad real queda pendiente de
medición del usuario.
