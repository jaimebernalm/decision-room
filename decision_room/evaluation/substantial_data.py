"""Independent CSV/Decimal oracle for the WWI baseline; never sent to agents."""
import csv
from collections import defaultdict
from decimal import Decimal

TABLES = ('Sales.Invoices', 'Sales.InvoiceLines', 'Sales.Customers',
          'Sales.CustomerCategories', 'Warehouse.StockItems')

# These are owner definitions, not expected answers or precomputed relationships.
OWNER = '''Somos un mayorista ficticio. Queremos estudiar los años naturales completos
2014 y 2015 según InvoiceDate. Cada fila de InvoiceLines es una línea de factura;
Quantity son unidades y UnitPrice es precio unitario sin impuestos. ExtendedPrice
y TaxAmount son importes totales de la línea; ExtendedPrice incluye TaxAmount.
LineProfit es margen bruto total de la línea, después del coste del producto,
no beneficio neto: no incluye gastos generales. Mantén los signos registrados,
incluidas notas de crédito; no filtres IsCreditNote. No conocemos aquí la moneda:
presenta los importes en unidades monetarias, sin atribuir euros o dólares.
Para segmentar usa el cliente comprador de la factura (CustomerID), no el pagador
BillToCustomerID. Los nombres y categorías actuales describen a esos clientes;
no tenemos su historial de clasificación. StockItems sirve para identificar los
productos; su precio actual no sustituye al precio registrado en cada venta.
No conocemos campañas ni causas externas. No queremos predicciones todavía.
'''

GOALS = {
    'organize': 'Quiero tener mis cifras organizadas: ventas sin impuestos, margen bruto '
                'e importe medio por factura para 2014 y 2015, evolución mensual y '
                'desglose por categoría de cliente. Prioriza un resumen claro para un dashboard.',
    'discover': 'Quiero descubrir oportunidades o problemas que quizá no haya visto '
                'comparando 2014 y 2015. Explora ventas y margen por productos y tipos '
                'de cliente, y prioriza pocos hallazgos relevantes con evidencia. '
                'No fuerces sorpresas si no las hay.',
    'question': '¿Cómo cambiaron las ventas sin impuestos y el margen bruto entre 2014 '
                'y 2015? ¿Qué productos y categorías de cliente contribuyeron más al '
                'cambio? Distingue cambios de importe y de porcentaje de margen.',
}


def rows(base, name):
    with (base / (name + '.csv')).open(encoding='utf-8-sig', newline='') as stream:
        yield from csv.DictReader(stream)


def index(base, name, key):
    result = {}
    for row in rows(base, name):
        value = row[key]
        if not value or value in result:
            raise ValueError(f'Invalid/duplicate {name}.{key}: {value}')
        result[value] = row
    return result


def reference(base):
    invoices = index(base, TABLES[0], 'InvoiceID')
    customers = index(base, TABLES[2], 'CustomerID')
    categories = index(base, TABLES[3], 'CustomerCategoryID')
    products = index(base, TABLES[4], 'StockItemID')
    # Validate the complete supplied relations, not only rows in the target years.
    for row in customers.values():
        if row['CustomerCategoryID'] not in categories:
            raise ValueError('Orphan customer category')
    for row in invoices.values():
        if row['CustomerID'] not in customers:
            raise ValueError('Orphan invoice customer')
    groups = defaultdict(lambda: dict(sales=Decimal(0), profit=Decimal(0),
                                     tax=Decimal(0), quantity=Decimal(0), lines=0, invoices=set()))
    line_ids = set()
    for row in rows(base, TABLES[1]):
        if row['InvoiceLineID'] in line_ids:
            raise ValueError('Duplicate invoice line')
        line_ids.add(row['InvoiceLineID'])
        if row['InvoiceID'] not in invoices or row['StockItemID'] not in products:
            raise ValueError('Orphan line invoice/product')
        invoice = invoices[row['InvoiceID']]
        year = invoice['InvoiceDate'][:4]
        if year not in ('2014', '2015'):
            continue
        customer = customers[invoice['CustomerID']]
        category = categories[customer['CustomerCategoryID']]['CustomerCategoryName']
        product = products[row['StockItemID']]['StockItemName']
        dimensions = [('year', year), ('month', invoice['InvoiceDate'][:7]),
                      ('category', year + ':' + category), ('product', year + ':' + product),
                      ('customer', year + ':' + customer['CustomerName'])]
        for dimension, key in dimensions:
            item = groups[dimension + ':' + key]
            item['sales'] += Decimal(row['ExtendedPrice']) - Decimal(row['TaxAmount'])
            item['profit'] += Decimal(row['LineProfit'])
            item['tax'] += Decimal(row['TaxAmount'])
            item['quantity'] += Decimal(row['Quantity'])
            item['lines'] += 1
            item['invoices'].add(row['InvoiceID'])
    for item in groups.values():
        item['invoices'] = len(item['invoices'])
        item['margin_pct'] = item['profit'] / item['sales'] * 100 if item['sales'] else None
        item['average_invoice'] = item['sales'] / item['invoices'] if item['invoices'] else None
    changes = {}
    for dimension in ('category', 'product', 'customer'):
        names = {key.split(':', 2)[2] for key in groups if key.startswith(dimension + ':')}
        changes[dimension] = {}
        for name in sorted(names):
            before = groups.get(f'{dimension}:2014:{name}', {})
            after = groups.get(f'{dimension}:2015:{name}', {})
            changes[dimension][name] = {metric: after.get(metric, Decimal(0)) - before.get(metric, Decimal(0))
                                        for metric in ('sales', 'profit')}
    return {'counts': dict(zip(TABLES, (len(invoices), len(line_ids), len(customers),
                                       len(categories), len(products)))),
            'groups': dict(groups), 'changes': changes,
            'joins': {'unique_keys': True, 'orphans': 0, 'joined_lines': len(line_ids)},
            'scope': 'Independent CSV and Decimal; current customer categories; 2014/2015 invoice dates.'}
