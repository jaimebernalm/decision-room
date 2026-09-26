# Correcciones explícitas y avisos, 25 de septiembre de 2026

## Alcance

- La extracción distingue las peticiones de corrección («puedes cambiar X por Y») de las preguntas sin datos nuevos. Solo sustituye automáticamente un recuerdo si identifica un único dato vigente del mismo tema, ámbito y periodo. Conserva la revisión anterior en el historial.
- Si el texto antiguo figura una vez en la descripción de «Mi negocio», el cambio se aplica exactamente a ese fragmento y se crea una nueva revisión del perfil. Esto también cubre un dato antiguo que ya no sea un recuerdo vigente; los recuerdos de otros temas no se alteran.
- El agente recibe un comprobante de los cambios declarados a partir del mensaje actual. Puede confirmar brevemente el resultado guardado sin afirmar que está pendiente. Si no se ha guardado una corrección, no puede atribuirse el cambio.
- Las contradicciones ordinarias siguen pendientes de revisión. El chat ofrece una sola acción para confirmar la propuesta y un enlace para editar el perfil. Los avisos y cajas emplean superficies sin borde permanente y texto oscuro; el foco de teclado sigue visible.

## Comprobación

- Pruebas de memoria y conversación: corrección inequívoca, contradicción sin instrucción de corregir, preservación del historial, actualización del perfil y confirmación del agente después del guardado.
- Una llamada sintética al modelo local devolvió un recuerdo acotado de ubicación y una sustitución exacta de «Valencia» por «Vila-real» cuando el perfil contenía la primera y la memoria vigente contenía otro tema. El servidor valida ambos valores antes de cambiar el perfil.
- Se revisó el diseño en el navegador local en chat y «Mi negocio». Las cajas y avisos visibles carecen de borde permanente y los avisos usan texto oscuro.
- La regresión general, las pruebas de interfaz, la sintaxis y la revisión de diferencias se ejecutaron antes del commit.
