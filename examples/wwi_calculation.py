"""Hand-written tool acceptance calculation; this is not the future agent."""
from dr_runtime import TABLES, connect, write_result

metrics, evidence = {}, []
with connect() as db:
    for alias in TABLES:
        query = f'SELECT count(*) FROM "{alias}"'
        metric = alias + '_rows'
        metrics[metric] = db.execute(query).fetchone()[0]
        evidence.append({'metric': metric, 'tables': [alias], 'operation': query})
    query = '''SELECT count(*),
        sum(CAST(ExtendedPrice AS DECIMAL(18,2))),
        sum(CAST(TaxAmount AS DECIMAL(18,2))),
        sum(CAST(ExtendedPrice AS DECIMAL(18,2)) - CAST(TaxAmount AS DECIMAL(18,2)))
        FROM sales_invoicelines'''
    count, total, tax, excluding_tax = db.execute(query).fetchone()
    for key, value in [('invoice_lines', count), ('extended_price_total', str(total)),
                       ('tax_total', str(tax)), ('amount_excluding_tax', str(excluding_tax))]:
        metrics[key] = value
        evidence.append({'metric': key, 'tables': ['sales_invoicelines'], 'operation': query})
    join_sql = '''SELECT count(*) FROM sales_invoicelines l
        JOIN sales_invoices i ON l.InvoiceID = i.InvoiceID'''
    metrics['joined_invoice_lines'] = db.execute(join_sql).fetchone()[0]
    evidence.append({'metric': 'joined_invoice_lines', 'tables': ['sales_invoicelines', 'sales_invoices'],
                     'operation': join_sql})
write_result(metrics, evidence=evidence, notes=[
    'Known WWI sample schema, supplied for an infrastructure test; relationship inference is not implemented.',
    'ExtendedPrice includes tax in this fixture. Business definitions still require validation for user files.'
])
