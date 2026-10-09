import unittest
from decision_room.reports.posthoc.inventory import from_snapshot
from decision_room.reports.posthoc.localization import classify
from decision_room.reports.posthoc.interpretation import masked_request,location_context

class LocalizationTests(unittest.TestCase):
    def setUp(self):
        self.sources={'s':{'table_id':'s','snapshot_sha256':'a'*64,'columns':[
            {'name':'product','aliases':[{'name':'Café de la casa 1 kg','code':'P01'}]},
            {'name':'unidades','numeric':True,'unit':'unidades'}]}}

    def inventory(self,text):return from_snapshot(b'synthetic',{'nodes':[{'path':[0],'text':text}]})

    def test_labels_are_traceable_and_quantities_override_year_or_day_rules(self):
        inv=self.inventory('En 2026, Café de la casa 1 kg y P13: 2026 unidades y 31 filas. Del 10 al 18 de marzo de 2025, archivo-001.csv.')
        labels=classify(inv,self.sources)
        self.assertEqual([labels[o['id']]['rule'] for o in inv['occurrences']],
            ['calendar_year','dimension_alias','identifier_adjacent_letter','numeric_target','numeric_target',
             'calendar_day_range','calendar_day','calendar_year','filename'])
        self.assertEqual(len(labels),len(inv['occurrences']))

    def test_excluded_label_still_masks_if_equal_to_a_target(self):
        inv=self.inventory('En 2026 hubo 2026 unidades; Café de la casa 1 kg aporta 42 unidades.')
        labels=classify(inv,self.sources);targets=[o for o in inv['occurrences'] if labels[o['id']]['eligible']]
        self.assertEqual([o['text'] for o in targets],['2026','42'])
        request=masked_request(inv,targets[0],self.sources)
        self.assertNotIn('2026',request['masked_text'])
        self.assertIn('1 kg',request['masked_text'])
        hint=location_context(request['masked_text'],targets[0])
        self.assertNotIn('2026',hint['excerpt']['text'])

    def test_no_bare_year_value_exclusion_without_calendar_context(self):
        inv=self.inventory('La suma es 2026. 31. Total 1.234 y 12,5 %.')
        labels=classify(inv,self.sources)
        self.assertTrue(all(v['eligible'] for v in labels.values()))

    def test_year_after_explicit_month_reference_is_not_an_aggregate(self):
        inv=self.inventory('Enero–agosto de 2025 y los mismos meses de 2026: suma de 2026.')
        labels=classify(inv,self.sources)
        self.assertEqual([labels[o['id']]['rule'] for o in inv['occurrences']],
                         ['calendar_year','calendar_year','numeric_target'])

    def test_header_year_and_heading_ordinal(self):
        inv=self.inventory('2025 y 2026. 1. Prioridad')
        inv['occurrences'][0]['context']['table']={'cell_is_header':True}
        one=inv['occurrences'][-1];a,b=one['span'];one['context']['section']=[{'text':inv['text'][a:],'span':[a,len(inv['text'])]}]
        labels=classify(inv,self.sources)
        self.assertEqual(labels[inv['occurrences'][0]['id']]['rule'],'calendar_year')
        self.assertEqual(labels[one['id']]['rule'],'heading_ordinal')
