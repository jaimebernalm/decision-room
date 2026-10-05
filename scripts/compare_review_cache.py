"""Compare two exported review audits without making provider calls.

Usage: python scripts/compare_review_cache.py before.json after.json
Each file contains review.show data (model_calls) or a list of agent_calls.
Unknown cached usage stays null, never inferred from estimated/prefix tokens.
"""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from decision_room.agent.review_cache import usage_summary


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before',type=Path);parser.add_argument('after',type=Path)
    args=parser.parse_args()
    report={}
    for label in ('before','after'):
        data=json.loads(getattr(args,label).read_text())
        calls=data if isinstance(data,list) else data['model_calls']
        report[label]=usage_summary(calls)
    report['note']='Provider-reported input/cache tokens only. No live measurement or assumed monetary price. Cache hits still consume TPM.'
    print(json.dumps(report,indent=2,ensure_ascii=False))


if __name__=='__main__':main()
