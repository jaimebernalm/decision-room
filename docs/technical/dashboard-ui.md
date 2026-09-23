# Inicio y navegación del negocio · avance visual de 2.5.6

**Estado:** avance independiente de interfaz sobre el paso 2.5.1. No cierra los
pasos 2.5.4–2.5.6 ni sustituye sus pruebas de integración.

## Incrementos

1. **Navegación y lenguaje visual:** Inicio, Informes y Mi negocio primero;
   pregunta nueva y actividad reciente accesibles. Base blanca, verde suave,
   tarjetas sin contorno, esquinas redondeadas y cambios al pasar el cursor.
2. **Inicio con evidencia:** lectura autenticada de una sola revisión publicable.
   Resumen, hasta tres hallazgos, cifras y gráficos provienen del contrato del
   informe aprobado. El servidor vuelve a comprobar vigencia y evidencia antes de
   entregar los valores. Cada pieza abre su hallazgo y su evidencia en el informe.
   Se puede seleccionar otra revisión disponible sin mezclar periodos.
3. **Pregunta y contexto:** el prompt permanece visible en Inicio y guarda el
   borrador mientras se escribe. Hoy conduce al análisis existente, con la
   pregunta rellenada y la selección de CSV requerida. Mi negocio muestra el
   perfil persistido y los archivos ligados a análisis, con una vía para editar
   contexto y preguntas opcionales que pueden ayudar a completarlo.
4. **Estados y adaptación:** Inicio vacío conduce al onboarding o a un nuevo
   análisis; un trabajo pendiente enlaza a su estado. Un informe bloqueado se
   retira del dashboard. Las tarjetas se adaptan a móvil; el prompt reserva
   espacio para no ocultar el contenido al final de la página.

## Integración pendiente según el plan de la entrega 2.5

- **2.5.3:** usar las dependencias transversales de memoria para comprobar la
  vigencia de hallazgos y respuestas entre sesiones. La proyección ya depende del
  mismo estado publicable que el informe.
- **2.5.4:** enviar el prompt a una conversación durable y mostrar chats recientes
  reales. Hasta entonces la sección Chats permanece vacía y los análisis tienen
  su propio historial; la interfaz no los presenta como conversaciones.
- **2.5.5:** mostrar hechos, prioridades, dudas, origen y vigencia de la memoria
  estructurada en Mi negocio, con edición y retirada mediante su servicio. La
  ficha actual solo muestra el perfil y los CSV accesibles en el backend de 2.5.1.
- **2.5.6:** conectar «Preguntar sobre esto» con la referencia estructurada del
  hallazgo y la revisión, y generar sugerencias basadas en capacidades y datos
  presentes. Los gráficos actuales muestran valores y evidencia, sin filtros que
  recalculen resultados.

## Comprobación

Ejecutar `node --check decision_room/web/static/app.js`, la suite `test_web.py`
con PostgreSQL y sandbox locales, y revisar Inicio, Informes y Mi negocio en
escritorio y a 390 px de ancho. La vista previa visual usa datos ficticios y no
se guarda en Git. La aceptación funcional completa corresponde al paso 2.5.7.
