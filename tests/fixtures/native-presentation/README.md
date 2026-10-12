# Informe sintético de presentación nativa

`informe.json` contiene una portada, dos tarjetas con valoración, una prioridad con
acción y sus dos ramas, tres tarjetas de ejemplo y una prioridad con una acción
sin ramas con el rótulo propio «Qué revisar en abril». Sus textos y cifras son ficticios; no procede de un cliente ni de los
negocios usados en la evaluación del motor.

El contenido pasa por el mismo parser que cualquier entrega nativa. La proyección
de referencia se guarda en `frontend/src/test-fixtures/blocks-presentation.json`.
Para regenerarla desde la raíz del repositorio:

```sh
.venv/bin/python - <<'PY'
import json
from pathlib import Path
from decision_room.engine import blocks

projection = blocks.parse(Path('tests/fixtures/native-presentation/informe.json').read_bytes())
Path('frontend/src/test-fixtures/blocks-presentation.json').write_text(
    json.dumps(projection, ensure_ascii=False, indent=1) + '\n')
PY
```

El fixture permite comprobar la misma información en web, texto canónico, citas
del chat y PDF. Las cifras fuera de prioridades quedan fuera de la cobertura del
comprobador independiente actual; el ejemplo no afirma que estén verificadas.
