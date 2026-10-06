# Auditoría de exactitud del lote `loop-panorama` (paso 1 del motor)

Fecha: 2026-10-06. Auditor: Astra, a ciegas respecto al sistema de cada informe.
Desciego y resumen: Claude. Paso 1 del plan de implementación del motor (v3).

Este documento es el resumen público. El registro detallado (una entrada por
cifra, con cita, valor esperado, cálculo y fuente) es privado y queda fuera de
Git, porque contiene citas de los informes y datos de los negocios de prueba.

## Qué se auditó

- Los 12 informes del lote `loop-panorama` (sección 18 del documento de ensayos):
  3 de Codex con panorama y 3 de OpenCode con panorama, en cada uno de los dos
  negocios de prueba.
- Las cifras comparativas registradas (variaciones, diferencias, cuotas,
  rankings, medias, cocientes), con su denominador y su periodo, y las cifras y
  afirmaciones que sostienen prioridades: 1.087 registros en total. No es un censo
  de cada repetición tipográfica (ver límites).
- Recalculado desde los CSV de entrada con scripts propios del auditor, sobre un
  kit congelado (48 archivos con hash, verificados antes de empezar).

## Resultados por sistema

| Sistema (con panorama) | Informes | Cifras revisadas | Correctas | Errores | Materiales | Ambiguas | Errores por informe | Informes con algún error |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex | 6 | 514 | 506 | 7 | 6 | 1 | 1,17 | 4 |
| OpenCode | 6 | 573 | 568 | 5 | 2 | 0 | 0,83 | 3 |

**Correctas** incluye las que solo difieren por el redondeo mostrado. Las
**ambiguas** (la frase admite más de un cálculo y el informe no dice cuál usó) se
cuentan aparte: ni correctas ni errores.

Un error es **material** si cambiaría lo que el dueño entiende o decide. Los
errores encontrados son de tres tipos: porcentajes intercambiados entre dos
comparaciones, cifras de un canal completo atribuidas a un solo producto, y
recuentos o rangos mal calculados.

### Cifras que sostienen prioridades

Definición del preregistro de la medida del paso 3 (v3): toda cifra citada en una
recomendación explícita o en su justificación frente a alternativas, con sus
denominadores y cifras enlazadas, en cualquier puesto; no cuentan los
descriptivos sin ese vínculo. El auditor la aplicó después de las tasas
agregadas, sin conocer la identidad de cada informe.

| Sistema (con panorama) | Cifras que sostienen prioridades | Correctas | Errores | Materiales | Ambiguas | Correctas sobre el total | Informes con algún error en ellas |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Codex | 313 | 306 | 6 | 5 | 1 | 97,8 % | 4 de 6 |
| OpenCode | 347 | 343 | 4 | 2 | 0 | 98,8 % | 3 de 6 |

El porcentaje se calcula sobre todas las cifras que sostienen prioridades,
incluidas las ambiguas, porque la puerta del paso 3 exige el 100 % verificadas y
correctas: una cifra ambigua tampoco la cumple.

En estos informes las prioridades sustantivas son dos o tres, así que la versión
limitada a las tres primeras da el mismo resultado.

## Qué implica para el paso 3

- 10 de los 12 errores están en cifras que sostienen prioridades: justo las que
  el dueño usaría para decidir.
- Sin verificación, entre la mitad y dos tercios de los informes del sistema
  ganador no cumplirían la condición de exactitud de la puerta del paso 3 (100 %
  de las cifras que sostienen prioridades, verificadas y correctas). La
  verificación final del motor es necesaria, no un adorno.
- Esta tasa es la línea base de exactitud del paso 3. No se compara directamente
  con la puerta: la puerta exige cifras verificadas por el motor, y este lote no
  tenía verificación.

## Límites

- 6 informes por sistema: sirve para ver el orden de magnitud, no para afirmar
  diferencias entre Codex y OpenCode.
- El auditor conocía, por la planificación, las descripciones de las señales y los
  resultados agregados de los ensayos. No conocía qué sistema escribió cada
  informe, ni abrió claves, oráculos o el generador de datos.
- Un registro es una cifra o afirmación: la misma cifra en tabla, gráfico y frase
  puede contar por separado. No se auditó cada punto histórico no comparativo.
- No se revisó el render en navegador (JavaScript, etiquetas, móvil); se medirá en
  la medida «artefacto» del paso 3.
- La auditoría no mide consumo: los topes del motor se calibran con las
  ejecuciones reales del paso 2.
