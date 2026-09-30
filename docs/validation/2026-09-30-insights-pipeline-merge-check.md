# Validación previa al merge de insights-pipeline

Fecha: 30 de septiembre de 2026. Base revisada: `master` en `3084654`.
Código de la rama comprobado: `3e41483`, con la corrección de prueba descrita abajo.

## Alcance

Integra rondas de investigación y revisión, onboarding conversacional,
conocimiento de relaciones, analistas paralelos, evaluación por objetivo,
planificador de negocio, actividad pública, monitor interno y lectura/exportación
del informe. Los criterios de aceptación general de calidad analítica permanecen
abiertos, según las evaluaciones documentadas de 3.6 y 3.7.

## Resultados

- Regresión completa de Python: **504 pruebas ejecutadas**, 503 aprobadas y un
  fallo en una expectativa antigua de migración. No hubo otros fallos ni errores.
  PostgreSQL real, bases desechables y sandbox; duración aproximada de 308 s.
- La prueba antigua esperaba esquema 21 aunque las migraciones llegan a 26.
  Se actualiza la expectativa y se comprueban también `activity_traces` y los
  campos `finished_at` de llamadas/revisiones de chat. Se mantiene la comprobación
  de conservación del onboarding y del archivo histórico. Repetición completa
  del módulo de migración: **9/9 aprobadas**. El cambio solo afecta a la prueba.
- Frontend: **111/111 pruebas aprobadas**, 16 archivos. TypeScript/Vite y lint
  completados sin errores, con los avisos existentes de Fast Refresh y bundle.
- Bruma guardado: presentación, actividad pública, monitor autorizado y PDF
  responden **HTTP 200** desde un servidor local temporal. PDF de **14 páginas**,
  `application/pdf` y `Cache-Control: no-store`. No se regenera el análisis ni
  se llama al proveedor del modelo. La primera selección del monitor en el
  script de comprobación usó un campo de listado inexistente; se corrigió el
  script para resolver la traza mediante el enlace persistente del job.
- `git diff --check` correcto. Revisión de los archivos y líneas añadidas:
  sin runtime, secretos reales, datos privados ni archivos de más de 1 MB.
  Las rutas ficticias de las pruebas de redacción son fixtures públicos.
- Rama sin divergencia respecto a la base remota: 0 commits exclusivos de
  `master`, antes de incorporar esta comprobación de cierre.

## Reproducción

Con PostgreSQL configurado mediante `DECISION_ROOM_DATABASE_URL`:

```sh
PYTHONPATH=.:tests .venv/bin/python -m unittest discover -s tests -v
PYTHONPATH=.:tests .venv/bin/python -m unittest test_business_migration -v
npm --prefix frontend test
npm --prefix frontend run lint
npm --prefix frontend run build
git diff --check
```

Los registros detallados permanecen en `.local/premerge-*.log`, fuera de Git.
La revisión visual previa del informe y de todas las páginas del PDF se conserva
en [la validación de lectura y PDF](2026-09-28-report-reading-and-pdf.md).
