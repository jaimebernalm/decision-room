# Wide World Importers — downloaded sample database

Downloaded on 18 September 2026 from Microsoft's official SQL Server samples release.

## Files

- `WideWorldImporters-Full.bacpac`: full operational database export, containing schema and table data. Size: 61,291,839 bytes (61.3 MB).
- `LICENSE.txt`: Microsoft's MIT sample license, retrieved from the official repository.
- `UPSTREAM-README.md`: Microsoft's sample documentation, retrieved from the official repository.
- `release-metadata.json`: GitHub release metadata captured at download time.
- `SHA256SUMS.txt`: locally computed SHA-256 for the database file.
- `tables-with-data.txt`: distinct table names found in the archive's data entries.

To verify the checksum, run `shasum -a 256 -c SHA256SUMS.txt` from this folder.

## Provenance

- [Official release](https://github.com/microsoft/sql-server-samples/releases/tag/wide-world-importers-v1.0).
- [Exact database download](https://github.com/microsoft/sql-server-samples/releases/download/wide-world-importers-v1.0/WideWorldImporters-Full.bacpac).
- Release asset ID: `80319388`; asset last updated on 7 October 2022 according to the captured metadata.
- [License source](https://raw.githubusercontent.com/microsoft/sql-server-samples/master/license.txt).
- [Documentation source](https://github.com/microsoft/sql-server-samples/blob/master/samples/databases/wide-world-importers/README.md).

## Checks performed

- Download completed successfully.
- File size matches the official release API's asset size.
- Archive integrity check (`unzip -tq`) passed without errors.
- Confirmed schema (`model.xml`) and table-data (`Data/.../*.BCP`) entries.
- SHA-256: `dddafe3e03d000c874e5cc4204e73de27e11283cf663b0f5f43d7d08948a0fc7`.

The SHA-256 is a local fingerprint, not a comparison against a publisher-provided checksum; the release metadata supplied no digest.

## What this is ready for

This is a fictional business sample, not real merchant records. The full operational database was selected for connected sales, purchasing, customer, supplier, and inventory scenarios.

The BACPAC remains the unmodified original. Its contents have now been converted
to CSV and Excel without installing a SQL Server instance.

## Converted files

- [CSV files](exports/csv): 48 files, one for each source table, including two empty tables with headers.
- [Excel workbooks](exports/excel): four workbooks, grouped by source schema.
- [Export details and limitations](exports/README.md).

| Workbook | Source data rows |
|---|---:|
| [Sales](exports/excel/WideWorldImporters-Sales.xlsx) | 701,656 |
| [Purchasing](exports/excel/WideWorldImporters-Purchasing.xlsx) | 12,915 |
| [Warehouse](exports/excel/WideWorldImporters-Warehouse.xlsx) | 3,958,807 |
| [Application](exports/excel/WideWorldImporters-Application.xlsx) | 40,455 |
| Total | 4,713,833 |

Start with the **InvoiceLines**, **Invoices**, and **Customers** sheets in the
Sales workbook. The Warehouse workbook is much larger because it also retains
the source's temperature-sensor history; it is not a small MVP fixture.

All 98 declared foreign-key relationships were checked. All 228,265 invoice
lines reconcile for quantity, unit price, tax, and extended price. These checks
validate the conversion's structure and key arithmetic, not every business
assumption in the synthetic source.

Downloading this sample does not change Decision Room's planned PostgreSQL application database.
