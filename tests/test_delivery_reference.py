import csv
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from decision_room.evaluation.delivery_reference import wwi_details


class DetailedReferenceTests(unittest.TestCase):
    def fixture(self, folder):
        data = {
            'Sales.CustomerCategories': [dict(CustomerCategoryID=1, CustomerCategoryName='Retail')],
            'Sales.Customers': [dict(CustomerID=1, CustomerCategoryID=1)],
            'Warehouse.StockItems': [dict(StockItemID=1, StockItemName='Sample')],
            'Sales.Invoices': [dict(InvoiceID=1, CustomerID=1, InvoiceDate='2014-01-01', IsCreditNote=0),
                               dict(InvoiceID=2, CustomerID=1, InvoiceDate='2014-02-01', IsCreditNote=1)],
            'Sales.InvoiceLines': [dict(InvoiceLineID=1, InvoiceID=1, StockItemID=1, Quantity=3, UnitPrice=10, ExtendedPrice=33, TaxAmount=3, LineProfit=12),
                                  dict(InvoiceLineID=2, InvoiceID=2, StockItemID=1, Quantity=-1, UnitPrice=8, ExtendedPrice=-9, TaxAmount=-1, LineProfit=-4)]}
        for name, values in data.items():
            with (folder / (name + '.csv')).open('w', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=values[0]); writer.writeheader(); writer.writerows(values)

    def test_tax_credit_signs_and_price_denominators_stay_distinct(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp); self.fixture(base); values = wwi_details(base)
        prefix = 'detail:cross:2014:Retail:1:'
        self.assertEqual(values['detail:stock_name:1'], 'Sample')
        self.assertEqual(values['detail:stock_id:1'], 1)
        self.assertEqual(values[prefix+'gross_sales'], 24)
        self.assertEqual(values[prefix+'net_sales'], 22)
        self.assertEqual(values[prefix+'credit_net_sales'], -8)
        self.assertEqual(values[prefix+'credit_lines'], 1)
        self.assertEqual(values[prefix+'weighted_unit_price'], 11)
        self.assertEqual(values[prefix+'avg_unit_price'], 9)
        self.assertEqual(values[prefix+'net_margin_pct'], Decimal(8)/22*100)

    def test_duplicate_line_cannot_double_an_independent_answer(self):
        with TemporaryDirectory() as tmp:
            base = Path(tmp); self.fixture(base)
            path = base / 'Sales.InvoiceLines.csv'
            content = path.read_text(); path.write_text(content + content.splitlines()[1] + '\n')
            with self.assertRaisesRegex(ValueError, 'Duplicate'):
                wwi_details(base)
