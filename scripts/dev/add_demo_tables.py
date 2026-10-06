"""Add the small synthetic stationery dataset to an explicitly selected local business."""
import argparse
import hashlib
from pathlib import Path
import sys
from types import SimpleNamespace
from uuid import NAMESPACE_URL, UUID, uuid5

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from decision_room.config import Config
from decision_room.database import connect
from decision_room.data_knowledge import service as knowledge
from decision_room.service import require_business
from decision_room.web import bundles


def add_demo_tables(config, business):
    business = UUID(str(business))
    with connect(config) as db:
        require_business(db, business)
    paths = sorted((ROOT / 'data/demo/papeleria').glob('*.csv'))
    contents = {p.name: p.read_bytes() for p in paths}
    signature = hashlib.sha256(b''.join(contents.values())).hexdigest()
    key = str(uuid5(NAMESPACE_URL, f'decision-room:papeleria-demo:{business}:{signature}'))
    ws = SimpleNamespace(config=config, business_id=lambda: business)
    state = bundles.start(ws, dict(
        business_id=str(business), request_key=key,
        title='Ejemplo: ventas, productos y proveedores', mode='separate',
        period_from='2026-09-01', period_until='2026-09-30',
        files=[dict(path=name, size=len(content)) for name, content in contents.items()],
    ))
    if not state['result']:
        for index, item in enumerate(state['files']):
            content = contents[item['path']]
            if item['uploaded'] < len(content):
                bundles.chunk(ws, key, index, item['uploaded'], content[item['uploaded']:])
    result = bundles.finish(ws, key)
    analysis = UUID(result['analysis_id'])
    model = knowledge.ensure(config, business, analysis)
    tables = {t['name']: t for t in model['body']['tables']}
    # Declare only these synthetic connections. Never overwrite a subsequent correction.
    for source, target, column, description in (
        ('ventas.csv', 'productos.csv', 'producto_id', 'Cada venta del ejemplo corresponde a un producto.'),
        ('productos.csv', 'proveedores.csv', 'proveedor_id', 'Cada producto del ejemplo corresponde a un proveedor ficticio.'),
    ):
        source_id, target_id = tables[source]['id'], tables[target]['id']
        if any(r['source'] == source_id and r['target'] == target_id
               and r['source_columns'] == [column] and r['target_columns'] == [column]
               for r in model['body']['relations']):
            continue
        model = knowledge.change(config, business, analysis, model['revision'], 'relation', dict(
            source=source_id, target=target_id, source_columns=[column], target_columns=[column],
            description=description, semantic_status='confirmed',
        ))
    return dict(analysis_id=str(analysis), tables=len(model['body']['tables']),
                relations=len(model['body']['relations']), revision=model['revision'])


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--business-id', type=UUID, required=True)
    args = parser.parse_args()
    print(add_demo_tables(Config.load(), args.business_id))


if __name__ == '__main__':
    main()
