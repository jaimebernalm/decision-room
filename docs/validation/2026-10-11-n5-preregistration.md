# N5: ensayo completo blocks-v1 contra legacy. Preregistro

**Estado:** borrador de Claude para que Astra lo revise. Se congela antes de inicializar el lote.
Solo se ejecuta si N4 pasa.

## Pregunta

La misma que en F5: ¿es v1, ahora en la variante blocks-v1 (bloques nativos, comprobación
independiente y una corrección), lo bastante fiable, exacto y preferido frente a legacy como para
ser el motor por defecto de los informes nuevos?

La regla de decisión es la de F5 con tres cambios, todos fijados antes de ver datos.

## Cambios respecto a F5

1. **Brazo v1:** perfil `blocks-v1` (`engine_format=blocks`) con el ciclo de N3, en lugar de
   `html-v1`.
2. **Legacy:** usa 16.384 tokens de salida por llamada (decisión D3 del dueño: la configuración
   de su instalación), en lugar de 8.192.
3. **Exactitud (b):** solo se exigen cero errores críticos **sin aviso visible**. Un error
   crítico que la plataforma marca con el aviso de cifra en revisión cuenta como error material,
   no como crítico.
   - Motivo: la decisión D1 del dueño acepta entregar con aviso lo que no se pudo resolver.
   - Se informa aparte cuántos críticos llevaban aviso.

**Lo que no cambia respecto a F5:**
- los negocios, los datos, el oráculo y las 6 repeticiones (24 informes);
- el dueño simulado de legacy;
- las cuotas del ledger del ensayo;
- la política de rechazos explícitos;
- la parada global ante una llamada incierta;
- los evaluadores (auditor, juez y lectores R1 y R2), los kits sellados y las condiciones
  (a), (c), (d) y (e);
- la definición de ensayo completo;
- la clasificación (candidato, mixto, no candidato o incompleto).

**Lectores.** En blocks-v1 ven las páginas del PDF de la plataforma y en legacy, la presentación
de legacy. Es la misma limitación declarada en N4.

## Gasto

- Ledger nuevo con tope de **8,00 USD** de catálogo para el lote y 2,50 USD por informe, como
  en F5.
- Los tres lotes juntos (N3 de desarrollo, N4 y N5) no superan el tope de 15 USD del dueño.

## Qué se hace con cada resultado

- **Candidato:** se prepara en una rama local el cambio de valor por defecto a blocks-v1, con el
  techo P4. No se fusiona ni se publica; decide el dueño.
- **Mixto, no candidato o incompleto:** legacy sigue por defecto. Se documenta qué falla.
