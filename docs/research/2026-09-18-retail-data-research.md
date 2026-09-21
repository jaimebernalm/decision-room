# Retail data sources and possible customer inputs for Decision Room

Research date: 18 September 2026.

Scope: gift shops, stationery shops, household goods, accessories, and other retailers of non-perishable products. Includes adjacent retail datasets when they supply useful data types missing from closer sector matches.

## Findings

Useful real data and fictional samples exist. There is enough material to start a varied evaluation collection. This search did not find one verified, openly reusable dataset containing all the records of a small independent shop: sales, purchases, historical costs, inventory, expenses, bank movements, staffing, and marketing together.

Use three complementary resources: real transactions for realistic irregularities, internally consistent fictional business data for connected operational scenarios, and vendor export documentation for realistic file structures. Separate datasets represent separate businesses; their rows must not be joined as though they describe one shop.

This is a research catalog, not an expansion of the agreed MVP. A data type being available does not mean Decision Room already supports it or should require it from every owner.

Verification: checked primary source pages, descriptions, published fields, access routes, and selected license statements. Reused the existing local inspection of Online Retail II. No new bulk datasets were downloaded or fully audited during this research. Sources with access, provenance, or reuse uncertainty are marked below.

## Dataset catalog

### 1. UCI Online Retail II — closest starting point for gift retail

- **Nature:** real UK online gift retailer; many wholesale customers. 1,067,371 transaction rows, December 2009–December 2011.
- **Data:** invoice, product, description, quantity, timestamp, selling price, customer identifier, country; cancellations and missing values.
- **Format/access:** public XLSX download; already present locally at `data/exploratory/2026-09-17/online_retail_II.xlsx`.
- **Reuse:** source declares CC BY 4.0; attribution required.
- **Limit:** no stock balances, acquisition costs, payroll, or operating expenses. `StockCode` identifies a product; it is not a stock quantity. Online/wholesale behavior is not equivalent to a small physical shop.
- **Our use:** first real-data ingestion and sales-evidence case. Prior local inspection checked two sheets and sampled 500 rows per sheet; it was not a full audit.

