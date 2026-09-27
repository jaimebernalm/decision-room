# Integración de interfaz y onboarding — 27 de septiembre de 2026

## Alcance

Se integran los commits de navegación compacta `8ae6973` y `7489fe9` en
`feature/ui-ux`, y se resuelven los conflictos con `master` (`538abcf`, PR #4).
Se conserva la interfaz React, los bundles CSV/Excel y el catálogo con diagramas
ER del paso 3.2. Los pasos 3.3–3.5 siguen pendientes.

La integración conserva los datos y las API de onboarding y lotes CSV de la
rama anterior. Mantiene los nombres originales con las dos interfaces de
importación, el límite actual de 2.000.000.000 bytes y la protección interna del
número de archivos. La migración 20 registra las tablas compatibles sin
confundir el antiguo uso del número 16 con el dashboard. Se conserva el
servicio de recursos compilados de React y se retira el JavaScript anterior.
Las cookies de sesión quedan separadas por puerto; puede ser necesario volver
a iniciar sesión después de reiniciar el servidor actualizado.

## Comprobaciones

- Backend: se ejecutan 96 pruebas de web, dossier, bundles, dashboard,
  migraciones, ingesta, catálogo, reintentos y contexto conversacional.
  Pasan 95; una prueba de bundles todavía inyectaba la antigua cookie fija.
  Se corrige para usar el inicio de sesión real. La revalidación
  descrita a continuación pasa.
- Revalidación concreta: pasan seis pruebas en total: tres de `BundleTests`,
  dos de lotes de `WebTests` y una nueva prueba de migración. Esta última
  comprueba que una instalación con el antiguo esquema 16 conserva el trabajo,
  el archivo y el vínculo de onboarding al incorporar dashboard y catálogo;
  también comprueba que repetir la migración es seguro.
- Frontend: 65 pruebas aprobadas; compilación TypeScript/Vite correcta.
- Lint: sin errores, con los avisos existentes de Fast Refresh. Vite conserva
  el aviso de tamaño de bundles.
- Compilación Python con el entorno del proyecto y revisión de espacios y
  marcadores de conflictos correctas.

Las pruebas utilizan bases de datos aisladas y modelos simulados. Esta
integración no repite la evaluación de calidad analítica con modelos reales;
la evidencia de los pasos 3.1 y 3.2 sigue en sus documentos de validación.
