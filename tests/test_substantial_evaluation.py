"""Protect the independent reference from common multi-table accounting errors."""
import csv
from decimal import Decimal
from pathlib import Path
from tempfile import TemporaryDirectory
import unittest

from decision_room.evaluation.substantial_data import reference, TABLES


class SubstantialReferenceTests(unittest.TestCase):
    def setUp(self):
        self.directory = TemporaryDirectory()
        self.addCleanup(self.directory.cleanup)
        self.base = Path(self.directory.name)
        self.data = {
            TABLES[0]: [dict(InvoiceID='a', CustomerID='c', InvoiceDate='2014-02-01'),
                        dict(InvoiceID='b', CustomerID='c', InvoiceDate='2015-02-01'),
                        dict(InvoiceID='z', CustomerID='c', InvoiceDate='2013-01-01')],
            TABLES[1]: [dict(InvoiceLineID='1', InvoiceID='a', StockItemID='p',
                            ExtendedPrice='120', TaxAmount='20', LineProfit='30', Quantity='2'),
                        dict(InvoiceLineID='2', InvoiceID='a', StockItemID='p',
                            ExtendedPrice='60', TaxAmount='10', LineProfit='15', Quantity='1'),
                        dict(InvoiceLineID='3', InvoiceID='b', StockItemID='p',
                            ExtendedPrice='240', TaxAmount='40', LineProfit='80', Quantity='4'),
                        dict(InvoiceLineID='4', InvoiceID='b', StockItemID='p',
                            ExtendedPrice='-60', TaxAmount='-10', LineProfit='-20', Quantity='-1'),
                        dict(InvoiceLineID='5', InvoiceID='z', StockItemID='p',
                            ExtendedPrice='999', TaxAmount='0', LineProfit='999', Quantity='1')],
            TABLES[2]: [dict(CustomerID='c', CustomerCategoryID='cat', CustomerName='Cliente')],
            TABLES[3]: [dict(CustomerCategoryID='cat', CustomerCategoryName='Tiendas')],
            TABLES[4]: [dict(StockItemID='p', StockItemName='Producto')],
        }

    def save(self):
        for name, rows in self.data.items():
            with (self.base / (name + '.csv')).open('w', encoding='utf-8-sig', newline='') as stream:
                writer = csv.DictWriter(stream, fieldnames=rows[0].keys())
                writer.writeheader(); writer.writerows(rows)

    def test_tax_sign_period_grain_and_contributions(self):
        self.save()
        got = reference(self.base)
        before, after = (got['groups']['year:' + year] for year in ('2014', '2015'))
        self.assertEqual(before['sales'], Decimal('150'))
        self.assertEqual(before['invoices'], 1)  # Two lines are not two invoices.
        self.assertEqual(before['average_invoice'], Decimal('150'))
        self.assertEqual(after['sales'], Decimal('150'))  # Preserve credit signs.
        self.assertEqual(after['profit'], Decimal('60'))
        self.assertEqual(after['margin_pct'], Decimal('40'))
        self.assertEqual(got['changes']['product']['Producto']['profit'], Decimal('15'))
        self.assertEqual(got['groups']['category:2015:Tiendas']['sales'], after['sales'])
        self.assertEqual(got['joins']['joined_lines'], 5)  # Includes out-of-scope dates.

    def test_duplicate_dimension_rejected_before_join(self):
        self.data[TABLES[4]].append(self.data[TABLES[4]][0].copy())
        self.save()
        with self.assertRaisesRegex(ValueError, 'duplicate'):
            reference(self.base)

    def test_orphan_outside_target_period_is_not_hidden(self):
        self.data[TABLES[1]][-1]['StockItemID'] = 'missing'
        self.save()
        with self.assertRaisesRegex(ValueError, 'Orphan'):
            reference(self.base)

    def test_duplicate_fact_rejected(self):
        self.data[TABLES[1]].append(self.data[TABLES[1]][0].copy())
        self.save()
        with self.assertRaisesRegex(ValueError, 'Duplicate invoice line'):
            reference(self.base)


if __name__ == '__main__':
    unittest.main()
