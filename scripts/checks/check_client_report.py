"""Reference client presentation: scripted analyst, real reviewer. NOT an autonomy test."""
import argparse
import json
import os
from pathlib import Path
import sys
from uuid import uuid4

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from decision_room.agent import review
from decision_room.agent.model import ModelClient, ModelSettings
from decision_room.config import Config
from decision_room.database import connect
from check_review import trace


class ReferenceAnalyst(ModelClient):
    def generate_analyst_review(self, context, correction=None):
        base = {'message': 'Contenido de referencia redactado para validar la presentación; no es un analista autónomo.',
                'report': None, 'code': '', 'table_ids': [], 'question': ''}
        if not context['conversation']:
            table = context['tables'][0]
            query = f'SELECT date, sales_ex_tax FROM {table["alias"]} ORDER BY date'
            code = f'''from decimal import Decimal
from dr_runtime import connect, write_result
with connect() as db: rows = db.execute({query!r}).fetchall()
assert len(rows)==24 and len({{d for d,_ in rows}})==24
metrics={{'sales_'+d:str(Decimal(s)) for d,s in rows}}
write_result(metrics,evidence=[{{'metric':'sales_'+d,'tables':[{table['alias']!r}],'operation':'Venta registrada en la fecha '+d+'; sin imputar fechas ausentes.'}} for d,_ in rows])
'''
            return {**base, 'action': 'execute', 'code': code, 'table_ids': [table['id']]}, {'fixture_seed': True}
        if any(e['role'] == 'reviewer' for e in context['conversation']):
            # Never replay an unchanged manual draft to steamroll a reviewer objection.
            return {**base, 'action': 'withdraw', 'message': 'El revisor cuestionó el ejemplo; requiere corregir el contenido de referencia.'}, {'fixture_seed': True}
        source = next(o for o in context['observations'] if o['current'] and o['result'] and 'w1_total_sales' in o['result']['metrics'])
        series = next(o for o in context['observations'] if o['current'] and o['result'] and 'sales_2016-04-01' in o['result']['metrics'])
        def ref(metric, observation=source):
            return {'execution_id': observation['execution_id'], 'metric': metric}
        report = {
            'title': 'Más ventas registradas en el segundo periodo',
            'summary': 'El segundo periodo suma más ventas registradas que el primero, con el mismo número de días disponibles. Antes de interpretar esa diferencia como una tendencia del negocio, conviene comprobar la cobertura de las fechas ausentes.',
            'scope': {'business': 'Actividad seleccionada · ejemplo de referencia',
                      'question': '¿Cómo cambiaron las ventas registradas entre el 1–14 y el 15–28 de abril, y qué conviene revisar?',
                      'period': '1–28 de abril de 2016',
                      'coverage': '24 fechas registradas de las 28 del periodo. El extracto contiene actividad seleccionada, no todas las ventas del negocio. Los importes excluyen impuestos y ya reflejan descuentos; no se ha indicado el nombre de la moneda.'},
            'claims': [
                {'key': 'comparison', 'title': 'El segundo periodo registra un importe mayor',
                 'statement': 'Se registraron 34.137,85 entre el 1 y el 14 de abril y 39.646,25 entre el 15 y el 28. Ambos periodos contienen 12 días con datos.',
                 'interpretation': 'La diferencia no se explica por tener más días registrados en el segundo periodo. El archivo permite comparar esta actividad, pero no demostrar un aumento de demanda ni de beneficio.',
                 'next_step': 'Confirmar que ambos periodos incluyen el mismo alcance de ventas antes de utilizar esta comparación para decidir compras o personal.',
                 'method': 'Sumar las ventas sin impuestos y con descuentos ya reflejados, separando los intervalos 1–14 y 15–28 de abril. Contar únicamente las fechas presentes, sin rellenar las ausentes.',
                 'evidence': [ref(k) for k in ('w1_total_sales','w2_total_sales','w1_days_present','w2_days_present')]},
                {'key': 'coverage', 'title': 'Cuatro fechas necesitan aclaración',
                 'statement': 'No hay registros para el 3, 10, 17 y 24 de abril. Hay dos fechas ausentes en cada periodo.',
                 'interpretation': 'La serie describe lo registrado. Estos huecos pueden corresponder a cierres, ausencia de ventas o datos omitidos; el archivo no permite distinguirlos.',
                 'next_step': 'Comprobar esas cuatro fechas en el sistema de origen. Si faltan registros, incorporarlos y recalcular la comparación.',
                 'method': 'Comparar las fechas distintas del archivo con el calendario del 1 al 28 de abril. En la línea solo se dibujan fechas registradas y se interrumpe la unión cuando falta un día.',
                 'evidence': [ref(k) for k in ('w1_days_missing','w2_days_missing','w1_missing_dates','w2_missing_dates')]}
            ],
            'charts': [
                {'key': 'totals', 'claim_key': 'comparison', 'kind': 'bar', 'title': 'Ventas registradas por periodo',
                 'unit': 'Importe sin impuestos · misma unidad monetaria', 'decimals': 2,
                 'caption': 'Periodos de igual duración; 12 días con datos en cada uno. Los importes incluyen el efecto de los descuentos.',
                 'points': [{'label':'1–14 de abril','value':ref('w1_total_sales')}, {'label':'15–28 de abril','value':ref('w2_total_sales')}]},
                {'key': 'daily', 'claim_key': 'coverage', 'kind': 'line', 'title': 'La actividad registrada, día a día',
                 'unit': 'Importe diario sin impuestos', 'decimals': 2,
                 'caption': 'Cada punto corresponde a una fecha del archivo. Los huecos se mantienen: una fecha ausente no equivale a ventas cero.',
                 'points': [{'label':k.removeprefix('sales_'), 'value':ref(k,series)} for k in sorted(series['result']['metrics'])]}
            ],
            'no_chart_reason': '',
            'limitations': ['Estos resultados describen el extracto aportado, no el conjunto de la empresa.',
                            'Sin costes, productos, clientes ni tickets, no se pueden calcular márgenes o ticket medio ni atribuir causas a los cambios.'],
            'checks': [{'key': 'no_duplicate_dates', 'operation': 'zero', 'actual': ref('duplicate_date_count'), 'operands': [], 'tolerance': '0'}]
        }
        return {**base, 'action': 'submit', 'report': report}, {'fixture_seed': True}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--business', required=True)
    parser.add_argument('--research', required=True, help='Saved research for reference case 01-daily-sales.')
    args = parser.parse_args()
    config = Config.load()
    with connect(config) as db:
        row = db.execute('SELECT s.model_settings FROM agent_sessions s JOIN agent_research r ON r.session_id=s.id WHERE r.id=%s AND r.business_id=%s',
                         (args.research,args.business)).fetchone()
    settings = ModelSettings(**row['model_settings'])
    request = 'reference-client-' + uuid4().hex
    result = review.start(config,args.business,args.research,request_key=request,
                          analyst=ReferenceAnalyst(settings),reviewer=ModelClient(settings))
    directory = ROOT / '.local/client-report-check' / request
    _, exported = trace(config,args.business,result['id'],directory)
    print(json.dumps({'reference_fixture': True, 'analyst': 'scripted', 'reviewer': 'real_model',
                      'review_id': str(result['id']), 'directory': str(directory), **exported}), flush=True)


if __name__ == '__main__':
    main()
