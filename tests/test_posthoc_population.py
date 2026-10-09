import unittest

from decision_room.reports.posthoc.interpretation import population_context, segments_of
from decision_room.reports.posthoc.recipes import unfiltered_population


class PopulationTests(unittest.TestCase):
    def check(self,text,quote,*,section=None,table=None,original=None):
        def ref(value):
            start=text.index(value)
            return {'span':[start,start+len(value)],'text':value}
        target=ref('42')['span']
        request={'span':target,'segments':segments_of(text),
                 'context':{'section':[ref(section)] if section else [],
                            'table':{k:[ref(v)] for k,v in (table or {}).items()}}}
        sources={'fixture':{'columns':[{'name':'channel','categories':['MA','HO'],
                 'aliases':[{'name':'Marketplace','code':'MA'},{'name':'Hostelería','code':'HO'}]}]}}
        operand={'evidence':{'population':[ref(quote)]}}
        unfiltered_population(operand,text,sources,population_context(request),original or text)

    def test_only_explicit_totality_without_catalogue_restriction_passes(self):
        self.check('Total de unidades registradas: 42','Total')
        self.check('Todas las unidades: 42','Todas')
        with self.assertRaisesRegex(ValueError,'explicit totality'):
            self.check('Unidades registradas: 42','Unidades registradas')
        with self.assertRaisesRegex(ValueError,'explicit totality'):
            self.check('Subtotal: 42','Subtotal')

    def test_totality_never_overrides_category_in_sentence_or_heading(self):
        for text,section in [('Total de Marketplace: 42',None),
                             ('Marketplace\nTotal de unidades: 42','Marketplace')]:
            with self.subTest(text=text),self.assertRaisesRegex(ValueError,'vetoes'):
                self.check(text,'Total',section=section)

    def test_table_context_is_checked_including_row_text(self):
        for field in ('caption','column_headers','row_headers','row_text'):
            with self.subTest(field=field),self.assertRaisesRegex(ValueError,'vetoes'):
                self.check('Hostelería\nTotal de unidades: 42','Total',table={field:'Hostelería'})

    def test_mask_does_not_hide_restrictive_category_from_server_veto(self):
        with self.assertRaisesRegex(ValueError,'vetoes'):
            self.check('██\nTotal de unidades: 42','Total',section='██',
                       original='MA\nTotal de unidades: 42')

    def test_context_is_specific_to_each_group_occurrence(self):
        text='Total de unidades: 42\nTotal de Marketplace: 43'
        request={'segments':segments_of(text),'context':{}}
        a={**request,'span':[text.index('42'),text.index('42')+2]}
        b={**request,'span':[text.index('43'),text.index('43')+2]}
        self.assertNotEqual(population_context(a),population_context(b))
        self.assertEqual(text[slice(*population_context(a)[0])],'Total de unidades: 42')
