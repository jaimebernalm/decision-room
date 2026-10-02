# Integración local de UI1 y UI2 · 1 de octubre de 2026

Se integran `feature/product-ux` (`4c9a2c2`) y `feature/ui-improvement`
(`93ed68e`) en `codex/ui-integration`, tomando `master` (`5af6cb7`) como base.
Las dos ramas originales se conservan. El merge mantiene sus historiales;
no incorpora `feature/report-quality` ni implica publicación en GitHub.

## Orden y resolución completados

1. Incorporar UI1 sobre la base mediante avance directo, sin inventar commits.
2. Unir UI2 y resolver los tres archivos con conflictos:
   - Ficha: conservar grupos, acciones compactas, descripción plegada y elección
     explícita de conflictos; incorporar idioma y selección de contexto de UI1.
   - Esquema: conservar `report_presentation_revisions` en migración 27 y añadir
     `web_dossier_layouts` en 28. Ambas ramas habían usado 27 independientemente.
     La migración declarativa debe funcionar desde cualquiera de ellas.
   - Extracción: combinar `presentation_only` y `group_id`, manteniendo las
     descripciones como datos no fiables y las órdenes de presentación fuera de
     la memoria del negocio. El prompt combinado queda versionado en `memory-v7`.
3. Comprobar el conjunto, revisar los archivos preparados y guardar el merge local.

Los archivos fusionados automáticamente se revisan también: esquema estricto del
proveedor, asignación de memorias, rutas autenticadas, tipos y pruebas de selección.
Los textos nuevos de ficha y editor de grupos entran en el catálogo inglés.
Nombres, descripciones y hechos escritos por el propietario se conservan.
Las versiones de conflicto tienen identificadores estables independientes del
idioma: cambiarlo no borra la selección ni el texto que se va a guardar.

## Comprobaciones

- Frontend: **194 pruebas en 25 archivos** pasan. Las regresiones nuevas eligen una
  alternativa, cambian de idioma y guardan el contenido original; comprueban grupo
  fijo al añadir, borrador conservado, nombre de cliente coincidente con una clave
  del catálogo y descripciones conservadas al cambiar de idioma.
- Compilación de producción y lint sin errores. Permanecen avisos existentes de
  tamaño de paquetes, Fast Refresh y efectos; no se declara que hayan desaparecido.
- Backend: **83 pruebas dirigidas** de ficha, migración, memoria, idioma y edición
  de presentación pasan. La regresión general ejecuta **551 pruebas**: 549 pasan
  en la primera ejecución y dos fixtures necesitan adaptación a los cambios de UI1
  y al esquema combinado. Se actualiza la expectativa de versión 26 a 28 y el
  stub de publicación se aplica al `Workspace` de cada petición, verificando el
  informe correcto. Tras corregirlos, las siete pruebas de actividad y las pruebas
  de onboarding/HTTP vuelven a pasar. La nueva regresión de migración desde cada
  rama forma parte del bloque dirigido; no se inventa una ejecución general posterior.
- PostgreSQL: comprobación de migración desde los esquemas de ambas ramas,
  repetición idempotente, tablas presentes y grupos/versiones/archivos conservados.
  Las órdenes solo de presentación no crean memorias; un mensaje mixto mantiene
  sus hechos independientes y su clasificación en el grupo correspondiente.
- Navegador con fixture sintético: ficha y compositor juntos, selección de la
  alternativa del 30 % con guardado habilitado, cancelación sin modificar el hecho,
  interfaz en inglés/español, nombres/descripciones originales y móvil 390 × 844.
  Un solo campo de mensaje y anchura de documento de 390 px en móvil.

Las pruebas y capturas usan datos ficticios y bases desechables. Los artefactos y
el servidor de vista previa permanecen en `.local/`, fuera de Git. No se envían
mensajes al modelo durante la comprobación visual. Esta integración no acredita
la calidad analítica pendiente de la rama de informes.
