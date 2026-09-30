"""Report timestamps are provenance, not the period of observed data."""
import unittest
from datetime import datetime, timezone
from unittest.mock import Mock, patch
from decision_room.memory.retrieval import Request, _reports

class ReportMetadataTests(unittest.TestCase):
    def test_latest_uses_approval_instant_not_search_rank_or_review_start(self):
        rows=[{'id':'older'},{'id':'newer'}]
        starts={'older':datetime(2026,9,28,tzinfo=timezone.utc),'newer':datetime(2026,9,27,tzinfo=timezone.utc)}
        approvals={'older':datetime.fromisoformat('2026-09-28T13:00:00+00:00'),
                   'newer':datetime.fromisoformat('2026-09-28T10:00:00-04:00')}
        db=Mock()
        def execute(sql,params):
            if 'SELECT id FROM' in sql:return Mock(fetchall=lambda:rows)
            return Mock(fetchone=lambda:{'created_at':approvals[params[0]]})
        db.execute.side_effect=execute
        def report(config,db,manifest,key):
            return dict(id=key,created_at=starts[key],analysis_id='dataset',approved_sha256='hash'),dict(report={'title':key,'summary':'','scope':{'period':'2025'}})
        request=Request(tool='search_reports',id='',query='',limit=1)
        with patch('decision_room.memory.retrieval._report',side_effect=report), patch('decision_room.memory.retrieval.semantic.rank') as rank:
            result,deps=_reports(None,db,{'business_id':'b','session_id':'s'},{'analysis_id':None},request)
        self.assertEqual(result['items'][0]['id'],'newer')
        self.assertEqual(result['items'][0]['approved_at'],'2026-09-28T10:00:00-04:00')
        self.assertEqual(result['items'][0]['scope']['period'],'2025')
        self.assertTrue(result['more_possible']);self.assertTrue(result['search']['approval_dates_complete'])
        self.assertEqual(deps,[dict(kind='report',id='newer',version='hash')]);rank.assert_not_called()
