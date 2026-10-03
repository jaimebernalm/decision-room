# Búsqueda de chats por contenido · 2 de octubre de 2026

Paso 2.5.22, sobre la navegación y fijación de 2.5.21.

El buscador de la biblioteca incluye lupa y explica que admite título o mensaje.
El campo activo conserva un borde neutro, sin contorno ni halo azul. Este ajuste
solo afecta al buscador de Chats.

`GET /api/chats?query=...` busca títulos, texto del propietario y prosa visible de
las respuestas guardadas, incluidas preguntas, recuerdos y evidencia citada.
La coincidencia es literal, sin distinguir mayúsculas o tildes; símbolos como
`%`, `_`, `+` y `&` son caracteres de búsqueda. La consulta admite 300 caracteres.
El servidor recorre mensajes por lotes de 50 y devuelve un fragmento corto con
su autor cuando la coincidencia está en el contenido. No envía historiales
completos al navegador ni consulta modelos, embeddings, prompts o logs internos.

Los resultados conservan el orden de fijación/último mensaje y se limitan al
negocio activo y a chats no eliminados. La interfaz espera 200 ms entre cambios,
cancela solicitudes previas y rechaza respuestas de otro negocio. Al borrar la
consulta recupera la biblioteca completa. Un fallo ofrece reintento y se distingue
de una búsqueda sin coincidencias.

## Comprobaciones

- 219 pruebas frontend en 29 archivos pasan. Las nuevas regresiones comprueban
  búsqueda remota y fragmentos escapados, borrado de consulta, respuestas tardías,
  errores/reintento y rechazo de resultados de otro negocio. Se verifica el texto
  del buscador en inglés/español.
- 6 pruebas backend dirigidas pasan: título con tildes, texto del propietario
  situado más allá de 4.000 caracteres, respuesta del asistente y evidencia
  anidada; exclusión de campos internos, chats ajenos y eliminados; autenticación,
  límite de longitud y caracteres literales. También pasan las regresiones de
  fijación y orden cronológico.
- Compilación TypeScript/Vite correcta y lint sin errores. Permanecen los avisos
  existentes de lint y de tamaño del paquete de chat.
- Navegador sobre localhost: una búsqueda devuelve chats cuyo título no contiene
  la consulta y muestra el fragmento del asistente. Campo enfocado con contorno
  `none`, sombra de extensión cero y borde gris. Lupa y borrado de consulta visibles.
- Móvil 390 × 844: buscador, fragmentos y menú por fila visibles. Ancho del documento
  y ancho desplazable de 390 px; se restablecen el tamaño y el listado completo.

Las capturas permanecen en `.local/`, fuera de Git. La búsqueda recorre el historial
local; no incorpora un índice de texto completo ni una búsqueda semántica. Los
fragmentos ayudan a localizar chats y conservan su carácter de diálogo histórico.
