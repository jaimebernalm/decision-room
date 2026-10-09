import unittest

from decision_room.reports.posthoc.interpretation import population_context, segments_of
from decision_room.reports.posthoc.recipes import unfiltered_population, PopulationVeto


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
        unfiltered_population(operand,text,sources,population_context(request),original or text,target_span=target)

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

    def test_veto_names_the_catalogue_field_and_context_without_changing_state(self):
        with self.assertRaises(PopulationVeto) as raised:
            self.check('Total de Marketplace: 42','Total')
        self.assertEqual(raised.exception.diagnostic,{'table_id':'fixture','column':'channel',
            'category':'Marketplace','context_span':[0,24]})

    def test_context_is_specific_to_each_group_occurrence(self):
        text='Total de unidades: 42\nTotal de Marketplace: 43'
        request={'segments':segments_of(text),'context':{}}
        a={**request,'span':[text.index('42'),text.index('42')+2]}
        b={**request,'span':[text.index('43'),text.index('43')+2]}
        self.assertNotEqual(population_context(a),population_context(b))
        self.assertEqual(text[slice(*population_context(a)[0])],'Total de unidades: 42')

    def test_negation_outside_the_quote_still_vetoes_totality(self):
        for text,quote in [('No incluye todas las tiendas: 42','todas'),
                           ('Total sin contar Hostelería: 42','Total'),
                           ('Sin contar lo anterior: 42. Total de unidades.','Total'),
                           ('Total excepto devoluciones: 42','Total')]:
            with self.subTest(text=text),self.assertRaisesRegex(PopulationVeto,'Negation'):
                self.check(text,quote)

    def test_negation_in_another_sentence_is_not_silently_a_global_veto(self):
        for boundary in ('.',';','?','!','\n','\t'):
            with self.subTest(boundary=boundary):
                self.check('No hay comentarios'+boundary+'Total de unidades: 42','Total')
