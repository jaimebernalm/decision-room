"""Regression: prose percentages must agree with independently recomputed checks."""
import unittest
from copy import deepcopy
from decision_room.agent.review_contract import checks


class ProsePercentageTests(unittest.TestCase):
    def sample(self):
        ref=lambda key:{'execution_id':'e','metric':key}
        observation={'execution_id':'e','status':'completed','current':True,
                     'result':{'metrics':{'before':'2844.82','after':'3303.85','growth':'16.14'},
                               'evidence':[{'metric':key} for key in ('before','after','growth')]}}
        report={'title':'Comparación','summary':'El promedio subió un 16,14 %.','claims':[{'key':'growth','evidence':[ref('growth')]}],
                'checks':[{'key':'growth_check','operation':'percent_change','actual':ref('growth'),
                           'operands':[ref('before'),ref('after')],'tolerance':'0.01'}]}
        return report,[observation]

    def test_dr002_wrong_percentage_fails_even_when_metric_and_model_approval_would_pass(self):
        report,observations=self.sample()
        self.assertTrue(all(c['passed'] for c in checks(report,observations)))
        report['summary']='El promedio subió un 16,13 %.'
        self.assertFalse(all(c['passed'] for c in checks(report,observations)))

    def test_missing_check_and_loose_tolerance_do_not_validate_wrong_prose(self):
        report,observations=self.sample()
        report['checks']=[]
        self.assertFalse(all(c['passed'] for c in checks(report,observations)))
        report,observations=self.sample()
        report['summary']='Aumento del 16.13%.'
        observations[0]['result']['metrics']['growth']='16.13'
        report['checks'][0]['tolerance']='0.1'
        results=checks(report,observations)
        self.assertTrue(next(c for c in results if c['check']=='growth_check')['passed'])
        self.assertFalse(next(c for c in results if c['check']=='percentage_text')['passed'])

    def test_caption_and_title_percentages_are_also_checked(self):
        for field in ('title','summary'):
            report,obs=self.sample();report[field]='Incremento del 99%.'
            self.assertFalse(all(c['passed'] for c in checks(report,obs)))

    def test_share_percent_and_zero_denominator(self):
        report,obs=self.sample()
        obs[0]['result']['metrics'].update(before='32745',after='73784.1',growth='44.38')
        report['checks'][0]['operation']='ratio_percent'
        report['summary']='Participación: 44,38 %.'
        self.assertTrue(all(c['passed'] for c in checks(report,obs)))
        obs[0]['result']['metrics']['after']='0'
        self.assertFalse(all(c['passed'] for c in checks(report,obs)))


if __name__=='__main__':unittest.main()
