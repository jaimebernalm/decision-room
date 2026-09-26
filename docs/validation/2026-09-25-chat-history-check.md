# Historial de chat tras un cambio de contexto, 25 de septiembre de 2026

## Comportamiento

- La consulta del chat devuelve el texto original de las respuestas anteriores aunque su contexto haya cambiado. Se marca su estado histórico sin sustituirlas por un aviso de error.
- Se muestra un separador antes del primer mensaje que usa la memoria o el perfil actualizado. Si el cambio ocurrió después del último mensaje, aparece al final del historial.
- Un resultado vinculado a un informe que ya no es vigente conserva su respuesta histórica con la etiqueta «Resultado anterior». No se ofrece abrir o generar un informe a partir de esa respuesta; se conserva la opción de recalcular un trabajo analítico cuando procede.
- La continuidad del agente y la búsqueda de antecedentes mantienen sus comprobaciones de vigencia. Las respuestas antiguas visibles no se reutilizan como prueba actual.

## Comprobación

- Pruebas de conversación: se conserva la respuesta original, el separador cambia de posición al continuar el chat y la respuesta nueva utiliza el dato vigente. La revisión de informes de otra versión conserva el contenido histórico y señala el resultado anterior.
- Se inspeccionó en el navegador local el chat existente que contenía una respuesta sobre Valencia y una corrección posterior a Vila-real: las dos respuestas anteriores reaparecen y la línea queda antes del mensaje de corrección.
- El separador usa la frase breve «Contexto actualizado desde aquí» para mantenerse en una sola línea también en la vista estrecha; su descripción accesible conserva la explicación completa.
- Pasan 274 pruebas Python y 16 pruebas JavaScript. La sintaxis JavaScript y Python, y `git diff --check` también pasan.
