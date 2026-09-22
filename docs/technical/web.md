# Aplicación web local · Entrega 2

La aplicación utiliza el backend existente: ingesta CSV, PostgreSQL, principal
LangGraph, Python aislado en Docker y revisor. El diseño y alcance están en
[web-plan.md](web-plan.md). La calidad analítica de la entrega 1 sigue pendiente;
construir la interfaz no resuelve los errores semánticos conocidos.

## Abrir la aplicación

Con el entorno Python y el sandbox ya preparados según las guías existentes,
iniciar LM Studio con el modelo del proyecto y ejecutar desde la raíz:

```sh
.venv/bin/python scripts/dev/start_web.py
```

Este comando arranca PostgreSQL local y abre el navegador con acceso al espacio.
Utiliza `qwen3.8-27b-splash` salvo que se indique `--model` o la variable
`DECISION_ROOM_AGENT_MODEL`. El servidor del modelo debe estar escuchando en el
endpoint configurado; Docker/Colima y la imagen del sandbox deben estar disponibles.
El lanzador no descarga modelos ni instala dependencias.

Para iniciar únicamente el servidor web:

```sh
DECISION_ROOM_AGENT_MODEL=qwen3.8-27b-splash \
DECISION_ROOM_AGENT_TIMEOUT=300 \
.venv/bin/python -m decision_room.web --open
```

Dirección predeterminada: `http://127.0.0.1:8787`. `--port` cambia el puerto.
Los parámetros de proveedor siguen siendo los del [agente](agent.md). No se
cargan automáticamente archivos `.env`. Sin modelo configurado se puede abrir
la interfaz y preparar un borrador, pero no iniciar análisis.

El acceso inicial usa una clave generada en el almacenamiento privado
(`.local/storage/.web-access-key` por defecto). `--open` la pasa al navegador en
un fragmento que se intercambia por una cookie HttpOnly y se retira enseguida de
la URL; no entra en URLs HTTP ni logs de acceso. La clave también se puede pegar
en la pantalla de acceso. No se debe publicar ni compartir ese archivo.

## Experiencia

- **Vista general y Mis análisis:** búsqueda, estados y acceso al detalle. El
  espacio web empieza vacío; las evaluaciones históricas por CLI no se incorporan
  automáticamente. No se inventan informes de muestra ni métricas de negocio.
- **Nuevo análisis:** contexto obligatorio, pregunta o exploración general,
  título y un CSV UTF-8 de hasta 20 MiB. Se puede usar el CSV público de ventas
  diarias de los casos de referencia; hay que describir su contexto ficticio.
- **Borrador:** texto guardado en el navegador. Antes de enviar, un archivo debe
  seleccionarse de nuevo tras cerrar o recargar. Después de enviar, original y
  estado quedan persistidos en el servidor.
- **Preguntas:** se muestran las del principal o el revisor, con su motivo,
  opciones reales si existen, texto libre y «No lo sé». Una respuesta pendiente
  en el formulario es un borrador; «Guardar y continuar» la registra duraderamente.
- **Progreso:** etapas reales, sin porcentajes ni tiempos inventados. Se puede
  salir y volver por el enlace del análisis. Cerrar la pestaña no detiene el
  trabajador; detener el servidor pausa la ejecución, que se recupera al arrancar.
- **Resultado:** solo el informe actualmente publicable; incluye cobertura,
  hallazgos, gráficos cuando los haya, interpretación, limitaciones y evidencia
  desplegable. Se comprueba otra vez su aprobación en cada acceso. Un hold
  independiente o un cambio de contexto retiran su disponibilidad también del panel.
- **Archivos:** descarga autenticada de cada original y enlace a su análisis.

Los informes bloqueados, insuficiencia de datos y fallos técnicos se distinguen.
Un fallo ofrece reintento desde los checkpoints. Una revisión sin aprobación
conserva el trabajo y explica que no se puede entregar un informe.

## Ejecución y recuperación

`web_jobs` registra una clave idempotente de envío, contexto, archivo, identidades
de las cuatro etapas, modelo, estado y respuesta pendiente. Cada análisis web
crea su ámbito de negocio separado. Los archivos permanecen en almacenamiento
privado; `web_jobs` no contiene filas CSV. `web_replies` conserva la idempotencia
de los envíos de respuestas.

El trabajador toma un advisory lock PostgreSQL exclusivo antes de seleccionar
un trabajo en cola o interrumpido. No depende de una petición HTTP abierta.
Las claves estables `web:<job-id>` permiten descubrir una sesión, investigación
o revisión ya guardada aunque se interrumpiera el proceso antes de enlazarla al
registro web. Las respuestas se registran antes de ejecutar el siguiente paso.
Los límites de llamadas, investigaciones y revisión siguen siendo los del backend.

Un resultado incierto de una llamada al modelo no se repite automáticamente:
se presenta como interrupción. El botón de reintento permite repetir esa llamada
sin duplicar la respuesta del propietario. Se añadió el parámetro opcional
`retry_uncertain` a las dos operaciones de respuesta del backend para cubrir ese
caso. No cambia la política de reintentos de los consumidores anteriores.

Si quedó una ejecución Python abandonada, el recuperador existente detiene su
contenedor y la registra como interrumpida antes de continuar el grafo. Los
resultados terminados se reutilizan según las reglas existentes del backend.
Un único archivo de evidencia ilegible bloquea su informe sin impedir abrir el
resto del espacio de trabajo.

## Frontera local

HTTP escucha **solo en 127.0.0.1**. Valida Host, Origin y un encabezado propio en
las mutaciones; todas las rutas de datos, archivos e informes exigen cookie de
acceso. Los recursos no se cachean, no se cargan recursos de terceros y se usa
CSP. El contenido del agente se escapa; el informe está en un iframe sin scripts.
La descarga se resuelve mediante el identificador del trabajo y su ámbito, nunca
mediante una ruta de archivo suministrada por el cliente.

Este acceso representa **un propietario local**, no un sistema multiusuario ni
un despliegue público. La operación concurrente de comercios, límites operativos
completos, gestión de identidades, backups y publicación pertenecen a entrega 4.
El dashboard con filtros que recalculan métricas sigue fuera de esta entrega.

## Archivos y comprobaciones

- `decision_room/web/service.py`: orquestación duradera y traducción al estado del producto.
- `decision_room/web/server.py`: HTTP autenticado, límites y archivos privados.
- `decision_room/web/static/`: frontend HTML, CSS y JavaScript sin dependencias de ejecución nuevas.
- `scripts/dev/start_web.py`: apertura del espacio local.
- `tests/test_web.py`: PostgreSQL y sandbox reales con roles controlados, fronteras HTTP y recuperación.

```sh
.venv/bin/python -m unittest discover -s tests -p 'test_web.py' -v
.venv/bin/python -m unittest discover -s tests -v
node --check decision_room/web/static/app.js
```

Los tests usan bases PostgreSQL temporales y el sandbox local. Los resultados de
Computer Use y modelo real se registran por separado en la validación de entrega 2.
