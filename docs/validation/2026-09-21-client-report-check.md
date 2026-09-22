# Informe del cliente — validación del 21 de septiembre de 2026

## Implementación comprobada

El paso 1.6 ahora separa el informe del cliente del registro interno. El contrato
incorpora contexto y cobertura, interpretación, siguientes comprobaciones,
explicación de cálculos y gráficos respaldados por referencias a métricas.
El revisor recibe ese contrato completo antes de aprobarlo.

Se ejecutó `python -m unittest discover -s tests`: **71 pruebas correctas en
48,062 segundos**, con PostgreSQL y Docker reales y modelos simulados en las
pruebas del controlador. `pip check` no encontró incompatibilidades.

Las ocho pruebas nuevas cubren separación entre contenido interno y cliente,
referencias de gráficos incluidas en la huella de aprobación, evidencia obsoleta,
métricas inexistentes/no finitas/sin procedencia, fechas desordenadas o duplicadas,
hallazgos inexistentes, huecos sin interpolar, números negativos y cero, tablas,
redondeo Decimal, escape de texto, referencias accesibles y ausencia justificada
de gráficos. La integración existente comprueba los dos HTML y permisos privados.

Las pruebas estructurales de accesibilidad y estilos no sustituyen una revisión
visual en navegador y móvil; esa comprobación queda pendiente. No se afirma que
se haya realizado una inspección visual automatizada del HTML.

## Prueba con modelo real

Se reutilizó la investigación persistente del caso de referencia de ventas
registradas entre el 1 y el 28 de abril de 2016 (24 fechas, extracto de WWI).
Se utilizó Qwen local en LM Studio para los dos roles, con llamadas separadas.
Los límites y el historial de la revisión se conservaron.

En el primer intento el principal eligió calcular una serie diaria y estadísticas
adicionales. Su primer programa falló por indentación; recibió el error y generó
una corrección que se ejecutó. La redacción posterior superó el timeout; se reanudó
expresamente la misma sesión. El siguiente borrador era JSON inválido y fue
rechazado por el contrato antes de llegar a una aprobación.

La comprobación independiente del CSV con Decimal encontró coincidencia de los
totales (34.137,85 y 39.646,25), variación (16,14 %), serie diaria y extremos.
Detectó dos medianas auxiliares incorrectas: el código tomó el elemento central
superior de doce valores en vez de promediar los dos centrales. Los valores
correctos redondeados son 2.491,30 y 3.185,13; el programa guardó 2.536,00 y
3.207,65. Esta detección fue una comprobación independiente del desarrollo,
no se atribuye al revisor.

Se registra el error de mediana como DR-003. El primer intento terminó sin
informe aprobado tras el timeout de la corrección de JSON. Se conservó su traza.

El éxito de las pruebas del controlador no cierra DR-001/DR-002/DR-003 ni demuestra
calidad general del modelo. El paso 1.7 sigue pendiente.


## Segundo intento autónomo y ejemplo controlado

Se inició otra revisión desde la investigación original, con instrucciones de
contenido más concisas. El principal calculó porcentajes y serie diaria sin
fallos de Python. La comprobación independiente coincidió en sus 53 métricas,
pero la redacción volvió a superar el timeout de 180 segundos. No hubo informe
aprobado ni se modificó manualmente la respuesta del modelo para conseguirlo.

Para comprobar la presentación completa se añadió
`scripts/checks/check_client_report.py`: analista de referencia explícitamente
programado, Python real en el sandbox y revisor Qwen real. El contenido describe
comparación de periodos y cobertura; incluye barras de totales y línea diaria,
con siguientes comprobaciones y explicaciones de cálculo. Cada acción del
analista se identifica como `fixture_seed: true`.

Los 45 valores guardados de este ejemplo coinciden con la comprobación
independiente del CSV; 32 métricas distintas respaldan hallazgos y gráficos.
Esto valida el ejemplo de referencia y los componentes, no la producción
autónoma del informe por Qwen. El timeout y los errores observados deben
formar parte del paso 1.7 antes de aceptar el recorrido para clientes.


El revisor real **aprobó** el ejemplo de referencia tras las acciones
`execute → submit → approve`. Confirmó alcance, totales, cobertura, gráficos y
siguientes comprobaciones. La exportación final contiene dos SVG, 24 puntos en la
línea y 19 segmentos: cuatro fechas ausentes interrumpen la unión de puntos.
El HTML del cliente no contiene conversación ni código; estos siguen en el HTML
interno. Copias locales en `outputs/client-report-demo/`, excluidas de Git.
