"""3.7 planner ablation with equal generous budgets and independent frozen references.

python -m decision_room.evaluation.business_planner_runner OUTPUT --wwi CSV_DIR --bruma CSV_DIR
Both modes use three workers, the quality-first profile and identical owner context.
Only planner consultation is disabled in control. This does not replace 3.6 results.
"""
import argparse
import json
import os
from pathlib import Path

from ..config import ROOT
from ..local_env import load_env
from .quality_runner import run


def main():
    os.umask(0o077);load_env(ROOT/'.env')
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('directory',type=Path)
    p.add_argument('--wwi',type=Path,required=True)
    p.add_argument('--bruma',type=Path,required=True)
    p.add_argument('--repeats',type=int,choices=(1,2,3),default=2)
    p.add_argument('--cases',nargs='+',choices=('bruma-discover','wwi-organize','wwi-discover','wwi-question'),
                   default=['bruma-discover','wwi-organize','wwi-discover'])
    a=p.parse_args()
    result=run(a.directory.resolve(),dict(wwi=a.wwi.resolve(),bruma=a.bruma.resolve()),a.repeats,a.cases,
               workflow=dict(quality_first=True,business_planner_modes=['planner']))
    print(json.dumps(result['modes'],indent=2))


if __name__=='__main__':main()