[Publisher and download](https://archive.ics.uci.edu/dataset/502/online+retail+ii). [Earlier inspection](2026-09-17/public_data_inspection.json).

### 2. Microsoft Wide World Importers — broad connected operational sample

- **Nature:** fictional novelty-goods wholesaler supplying retailers; generated sample business.
- **Coverage:** customers, suppliers, sales orders and invoices, purchase orders, supplier/customer financial transactions, special prices, products, holdings, and inventory movements.
- **Format/access:** SQL Server database releases and source scripts. Follow-up: downloaded the full BACPAC and converted all 48 tables into CSV files and four Excel workbooks, retaining 4,713,833 rows. See [data/wide-world-importers](../../data/wide-world-importers/README.md) for files and validation details.
- **Reuse:** Microsoft links its MIT sample license from the database documentation.
- **Limit:** not evidence from a real shop, and not a complete payroll/general-ledger dataset.
- **Our use:** connected purchasing, stock, sales, and payment cases with known relationships.

[Business description](https://learn.microsoft.com/en-us/sql/samples/wide-world-importers-what-is?view=sql-server-ver17), [table catalog](https://learn.microsoft.com/en-us/sql/samples/wide-world-importers-oltp-database-catalog?view=sql-server-ver17), [download repository](https://github.com/microsoft/sql-server-samples/blob/master/samples/databases/wide-world-importers/README.md), [license](https://github.com/Microsoft/sql-server-samples/blob/master/license.txt).

### 3. Olist Brazilian Ecommerce — real orders, payments, logistics, and feedback

- **Nature:** anonymized real commercial data, approximately 100,000 orders from 2016–2018.
- **Coverage:** orders and items, products, sellers, customers, payments, delivery information, freight, geography, and reviews.
- **Format/access:** related CSV tables on Kaggle; download/account requirements were not exercised here.
- **Reuse:** publisher lists **CC BY-NC-SA 4.0**. Do not assume this is suitable for commercial product testing or redistribution without resolving that restriction.
- **Limit:** marketplace activity, not one independent shop; not a complete cost, stock, or expense ledger.
- **Our use:** research reference for joins and different record granularities; an order can contain items from multiple sellers.

[Publisher dataset, schema, and license](https://www.kaggle.com/datasets/olistbr/brazilian-ecommerce).

### 4. dunnhumby Source Files — promotions and customer purchase histories

- **Nature:** publisher describes these as representations inspired by real-world data; do not label every release as untouched real transactions.
- **Coverage:** Complete Journey provides two years of transactions for 2,500 frequent-shopping households, with selected attributes and direct-marketing history. Breakfast at the Frat adds product/store/week sales, prices, and promotional context.
- **Format/access:** download options on the publisher page; actual packages and download conditions were not tested.
- **Reuse:** a clear general-purpose commercial reuse license was not established in this review.
- **Limit:** grocery-oriented, selected customers/categories, and not a full business ledger.
- **Our use:** optional research on customer history and promotions. Observed sales changes do not by themselves establish campaign causation.

[Publisher descriptions and download options](https://www.dunnhumby.com/source-files/).

### 5. Walmart M5 — daily item sales, selling prices, and calendar

- **Nature:** Walmart retail sales competition data.
- **Coverage:** historical daily unit sales by item/store, selling prices, and calendar records.
- **Format/access:** CSV files on Kaggle; competition rules govern access/use. No download performed here.
- **Limit:** daily units are not transaction receipts; selling prices are not purchase costs. It does not provide the complete financial or operational state of a shop.
- **Our use:** long histories, daily aggregation, wide tables, and calendar alignment. This does not commit the MVP to forecasting.

[Organizer data description and files](https://www.kaggle.com/c/m5-forecasting-accuracy/data).

### 6. Google Merchandise Store GA4 sample — online shopping behavior

- **Nature:** obfuscated event data from a merchandise ecommerce site, covering November 2020–January 2021.
- **Coverage:** ecommerce web events, useful for browsing and purchase-funnel exploration.
- **Format/access:** public BigQuery dataset `bigquery-public-data.ga4_obfuscated_sample_ecommerce`; a query/export step is needed for CSV. Not downloaded.
- **Limit:** obfuscation affects consistency; not a full sales ledger and not the same data as the Analytics demo account. It does not supply a complete advertising-spend ledger.
- **Our use:** an optional online-channel scenario, separate from physical-store sales.

[Google's dataset documentation](https://developers.google.com/analytics/bigquery/web-ecommerce-demo-dataset).

### 7. Microsoft/obviEnce Power BI samples — retail and business-function examples

- **Nature:** the Retail Analysis page describes real anonymized source data; the collection also contains illustrative/fictitious examples. Classify each sample separately.
- **Coverage:** retail performance; separate samples for procurement, supplier quality, HR, profitability, and spending.
- **Format/access:** XLSX and/or PBIX, depending on the sample. Some underlying Excel data requires Power Pivot rather than ordinary visible worksheets.
- **Reuse:** published terms permit internal reference and describe Power BI demonstration purposes, with obviEnce attribution. Do not treat these as unrestricted open datasets for Decision Room.
- **Our use:** inspect business concepts and report layouts; these are not tables from one shared retailer.

[Retail sample](https://learn.microsoft.com/en-us/power-bi/create-reports/sample-retail-analysis), [sample files and usage terms](https://learn.microsoft.com/en-us/power-bi/create-reports/sample-datasets).

### 8. Retail Transactions and Stocks Data — promising physical-store candidate

- **Nature:** contributor describes a retail-business sample covering 40 storefronts and 2,326 SKUs; published April 2026.
- **Coverage:** daily transaction sales, on-hand stock, and product hierarchy.
- **Access/reuse:** Mendeley Data record with download control and CC BY 4.0 designation.
- **Verification limit:** the indexed page did not expose the file listing. File schema, quality, business identity, and underlying provenance were not independently verified. Keep this as a candidate, not an approved benchmark.

[Dataset record](https://data.mendeley.com/datasets/27x8mjm8k4/1).

### 9. Xero demo company — fictional accounting records

- **Nature:** fictional company available to users with a Xero login.
- **Coverage:** accounting workflows and fictional bank statements; useful as a route to accounting examples.
- **Access:** interactive demo, not a verified direct ZIP/CSV download. Xero documents exporting different areas separately. No account was opened or accessed for this research.
- **Limit:** actual export contents and reuse terms for an external benchmark still need checking. Not a real retailer's books.

[Demo company](https://central.xero.com/s/article/Use-the-demo-company), [export documentation](https://central.xero.com/0/article/Export-data-out-of-Xero-AU).

### 10. CORD — receipt images and structured annotations

- **Nature:** Indonesian shop/restaurant receipts. The public release contains 1,000 examples, smaller than the total collection described in the research.
- **Coverage:** receipt images, OCR text/boxes, and semantic annotations.
- **Access/reuse:** publisher repository links downloadable datasets and declares CC BY 4.0.
- **Limit:** not a longitudinal shop ledger; some fields were removed from the public release. Images/OCR are outside the current Excel/CSV MVP.
- **Our use:** future document-input research, not a dependency for the initial build.

[Publisher repository and releases](https://github.com/clovaai/cord).

### 11. Census/FRED — stationery-sector context

Published industry aggregates exist for office-supply and stationery retail, including a FRED sales series and Census retail summary tables. These are external benchmarks, not individual-shop records. Check geography, industry definitions, coverage dates, and units before comparison; no current growth claim is made here.

[FRED stationery retail series](https://fred.stlouisfed.org/series/MRTSSM45321USN), [Census retail summary](https://data.census.gov/table/AIESBASICTIMESERIES.AIES44BASIC?codeset=naics~45321&g=010XX00US).

## Real files an owner could supply

This is a broad input inventory, not an assertion that every shop has every file. Fields below are illustrative design examples. “Documentation” means the export route is documented, not that a populated public sample was downloaded. “Gap” means no sufficiently matched, reusable public sample was verified in this search.

| Input family | Examples of records/fields | Evidence or sample route |
|---|---|---|
| Daily/weekly/monthly sales summaries | Period, shop, sales, units, transaction count if recorded | Aggregate UCI or M5 into explicitly derived test files |
| Ticket/order headers | Order ID, timestamp, total, status, channel | UCI; Olist; Shopify order documentation |
| Itemized sales | Order ID, SKU, quantity, charged price | UCI; Olist; Shopify |
| Returns, cancellations, refunds, exchanges | Original reference, event date, quantity, amount, reason | UCI cancellations; Shopify refunds; richer exchange/reason cases remain a gap |
| Discounts and promotions | Offer, validity dates, qualifying products, discount | WWI special deals; dunnhumby; owner campaign sheet |
| Product catalog | SKU, barcode, category, variant, supplier, pack/unit | Shopify product sample/documentation |
| Price and cost records | SKU, effective date, selling price, acquisition cost | M5 selling prices; Shopify cost field; historical cost cases need separate evidence |
| Stock snapshots | SKU, location, timestamp, available/reserved/on-hand | Shopify inventory sample; Mendeley candidate |
| Stock movements and counts | Receipt, transfer, adjustment, write-off, counted quantity | WWI movements; richer stocktake discrepancy cases need inspection |
| Purchase orders and goods received | Supplier, ordered/received quantity, dates, status | WWI purchasing |
| Supplier records and commercial terms | Supplier ID, payment terms, lead times, minimum order | WWI suppliers; bespoke lead-time/minimum-order sheets remain a gap |
| Supplier invoices and credits | Invoice reference, item costs, charges, outstanding amount | WWI supplier financial records; accounting demo route |
| Customer records and loyalty | Pseudonymous customer ID, purchase history, membership | UCI/Olist/dunnhumby; full points/reward ledger remains a gap |
| Payment activity | Payment reference, method, amount, success/refund status | Olist; Shopify transaction-history documentation |
| Processor fees, disputes, settlements | Gross amount, fees, net, settlement dates | Stripe reporting documentation; populated matched public retailer sample not verified |
| Cash-register reconciliation | Opening float, cash counted, withdrawals, variance | Owner cashbook/register records; public matched sample gap |
| Bank and card statements | Booking/value date, amount, currency, description, balance | Xero fictional statement route; no real shop-linked bank sample verified |
| Operating expenses | Rent, utilities, packaging, insurance, software, maintenance | Accounting exports/demo route; no complete matched real-shop ledger found |
| Accounting reports | General ledger, chart of accounts, trial balance, income statement, balance sheet | Xero/QuickBooks report/export documentation |
| Receivables and payables | Invoice, due date, paid/unpaid amount, aging | WWI customer/supplier transactions; accounting report route |
| Tax records | Tax codes, collected amounts, input tax, filing period | Order/accounting exports; these are data examples, not tax calculations or advice |
| Staff schedules and timecards | Employee ID, location, clock times, breaks, hours | Square's documented CSV exports |
| Payroll and commissions | Pay period, earnings, employer costs, commission basis | QuickBooks payroll export route; no matched public retail payroll dataset verified |
| Fulfillment and delivery | Order, dispatch/delivery dates, carrier, freight, failure | Olist; WWI |
| Marketing and advertising | Campaign, date, impressions, clicks, spend, conversions | Google Ads exports; dunnhumby for promotion/contact examples |
| Website and ecommerce behavior | Sessions/events, product views, cart/purchase events | Google GA4 public sample |
| Customer feedback and service | Review, rating, complaint category, resolution date | Olist reviews; operational support/repair/warranty logs remain gaps |
| Footfall and store activity | Visitors by hour, opening hours, closure periods | Owner counter exports or manual counts; matched public sample not verified |
| Budgets, targets, and plans | Target sales/spend, period, planned orders, assumptions | Owner spreadsheets; context rather than observed results |
| Financing, assets, and commitments | Loan schedule, asset purchase, lease terms, subscriptions | Accounting exports and owner documents; matched sample gap |
| Business context and events | Currency, tax basis, holidays, closures, stockouts, supplier changes | Owner answers/notes; calendar reference data. Label declarations separately from measured facts |

## Verified export references

- **Shopify orders:** documents order and transaction CSVs. One order can occupy several item rows with blank shared fields. Its refund total is not a complete item-level returns ledger. [Order export structure](https://help.shopify.com/en/manual/fulfillment/managing-orders/exporting-orders).
- **Shopify products:** provides a sample CSV, including variants, selling price, acquisition-cost field, and product metadata. A present-day cost field does not establish historical cost. [Product CSV and sample](https://help.shopify.com/en/manual/products/import-export/using-csv).
- **Shopify inventory:** provides a sample CSV and distinguishes available, committed, incoming, unavailable, and on-hand quantities. A snapshot alone cannot reconstruct past stockouts. [Inventory CSV and sample](https://help.shopify.com/en/manual/products/inventory/setup/inventory-csv).
- **Square sales reports:** documents export routes but explicitly excludes some reports, including cash drawer exports. Do not promise every visible report is downloadable. [Report export limitations](https://squareup.com/help/us/en/article/8362-print-export-or-email-your-reports).
- **Square staffing:** supports timecard and labor-cost reporting, with CSV export instructions. [Staff-hours reports](https://squareup.com/help/us/en/article/6140-employee-timecard-reporting).
- **QuickBooks:** documents Excel exports for customer, supplier, payroll, item, and transaction information; exact options depend on the product/version. [Export documentation](https://quickbooks.intuit.com/learn-support/en-ca/help-article/list-management/import-export-ms-excel-files/L9BDPsTTX_CA_en_CA).
- **Stripe:** documents an itemized CSV for account balance activity. Useful as an input structure for reconciling payments, fees, and settlement activity. [Balance report](https://docs.stripe.com/reports/balance).
- **Google Ads:** supports downloading statistics reports in spreadsheet formats. [Report exports](https://support.google.com/google-ads/answer/2404176?hl=en-gb).

## Formats and interpretation problems to include in testing

Owners may have CSV/Excel exports, manually maintained spreadsheets, exported Google Sheets, PDFs, scanned receipts, photographs, messages, contracts, and text notes. The first group matches the existing MVP; document/image extraction and new connectors would require additional scope.

The following are proposed tests based on the research, not claims that every cited dataset contains each issue:

1. Different levels of detail: one row per sale item, transaction, product/day, or month.
2. Several tabs/tables, report titles before the header, subtotals, merged cells, and formulas.
3. Decimal commas, currency symbols, ambiguous dates, time zones, and identifiers with leading zeros.
4. Gross versus net amounts; tax-inclusive prices; discount placement; refunds occurring after the original sale.
5. Summary/detail overlap, repeated uploads, revised exports, and duplicate transactions.
6. Missing days versus true zero sales; store closures versus missing coverage.
7. Pack quantities versus individual units; variant IDs versus product IDs; changing names and SKUs.
8. Current snapshots versus historical events; present costs versus costs effective at the sale date.
9. Many-to-many joins, partial payments, partial deliveries, and multiple records per order.
10. Separate reported facts, derived values, estimates, and owner explanations.

## Recommended first collection

1. **Start with the existing UCI workbook.** Produce a small chronological slice retaining complete invoices. Independently validate cancellation handling, then create labeled daily-summary and product-summary derivatives. This provides several data granularities from one provenance chain.
2. **Create controlled clarification variants.** Missing coverage and unclear treatment of returns must have recorded intended answers. Any edits to real data are labeled transformations; they are not presented as unmodified real records.
3. **Use WWI for later connected operational cases.** Extract a manageable set of mutually consistent tables before testing joins. Do not graft fictional stock or costs onto UCI and call the result real business data.
4. **Use official export structures for format variation.** Build clearly labeled synthetic fixtures for payroll, expenses, settlements, and similar gaps. An export template tests parsing; it does not supply realistic longitudinal behavior by itself.
5. **Keep restricted and unverified candidates separate.** Olist, M5, dunnhumby, obviEnce, Xero, and the Mendeley candidate each have unresolved access, use, or validation considerations identified above. This does not block starting with UCI and the Microsoft SQL sample.
6. **Retain real pilot files as a later evaluation source.** Public datasets cannot establish how representative the files of our eventual small-shop users will be.

No models were trained, product evaluations run, vendor accounts accessed, or existing MVP decisions changed during this research.
