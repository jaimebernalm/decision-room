#!/usr/bin/env python3
"""Opt-in real-model conversation evaluation with isolated synthetic data."""

import argparse
import json
import sys
import tempfile
import time
from dataclasses import replace
from pathlib import Path
from uuid import uuid4

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from psycopg import sql
from psycopg.conninfo import make_conninfo
from decision_room.config import Config
from decision_room.database import connect, migrate
from decision_room.local_env import load_env
from decision_room.agent.model import ModelSettings
from decision_room.web.service import Workspace
from decision_room.conversations import Conversations
from decision_room.service import import_batch
from decision_room.memory import service as memory, extraction
from evaluate_context import check_report
from decision_room.agent import review


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--output', required=True)
    p.add_argument('--env-file', default='.env')
    args = p.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    load_env(args.env_file)
    base = Config.load()
    settings = ModelSettings.load()
    name = 'dr_chat_eval_' + uuid4().hex
    summary = dict(passed=False, checks=[], model=settings.model)
    start = time.monotonic()
    with connect(base) as db:
        db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    try:
        with tempfile.TemporaryDirectory(prefix='dr-chat-eval-') as directory:
            config = replace(
                base, dsn=make_conninfo(base.dsn, dbname=name), storage=Path(directory) / 'storage'
            )
            migrate(config)
            ws = Workspace(config, settings)
            b = ws.save_business(
                dict(
                    request_key=str(uuid4()),
                    name='Tienda ficticia',
                    description='Negocio sintético para comprobar conversaciones.',
                )
            )['id']
            while extraction.work_once(config, ws.model_factory, settings):
                pass
            chats = Conversations(ws.scoped(b))

            def create(analysis=None):
                return chats.create(
                    dict(
                        business_id=str(b),
                        request_key=str(uuid4()),
                        analysis_id=str(analysis) if analysis else None,
                    )
                )['id']

            def send(chat, text, allowed=('completed',)):
                t = chats.send(chat, dict(business_id=str(b), request_key=str(uuid4()), text=text))['id']
                for _ in range(12):
                    while extraction.work_once(config, ws.model_factory, settings):
                        pass
                    if not ws.work_once():
                        break
                    last = chats.detail(chat)['turns'][-1]
                    if last['status'] in ('completed', 'failed', 'blocked', 'waiting', 'stale'):
                        break
                detail = chats.detail(chat)
                (output / (str(t) + '.json')).write_text(
                    json.dumps(detail, ensure_ascii=False, indent=2, default=str)
                )
                turn = detail['turns'][-1]
                assert turn['status'] in allowed, f'Turn {t}: {turn["status"]} {turn.get("issue")}'
                return turn

            chat = create()
            first = send(chat, 'Recuerda que nuestra tienda permanece cerrada todos los domingos.')
            assert first['response']['kind'] == 'memory'
            second = send(create(), '¿Qué sabes sobre nuestro horario de los domingos?')
            assert any(
                'domingo' in x['content']['statement'].lower() and x['status'] == 'declared'
                for x in second['response']['items']
            )
            summary['checks'].append('Real memory extraction reused in another conversation.')
            print(summary['checks'][-1], flush=True)
            file = Path(directory) / 'ventas.csv'
            file.write_text('date,quantity,amount\n2026-06-01,2,10\n2026-06-02,3,20\n')
            analysis = import_batch(config, b, [file], title='Ventas registradas en junio de 2026')[
                'analysis'
            ]['id']
            definition = dict(
                topic='amount_basis',
                kind='definition',
                statement='Cada fila es una venta. quantity son unidades. amount es el precio unitario en euros, sin impuestos y con descuentos aplicados. date es la fecha de venta.',
                scope='analysis',
                scope_id=str(analysis),
                temporal_scope='unspecified',
                valid_from=None,
                valid_until=None,
                result_id=None,
            )
            memory.change(config, b, action='declare', request_key='definition', content=definition)
            analytical = create(analysis)
            result = send(
                analytical,
                'Calcula el total vendido registrado en este archivo de junio de 2026. No extrapoles a todo el negocio. La memoria contiene la definición de las columnas.',
            )
            assert result['response']['kind'] == 'evidence'
            check_report(review.show(config, b, result['response']['report_id']), '80')
            assert not result['report_requested']
            summary['checks'].append(
                'New calculation from existing data: reviewed total 80, no upload or automatic report publication.'
            )
            print(summary['checks'][-1], flush=True)
            explained = send(
                analytical,
                'Explícame el resultado que acabas de comprobar: recupera el informe existente y sus afirmaciones. No hagas otro cálculo.',
            )
            assert explained['response']['kind'] == 'evidence'
            assert explained['response']['report_id'] == result['response']['report_id']
            chats.report(analytical, explained['id'], dict(business_id=str(b)))
            assert '<' in chats.report(analytical, explained['id'])
            summary['checks'].append(
                'Real model retrieves and explains exact reviewed claims; linked report opens after explicit request.'
            )
            print(summary['checks'][-1], flush=True)
            send(chat, 'Corrijo el horario anterior: nuestra tienda abre todos los domingos.')
            detail = chats.detail(chat)
            conflicts = [f for f in detail['memory_items'] if f['status'] == 'conflicted']
            assert conflicts, 'Expected correction conflict for explicit confirmation.'
            f = conflicts[0]
            i = next(
                i
                for i, a in enumerate(f['alternatives'])
                if 'abre' in a['content']['statement'].lower()
                or 'abiert' in a['content']['statement'].lower()
            )
            chats.resolve(
                chat,
                dict(
                    business_id=str(b),
                    request_key=str(uuid4()),
                    fact_id=f['id'],
                    revision=f['revision'],
                    alternative=i,
                ),
            )
            updated = send(create(), '¿Cuál es ahora nuestro horario de los domingos?')
            assert any(
                x['status'] == 'declared'
                and (
                    'abre' in x['content']['statement'].lower()
                    or 'abiert' in x['content']['statement'].lower()
                )
                for x in updated['response']['items']
            )
            assert chats.detail(analytical)['turns'][0]['status'] == 'stale'
            summary['checks'].append(
                'Correction confirmed through shared memory, reused in new chat, old dependent answer withheld.'
            )
            print(summary['checks'][-1], flush=True)
            historical = create()
            hypothetical = send(
                historical,
                '¿Y si agrupásemos los cobros por semana en vez de por día?',
                allowed=('completed', 'waiting'),
            )
            recalled = send(
                create(),
                'Busca con search_chats la conversación donde propuse consolidar los ingresos semanalmente. Cita el mensaje original como una hipótesis histórica, sin convertirlo en un hecho.',
            )
            assert recalled['response']['kind'] == 'history', recalled['response']
            assert str(hypothetical['id']) in [x['message_id'] for x in recalled['response']['items']]
            summary['checks'].append(
                'Paraphrased historical hypothesis retrieved semantically with original message citation.'
            )
            print(summary['checks'][-1], flush=True)
            with connect(config) as db:
                history_events = db.execute(
                    "SELECT response FROM chat_retrievals WHERE request->>'tool'='search_chats'"
                ).fetchall()
                assert any(e['response']['search']['mode'] == 'hybrid' for e in history_events)
                calls = db.execute('SELECT * FROM chat_calls ORDER BY created_at').fetchall()
                events = db.execute(
                    'SELECT * FROM chat_retrievals ORDER BY turn_id,attempt,ordinal'
                ).fetchall()
                summary['chat_calls'] = len(calls)
                summary['tools'] = [e['request']['tool'] for e in events]
                (output / 'calls.json').write_text(
                    json.dumps(calls, ensure_ascii=False, indent=2, default=str)
                )
                (output / 'retrievals.json').write_text(
                    json.dumps(events, ensure_ascii=False, indent=2, default=str)
                )
            summary['passed'] = True
    except Exception as e:
        summary['error'] = str(e)
        raise
    finally:
        if 'config' in locals():
            with connect(config) as db:
                for table in ('chat_calls', 'chat_retrievals', 'memory_calls'):
                    records = db.execute(sql.SQL('SELECT * FROM {}').format(sql.Identifier(table))).fetchall()
                    (output / (table + '.json')).write_text(
                        json.dumps(records, ensure_ascii=False, indent=2, default=str)
                    )
        summary['seconds'] = round(time.monotonic() - start, 1)
        (output / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2, default=str))
        with connect(base) as db:
            db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        print(json.dumps(summary, ensure_ascii=False), flush=True)


if __name__ == '__main__':
    main()
