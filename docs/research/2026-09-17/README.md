# Fuentes de datos inspeccionadas

Investigación de Decision Room del 17 de septiembre de 2026. Se descargaron archivos públicos para comprobar su estructura. No se entrenaron modelos ni se evaluó el producto con usuarios.

## Atribución y procedencia

### Online Retail II

- Autor: Daqing Chen.
- Cita de la fuente: Chen, D. (2012). *Online Retail II*. UCI Machine Learning Repository. DOI: [10.24432/C5CG6D](https://doi.org/10.24432/C5CG6D).
- [Ficha original y licencia CC BY 4.0](https://archive.ics.uci.edu/dataset/502/online+retail+ii).
- [ZIP original](https://archive.ics.uci.edu/static/public/502/online+retail+ii.zip).
- Archivos locales: [ZIP original](../../../data/exploratory/2026-09-17/online-retail-ii.zip) y [Excel extraído](../../../data/exploratory/2026-09-17/online_retail_II.xlsx).
- No se modificaron los datos. Se inspeccionaron las dimensiones, cabeceras y primeras 500 filas de cada hoja. Los conteos de vacíos corresponden a esas muestras.
- Resultado: `public_data_inspection.json`.

### Sport Services

- Autores: Paulo Pinheiro y Luis Cavique.
- *Sport Services Dataset*, versión 1 (2020). DOI: [10.17632/yprk4jdgnv.1](https://doi.org/10.17632/yprk4jdgnv.1).
- [Repositorio original y licencia CC BY 4.0](https://data.mendeley.com/datasets/yprk4jdgnv/1).
- [Descripción científica de los autores](https://pmc.ncbi.nlm.nih.gov/articles/PMC8100056/).
- [Descarga original](https://data.mendeley.com/public-files/datasets/yprk4jdgnv/files/8421f41a-b8f4-463c-aa37-78ac28bdd24d/file_downloaded).
- Archivo local: [sport-services.csv](../../../data/exploratory/2026-09-17/sport-services.csv), nombre original `DadosV3.csv`.
- Solo se cambió el nombre del archivo. Se leyeron todos los registros para comprobar estructura y campos vacíos, no calidad semántica exhaustiva.
- SHA-256: `775f226bef749497017579a9088e5f83249d8f1916c27d8d89acc189bccaa04d`.
- Resultado: `sport_data_inspection.json`.

### Hotel Booking Demand

- Autores: Nuno Antonio, Ana de Almeida y Luis Nunes.
- *Hotel booking demand datasets*. Data in Brief 22 (2019), 41–49. DOI: [10.1016/j.dib.2018.11.126](https://doi.org/10.1016/j.dib.2018.11.126).
- [Artículo original y suplementos](https://pmc.ncbi.nlm.nih.gov/articles/PMC6297060/). El artículo declara CC BY 4.0; los CSV se obtuvieron de su suplemento original.
- [ZIP original del editor](https://ars.els-cdn.com/content/image/1-s2.0-S2352340918315191-mmc2.zip).
- Archivo local: [hotel-original-2.zip](../../../data/exploratory/2026-09-17/hotel-original-2.zip); contiene `H1.csv` y `H2.csv`.
- No se modificaron los datos. Se leyeron ambos CSV para comprobar registros, cabeceras y número de campos. Se omitieron archivos auxiliares de macOS.
- Los primeros intentos de descarga desde PMC devolvieron HTML en lugar de ZIP; los datos utilizados proceden de la descarga posterior del editor.
- Resultado y SHA-256: `hotel_data_inspection.json`.

## Reproducción

Desde la raíz del repositorio, el script siguiente lee los originales de
`data/exploratory/2026-09-17/` y guarda los informes JSON en esta carpeta,
`docs/research/2026-09-17/`. Requiere Python y `openpyxl`; el análisis de CSV
utiliza la biblioteca estándar.

```sh
.venv/bin/python scripts/datasets/inspect_public_data.py
```

En este entorno se ejecutó con el Python del runtime de Codex porque el Python del sistema no estaba disponible sin aceptar la licencia de Xcode.

Los JSON generados describen comprobaciones estructurales. No representan una auditoría integral ni una validación predictiva o comercial.
