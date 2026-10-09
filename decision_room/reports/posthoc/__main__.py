"""Explicit preparation/estimation/run commands for the post-hoc pilot."""
import argparse
import json
import os

from ...config import Config
from . import api

parser=argparse.ArgumentParser(description=__doc__)
commands=parser.add_subparsers(dest='command',required=True)
prepare=commands.add_parser('prepare');prepare.add_argument('report');prepare.add_argument('dest');prepare.add_argument('--csv',action='append',required=True)
estimate=commands.add_parser('estimate');estimate.add_argument('dest');estimate.add_argument('--batch-size',type=int,default=4)
run=commands.add_parser('run');run.add_argument('dest');run.add_argument('--budget',required=True);run.add_argument('--batch-size',type=int,default=4);run.add_argument('--report-limit',default='0.50')
args=parser.parse_args()
if args.command=='prepare':result=api.prepare(args.report,args.csv,args.dest)
elif args.command=='estimate':result=api.estimate_preflight(args.dest,batch_size=args.batch_size)
else:
    key=os.environ.get('OPENAI_API_KEY')
    if not key:parser.error('OPENAI_API_KEY must be supplied only through the subprocess environment.')
    result=api.run(Config.load(),args.dest,args.budget,api_key=key,batch_size=args.batch_size,report_limit=args.report_limit)
print(json.dumps(result,ensure_ascii=False,indent=2))
