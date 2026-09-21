"""Run with .venv/bin/python -m decision_room --help."""
import argparse
import json
import os
import subprocess
import sys
import uuid
from pathlib import Path

import psycopg

from .config import Config
from .database import connect, migrate
from .service import create_business, describe, import_batch, list_analyses, resume
from .execution import execute, get_execution, list_executions, recover_executions


def emit(value):
    print(json.dumps(value, indent=2, ensure_ascii=False, default=str))


def progress(name, status, rows):
    print(f'{status}: {name}' + (f' ({rows:,} rows)' if rows is not None else ''), file=sys.stderr, flush=True)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description='Decision Room: local CSV batch ingestion and recovery.')
    commands = parser.add_subparsers(dest='command', required=True)
    commands.add_parser('init', help='Create versioned PostgreSQL metadata tables.')
    commands.add_parser('businesses', help='List local development businesses.')
    business = commands.add_parser('create-business')
    business.add_argument('--name', required=True)
    business.add_argument('--description', default='')
    upload = commands.add_parser('import', help='Import files together as one business analysis.')
    upload.add_argument('--business', type=uuid.UUID, required=True)
    upload.add_argument('--title', default='CSV upload')
    upload.add_argument('--directory', type=Path, help='Import all .csv files directly inside this folder.')
    upload.add_argument('--delimiter', choices=[',', ';', '|', 'tab'], help='Omit to detect; use tab for TSV-style CSVs.')
    upload.add_argument('files', nargs='*', type=Path)
    for name in ['show', 'resume']:
        command = commands.add_parser(name)
        command.add_argument('--business', type=uuid.UUID, required=True)
        command.add_argument('--analysis', type=uuid.UUID, required=True)
        if name == 'show':
            command.add_argument('--details', action='store_true')
    listing = commands.add_parser('analyses')
    listing.add_argument('--business', type=uuid.UUID, required=True)
    run = commands.add_parser('run', help='Execute Python in the isolated local runtime.')
    run.add_argument('--business', type=uuid.UUID, required=True)
    run.add_argument('--analysis', type=uuid.UUID, required=True)
    run.add_argument('--code', type=Path, required=True)
    run.add_argument('--table', action='append', required=True, help='alias=prepared-table-UUID; repeat for multiple tables')
    run.add_argument('--definitions', type=Path, help='JSON object with agreed business definitions.')
    run.add_argument('--request-key', required=True)
    run.add_argument('--timeout', type=int, default=30)
    executions = commands.add_parser('executions')
    executions.add_argument('--business', type=uuid.UUID, required=True)
    executions.add_argument('--analysis', type=uuid.UUID, required=True)
    execution = commands.add_parser('show-execution')
    execution.add_argument('--business', type=uuid.UUID, required=True)
    execution.add_argument('--execution', type=uuid.UUID, required=True)
    recover = commands.add_parser('recover-executions')
    recover.add_argument('--business', type=uuid.UUID, required=True)
    for name in ('agent-start', 'agent-show', 'agent-resume', 'agent-answer'):
        command = commands.add_parser(name, help='Step 1.4: provisional planning and persistent owner questions.')
        command.add_argument('--business', type=uuid.UUID, required=True)
        if name == 'agent-start':
            command.add_argument('--analysis', type=uuid.UUID, required=True)
            command.add_argument('--context-file', type=Path, required=True)
            command.add_argument('--request-key', required=True)
            command.add_argument('--model')
        else:
            command.add_argument('--session', type=uuid.UUID, required=True)
        if name == 'agent-resume':
            command.add_argument('--retry-model', action='store_true', help='Retry an interrupted model request that may already have been processed.')
        if name == 'agent-answer':
            command.add_argument('--question', type=uuid.UUID, required=True)
            command.add_argument('--text', default='')
            command.add_argument('--disposition', choices=['answered', 'unknown', 'declined'], default='answered')
            command.add_argument('--request-key', required=True)
    for name in ('agent-research', 'research-show', 'research-resume', 'agent-replan'):
        command = commands.add_parser(name, help='Step 1.5: isolated Python investigations and candidate evidence.')
        command.add_argument('--business', type=uuid.UUID, required=True)
        if name in ('agent-research', 'agent-replan'):
            command.add_argument('--session', type=uuid.UUID, required=True)
            command.add_argument('--request-key', required=True)
        else:
            command.add_argument('--research', type=uuid.UUID, required=True)
        if name == 'agent-research':
            command.add_argument('--max-investigations', type=int, default=2)
            command.add_argument('--investigation', action='append', default=[])
            command.add_argument('--timeout', type=int, default=30)
        elif name == 'research-resume':
            command.add_argument('--retry-model', action='store_true')
        elif name == 'agent-replan':
            command.add_argument('--context-file', type=Path, required=True, help='Complete corrected owner context, replacing the previous context.')
            command.add_argument('--model', help='Optional model override for the new planning session.')
    args = parser.parse_args()
    config = Config.load()
    try:
        if args.command == 'init':
            migrate(config)
            with connect(config) as db:
                version = db.execute('SELECT max(version) AS version FROM schema_versions').fetchone()['version']
            emit({'schema_version': version, 'status': 'ready'})
        elif args.command == 'businesses':
            with connect(config) as db:
                emit(db.execute('SELECT * FROM businesses ORDER BY created_at').fetchall())
        elif args.command == 'create-business':
            emit(create_business(config, args.name, args.description))
        elif args.command == 'import':
            if args.directory and args.files:
                parser.error('Use either --directory or a list of files, not both.')
            files = args.files
            if args.directory:
                if not args.directory.is_dir():
                    parser.error('--directory must be an existing directory.')
                files = sorted(p for p in args.directory.iterdir() if p.is_file() and p.suffix.lower() == '.csv')
            report = import_batch(config, args.business, files, args.title,
                                  '\t' if args.delimiter == 'tab' else args.delimiter, progress)
            emit(report)
            return 0 if report['analysis']['status'] == 'ready' else 2
        elif args.command == 'show':
            emit(describe(config, args.business, args.analysis, args.details))
        elif args.command == 'resume':
            report = resume(config, args.business, args.analysis, progress)
            emit(report)
            return 0 if report['analysis']['status'] == 'ready' else 2
        elif args.command == 'analyses':
            emit(list_analyses(config, args.business))
        elif args.command == 'run':
            tables = {}
            for item in args.table:
                if '=' not in item:
                    raise ValueError('Use --table alias=UUID.')
                alias, table_id = item.split('=', 1)
                if alias in tables:
                    raise ValueError('Duplicate table alias.')
                tables[alias] = uuid.UUID(table_id)
            definitions = json.loads(args.definitions.read_text()) if args.definitions else {}
            report = execute(config, args.business, args.analysis, code=args.code.read_text(), tables=tables,
                             definitions=definitions, request_key=args.request_key, timeout=args.timeout)
            emit(report)
            return 0 if report['status'] == 'completed' else 2
        elif args.command == 'executions':
            emit(list_executions(config, args.business, args.analysis))
        elif args.command == 'show-execution':
            emit(get_execution(config, args.business, args.execution))
        elif args.command == 'recover-executions':
            emit({'recovered': recover_executions(config, args.business)})
        elif args.command in ('agent-research', 'research-show', 'research-resume', 'agent-replan'):
            from .agent import research
            from .agent import service as agent
            from .agent.model import ModelClient, ModelSettings
            if args.command == 'agent-research':
                report = research.start(config, args.business, args.session, request_key=args.request_key,
                                        max_investigations=args.max_investigations,
                                        investigation_keys=args.investigation, python_timeout=args.timeout)
            elif args.command == 'research-show':
                report = research.show(config, args.business, args.research)
            elif args.command == 'research-resume':
                report = research.resume(config, args.business, args.research, retry_uncertain=args.retry_model)
            else:
                if args.context_file.stat().st_size > 48000:
                    raise ValueError('Context file is too large.')
                report = agent.replan(config, args.business, args.session, owner_context=args.context_file.read_text(),
                                      request_key=args.request_key,
                                      model=ModelClient(ModelSettings.load(args.model)) if args.model else None)
            emit(report)
            return 2 if report['status'] in ('failed', 'stale') else 0
        elif args.command.startswith('agent-'):
            from .agent import service as agent
            from .agent.model import ModelClient, ModelSettings
            if args.command == 'agent-start':
                if args.context_file.stat().st_size > 48000:
                    raise ValueError('Context file is too large.')
                report = agent.start(config, args.business, args.analysis,
                                     owner_context=args.context_file.read_text(), request_key=args.request_key,
                                     model=ModelClient(ModelSettings.load(args.model)))
            elif args.command == 'agent-show':
                report = agent.show(config, args.business, args.session)
            elif args.command == 'agent-resume':
                report = agent.resume(config, args.business, args.session, retry_uncertain=args.retry_model)
            else:
                report = agent.answer(config, args.business, args.session, question_id=args.question,
                                      text=args.text, disposition=args.disposition, request_key=args.request_key)
            emit(report)
            return 2 if report['status'] == 'failed' else 0
        return 0
    except psycopg.OperationalError:
        print('Cannot connect to PostgreSQL. Start scripts/dev/local_postgres.py or check DECISION_ROOM_DATABASE_URL.', file=sys.stderr)
        return 1
    except (ValueError, OSError, psycopg.Error, subprocess.SubprocessError) as error:
        print(f'{type(error).__name__}: {error}', file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
