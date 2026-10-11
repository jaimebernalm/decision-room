# N4: piloto v1 en bloques nativos frente a v1 en HTML. Preregistro

**Estado:** borrador de Claude para que Astra lo revise. Se congela antes de inicializar el lote
y no hay datos de este lote.

**Autorización.** El dueño (11-oct-2026) autorizó implementar el plan del informe nativo
completo, de N0 a N5, con todos los cambios necesarios. El presupuesto de N4 y su tope los fija
este documento (§Gasto), dentro de la autorización que el dueño confirme para N3–N5.

## Pregunta

¿Pierde calidad v1 al entregar el informe como bloques nativos en lugar de HTML? Y, con la
comprobación independiente y la vuelta de corrección de N3, ¿mejora o iguala su exactitud?

Se compara la **variante completa** (formato más comprobación). El resultado no se atribuye
solo al formato.

## Brazos

| | html-v1 | blocks-v1 |
|---|---|---|
| Motor | `engine_kind=opencode`, perfil HTML (el v1 de F5) con el techo P4 | `engine_kind=opencode`, `engine_format=blocks`, con el ciclo de N3 |
| Modelo | `gpt-6-luna`, variante `low`, misma imagen | igual |
| Entrega | `informe.html` → instantánea aislada (raster-2) | `informe.json` → proyección de la plataforma, comprobación y una corrección |
| Lo que ve el lector | páginas de la instantánea | páginas del PDF de la plataforma (`blocks_pdf`), que dibuja los mismos bloques que la vista web |
| Preguntas al dueño | desactivadas | desactivadas |

**Variante exacta de blocks-v1.** Hay una sola vuelta de corrección por informe, y la consume lo
que ocurra primero:
- una **reparación de formato**, si el borrador no valida. El agente recibe rutas y causas, sin
  contenido;
- una **corrección de cifras**, si el comprobador encuentra discrepancias.

Después hay siempre una comprobación final. Si tras reparar quedan discrepancias, se avisan sin
un tercer turno. Si el borrador sigue sin validar, el intento cuenta como pérdida y se conservan
los dos recibos.

**Limitación declarada.** El dueño verá la versión web. Los lectores ven el PDF de la plataforma,
porque en este entorno no se puede capturar la página web completa sin un navegador. Ambos salen
de los mismos bloques, con la misma paleta y el mismo diseño.

## Datos

- Generador de F5 (`scripts/f5/generate.py`, semilla 20261011) con los mismos dos negocios:
  - herbolario: ventas, con panorama;
  - clínica: no ventas, sin panorama.
- El oráculo de señales (S1–S5 y señuelo) es el de F5 y nunca llega a los agentes.
- 3 repeticiones × 2 negocios × 2 brazos = **12 informes**. Cada uno va en un negocio
  independiente.
- El orden de ejecución se alterna por pareja, igual que en F5.

## Ejecución y gasto

- **Ejecutor:** `scripts/checks/product_trial.py`, `arms: ["opencode", "blocks"]`.
- **Ledger nuevo:**
  - tope de **3,00 USD** de catálogo para el lote;
  - 1,00 USD por informe (igual que P4);
  - política de rechazos HTTP explícitos (la de F5b y F5c).
- **La regla de parada no cambia:** una llamada incierta detiene el lote, y entonces el lote
  queda incompleto.
- **Sin reintentos automáticos.** Un trabajo que queda en cola se continúa como en F5.

## Evaluación

La canalización es la de F5. Kits sellados, sin brazo visible, y cada evaluador es una sesión
Opus nueva.
- **Auditor:** CSV más el informe. Cuenta las cifras de las prioridades y del resto y los errores
  menores, materiales y críticos, como en F5.
  - En blocks-v1 el auditor recibe una copia **sin avisos** (`informe-auditor.pdf`), para que su
    exactitud sea independiente del comprobador.
  - Después se cruza cada error con los items del comprobador por bloque y cita, de forma
    mecánica, para saber si la cifra errónea llevaba aviso en el informe que vio el dueño.
- **Juez:** oráculo, señales S1–S5 y señuelo, como en F5.
- **Lectores:** uno como dueño y otro como asesor, por pareja (orden A/B aleatorio), con la misma
  pregunta que en F5.
- **Comprobador (validación retenida de N3).** Hay dos fuentes, con denominadores separados:
  1. **Errores naturales.** Las comprobaciones del ciclo en blocks-v1 se comparan con lo que el
     auditor ciego marca en las prioridades. Se cuentan por separado los negativos correctos
     (cifras correctas no señaladas), las falsas alarmas, las detecciones y los no comprobables.
     El auditor es un modelo, no una verdad certificada, y se declara así.
  2. **Errores sembrados.** En copias de los informes blocks-v1 entregados, Claude cambia 2
     cifras de prioridades por informe. Elige cifras que el auditor dio por correctas y les
     aplica un cambio material (±20–60 % o un periodo equivocado). Los cambios se fijan con
     semilla y se guardan fuera de los kits. Después se vuelve a ejecutar solo el comprobador
     sobre esas prioridades, con su propio coste en el ledger. Se mide la detección de lo
     sembrado y las falsas alarmas sobre el resto.
  - También se registran las correcciones aplicadas y el coste y el tiempo de la comprobación.

## Regla (blocks-v1 «pasa N4» solo si se cumplen todas)

- **(a) Entregas:** las pérdidas de blocks-v1 no superan a las de html-v1 entre los intentos
  iniciados.
- **(b) Exactitud:**
  - 0 errores críticos sin aviso en blocks-v1;
  - errores materiales por informe **entregado** en blocks-v1 ≤ html-v1, calculados sobre los
    informes entregados (las pérdidas cuentan en (a));
  - si un brazo no entrega ningún informe en un negocio, (b) queda sin acreditar.
- **(c) Lectura:** en las parejas completas, blocks-v1 se elige en al menos el 50 % de las
  decisiones de los lectores. Un empate cuenta como medio.
- **(d) Señales:** en cada negocio, la media de blocks-v1 ≥ la media de html-v1 − 0,5 (sobre 10).
- **(e) Coste y tiempo:**
  - todos los informes blocks-v1 dentro del techo P4;
  - mediana de coste ≤ 0,30 USD;
  - mediana de tiempo ≤ mediana de html-v1 + 5 min.
- **(f) Comprobador:**
  - falsas alarmas ≤ 10 % de las cifras correctas que comprobó;
  - detecta al menos el 70 % de **todos** los errores sembrados (denominador: todos, incluidos los
    que no llegó a comprobar);
  - la cobertura se informa además aparte;
  - detecta todo error crítico natural presente en las prioridades de blocks-v1, si lo hay.

**Resultado:**
- **incompleto** si algún intento no se inició o alguna pareja quedó sin leer por pérdida;
- si no es incompleto: **pasa** o **no pasa**, con el detalle de cada condición.

**Qué pasa después:**
- Si pasa, N5 compara blocks-v1 con legacy (24 informes, legacy con 16.384 tokens).
- Si no pasa, se analiza qué se perdió y no se ejecuta N5 sin corregirlo.

Ninguna decisión de valor por defecto sale de N4.

## Desviaciones

Cualquier cambio después de congelar el preregistro se anota en un anexo con su motivo, antes
de ver la calidad.
