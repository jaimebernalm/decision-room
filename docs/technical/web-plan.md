# Entrega 2 · Experiencia web local

Decisión del 22 de septiembre de 2026: avanzar a la web por petición del
propietario, manteniendo abiertos los errores semánticos de la entrega 1.
No se cambia el criterio de aceptación analítica ni se introduce otro agente.

## Recorrido y diseño

1. Inicio: espacio de trabajo local, análisis creados desde la web, búsqueda,
   filtros por estado y acceso a sus archivos. Primera visita sin métricas ficticias.
2. Nuevo análisis: nombre y contexto del negocio, pregunta o exploración general,
   un CSV y revisión antes del envío. Borrador de texto guardado localmente;
   el navegador exige volver a seleccionar un archivo si se cierra antes de enviarlo.
3. Detalle: etapas reales, archivo y contexto. Preguntas del principal o revisor,
   opciones cuando existan, texto libre y posibilidad de no saber la respuesta.
4. Continuidad: envío breve a una cola PostgreSQL, ejecución en segundo plano,
   respuestas duraderas y recuperación de checkpoints al reiniciar el servidor.
5. Resultado: informe aprobado integrado, gráficos derivados de evidencia,
   hallazgos, cobertura, limitaciones y cálculos desplegables. Una revisión
   bloqueada, rechazada u obsoleta no entrega conclusiones como aprobadas.

Dirección visual: fondo marfil, verde profundo, acento naranja, tipografía de
sistema, composición editorial, navegación lateral compacta y mucho espacio.
Diseño adaptable al móvil, controles semánticos, foco visible y movimiento reducido.
Sin dashboard analítico, porcentajes de progreso inventados ni configuración de
modelos en el recorrido del propietario.

## Arquitectura y límites

Servidor Python local con HTTP de la biblioteca estándar y frontend HTML/CSS/JS
sin dependencias nuevas. API del mismo origen; los módulos existentes mantienen
la lógica de ingesta, LangGraph, sandbox, revisión y representación del informe.
Un registro web enlaza las identidades existentes y no copia los datos CSV a SQL.
Un trabajador serializado mediante advisory lock usa claves estables por etapa.
Al reiniciar recupera trabajos; las llamadas de resultado incierto requieren un
reintento explícito desde la interfaz. Se limita a 1 CSV y 20 MiB por envío web.

Acceso de un único propietario local: escucha exclusiva en 127.0.0.1, clave de
acceso generada en almacenamiento privado, cookie HttpOnly/SameSite=Strict,
validación Host/Origin y encabezado propio para mutaciones. No es autenticación
multiusuario ni despliegue para comercios. Los ensayos CLI históricos quedan en
su almacenamiento; el inicio web lista únicamente los análisis de este espacio.

## Verificación prevista

Pruebas sobre PostgreSQL real: cola, reenvío idempotente, respuestas, recuperación,
exclusión concurrente, límites de subida, acceso, aislamiento de archivos e informes
bloqueados. Recorrido completo con modelo controlado y sandbox real, distinguido
de las pruebas con el modelo real. Computer Use: primera visita, formulario,
validación, preguntas, persistencia al recargar y revisión visual en escritorio/móvil.
Revisión del diff y de archivos preparados antes de un commit local de entrega 2.
