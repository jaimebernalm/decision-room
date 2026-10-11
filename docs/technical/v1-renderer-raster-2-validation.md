# Captura contenida: espera acotada de composición

Cambio posterior a la congelación de F5b, separado de sus materiales y resultados.
No cambia el motor por defecto ni recupera una pérdida del ensayo como entrega válida.

El HTML original de `clinica-1-opencode` en F5, SHA-256
`5fb0050c52fdae09ec525a616b5329c3d0bf7aea850552d2e3a3b96b05a3e4a5`,
falla en cinco ejecuciones consecutivas con el renderizador original. El diagnóstico
se ejecutó exclusivamente en su contenedor, sin credenciales, red ni montajes de datos.
Conserva intactos el HTML y el resultado fallido original; no examina su calidad.

No hay timers, requestAnimationFrame, animaciones CSS/SMIL, imágenes ni canvas en ese
documento. El navegador confirma cero animaciones. Durante capturas inmediatas, el
HTML completo serializado permanece idéntico (SHA-256
`1b7cd18c8cba3886cb449ea3d6312c6df7870fa84c44750658c4648a8792fd32`),
pero cambian píxeles en una región del SVG. La pausa entre capturas elimina el fallo
en estas reproducciones. La evidencia es compatible con composición asíncrona de
Chromium; no identifica una causa interna específica del navegador.

`v1-container-raster-2` conserva la desactivación de scripts/animaciones y exige dos
capturas PNG exactamente iguales separadas por 100 ms. Si difieren, permite hasta
seis capturas por tile; después falla. No acepta tolerancias, una captura parcial ni
un par distinto. El inventario y la URL se vuelven a comprobar al terminar. Conserva
los límites de dimensión, bytes, CPU, memoria, tiempo y el aislamiento de F4. La
instantánea sigue siendo HTML propio con PNG, sin marcado del agente.

La versión nueva tiene una imagen distinta:
`sha256:76f6065cf3bf25ccc0fb440a8435d9dbaabe9d2e02e807d42c7c946e07fab6e0`.
Por tanto, recibe otra clave de derivado; no sustituye resultados anteriores bajo
la misma identidad. F5b sigue usando su imagen y versión originales congeladas.

Sobre los bytes exactos del HTML que falló, cinco ejecuciones nuevas pasan, con tres
páginas y los mismos hashes en las cinco:

- Instantánea: `0a3da9419fe7d09c5745526a11361fc7f0787ed7f34443de42096f0afbbb3089`.
- Texto: `7f66351f496ffc509395e128e61ccd6fa64f25bbd6bc3ac7d599fed5e9d94e81`.

Validación: 42/42 pruebas focalizadas de `test_report_browser`, `test_report_derive`,
`test_report_derivatives`, `test_engine_view` y `test_engine_chat`, sin omitidas,
con PostgreSQL real y Chrome contenido; cero llamadas API. Incluyen la espera
simulada que termina en un par idéntico, el rechazo al agotar las seis capturas,
los fixtures hostiles, límites y recuperación. No se añaden HTML ni datos del ensayo
al repositorio. Esto acredita la corrección técnica de esa captura, no su exactitud
numérica ni la adopción del motor.
