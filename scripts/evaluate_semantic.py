#!/usr/bin/env python3
"""Opt-in Spanish retrieval evaluation with real embeddings, isolated synthetic data."""
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
from decision_room.memory import semantic
from decision_room.service import create_business


# Expectations are written before running the provider. Similar distractors prevent
# the trivial success of returning the only document in a corpus.
DOCUMENTS = [
    ('sales', 'Ventas de productos: fecha, artículo, unidades y precio unitario. Cada registro es una línea de venta.'),
    ('stock', 'Inventario del almacén: existencias disponibles y movimientos de entrada y salida por producto.'),
    ('payroll', 'Plantilla y nóminas: empleados, salario bruto, retenciones y cotizaciones mensuales.'),
    ('suppliers', 'Facturas de proveedores: compras, vencimiento y estado de pago de cada factura recibida.'),
    ('returns', 'Devoluciones de clientes: artículos devueltos, motivo, fecha y reembolso del importe.'),
    ('advertising', 'Campañas publicitarias: inversión por canal, impresiones, clics y conversiones.'),
    ('delivery', 'Entregas de pedidos: transportista, fecha prometida y fecha efectiva de recepción.'),
    ('utilities', 'Consumo de electricidad y agua por local, periodo de lectura y coste del suministro.'),
]
QUERIES = [
    ('facturación de mercancías', 'sales'),
    ('cuánto dinero generamos comercializando artículos', 'sales'),
    ('qué nos queda guardado para poder vender', 'stock'),
    ('sueldos del personal contratado', 'payroll'),
    ('deudas pendientes con quienes nos abastecen', 'suppliers'),
    ('compradores que nos trajeron lo adquirido para recuperar su dinero', 'returns'),
    ('rendimiento de los anuncios y gasto en promoción', 'advertising'),
    ('retrasos de los envíos hasta llegar al comprador', 'delivery'),
    ('gasto energético de nuestros establecimientos', 'utilities'),
    ('ventas de productos', 'sales'),
]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', required=True)
    parser.add_argument('--env-file', default='.env')
    parser.add_argument('--compare-large', action='store_true')
    args = parser.parse_args()
    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=False)
    load_env(args.env_file)
    base = Config.load()
    name = 'dr_semantic_eval_' + uuid4().hex
    summary = dict(passed=False, runs=[], cases=len(QUERIES), repetitions=3)
    started = time.monotonic()
    with connect(base) as db:
        db.execute(sql.SQL('CREATE DATABASE {}').format(sql.Identifier(name)))
    try:
        with tempfile.TemporaryDirectory(prefix='dr-semantic-eval-') as directory:
            config = replace(base, dsn=make_conninfo(base.dsn, dbname=name), storage=Path(directory), semantic_search=True)
            migrate(config)
            models = ['text-embedding-3-small'] + (['text-embedding-3-large'] if args.compare_large else [])
            for model in models:
                config = replace(config, embedding_model=model, embedding_dimensions=1536)
                for repetition in range(3):
                    business = create_business(config, 'Negocio ficticio de evaluación')['id']
                    docs = [dict(key=key, version='fixture-v1', text=text) for key, text in DOCUMENTS]
                    result = dict(model=model, dimensions=1536, repetition=repetition + 1, queries=[])
                    with connect(config) as db:
                        for query, expected in QUERIES:
                            lexical, _ = semantic.rank(replace(config, semantic_search=False), db, business, 'dataset', docs, query, 3)
                            hybrid, metadata = semantic.rank(config, db, business, 'dataset', docs, query, 3)
                            assert metadata['mode'] == 'hybrid', metadata
                            result['queries'].append(dict(query=query, expected=expected, lexical=lexical, hybrid=hybrid, search=metadata))
                        result['recall_at_3'] = sum(r['expected'] in r['hybrid'] for r in result['queries']) / len(QUERIES)
                        result['top_1'] = sum(r['hybrid'][0] == r['expected'] for r in result['queries']) / len(QUERIES)
                        result['lexical_recall_at_3'] = sum(r['expected'] in r['lexical'] for r in result['queries']) / len(QUERIES)
                        calls = db.execute('SELECT model,purpose,status,usage FROM semantic_calls WHERE business_id=%s ORDER BY created_at', (business,)).fetchall()
                        result['embedding_calls'] = calls
                    summary['runs'].append(result)
                    (output/f'{model}-{repetition + 1}.json').write_text(json.dumps(result, ensure_ascii=False, indent=2))
                    print(json.dumps({k:v for k,v in result.items() if k not in ('queries','embedding_calls')}), flush=True)
                    assert result['recall_at_3'] == 1 and result['top_1'] >= .8, 'Retrieval quality gate failed.'
            summary['passed'] = True
    except Exception as error:
        summary['error'] = str(error)
        raise
    finally:
        summary['seconds'] = round(time.monotonic() - started, 2)
        (output/'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2))
        with connect(base) as db:
            db.execute(sql.SQL('DROP DATABASE {} WITH (FORCE)').format(sql.Identifier(name)))
        print(json.dumps({k:v for k,v in summary.items() if k != 'runs'}), flush=True)


if __name__ == '__main__':
    main()
